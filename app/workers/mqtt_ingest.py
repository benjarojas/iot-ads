import aiomqtt
import asyncio
import json
import numpy as np
from pydantic import ValidationError

import sys

from app.core.logging_utils import get_logger
from app.services.redis_service import redis_svc
from app.core.runtime_state import runtime_state, AppMode
from app.core.config import settings
from app.schemas.sensor_data import SensorPayload

logger = get_logger(__name__)
MQTT_BROKER_HOST = settings.MQTT_BROKER_HOST
MQTT_BROKER_PORT = settings.MQTT_BROKER_PORT
MQTT_TOPIC = settings.MQTT_TOPIC
INGEST_WORKER_COUNT = settings.INGEST_WORKER_COUNT

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

async def work(client, worker_id: int):
    logger.info(f"Worker {worker_id} started and listening for messages on topic: {MQTT_TOPIC}")
    message_count = 0
    
    try:
        async for message in client.messages:
            message_count += 1
            try:
                logger.debug(
                    f"Worker {worker_id} received message #{message_count} | "
                    f"Topic: {message.topic} | "
                    f"QoS: {message.qos} | "
                    f"Retain: {message.retain} | "
                    f"Payload length: {len(message.payload)} bytes"
                )
                #logger.info(f"Worker {worker_id} message payload: {message.payload}")

                data = json.loads(message.payload.decode('utf-8'))
                sensor_data = SensorPayload(**data)

                samples_array = np.array(sensor_data.samples, dtype=np.float32)

                app_mode = await runtime_state.get_mode()

                await redis_svc.publish_sensor_data(
                    device_id=sensor_data.device_id,
                    timestamp=sensor_data.timestamp,
                    samples=sensor_data.samples,
                    mode=app_mode.value
                )

                if(app_mode == AppMode.STANDBY):
                    continue

                target_stream = settings.TRAINING_STREAM_NAME if app_mode == AppMode.TRAINING else settings.SENSOR_STREAM_NAME

                await redis_svc.add_sensor_data(
                    device_id=sensor_data.device_id,
                    timestamp=sensor_data.timestamp,
                    samples_bytes=samples_array.tobytes(),
                    stream_name=target_stream
                )
            except ValidationError as ve:
                logger.error(
                    f"Worker {worker_id} validation error processing message #{message_count}: {ve}",
                    exc_info=True
                )
                
            except Exception as e:
                logger.error(
                    f"Worker {worker_id} error processing message #{message_count}: {type(e).__name__}: {e}",
                    exc_info=True
                )
    except asyncio.CancelledError:
        logger.info(f"Worker {worker_id} received cancellation signal after processing {message_count} messages")
        raise
    except Exception as e:
        logger.error(
            f"Worker {worker_id} encountered fatal error after processing {message_count} messages: "
            f"{type(e).__name__}: {e}",
            exc_info=True
        )
        raise
    finally:
        logger.info(f"Worker {worker_id} shutting down (processed {message_count} messages)")


async def main():
    logger.info(f"=== MQTT Ingest Worker Starting ===")
    logger.info(f"Configuration:")
    logger.info(f"  MQTT Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    logger.info(f"  Topic: {MQTT_TOPIC}")
    logger.info(f"  Worker count: {INGEST_WORKER_COUNT}")
    
    try:
        logger.info(f"Connecting to MQTT broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
        async with aiomqtt.Client(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT, logger=logger) as client:
            logger.info(f"Successfully connected to MQTT broker")
            
            logger.info(f"Subscribing to topic: {MQTT_TOPIC}")
            await client.subscribe(MQTT_TOPIC)
            logger.info(f"Successfully subscribed to topic: {MQTT_TOPIC}")
            
            logger.info(f"Starting {INGEST_WORKER_COUNT} worker tasks...")
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for worker_id in range(INGEST_WORKER_COUNT):
                    task = tg.create_task(work(client, worker_id))
                    tasks.append(task)
                    logger.debug(f"Spawned worker {worker_id}")
                
                logger.info(f"All {INGEST_WORKER_COUNT} workers started. Listening for messages...")
                # TaskGroup will wait for all tasks to complete
                
    except aiomqtt.MqttError as e:
        logger.error(f"MQTT connection error: {type(e).__name__}: {e}", exc_info=True)
        raise
    except asyncio.TimeoutError:
        logger.error(f"Connection timeout to {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in main: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        logger.info(f"=== MQTT Ingest Worker Shutting Down ===")


if __name__ == "__main__":
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Fatal error: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)