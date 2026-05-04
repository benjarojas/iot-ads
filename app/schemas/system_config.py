from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class SystemConfigRead(BaseModel):
    id: int
    p_high: float
    p_low: float
    active_inference_model: Optional[str]
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemConfigUpdate(BaseModel):
    p_high: Optional[float] = None
    p_low: Optional[float] = None
    active_inference_model: Optional[str] = None

    @field_validator("p_high", "p_low")
    @classmethod
    def valid_percentile(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 < v < 100.0):
            raise ValueError("must be between 0 and 100 (exclusive)")
        return v
