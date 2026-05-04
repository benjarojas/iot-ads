from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field


class ModelVersion(SQLModel, table=True):
    __tablename__ = "model_versions"

    name: str = Field(primary_key=True)
    device_id: str
    trained_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    epochs_run: Optional[int] = None
    samples_captured: Optional[int] = None
    windows_train: Optional[int] = None
    windows_val: Optional[int] = None
    val_mae: Optional[float] = None
    val_mse: Optional[float] = None
    val_rmse: Optional[float] = None
    notes: Optional[str] = None
