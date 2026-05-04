import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.anomaly_event import AnomalyEventRead
from app.services.anomaly_repository import anomaly_repo

anomalies_router = APIRouter()


@anomalies_router.get("/anomalies", response_model=list[AnomalyEventRead], tags=["Anomalies"])
async def list_anomalies(
    device_id: Optional[str] = Query(default=None),
    model_version: Optional[str] = Query(default=None),
    status: Literal["open", "closed", "all"] = Query(default="all"),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await anomaly_repo.list_filtered(
        device_id=device_id,
        model_version=model_version,
        status=status,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@anomalies_router.get(
    "/anomalies/{event_id}", response_model=AnomalyEventRead, tags=["Anomalies"]
)
async def get_anomaly(event_id: uuid.UUID):
    event = await anomaly_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Anomaly event '{event_id}' not found")
    return event
