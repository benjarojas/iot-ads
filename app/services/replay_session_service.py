from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.services.redis_service import redis_svc

logger = get_logger(__name__)

SESSION_KEY = "replay:session"
CANCEL_KEY = "replay:cancel"

TERMINAL_PHASES = {"completed", "failed", "cancelled"}


class ReplaySessionService:
    async def get(self) -> Optional[dict]:
        raw = await redis_svc.client.get(SESSION_KEY)
        if raw is None:
            return None
        return json.loads(raw)

    async def create(
        self,
        file: str,
        device_id: str,
        speed: float,
        max_frames: Optional[int],
        total_frames: Optional[int],
    ) -> dict:
        now = datetime.now(timezone.utc)
        session = {
            "id": str(uuid.uuid4()),
            "file": file,
            "device_id": device_id,
            "speed": speed,
            "max_frames": max_frames,
            "started_at": now.isoformat(),
            "phase": "running",
            "frames_emitted": 0,
            "total_frames": total_frames,
            "samples_emitted": 0,
            "true_anomaly_frames": 0,
            "error": None,
        }
        await redis_svc.client.set(SESSION_KEY, json.dumps(session))
        await redis_svc.client.delete(CANCEL_KEY)
        await self._publish(session)
        logger.info("Replay session created: id=%s file=%s", session["id"], file)
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
        logger.info("Replay cancellation requested.")

    async def is_cancelled(self) -> bool:
        return await redis_svc.client.exists(CANCEL_KEY) == 1

    async def _publish(self, session: dict) -> None:
        payload = json.dumps({"type": "replay_progress", **session}).encode("utf-8")
        await redis_svc.client.publish(settings.REPLAY_PROGRESS_CHANNEL, payload)


replay_session_svc = ReplaySessionService()
