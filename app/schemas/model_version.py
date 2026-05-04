from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ModelVersionRead(BaseModel):
    name: str
    device_id: str
    trained_at: datetime
    epochs_run: Optional[int]
    samples_captured: Optional[int]
    windows_train: Optional[int]
    windows_val: Optional[int]
    val_mae: Optional[float]
    val_mse: Optional[float]
    val_rmse: Optional[float]
    notes: Optional[str]

    model_config = {"from_attributes": True}
