from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.runtime_state import AppMode, runtime_state
from app.schemas.replay import ReplayStartRequest, ReplayStatusResponse
from app.services import dataset_service
from app.services.redis_service import redis_svc
from app.services.replay_session_service import TERMINAL_PHASES, replay_session_svc

replay_router = APIRouter()


@replay_router.post(
    "/replay/start",
    response_model=ReplayStatusResponse,
    status_code=202,
    tags=["Replay"],
)
async def start_replay(req: ReplayStartRequest):
    current_mode = await runtime_state.get_mode()
    if current_mode != AppMode.STANDBY:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start replay: current mode is '{current_mode.value}', expected 'standby'",
        )

    existing = await replay_session_svc.get()
    if existing is not None and existing["phase"] not in TERMINAL_PHASES:
        raise HTTPException(status_code=409, detail="A replay session is already active")

    try:
        dataset_service.resolve_dataset(req.file)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))

    device_id = req.device_id or Path(req.file).stem
    total_frames = dataset_service.estimate_total_frames(req.file)
    if req.max_frames is not None:
        total_frames = req.max_frames if total_frames is None else min(total_frames, req.max_frames)

    session = await replay_session_svc.create(
        file=req.file,
        device_id=device_id,
        speed=req.speed,
        max_frames=req.max_frames,
        total_frames=total_frames,
    )
    # Flush stale frames from any previous run BEFORE entering REPLAY, so the
    # inference worker starts from an empty stream.
    await redis_svc.flush_sensor_stream()
    await runtime_state.set_mode(AppMode.REPLAY)
    return session


@replay_router.get(
    "/replay/status",
    response_model=Optional[ReplayStatusResponse],
    tags=["Replay"],
)
async def get_replay_status():
    return await replay_session_svc.get()


@replay_router.post("/replay/cancel", tags=["Replay"])
async def cancel_replay():
    session = await replay_session_svc.get()
    if session is None:
        raise HTTPException(status_code=404, detail="No active replay session")
    if session["phase"] in TERMINAL_PHASES:
        raise HTTPException(
            status_code=409,
            detail=f"Session already in terminal phase '{session['phase']}'",
        )
    await replay_session_svc.request_cancel()
    return {"status": "cancellation_requested"}


@replay_router.delete("/replay/session", tags=["Replay"])
async def clear_replay_session():
    """Clear a terminal session blob so a new replay can be started cleanly."""
    session = await replay_session_svc.get()
    if session is None:
        return {"status": "no_session"}
    if session["phase"] not in TERMINAL_PHASES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot clear non-terminal session (phase '{session['phase']}')",
        )
    await replay_session_svc.clear()
    return {"status": "cleared"}
