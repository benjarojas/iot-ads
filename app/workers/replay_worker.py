import asyncio
import json
import sys
import threading
import time
from array import array
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np
from scipy.signal import resample_poly

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.runtime_state import AppMode, runtime_state
from app.services import dataset_service
from app.services.dataset_service import (
    RESAMPLE_P,
    RESAMPLE_Q,
    SAMPLES_PER_FRAME,
)
from app.services.redis_service import redis_svc
from app.services.replay_session_service import TERMINAL_PHASES, replay_session_svc

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

logger = get_logger(__name__)

# How many frames between session progress updates.
REPORT_EVERY = 5

# Backpressure: pause emitting when the inference consumer group falls this far
# behind, resume once it drains below the low watermark. Keeps emission paced to
# scoring so the dashboard's emitted/scored counters stay aligned and no frames
# are lost to the stream's maxlen cap.
LAG_HIGH_WATERMARK = 60
LAG_LOW_WATERMARK = 20


# ── CSV: load whole signal, downsample 48828→2048 Hz, frame it ──────────────────

class _LoadCancelled(Exception):
    """Raised inside the loader thread when the session is cancelled mid-load."""


def _load_and_downsample_csv(
    path: Path, should_cancel: Optional[Callable[[], bool]] = None
) -> tuple[np.ndarray, np.ndarray]:
    """Read the full Current column + anomaly labels, then downsample the signal to
    2048 Hz with the same polyphase factors used in training. Returns (signal_2048hz,
    labels_2048hz) as equal-length arrays. Memory: the source column is ~4 bytes per
    sample (≈117 MB for the largest files); the downsampled output is ~24× smaller.
    Raises _LoadCancelled if should_cancel() turns true mid-parse."""
    cur = array("f")
    lab = array("B")
    with path.open("r", newline="") as f:
        header = f.readline().strip().split(",")
        cur_idx = header.index("Current") if "Current" in header else 2
        str_idx = header.index("anno_string") if "anno_string" in header else -1
        type_idx = header.index("anno_type") if "anno_type" in header else -1
        need = max(cur_idx, str_idx, type_idx) + 1

        for row_no, line in enumerate(f):
            if should_cancel is not None and (row_no & 0x3FFFFF) == 0 and should_cancel():
                raise _LoadCancelled
            parts = line.split(",", need)
            if len(parts) <= cur_idx:
                continue
            try:
                cur.append(float(parts[cur_idx]))
            except ValueError:
                continue
            is_anom = 0
            if str_idx >= 0 and len(parts) > str_idx and parts[str_idx].strip() == "Anomaly":
                is_anom = 1
            elif str_idx < 0 and type_idx >= 0 and len(parts) > type_idx \
                    and parts[type_idx].strip().lower() not in ("normal", ""):
                is_anom = 1
            lab.append(is_anom)

    current = np.frombuffer(cur, dtype=np.float32)
    labels = np.frombuffer(lab, dtype=np.uint8)
    if current.size == 0:
        return current, labels

    signal_ds = resample_poly(current, RESAMPLE_P, RESAMPLE_Q).astype(np.float32)

    # Map per-sample labels into the downsampled time base by index scaling.
    n_ds = signal_ds.size
    if labels.size and n_ds:
        idx = (np.arange(n_ds, dtype=np.float64) * (labels.size / n_ds)).astype(np.int64)
        np.clip(idx, 0, labels.size - 1, out=idx)
        labels_ds = labels[idx]
    else:
        labels_ds = np.zeros(n_ds, dtype=np.uint8)
    return signal_ds, labels_ds


# ── NDJSON: already 2048 Hz, one batch per line, no labels ──────────────────────

def _ndjson_frames(path: Path, max_frames: Optional[int]) -> Iterator[tuple[list[float], Optional[int], int]]:
    frame_index = 0
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "meta" in obj:
                continue
            samples = obj.get("samples")
            if not isinstance(samples, list) or len(samples) != SAMPLES_PER_FRAME:
                continue
            yield [float(x) for x in samples], None, frame_index
            frame_index += 1
            if max_frames and frame_index >= max_frames:
                return


