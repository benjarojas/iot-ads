import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.runtime_state import AppMode, runtime_state
from app.ml.model_architecture import build_forecaster
from app.ml.preprocessing import apply_moving_average
from app.ml.training_pipeline import (
    FORECAST_SIZE,
    INPUT_SIZE,
    WINDOW_SPAN,
    build_supervised_dataset,
    compute_metrics,
    fit_scaler,
    time_split,
)
from app.models.model_version import ModelVersion
from app.services.db_service import db_svc
from app.services.model_registry import ML_MODELS_ROOT
from app.services.redis_service import redis_svc
from app.services.training_session_service import training_session_svc

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

logger = get_logger(__name__)

GROUP_NAME = settings.TRAINING_GROUP_NAME
CONSUMER_NAME = "training_worker_1"
MIN_WINDOWS = 10  # bail out if we don't have at least this many supervised windows


async def setup_consumer_group() -> None:
    try:
        await redis_svc.client.xgroup_create(
            settings.TRAINING_STREAM_NAME, GROUP_NAME, id="0", mkstream=True
        )
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise
    logger.info(
        "Consumer group '%s' ready on stream '%s'.", GROUP_NAME, settings.TRAINING_STREAM_NAME
    )


async def recover_orphan_session() -> None:
    session = await training_session_svc.get()
    if session is None:
        return
    if session["phase"] in {"completed", "failed", "cancelled"}:
        return
    logger.warning("Recovering orphan session %s in phase '%s'", session["id"], session["phase"])
    await training_session_svc.update(
        phase="failed",
        error="Training worker restarted before session completed",
    )
    if await runtime_state.get_mode() == AppMode.TRAINING:
        await runtime_state.set_mode(AppMode.STANDBY)


async def _capture(session: dict) -> np.ndarray:
    capture_ends_at = datetime.fromisoformat(session["capture_ends_at"])
    chunks: list[np.ndarray] = []
    samples_total = 0
    last_reported = 0

    while datetime.now(timezone.utc) < capture_ends_at:
        if await training_session_svc.is_cancelled():
            return np.array([], dtype=np.float32)

        try:
            messages = await redis_svc.client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={settings.TRAINING_STREAM_NAME: ">"},
                count=20,
                block=1000,
            )
        except Exception:
            logger.exception("Error reading training stream; retrying in 1s")
            await asyncio.sleep(1)
            continue

        if not messages:
            continue

        for _stream, entries in messages:
            for msg_id, fields in entries:
                samples = np.frombuffer(fields[b"samples"], dtype=np.float32)
                chunks.append(samples)
                samples_total += samples.size
                await redis_svc.client.xack(
                    settings.TRAINING_STREAM_NAME, GROUP_NAME, msg_id
                )

        if samples_total - last_reported >= 10240:
            await training_session_svc.update(samples_captured=samples_total)
            last_reported = samples_total

    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks)


def _train_sync(X_train, Y_train, X_val, Y_val, on_epoch_end, cancel_check):
    """Blocking training. Runs in a thread."""
    import tensorflow as tf

    class ProgressCallback(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            on_epoch_end(epoch + 1, logs or {})
            if cancel_check():
                self.model.stop_training = True

    model = build_forecaster(INPUT_SIZE, FORECAST_SIZE)

    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=15,
        min_delta=1e-5,
        restore_best_weights=True,
        verbose=1,
    )
    plateau = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=5,
        min_lr=1e-6,
        verbose=1,
    )

    history = model.fit(
        X_train,
        Y_train,
        validation_data=(X_val, Y_val),
        epochs=settings.TRAINING_DEFAULT_EPOCHS,
        batch_size=settings.TRAINING_BATCH_SIZE,
        callbacks=[early, plateau, ProgressCallback()],
        verbose=1,
    )
    return model, history


async def _finalize_failure(reason: str) -> None:
    await training_session_svc.update(phase="failed", error=reason)
    if await runtime_state.get_mode() == AppMode.TRAINING:
        await runtime_state.set_mode(AppMode.STANDBY)


async def _finalize_cancelled() -> None:
    await training_session_svc.update(phase="cancelled")
    if await runtime_state.get_mode() == AppMode.TRAINING:
        await runtime_state.set_mode(AppMode.STANDBY)


