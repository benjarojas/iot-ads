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

    # Replay (offline dataset replay through the detection pipeline)
    REPLAY_PROGRESS_CHANNEL: str = "replay_progress_channel"
    REPLAY_DATA_DIR: str = "replay_datasets"
    REPLAY_DEFAULT_SPEED: float = 1.0  # multiple of real-time (1 frame/sec @ 2048 Hz)

    # Detection — residual aggregation (Lever #1)
    # The instantaneous EWM-smoothed residual has too tight a normal/anomaly margin
    # on low-resolution sensors (e.g. INA219), so brief normal excursions trip the
    # log-hysteresis trigger. We instead threshold a residual averaged over a few
    # seconds (calibrated on the same aggregation of train_residuals), which shrinks
    # the normal spread while a sustained attack's level shift survives.
    RESIDUAL_AGG_SECONDS: float = 3.0   # aggregation window for the detection statistic
    ANOMALY_DWELL_WINDOWS: int = 2      # windows the raised state must persist before confirming

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()