import asyncio
import sys
import uuid
from datetime import datetime, timezone

import numpy as np

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.runtime_state import AppMode, runtime_state
from app.ml.anomaly_detection import LogHysteresisDetector
from app.ml.preprocessing import apply_ewm, apply_moving_average, scale_array
from app.services.anomaly_repository import anomaly_repo
from app.services.config_repository import DETECTION_CONFIG_KEY, config_repo
from app.services.db_service import db_svc
from app.services.model_registry import (
    ACTIVE_MODEL_CONFIG_KEY,
    ACTIVE_MODEL_DEFAULT,
    ModelBundle,
    model_registry,
)
from app.services.redis_service import redis_svc

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

logger = get_logger(__name__)

INPUT_SIZE = 2048
FORECAST_SIZE = 32
STRIDE = 512
WINDOWS_PER_MESSAGE = INPUT_SIZE // STRIDE  # 4
BUFFER_TARGET = INPUT_SIZE * 2              # 4096
GROUP_NAME = settings.INFERENCE_GROUP_NAME
CONSUMER_NAME = "worker_1"

_bundle: ModelBundle | None = None
_active_mode: AppMode | None = None  # last processing mode, for state-reset on transitions
device_buffers:      dict[str, np.ndarray]            = {}
device_detectors:    dict[str, LogHysteresisDetector] = {}
device_ewm_states:   dict[str, float | None]          = {}
device_open_anomaly: dict[str, uuid.UUID | None]      = {}


def _clear_device_state() -> None:
    device_buffers.clear()
    device_detectors.clear()
    device_ewm_states.clear()
    device_open_anomaly.clear()
    logger.info("Per-device state cleared.")


def _warmup(bundle: ModelBundle) -> None:
    dummy = np.zeros((1, INPUT_SIZE), dtype=np.float32)
    bundle.infer(dummy)  # triggers tf.function trace + XLA compilation
    logger.info("Bundle '%s' warmed up.", bundle.name)


def _run_windows_sync(
    bundle: ModelBundle,
    filtered: np.ndarray,
    detector: LogHysteresisDetector,
    ewm_state: float | None,
) -> tuple[list[tuple[bool, bool, float]], float | None]:
    """All CPU-bound work for the 4 sliding windows. Runs in a thread pool."""
    results = []
    for i in range(WINDOWS_PER_MESSAGE):
        off    = i * STRIDE
        x_input = scale_array(filtered[off: off + INPUT_SIZE], bundle.scaler)
        y_true  = scale_array(
            filtered[off + INPUT_SIZE: off + INPUT_SIZE + FORECAST_SIZE], bundle.scaler
        )
        was_on = detector.alarm_state  # capture BEFORE detect_window mutates state
        y_pred = bundle.infer(x_input.reshape(1, -1)).numpy()[0]
        raw_res    = np.abs(y_true - y_pred)
        smooth_res, ewm_state = apply_ewm(raw_res, ewm_state)
        is_anomaly, max_residual, _ = detector.detect_window(smooth_res)
        results.append((was_on, bool(is_anomaly), float(max_residual)))
    return results, ewm_state


async def load_bundle_by_name(name: str) -> None:
    global _bundle
    bundle = await asyncio.to_thread(model_registry.load_bundle, name)
    await asyncio.to_thread(_warmup, bundle)
    _bundle = bundle
    _clear_device_state()
    logger.info("Active bundle set to '%s'.", name)


async def _desired_bundle_name(mode: AppMode) -> str:
    """Replay always detects against the built-in 'default' bundle (trained on the
    same normal datasets); live DETECTION uses the configured active model."""
    if mode == AppMode.REPLAY:
        return ACTIVE_MODEL_DEFAULT
    cfg = await config_repo.get(ACTIVE_MODEL_CONFIG_KEY)
    return cfg["name"] if cfg else ACTIVE_MODEL_DEFAULT


async def reload_active_bundle() -> None:
    await load_bundle_by_name(await _desired_bundle_name(await runtime_state.get_mode()))


async def ensure_bundle_for_mode(mode: AppMode) -> None:
    """Swap the loaded bundle if the current mode requires a different one.
    Cheap no-op when the correct bundle is already loaded."""
    desired = await _desired_bundle_name(mode)
    if _bundle is None or _bundle.name != desired:
        logger.info("Mode '%s' requires bundle '%s' — loading.", mode.value, desired)
        await load_bundle_by_name(desired)


async def setup_consumer_group() -> None:
    try:
        await redis_svc.client.xgroup_create(
            settings.SENSOR_STREAM_NAME, GROUP_NAME, id="0", mkstream=True
        )
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise
    logger.info(
        "Consumer group '%s' ready on stream '%s'.", GROUP_NAME, settings.SENSOR_STREAM_NAME
    )


async def _get_detector(device_id: str) -> LogHysteresisDetector:
    if device_id not in device_detectors:
        cfg = await config_repo.get(DETECTION_CONFIG_KEY)
        device_detectors[device_id] = LogHysteresisDetector(
            train_residuals=_bundle.train_residuals,
            p_high=cfg["p_high"],
            p_low=cfg["p_low"],
        )
        logger.debug(
            "Detector built for '%s': p_high=%.1f p_low=%.1f",
            device_id, cfg["p_high"], cfg["p_low"],
        )
    return device_detectors[device_id]


