from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class DatasetInfo(BaseModel):
    name: str
    size_bytes: int
    format: str
    has_labels: bool
    total_samples: Optional[int] = None
    total_frames: Optional[int] = None
    anomaly_types: List[str] = []
    has_anomalies: bool = False


class ReplayStartRequest(BaseModel):
    file: str
    device_id: Optional[str] = None  # defaults to the dataset filename stem
    speed: float = 1.0               # multiple of real-time (1 frame/sec @ 2048 Hz)
    max_frames: Optional[int] = None

    @field_validator("file")
    @classmethod
    def valid_file(cls, v: str) -> str:
        if "/" in v or "\\" in v or v.startswith("."):
            raise ValueError("file must be a bare filename inside the replay data directory")
        return v

    @field_validator("speed")
    @classmethod
    def valid_speed(cls, v: float) -> float:
        if not (0.1 <= v <= 1000):
            raise ValueError("speed must be between 0.1 and 1000 frames/second")
        return v

    @field_validator("max_frames")
    @classmethod
    def valid_max_frames(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("max_frames must be >= 1")
        return v


class ReplayStatusResponse(BaseModel):
    id: str
    file: str
    device_id: str
    speed: float
    max_frames: Optional[int] = None
    started_at: datetime
    phase: str
    frames_emitted: int
    total_frames: Optional[int] = None
    samples_emitted: int
    true_anomaly_frames: int
    error: Optional[str] = None
