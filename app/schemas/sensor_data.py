from pydantic import BaseModel, Field, field_validator
from typing import List

class SensorPayload(BaseModel):
    device_id: str = Field(..., description="IoT Sensor UUID")
    timestamp: int = Field(..., description="UNIX Timestamp")
    samples: List[float] = Field(..., description="2048 raw samples (1 second of data at 2048 Hz)")

    @field_validator('samples')
    def validate_samples_length(cls, v):
        if len(v) != 2048:
            raise ValueError("Payload must contain exactly 2048 samples (1 second at 2048 Hz), but received {}".format(len(v)))
        return v