# ── Backpressure ────────────────────────────────────────────────────────────────

async def _consumer_lag() -> Optional[int]:
    """Frames added to the sensor stream not yet delivered to the inference group.
    Returns None if the group/stream doesn't exist or Redis can't report lag."""
    try:
        groups = await redis_svc.client.xinfo_groups(settings.SENSOR_STREAM_NAME)
    except Exception:
        return None
    for g in groups:
        name = g.get(b"name") or g.get("name")
        if isinstance(name, bytes):
            name = name.decode()
        if name == settings.INFERENCE_GROUP_NAME:
            lag = g.get(b"lag", g.get("lag"))
            return int(lag) if lag is not None else None
    return None


async def _await_capacity() -> None:
    """Block while the inference consumer is too far behind (responsive to cancel)."""
    lag = await _consumer_lag()
    if lag is None or lag <= LAG_HIGH_WATERMARK:
        return
    while not await replay_session_svc.is_cancelled():
        lag = await _consumer_lag()
        if lag is None or lag <= LAG_LOW_WATERMARK:
            return
        await asyncio.sleep(0.2)


# ── Session lifecycle ───────────────────────────────────────────────────────────

async def recover_orphan_session() -> None:
    session = await replay_session_svc.get()
    if session is None or session["phase"] in TERMINAL_PHASES:
        return
    logger.warning("Recovering orphan replay session %s in phase '%s'",
                   session["id"], session["phase"])
    await replay_session_svc.update(
        phase="failed",
        error="Replay worker restarted before session completed",
    )
    if await runtime_state.get_mode() == AppMode.REPLAY:
        await runtime_state.set_mode(AppMode.STANDBY)


async def _finalize_failure(reason: str) -> None:
    await replay_session_svc.update(phase="failed", error=reason)
    if await runtime_state.get_mode() == AppMode.REPLAY:
        await runtime_state.set_mode(AppMode.STANDBY)


async def _finalize_cancelled(**progress) -> None:
    await replay_session_svc.update(phase="cancelled", **progress)
    if await runtime_state.get_mode() == AppMode.REPLAY:
        await runtime_state.set_mode(AppMode.STANDBY)


async def _emit_frame(device_id: str, vals: list[float], label: Optional[int], frame_index: int) -> None:
    arr = np.asarray(vals, dtype=np.float32)
    extra: dict = {"frame_index": frame_index}
    if label is not None:
        extra["label"] = label
    await redis_svc.add_sensor_data(
        device_id=device_id,
        timestamp=frame_index,
        samples_bytes=arr.tobytes(),
        stream_name=settings.SENSOR_STREAM_NAME,
        extra_fields=extra,
    )
    await redis_svc.publish_sensor_data(
        device_id=device_id,
        timestamp=frame_index,
        samples=vals,
        mode=AppMode.REPLAY.value,
        label=label,
        frame_index=frame_index,
    )


