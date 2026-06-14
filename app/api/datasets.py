from typing import List

from fastapi import APIRouter

from app.schemas.replay import DatasetInfo
from app.services import dataset_service

datasets_router = APIRouter()


@datasets_router.get("/datasets", response_model=List[DatasetInfo], tags=["Replay"])
async def list_datasets():
    """List replayable datasets in the configured replay data directory."""
    return dataset_service.list_datasets()
