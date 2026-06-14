# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.runtime_state import AppMode, runtime_state
from app.api.websockets import ws_router
from app.api.config import config_router
from app.api.models import models_router
from app.api.training import training_router
from app.api.anomalies import anomalies_router
from app.api.datasets import datasets_router
from app.api.replay import replay_router
from app.services.redis_service import redis_svc
from app.services.db_service import db_svc
from app.services.config_repository import config_repo
from app.services.model_version_repository import model_version_repo

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up {settings.PROJECT_NAME}...")

    await runtime_state.initialize()
    logger.info(f"Runtime State Machine initialized with mode: {await runtime_state.get_mode()}")

    await db_svc.connect()
    await db_svc.create_all()
    await config_repo.ensure_seeded()
    await model_version_repo.seed_defaults()
    logger.info("Database ready.")

    try:
        yield
    finally:
        logger.info("Shutting down %s...", settings.PROJECT_NAME)
        await redis_svc.close()
        await db_svc.close()
        logger.info("Shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(training_router, prefix="/api")
app.include_router(anomalies_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(replay_router, prefix="/api")


@app.get("/api/state", tags=["State"])
async def get_state():
    return {"mode": (await runtime_state.get_mode()).value}


@app.put("/api/state/{mode}", tags=["State"])
async def set_state(mode: AppMode):
    await runtime_state.set_mode(mode)
    logger.info("Application mode changed to %s", mode.value)
    return {"mode": (await runtime_state.get_mode()).value}

@app.get("/", tags=["Health"])
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "message": "Energy-based side-channel anomaly detection API is running.",
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    try:
        await redis_svc.client.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"


    return {"api": "ok", "redis": redis_status}