async def run_replay_session(session: dict) -> None:
    try:
        path = dataset_service.resolve_dataset(session["file"])
    except (FileNotFoundError, ValueError) as e:
        await _finalize_failure(str(e))
        return

    device_id = session["device_id"]
    speed = float(session["speed"])
    period = 1.0 / speed if speed > 0 else 0.0
    max_frames = session.get("max_frames")
    is_csv = path.suffix.lower() != ".ndjson"

    logger.info("Replay starting: file=%s device=%s speed=%.2f fps max_frames=%s csv=%s",
                session["file"], device_id, speed, max_frames, is_csv)

    # ── Build the frame source ──────────────────────────────────────────────────
    if is_csv:
        # Load + downsample up front (heavy); reflect it in the UI as a phase.
        await replay_session_svc.update(phase="preparing")

        # Watch for cancellation during the (possibly minute-long) parse.
        cancel_event = threading.Event()

        async def _watch_cancel() -> None:
            while not cancel_event.is_set():
                if await replay_session_svc.is_cancelled():
                    cancel_event.set()
                    return
                await asyncio.sleep(0.5)

        watcher = asyncio.create_task(_watch_cancel())
        try:
            signal_ds, labels_ds = await asyncio.to_thread(
                _load_and_downsample_csv, path, cancel_event.is_set
            )
        except _LoadCancelled:
            await _finalize_cancelled()
            logger.info("Replay cancelled during preprocessing.")
            return
        finally:
            cancel_event.set()
            watcher.cancel()

        n_frames = signal_ds.size // SAMPLES_PER_FRAME
        if max_frames:
            n_frames = min(n_frames, max_frames)
        if n_frames < 1:
            await _finalize_failure("Dataset produced no full frames after downsampling")
            return

        def frame_iter() -> Iterator[tuple[list[float], Optional[int], int]]:
            for fi in range(n_frames):
                off = fi * SAMPLES_PER_FRAME
                seg = signal_ds[off: off + SAMPLES_PER_FRAME]
                seg_lab = labels_ds[off: off + SAMPLES_PER_FRAME]
                label = 1 if int(seg_lab.sum()) * 2 >= seg_lab.size else 0
                yield seg.tolist(), label, fi

        source = frame_iter()
        await replay_session_svc.update(phase="running", total_frames=n_frames)
    else:
        source = _ndjson_frames(path, max_frames)
        await replay_session_svc.update(phase="running")

    # ── Stream frames ───────────────────────────────────────────────────────────
    gen = iter(source)
    sentinel = object()
    frames_emitted = samples_emitted = true_anomaly_frames = last_report = 0

    try:
        while True:
            if await replay_session_svc.is_cancelled():
                await _finalize_cancelled(
                    frames_emitted=frames_emitted,
                    samples_emitted=samples_emitted,
                    true_anomaly_frames=true_anomaly_frames,
                )
                logger.info("Replay cancelled after %d frames.", frames_emitted)
                return

            await _await_capacity()
            if await replay_session_svc.is_cancelled():
                continue

            item = await asyncio.to_thread(next, gen, sentinel)
            if item is sentinel:
                break

            vals, label, frame_index = item
            started = time.monotonic()
            await _emit_frame(device_id, vals, label, frame_index)

            frames_emitted += 1
            samples_emitted += len(vals)
            if label:
                true_anomaly_frames += 1

            if frames_emitted - last_report >= REPORT_EVERY:
                await replay_session_svc.update(
                    frames_emitted=frames_emitted,
                    samples_emitted=samples_emitted,
                    true_anomaly_frames=true_anomaly_frames,
                )
                last_report = frames_emitted

            if period > 0:
                remaining = period - (time.monotonic() - started)
                if remaining > 0:
                    await asyncio.sleep(remaining)
    finally:
        if hasattr(gen, "close"):
            gen.close()

    await replay_session_svc.update(
        phase="completed",
        frames_emitted=frames_emitted,
        samples_emitted=samples_emitted,
        true_anomaly_frames=true_anomaly_frames,
    )
    if await runtime_state.get_mode() == AppMode.REPLAY:
        await runtime_state.set_mode(AppMode.STANDBY)
    logger.info("Replay complete: %d frames, %d anomalous.",
                frames_emitted, true_anomaly_frames)


async def main_loop() -> None:
    while True:
        try:
            mode = await runtime_state.get_mode()
            session = await replay_session_svc.get()

            if mode != AppMode.REPLAY or session is None:
                await asyncio.sleep(2)
                continue
            if session["phase"] in TERMINAL_PHASES:
                await asyncio.sleep(2)
                continue

            await run_replay_session(session)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unhandled error in replay_worker main loop")
            try:
                await _finalize_failure("Unexpected error in replay worker")
            except Exception:
                logger.exception("Failed to update session on error")
            await asyncio.sleep(2)


async def main() -> None:
    logger.info("=== Replay Worker Starting ===")
    logger.info("  Data dir: %s | Stream: %s",
                settings.REPLAY_DATA_DIR, settings.SENSOR_STREAM_NAME)
    await recover_orphan_session()
    logger.info("=== Replay Worker Ready ===")
    try:
        await main_loop()
    except asyncio.CancelledError:
        logger.info("Replay worker cancelled.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
