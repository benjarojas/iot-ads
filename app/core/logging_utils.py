import logging

from app.core.config import settings

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(logging.INFO if settings.LOG_LEVEL.upper() == "INFO" else logging.DEBUG)
    logger.propagate = False
    return logger