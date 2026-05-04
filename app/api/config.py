from fastapi import APIRouter, HTTPException

from app.schemas.system_config import SystemConfigRead, SystemConfigUpdate
from app.services.config_repository import config_repo

config_router = APIRouter()


@config_router.get("/config", response_model=SystemConfigRead, tags=["Config"])
async def get_config():
    return await config_repo.get_system_config()


@config_router.put("/config", response_model=SystemConfigRead, tags=["Config"])
async def update_config(patch: SystemConfigUpdate):
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update")

    current = await config_repo.get_system_config()
    eff_high = updates.get("p_high", current.p_high)
    eff_low = updates.get("p_low", current.p_low)

    if eff_low >= eff_high:
        raise HTTPException(
            status_code=422,
            detail=f"p_low ({eff_low}) must be strictly less than p_high ({eff_high})",
        )

    return await config_repo.update_system_config(updates)
