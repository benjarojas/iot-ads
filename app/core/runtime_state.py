from enum import Enum

from app.services.redis_service import redis_svc
from app.core.logging_utils import get_logger

logger = get_logger(__name__)

class AppMode(str, Enum):
    STANDBY = "standby"
    TRAINING = "training"
    DETECTION = "detection"
    REPLAY = "replay"

class RuntimeState:
    
    REDIS_KEY = "runtime:mode"
    DEFAULT_MODE = AppMode.STANDBY
    
    def __init__(self):
        pass
    
    async def initialize(self):
        try:
            existing_mode = await self.get_mode()
            # if mode exists and is valid, change it to STANDBY on startup to avoid confusion
            if existing_mode in AppMode:
                logger.info(f"Existing mode found in Redis. Resetting to {self.DEFAULT_MODE} on startup.")
                await self.set_mode(self.DEFAULT_MODE)
        except Exception as e:
            logger.warning(f"Error reading initial mode from Redis: {e}. Setting to {self.DEFAULT_MODE}")
            await self.set_mode(self.DEFAULT_MODE)
    
    async def get_mode(self) -> AppMode:
        try:
            mode_value = await redis_svc.client.get(self.REDIS_KEY)
            
            if mode_value is None:
                # Key doesn't exist, initialize to STANDBY
                logger.info(f"Mode key not found in Redis, initializing to {self.DEFAULT_MODE.value}")
                await self.set_mode(self.DEFAULT_MODE)
                return self.DEFAULT_MODE
            
            # Redis returns bytes when decode_responses=False, so decode it
            if isinstance(mode_value, bytes):
                mode_value = mode_value.decode('utf-8')
            
            # Validate and return the mode
            return AppMode(mode_value)
        
        except ValueError as e:
            logger.error(f"Invalid mode value in Redis: {mode_value}. Expected one of {[m.value for m in AppMode]}")
            raise
        except Exception as e:
            logger.error(f"Error reading mode from Redis: {e}", exc_info=True)
            raise
    
    async def set_mode(self, mode: AppMode) -> AppMode:
        try:
            # Redis stores strings, so encode the mode value
            await redis_svc.client.set(self.REDIS_KEY, mode.value)
            logger.info(f"RuntimeState mode changed to: {mode.value}")
            return mode
        except Exception as e:
            logger.error(f"Error setting mode in Redis: {e}", exc_info=True)
            raise
    
    async def is_standby(self) -> bool:
        return await self.get_mode() == AppMode.STANDBY
    
    async def is_training(self) -> bool:
        return await self.get_mode() == AppMode.TRAINING
    
    async def is_detection(self) -> bool:
        return await self.get_mode() == AppMode.DETECTION

    async def is_replay(self) -> bool:
        return await self.get_mode() == AppMode.REPLAY

# Global singleton instance
runtime_state = RuntimeState()