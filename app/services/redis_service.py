import json
import redis.asyncio as redis
from app.core.config import settings

class RedisService:
    def __init__(self):
       
        self.pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False
        )
        self.client = redis.Redis(connection_pool=self.pool)

    async def close(self):
        # close the Redis connection pool and client
        await self.client.aclose()
        await self.pool.disconnect()

    async def add_sensor_data(self, device_id: str, timestamp: int, samples_bytes: bytes, stream_name: str | None = None):
        stream_data = {
            b"device_id": device_id.encode('utf-8'),
            b"timestamp": str(timestamp).encode('utf-8'),
            b"samples": samples_bytes
        }

        await self.client.xadd(
            name=stream_name or settings.SENSOR_STREAM_NAME,
            fields=stream_data,
            maxlen=10000,
            approximate=True
        )

    # Use Pub/Sub for real-time visualization of sensor data and inference results
    async def publish_sensor_data(self, device_id: str, timestamp: int, samples: list[float], mode: str):
        payload = json.dumps({
            "type": "sensor_data",
            "mode": mode,
            "device_id": device_id,
            "timestamp": timestamp,
            "samples": samples,
        }).encode('utf-8')

        await self.client.publish(settings.SENSOR_DATA_CHANNEL, payload)

    async def publish_inference_result(self, device_id: str, max_residual: float, is_anomaly: bool, t_high: float = 0.0):
        payload = json.dumps({
            "type": "inference_result",
            "device_id": device_id,
            "max_residual": float(max_residual),
            "is_anomaly": bool(is_anomaly),
            "t_high": float(t_high),
        }).encode('utf-8')

        await self.client.publish(settings.INFERENCE_RESULTS_CHANNEL, payload)


redis_svc = RedisService()