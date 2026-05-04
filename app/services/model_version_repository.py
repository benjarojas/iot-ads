import json
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

from app.core.logging_utils import get_logger
from app.models.model_version import ModelVersion
from app.services.db_service import db_svc
from app.services.model_registry import ML_MODELS_ROOT, _REQUIRED_ARTIFACTS

logger = get_logger(__name__)


class ModelVersionRepository:
    async def get_all(self) -> list[ModelVersion]:
        async with db_svc.session() as session:
            result = await session.execute(select(ModelVersion))
            return list(result.scalars().all())

    async def get(self, name: str) -> ModelVersion | None:
        async with db_svc.session() as session:
            result = await session.execute(
                select(ModelVersion).where(ModelVersion.name == name)
            )
            return result.scalar_one_or_none()

    async def seed_defaults(self) -> None:
        """Insert a ModelVersion row for each on-disk bundle that has no DB entry yet."""
        if not ML_MODELS_ROOT.exists():
            return
        for bundle_dir in sorted(ML_MODELS_ROOT.iterdir()):
            if not bundle_dir.is_dir():
                continue
            if not all((bundle_dir / f).exists() for f in _REQUIRED_ARTIFACTS):
                continue
            name = bundle_dir.name
            if await self.get(name) is not None:
                continue
            with open(bundle_dir / "metadata.json") as f:
                meta = json.load(f)
            raw_ts = meta.get("trained_at")
            if raw_ts:
                trained_at = datetime.fromisoformat(raw_ts)
                if trained_at.tzinfo is None:
                    trained_at = trained_at.replace(tzinfo=timezone.utc)
            else:
                trained_at = datetime.now(timezone.utc)
            row = ModelVersion(
                name=name,
                device_id=meta.get("device_id", "unknown"),
                trained_at=trained_at,
                epochs_run=meta.get("epochs_run"),
                samples_captured=meta.get("samples_captured"),
                windows_train=meta.get("windows_train"),
                windows_val=meta.get("windows_val"),
                val_mae=meta.get("val_mae"),
                val_mse=meta.get("val_mse"),
                val_rmse=meta.get("val_rmse"),
                notes=meta.get("notes"),
            )
            async with db_svc.session() as session:
                session.add(row)
                await session.commit()
            logger.info("Seeded ModelVersion '%s' from disk.", name)


model_version_repo = ModelVersionRepository()
