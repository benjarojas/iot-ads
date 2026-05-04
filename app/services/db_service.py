from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.logging_utils import get_logger

logger = get_logger(__name__)


class DBService:
    def __init__(self):
        self._engine = None
        self._session_factory: async_sessionmaker | None = None

    async def connect(self) -> None:
        self._engine = create_async_engine(
            settings.POSTGRES_URL,
            echo=settings.POSTGRES_ECHO,
        )
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Database engine created.")

    async def create_all(self) -> None:
        import app.models  # registers all SQLModel tables in metadata
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables created/verified.")

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("Database engine disposed.")

    def session(self) -> AsyncSession:
        return self._session_factory()


db_svc = DBService()
