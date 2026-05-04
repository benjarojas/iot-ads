from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.services.redis_service import redis_svc

logger = get_logger(__name__)

SESSION_KEY = "training:session"
CANCEL_KEY = "training:cancel"


class TrainingSessionService:
    async def get(self) -> Optional[dict]:
        raw = await redis_svc.client.get(SESSION_KEY)
        if raw is None:
            return None
        return json.loads(raw)

    async def create(
        self, name: str, device_id: str, duration_minutes: int, notes: Optional[str]
    ) -> dict:
        now = datetime.now(timezone.utc)
        session = {
            "id": str(uuid.uuid4()),
            "name": name,
            "device_id": device_id,
            "notes": notes,
            "duration_minutes": duration_minutes,
            "started_at": now.isoformat(),
            "capture_ends_at": (now + timedelta(minutes=duration_minutes)).isoformat(),
            "phase": "capturing",
            "samples_captured": 0,
            "windows_train": None,
            "windows_val": None,
            "current_epoch": 0,
            "total_epochs": settings.TRAINING_DEFAULT_EPOCHS,
            "metrics": None,
            "error": None,
        }
        await redis_svc.client.set(SESSION_KEY, json.dumps(session))
        await redis_svc.client.delete(CANCEL_KEY)
        await self._publish(session)
        logger.info("Training session created: id=%s name=%s", session["id"], name)
        return session

    async def update(self, **changes) -> Optional[dict]:
        session = await self.get()
        if session is None:
            return None
        session.update(changes)
        await redis_svc.client.set(SESSION_KEY, json.dumps(session))
        await self._publish(session)
        return session

    async def clear(self) -> None:
        await redis_svc.client.delete(SESSION_KEY)
        await redis_svc.client.delete(CANCEL_KEY)

    async def request_cancel(self) -> None:
        await redis_svc.client.set(CANCEL_KEY, "1")
        logger.info("Training cancellation requested.")

    async def is_cancelled(self) -> bool:
        return await redis_svc.client.exists(CANCEL_KEY) == 1

    async def _publish(self, session: dict) -> None:
        payload = json.dumps({"type": "training_progress", **session}).encode("utf-8")
        await redis_svc.client.publish(settings.TRAINING_PROGRESS_CHANNEL, payload)


training_session_svc = TrainingSessionService()
