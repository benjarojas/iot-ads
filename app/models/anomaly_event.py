import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime, JSON
from sqlmodel import SQLModel, Field


class AnomalyEvent(SQLModel, table=True):
    __tablename__ = "anomaly_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: str
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    max_residual: float
    threshold: float
    model_version: str
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
