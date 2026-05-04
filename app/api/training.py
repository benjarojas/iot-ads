from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.runtime_state import AppMode, runtime_state
from app.schemas.training import TrainingStartRequest, TrainingStatusResponse
from app.services.model_registry import ML_MODELS_ROOT
from app.services.model_version_repository import model_version_repo
from app.services.training_session_service import training_session_svc

training_router = APIRouter()


@training_router.post(
    "/training/start",
    response_model=TrainingStatusResponse,
    status_code=202,
    tags=["Training"],
)
async def start_training(req: TrainingStartRequest):
    current_mode = await runtime_state.get_mode()
    if current_mode != AppMode.STANDBY:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start training: current mode is '{current_mode.value}', expected 'standby'",
        )

    existing = await training_session_svc.get()
    if existing is not None and existing["phase"] not in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="A training session is already active")

    if (ML_MODELS_ROOT / req.name).exists():
        raise HTTPException(
            status_code=409, detail=f"Model directory '{req.name}' already exists on disk"
        )
    if await model_version_repo.get(req.name) is not None:
        raise HTTPException(
            status_code=409, detail=f"Model '{req.name}' already exists in database"
        )

    session = await training_session_svc.create(
        name=req.name,
        device_id=req.device_id,
        duration_minutes=req.duration_minutes,
        notes=req.notes,
    )
    await runtime_state.set_mode(AppMode.TRAINING)
    return session


@training_router.get(
    "/training/status",
    response_model=Optional[TrainingStatusResponse],
    tags=["Training"],
)
async def get_training_status():
    return await training_session_svc.get()


@training_router.post("/training/cancel", tags=["Training"])
async def cancel_training():
    session = await training_session_svc.get()
    if session is None:
        raise HTTPException(status_code=404, detail="No active training session")
    if session["phase"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Session already in terminal phase '{session['phase']}'",
        )
    await training_session_svc.request_cancel()
    return {"status": "cancellation_requested"}


@training_router.delete("/training/session", tags=["Training"])
async def clear_session():
    """Clear a terminal session blob so a new training run can be started cleanly."""
    session = await training_session_svc.get()
    if session is None:
        return {"status": "no_session"}
    if session["phase"] not in {"completed", "failed", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot clear non-terminal session (phase '{session['phase']}')",
        )
    await training_session_svc.clear()
    return {"status": "cleared"}