async def _handle_anomaly_edge(
    device_id: str,
    was_on: bool,
    is_anomaly: bool,
    max_residual: float,
    window_idx: int,
) -> None:
    open_id  = device_open_anomaly.get(device_id)
    detector = device_detectors[device_id]
    now      = datetime.now(timezone.utc)

    if not was_on and is_anomaly:
        event = await anomaly_repo.open_anomaly(
            device_id=device_id,
            started_at=now,
            max_residual=max_residual,
            threshold=float(detector.t_high),
            model_version=_bundle.name,
            details={
                "window_index": window_idx,
                "input_size": INPUT_SIZE,
                "forecast_size": FORECAST_SIZE,
                "stride": STRIDE,
                "t_high": float(detector.t_high),
                "t_low": float(detector.t_low),
            },
        )
        device_open_anomaly[device_id] = event.id

    elif was_on and is_anomaly and open_id is not None:
        await anomaly_repo.update_max_residual_if_higher(open_id, max_residual)

    elif was_on and not is_anomaly and open_id is not None:
        await anomaly_repo.close_anomaly(open_id, now)
        device_open_anomaly[device_id] = None


async def _process_message(
    device_id: str,
    samples: np.ndarray,
    true_label: int | None = None,
    frame_index: int | None = None,
) -> None:
    existing = device_buffers.get(device_id)
    buf = samples.copy() if existing is None else np.concatenate([existing, samples])
    device_buffers[device_id] = buf

    if buf.size < BUFFER_TARGET:
        logger.debug("[%s] Buffer warming up (%d/%d).", device_id, buf.size, BUFFER_TARGET)
        return

    filtered  = apply_moving_average(buf)
    detector  = await _get_detector(device_id)
    ewm_state = device_ewm_states.get(device_id)

    results, new_ewm = await asyncio.to_thread(
        _run_windows_sync, _bundle, filtered, detector, ewm_state
    )
    device_ewm_states[device_id] = new_ewm

    for idx, (was_on, is_anomaly, max_residual) in enumerate(results):
        await redis_svc.publish_inference_result(
            device_id=device_id,
            max_residual=max_residual,
            is_anomaly=is_anomaly,
            t_high=float(detector.t_high),
            t_low=float(detector.t_low),
            true_label=true_label,
            frame_index=frame_index,
        )
        await _handle_anomaly_edge(device_id, was_on, is_anomaly, max_residual, idx)
        logger.info(
            "[%s] window %d/%d %s | max_res=%.6f",
            device_id, idx + 1, WINDOWS_PER_MESSAGE,
            "ANOMALY" if is_anomaly else "normal", max_residual,
        )

    device_buffers[device_id] = buf[-INPUT_SIZE:]


async def config_listener() -> None:
    logger.info("Config listener subscribed to '%s'.", settings.CONFIG_UPDATES_CHANNEL)
    async with redis_svc.client.pubsub() as ps:
        await ps.subscribe(settings.CONFIG_UPDATES_CHANNEL)
        async for msg in ps.listen():
            if msg["type"] != "message":
                continue
            config_repo.invalidate_cache()
            mode = await runtime_state.get_mode()
            # During REPLAY the worker is pinned to the 'default' bundle, so an
            # active-model config change must not pull it off — it only takes
            # effect once back in DETECTION. Threshold changes still apply via
            # detector rebuild below.
            new_name = await _desired_bundle_name(mode)
            if _bundle is None or new_name != _bundle.name:
                logger.info("Active model changed to '%s' — reloading bundle.", new_name)
                await load_bundle_by_name(new_name)  # also calls _clear_device_state()
            else:
                device_detectors.clear()
                logger.info("Config change received — cache invalidated, detectors will rebuild.")


async def main_loop() -> None:
    while True:
        try:
            global _active_mode
            mode = await runtime_state.get_mode()
            if mode not in (AppMode.DETECTION, AppMode.REPLAY):
                _active_mode = None
                await asyncio.sleep(1)
                continue

            # On entering a processing mode (e.g. a fresh replay), clear per-device
            # buffers/detectors/EWM so leftover state from a prior run can't leak in.
            if mode != _active_mode:
                logger.info("Entering %s mode — clearing per-device state.", mode.value)
                _clear_device_state()
                _active_mode = mode

            # Ensure the correct bundle is loaded for the active mode (REPLAY → default).
            await ensure_bundle_for_mode(mode)

            messages = await redis_svc.client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={settings.SENSOR_STREAM_NAME: ">"},
                count=10,
                block=2000,
            )

            if not messages:
                continue

            for _stream, entries in messages:
                for msg_id, fields in entries:
                    device_id = fields[b"device_id"].decode()
                    samples   = np.frombuffer(fields[b"samples"], dtype=np.float32)
                    if samples.size != INPUT_SIZE:
                        logger.warning(
                            "[%s] Skipping: expected %d samples, got %d.",
                            device_id, INPUT_SIZE, samples.size,
                        )
                        await redis_svc.client.xack(
                            settings.SENSOR_STREAM_NAME, GROUP_NAME, msg_id
                        )
                        continue
                    # Optional ground-truth label / frame index carried by replay frames.
                    true_label = int(fields[b"label"]) if b"label" in fields else None
                    frame_index = int(fields[b"frame_index"]) if b"frame_index" in fields else None
                    await _process_message(device_id, samples, true_label, frame_index)
                    await redis_svc.client.xack(
                        settings.SENSOR_STREAM_NAME, GROUP_NAME, msg_id
                    )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in main_loop; resuming in 1 s.")
            await asyncio.sleep(1)


async def main() -> None:
    logger.info("=== Inference Worker Starting ===")
    logger.info(
        "  Stream: %s | Group: %s | Consumer: %s",
        settings.SENSOR_STREAM_NAME, GROUP_NAME, CONSUMER_NAME,
    )
    await db_svc.connect()
    await db_svc.create_all()
    await anomaly_repo.close_all_open(datetime.now(timezone.utc))
    await reload_active_bundle()
    await setup_consumer_group()
    logger.info("=== Inference Worker Ready ===")
    try:
        await asyncio.gather(main_loop(), config_listener())
    except asyncio.CancelledError:
        logger.info("Inference worker cancelled.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
