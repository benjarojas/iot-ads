from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field


class SystemConfig(SQLModel, table=True):
    __tablename__ = "system_config"

    id: int = Field(default=1, primary_key=True)
    p_high: float = Field(default=95.0)
    p_low: float = Field(default=85.0)
    active_inference_model: Optional[str] = Field(default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
