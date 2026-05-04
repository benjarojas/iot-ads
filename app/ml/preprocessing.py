from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from scipy.signal import lfilter
from sklearn.preprocessing import StandardScaler

FILTER_WIN = 15
_FILTER_B = np.ones(FILTER_WIN, dtype=np.float64) / FILTER_WIN
_FILTER_A = np.array([1.0], dtype=np.float64)

SCALER_PATH = Path("ml_models/stdscaler-prod.gz")

def load_scaler() -> StandardScaler:
    if not SCALER_PATH.exists():
        raise FileNotFoundError(
            f"StandardScaler not found at '{SCALER_PATH}'. "
            "Place stdscaler-prod.gz in the ml_models/ directory."
        )
    return joblib.load(SCALER_PATH)


def apply_moving_average(buffer: np.ndarray) -> np.ndarray:
    """Causal moving-average filter (production-safe replacement for filtfilt)."""
    return lfilter(_FILTER_B, _FILTER_A, buffer.astype(np.float64)).astype(np.float32)


def scale_array(x: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    # scaler was fitted on (-1, 1) shaped data: each sample is one feature
    return scaler.transform(x.reshape(-1, 1)).flatten().astype(np.float32)


EWM_SPAN = 256
EWM_ALPHA = 2.0 / (EWM_SPAN + 1)  # ≈ 0.00778


def apply_ewm(residuals: np.ndarray, state: float | None) -> tuple[np.ndarray, float]:
    """
    Apply exponentially weighted moving average (adjust=False, span=256) to a
    residual window, carrying the running state across windows and messages.

    Returns (smoothed_residuals, updated_state).
    state=None initialises to the first residual value (pandas default).
    """
    smoothed = np.empty_like(residuals, dtype=np.float32)
    s = state
    for i, r in enumerate(residuals):
        s = float(r) if s is None else (1.0 - EWM_ALPHA) * s + EWM_ALPHA * float(r)
        smoothed[i] = s
    return smoothed, s  # type: ignore[return-value]
