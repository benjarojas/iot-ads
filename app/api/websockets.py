# app/api/v1/websockets.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.logging_utils import get_logger
from app.core.config import settings
from app.services.redis_service import redis_svc

ws_router = APIRouter()
logger = get_logger(__name__)

@ws_router.websocket("/ws/dashboard")
async def dashboard_telemetry(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to WebSockets API")
    
    channels = (
        settings.SENSOR_DATA_CHANNEL,
        settings.INFERENCE_RESULTS_CHANNEL,
        settings.TRAINING_PROGRESS_CHANNEL,
    )
    pubsub = redis_svc.client.pubsub()
    await pubsub.subscribe(*channels)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data_str = message["data"].decode("utf-8")
                await websocket.send_text(data_str)

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSockets API")
    except Exception as e:
        logger.exception("WebSockets connection error: %s", e)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.close()