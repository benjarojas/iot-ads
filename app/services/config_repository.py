import json
import time
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.models.system_config import SystemConfig
from app.services.db_service import db_svc
from app.services.redis_service import redis_svc

logger = get_logger(__name__)

# Keys used by inference_worker to query specific config slices
from app.services.model_registry import ACTIVE_MODEL_CONFIG_KEY  # noqa: F401 — re-export for workers

DETECTION_CONFIG_KEY = "detection_settings"

_CACHE_TTL = 10.0  # seconds


class ConfigRepository:
    def __init__(self):
        self._cached_row: Optional[SystemConfig] = None
        self._cache_ts: float = 0.0

    def _cache_valid(self) -> bool:
        return (
            self._cached_row is not None
            and time.monotonic() - self._cache_ts < _CACHE_TTL
        )

    def invalidate_cache(self) -> None:
        self._cached_row = None
        self._cache_ts = 0.0

    async def _fetch_row(self) -> SystemConfig:
        async with db_svc.session() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.id == 1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise RuntimeError("SystemConfig row missing; ensure_seeded() must run on startup")
            return row

    async def _get_row(self) -> SystemConfig:
        if not self._cache_valid():
            self._cached_row = await self._fetch_row()
            self._cache_ts = time.monotonic()
        return self._cached_row

    async def get(self, key: str) -> dict | None:
        """Key-based access used by workers. Maps known keys to SystemConfig fields."""
        row = await self._get_row()
        if key == DETECTION_CONFIG_KEY:
            return {"p_high": row.p_high, "p_low": row.p_low}
        if key == ACTIVE_MODEL_CONFIG_KEY:
            return {"name": row.active_inference_model} if row.active_inference_model else None
        logger.warning("Unknown config key requested: %s", key)
        return None

    async def get_system_config(self) -> SystemConfig:
        return await self._get_row()

    async def update_system_config(self, updates: dict) -> SystemConfig:
        async with db_svc.session() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.id == 1)
            )
            row = result.scalar_one()
            for field, value in updates.items():
                setattr(row, field, value)
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
            await session.commit()
            await session.refresh(row)

        self.invalidate_cache()
        await self._publish_invalidation()
        return row

    async def _publish_invalidation(self) -> None:
        payload = json.dumps({"action": "invalidate"}).encode()
        await redis_svc.client.publish(settings.CONFIG_UPDATES_CHANNEL, payload)
        logger.debug("Config invalidation published to %s", settings.CONFIG_UPDATES_CHANNEL)

    async def ensure_seeded(self) -> None:
        async with db_svc.session() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.id == 1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                session.add(SystemConfig(id=1))
                await session.commit()
                logger.info("SystemConfig seeded with defaults (p_high=95, p_low=85).")
            else:
                logger.info(
                    "SystemConfig found: p_high=%.1f, p_low=%.1f, model=%s",
                    row.p_high, row.p_low, row.active_inference_model,
                )


config_repo = ConfigRepository()