async def run_training_session(session: dict) -> None:
    name = session["name"]
    bundle_dir = ML_MODELS_ROOT / name

    # Phase 1: Capture
    logger.info("Capturing training data for %d minute(s)...", session["duration_minutes"])
    raw_samples = await _capture(session)

    if await training_session_svc.is_cancelled():
        await _finalize_cancelled()
        return

    if raw_samples.size < WINDOW_SPAN * MIN_WINDOWS:
        await _finalize_failure(
            f"Not enough samples captured ({raw_samples.size}); need at least {WINDOW_SPAN * MIN_WINDOWS}"
        )
        return

    await training_session_svc.update(samples_captured=int(raw_samples.size), phase="preprocessing")

    # Phase 2: Preprocessing
    logger.info("Preprocessing %d samples...", raw_samples.size)
    filtered = apply_moving_average(raw_samples)
    scaler = fit_scaler(filtered)
    scaled = scaler.transform(filtered.reshape(-1, 1)).flatten().astype(np.float32)

    X, Y = build_supervised_dataset(scaled)
    X_train, Y_train, X_val, Y_val = time_split(
        X, Y, val_fraction=settings.TRAINING_VAL_SPLIT
    )

    if X_train.shape[0] < 1 or X_val.shape[0] < 1:
        await _finalize_failure(
            f"Insufficient windows after split (train={X_train.shape[0]}, val={X_val.shape[0]})"
        )
        return

    logger.info(
        "Dataset ready: %d train windows, %d val windows", X_train.shape[0], X_val.shape[0]
    )
    await training_session_svc.update(
        phase="training",
        windows_train=int(X_train.shape[0]),
        windows_val=int(X_val.shape[0]),
    )

    # Phase 3: Training
    loop = asyncio.get_running_loop()

    def on_epoch_end(epoch: int, logs: dict) -> None:
        # called from training thread — schedule the async update on the main loop
        asyncio.run_coroutine_threadsafe(
            training_session_svc.update(current_epoch=epoch), loop
        )

    cancel_flag = {"v": False}

    async def watch_cancel() -> None:
        while True:
            if await training_session_svc.is_cancelled():
                cancel_flag["v"] = True
                return
            await asyncio.sleep(2)

    cancel_task = asyncio.create_task(watch_cancel())
    try:
        model, history = await asyncio.to_thread(
            _train_sync,
            X_train, Y_train, X_val, Y_val,
            on_epoch_end,
            lambda: cancel_flag["v"],
        )
    finally:
        cancel_task.cancel()

    if cancel_flag["v"]:
        await _finalize_cancelled()
        return

    # Phase 4: Finalize
    logger.info("Computing metrics and saving artifacts...")
    Y_val_pred = model.predict(X_val, verbose=0)
    metrics = compute_metrics(Y_val, Y_val_pred)

    Y_train_pred = model.predict(X_train, verbose=0)
    train_residuals = np.abs(Y_train - Y_train_pred).flatten().astype(np.float32)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    model.save(bundle_dir / "model.keras")
    joblib.dump(scaler, bundle_dir / "scaler.gz")
    np.save(bundle_dir / "train_residuals.npy", train_residuals)

    epochs_run = len(history.history.get("loss", []))
    trained_at = datetime.now(timezone.utc)

    metadata = {
        "model_name": name,
        "device_id": session["device_id"],
        "trained_at": trained_at.isoformat(),
        "epochs_run": epochs_run,
        "windows_train": int(X_train.shape[0]),
        "windows_val": int(X_val.shape[0]),
        "val_mae": metrics["mae"],
        "val_mse": metrics["mse"],
        "val_rmse": metrics["rmse"],
        "samples_captured": int(raw_samples.size),
        "notes": session["notes"],
    }
    with open(bundle_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    row = ModelVersion(
        name=name,
        device_id=session["device_id"],
        trained_at=trained_at,
        epochs_run=epochs_run,
        samples_captured=int(raw_samples.size),
        windows_train=int(X_train.shape[0]),
        windows_val=int(X_val.shape[0]),
        val_mae=metrics["mae"],
        val_mse=metrics["mse"],
        val_rmse=metrics["rmse"],
        notes=session["notes"],
    )
    async with db_svc.session() as s:
        s.add(row)
        await s.commit()

    await training_session_svc.update(phase="completed", metrics=metrics)
    await runtime_state.set_mode(AppMode.STANDBY)
    logger.info("Training complete: name=%s metrics=%s", name, metrics)


async def main_loop() -> None:
    while True:
        try:
            mode = await runtime_state.get_mode()
            session = await training_session_svc.get()

            if mode != AppMode.TRAINING or session is None:
                await asyncio.sleep(2)
                continue

            if session["phase"] in {"completed", "failed", "cancelled"}:
                await asyncio.sleep(2)
                continue

            await run_training_session(session)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unhandled error in training_worker main loop")
            try:
                await _finalize_failure("Unexpected error in training worker")
            except Exception:
                logger.exception("Failed to update session on error")
            await asyncio.sleep(2)


async def main() -> None:
    logger.info("=== Training Worker Starting ===")
    logger.info("  Stream: %s | Group: %s | Consumer: %s",
                settings.TRAINING_STREAM_NAME, GROUP_NAME, CONSUMER_NAME)
    await db_svc.connect()
    await db_svc.create_all()
    await setup_consumer_group()
    await recover_orphan_session()
    logger.info("=== Training Worker Ready ===")
    try:
        await main_loop()
    except asyncio.CancelledError:
        logger.info("Training worker cancelled.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
