import uuid
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import update
from sqlmodel import select

from app.core.logging_utils import get_logger
from app.models.anomaly_event import AnomalyEvent
from app.services.db_service import db_svc

logger = get_logger(__name__)


class AnomalyRepository:
    async def open_anomaly(
        self,
        device_id: str,
        started_at: datetime,
        max_residual: float,
        threshold: float,
        model_version: str,
        details: dict,
    ) -> AnomalyEvent:
        event = AnomalyEvent(
            device_id=device_id,
            started_at=started_at,
            max_residual=max_residual,
            threshold=threshold,
            model_version=model_version,
            details=details,
        )
        async with db_svc.session() as session:
            session.add(event)
            await session.commit()
            await session.refresh(event)
        logger.info("Anomaly opened: id=%s device=%s", event.id, device_id)
        return event

    async def close_anomaly(self, event_id: uuid.UUID, ended_at: datetime) -> None:
        async with db_svc.session() as session:
            await session.execute(
                update(AnomalyEvent)
                .where(AnomalyEvent.id == event_id)
                .values(ended_at=ended_at)
            )
            await session.commit()
        logger.info("Anomaly closed: id=%s", event_id)

    async def update_max_residual_if_higher(self, event_id: uuid.UUID, value: float) -> None:
        async with db_svc.session() as session:
            await session.execute(
                update(AnomalyEvent)
                .where(AnomalyEvent.id == event_id, AnomalyEvent.max_residual < value)
                .values(max_residual=value)
            )
            await session.commit()

    async def get(self, event_id: uuid.UUID) -> Optional[AnomalyEvent]:
        async with db_svc.session() as session:
            return await session.get(AnomalyEvent, event_id)

    async def list_filtered(
        self,
        *,
        device_id: Optional[str] = None,
        model_version: Optional[str] = None,
        status: Literal["open", "closed", "all"] = "all",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnomalyEvent]:
        stmt = select(AnomalyEvent)
        if device_id is not None:
            stmt = stmt.where(AnomalyEvent.device_id == device_id)
        if model_version is not None:
            stmt = stmt.where(AnomalyEvent.model_version == model_version)
        if status == "open":
            stmt = stmt.where(AnomalyEvent.ended_at.is_(None))
        elif status == "closed":
            stmt = stmt.where(AnomalyEvent.ended_at.is_not(None))
        if since is not None:
            stmt = stmt.where(AnomalyEvent.started_at >= since)
        if until is not None:
            stmt = stmt.where(AnomalyEvent.started_at <= until)
        stmt = stmt.order_by(AnomalyEvent.started_at.desc()).limit(limit).offset(offset)
        async with db_svc.session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def close_all_open(self, ended_at: datetime) -> int:
        async with db_svc.session() as session:
            result = await session.execute(
                select(AnomalyEvent).where(AnomalyEvent.ended_at.is_(None))
            )
            orphans = result.scalars().all()
            for event in orphans:
                event.ended_at = ended_at
                session.add(event)
            await session.commit()
        if orphans:
            logger.warning("Closed %d orphaned anomaly event(s) from previous run.", len(orphans))
        return len(orphans)


anomaly_repo = AnomalyRepository()
