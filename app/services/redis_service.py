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

    async def flush_sensor_stream(self):
        """Drop all entries from the sensor stream (keeps the consumer group intact).
        Used before a replay starts so stale frames from a previous run are not
        consumed by the inference worker. XTRIM (not DEL) preserves the group so the
        inference worker's xreadgroup keeps working."""
        try:
            await self.client.xtrim(settings.SENSOR_STREAM_NAME, maxlen=0, approximate=False)
        except Exception:
            pass  # stream may not exist yet — nothing to flush

    async def add_sensor_data(self, device_id: str, timestamp: int, samples_bytes: bytes, stream_name: str | None = None, extra_fields: dict | None = None):
        stream_data = {
            b"device_id": device_id.encode('utf-8'),
            b"timestamp": str(timestamp).encode('utf-8'),
            b"samples": samples_bytes
        }
        # Optional metadata (e.g. ground-truth label + frame index for replay) is
        # carried through the stream so the inference worker can echo it back,
        # time-aligned, on each inference result.
        if extra_fields:
            for key, value in extra_fields.items():
                stream_data[key.encode('utf-8')] = str(value).encode('utf-8')

        await self.client.xadd(
            name=stream_name or settings.SENSOR_STREAM_NAME,
            fields=stream_data,
            maxlen=10000,
            approximate=True
        )

    # Use Pub/Sub for real-time visualization of sensor data and inference results
    async def publish_sensor_data(self, device_id: str, timestamp: int, samples: list[float], mode: str, label: int | None = None, frame_index: int | None = None):
        payload = {
            "type": "sensor_data",
            "mode": mode,
            "device_id": device_id,
            "timestamp": timestamp,
            "samples": samples,
        }
        if label is not None:
            payload["label"] = int(label)
        if frame_index is not None:
            payload["frame_index"] = int(frame_index)

        await self.client.publish(settings.SENSOR_DATA_CHANNEL, json.dumps(payload).encode('utf-8'))

    async def publish_inference_result(self, device_id: str, max_residual: float, is_anomaly: bool, t_high: float = 0.0, t_low: float = 0.0, true_label: int | None = None, frame_index: int | None = None):
        payload = {
            "type": "inference_result",
            "device_id": device_id,
            "max_residual": float(max_residual),
            "is_anomaly": bool(is_anomaly),
            "t_high": float(t_high),
            "t_low": float(t_low),
        }
        if true_label is not None:
            payload["true_label"] = int(true_label)
        if frame_index is not None:
            payload["frame_index"] = int(frame_index)

        await self.client.publish(settings.INFERENCE_RESULTS_CHANNEL, json.dumps(payload).encode('utf-8'))


redis_svc = RedisService()