import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AnomalyEventRead(BaseModel):
    id: uuid.UUID
    device_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    max_residual: float
    threshold: float
    model_version: str
    details: dict[str, Any]

    model_config = {"from_attributes": True}
