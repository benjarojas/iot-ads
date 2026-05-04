from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "IoT-ADS Backend Services"

    # Redis
    REDIS_URL: str

    # Postgres
    POSTGRES_URL: str
    POSTGRES_ECHO: bool = False

    # MQTT Broker
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPIC: str = "sensor/+/current"

    # MQTT Ingest Worker
    INGEST_WORKER_COUNT: int = 2

    SENSOR_STREAM_NAME: str = "sensor_data_stream"
    INFERENCE_GROUP_NAME: str = "inference_workers_group"
    CONFIG_UPDATES_CHANNEL: str = "config_updates_channel"

    # Training
    TRAINING_GROUP_NAME: str = "training_workers_group"
    TRAINING_PROGRESS_CHANNEL: str = "training_progress_channel"
    TRAINING_DEFAULT_DURATION_MINUTES: int = 20
    TRAINING_DEFAULT_EPOCHS: int = 100
    TRAINING_BATCH_SIZE: int = 32
    TRAINING_VAL_SPLIT: float = 0.2
    TRAINING_STREAM_NAME: str = "training_data_stream"
    SENSOR_DATA_CHANNEL: str = "sensor_data_channel"
    INFERENCE_RESULTS_CHANNEL: str = "inference_results_channel"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()