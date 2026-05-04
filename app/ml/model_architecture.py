import tensorflow as tf

INPUT_SIZE = 2048
FORECAST_SIZE = 32


def build_forecaster(input_size: int = INPUT_SIZE, forecast_size: int = FORECAST_SIZE):
    layers = tf.keras.layers
    model = tf.keras.Sequential([
        layers.Input(shape=(input_size, 1)),
        layers.Conv1D(64, kernel_size=7, dilation_rate=1, activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.Conv1D(64, kernel_size=7, dilation_rate=2, activation="relu", padding="same"),
        layers.MaxPooling1D(pool_size=4),
        layers.Bidirectional(layers.GRU(128, return_sequences=False)),
        layers.Dropout(0.2),
        layers.Dense(64, activation="relu"),
        layers.Dense(forecast_size),
    ])
    model.compile(optimizer="adam", loss="mae")
    return model
