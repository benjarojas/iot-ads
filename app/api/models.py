from fastapi import APIRouter

from app.schemas.model_version import ModelVersionRead
from app.services.model_version_repository import model_version_repo

models_router = APIRouter()


@models_router.get("/models", response_model=list[ModelVersionRead], tags=["Models"])
async def list_models():
    return await model_version_repo.get_all()
