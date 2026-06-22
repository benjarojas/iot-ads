from __future__ import annotations

import numpy as np

class LogHysteresisDetector:
    def __init__(self, train_residuals: np.ndarray, p_high: float = 95, p_low: float = 85, eps: float = 1e-6):
        """
        Hysteresis-based anomaly detector using residuals on log-scale.

        Args:
            train_residuals (array): Residuals generated on training data (deben ser >= 0).
            p_high (float): Percentile to trigger the alarm.
            p_low (float): Percentile to release the alarm.
            eps (float): Small eps to avoid computing log(0).
        """
        self.eps = eps
        self.alarm_state = False

        residuals = np.asarray(train_residuals, dtype=np.float32)
        if residuals.size == 0:
            raise ValueError("train_residuals must not be empty")

        residuals = np.clip(residuals, 0.0, None)
        log_residuals = np.log(residuals + self.eps)

        self.t_high = float(np.percentile(log_residuals, p_high))
        self.t_low = float(np.percentile(log_residuals, p_low))

    def detect(self, single_residual: float) -> int:
        log_r = float(np.log(max(single_residual, 0.0) + self.eps))

        if not self.alarm_state:
            if log_r > self.t_high:
                self.alarm_state = True
        else:
            if log_r < self.t_low:
                self.alarm_state = False

        return 1 if self.alarm_state else 0

    def detect_window(self, residuals: np.ndarray) -> tuple[bool, float, int]:
        residuals_array = np.asarray(residuals, dtype=np.float32)
        if residuals_array.size == 0:
            return False, 0.0, 0

        max_residual = float(np.max(np.clip(residuals_array, 0.0, None)))
        alarm_state = 0
        for res in residuals_array:
            alarm_state = self.detect(float(res))

        return bool(alarm_state), max_residual, alarm_state