import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class TrainingStartRequest(BaseModel):
    name: str
    device_id: str
    duration_minutes: int = 20
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("name must contain only letters, numbers, underscores, and hyphens")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def valid_duration(cls, v: int) -> int:
        if not (1 <= v <= 180):
            raise ValueError("duration_minutes must be between 1 and 180")
        return v


class TrainingMetrics(BaseModel):
    mae: float
    mse: float
    rmse: float
    r2: float


class TrainingStatusResponse(BaseModel):
    id: str
    name: str
    device_id: str
    notes: Optional[str]
    duration_minutes: int
    started_at: datetime
    capture_ends_at: datetime
    phase: str
    samples_captured: int
    windows_train: Optional[int] = None
    windows_val: Optional[int] = None
    current_epoch: int
    total_epochs: int
    metrics: Optional[TrainingMetrics]
    error: Optional[str]
