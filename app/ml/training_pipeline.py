from __future__ import annotations

import numpy as np
from sklearn.preprocessing import StandardScaler

INPUT_SIZE = 2048
FORECAST_SIZE = 32
STRIDE = 512
WINDOW_SPAN = INPUT_SIZE + FORECAST_SIZE


def fit_scaler(filtered_samples: np.ndarray) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(filtered_samples.reshape(-1, 1))
    return scaler


def build_supervised_dataset(scaled_samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if scaled_samples.size < WINDOW_SPAN:
        raise ValueError(
            f"Not enough samples for a single window: need at least {WINDOW_SPAN}, got {scaled_samples.size}"
        )

    n_windows = (scaled_samples.size - WINDOW_SPAN) // STRIDE + 1
    X = np.empty((n_windows, INPUT_SIZE, 1), dtype=np.float32)
    Y = np.empty((n_windows, FORECAST_SIZE), dtype=np.float32)

    for i in range(n_windows):
        off = i * STRIDE
        X[i, :, 0] = scaled_samples[off: off + INPUT_SIZE]
        Y[i] = scaled_samples[off + INPUT_SIZE: off + WINDOW_SPAN]

    return X, Y


def time_split(
    X: np.ndarray, Y: np.ndarray, val_fraction: float = 0.2
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Time-ordered train/val split (no shuffling — temporal data)."""
    n = X.shape[0]
    split = int(n * (1.0 - val_fraction))
    return X[:split], Y[:split], X[split:], Y[split:]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true_f = y_true.flatten().astype(np.float64)
    y_pred_f = y_pred.flatten().astype(np.float64)

    diff = y_true_f - y_pred_f
    mae = float(np.mean(np.abs(diff)))
    mse = float(np.mean(diff ** 2))
    rmse = float(np.sqrt(mse))

    ss_res = float(np.sum(diff ** 2))
    ss_tot = float(np.sum((y_true_f - np.mean(y_true_f)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {"mae": mae, "mse": mse, "rmse": rmse, "r2": r2}
