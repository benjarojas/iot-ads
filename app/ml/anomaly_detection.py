from __future__ import annotations

from collections import deque

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


def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """Causal trailing moving average; the first `window-1` points average fewer
    samples (cumulative warm-up) so the output length matches the input."""
    x = np.asarray(x, dtype=np.float64)
    if window <= 1 or x.size == 0:
        return x.astype(np.float32)
    csum = np.cumsum(x)
    out = np.empty_like(x)
    out[:window] = csum[:window] / np.arange(1, window + 1)
    out[window:] = (csum[window:] - csum[:-window]) / window
    return out.astype(np.float32)


class AggregatedResidualDetector:
    """Lever #1 detector.

    Thresholds a residual *averaged over a few seconds* instead of the
    instantaneous EWM-smoothed residual. Calibration is self-consistent: the
    same trailing moving average is applied to `train_residuals` (which are
    already the EWM-smoothed, temporally-ordered validation residuals) before
    taking the log-space p_high/p_low percentiles. A sustained attack shifts the
    aggregated residual past the (now much tighter) trigger; brief normal
    excursions average out. A dwell counter requires the raised hysteresis state
    to persist for `dwell_windows` update() calls before the alarm is confirmed.

    update() consumes the per-window smoothed-residual array exactly as
    LogHysteresisDetector.detect_window() did, so it is a drop-in at the call site.
    """

    def __init__(
        self,
        train_residuals: np.ndarray,
        p_high: float = 95,
        p_low: float = 85,
        agg_window: int = 384,   # ~3 s at ~128 smoothed-residual points/sec
        dwell_windows: int = 2,
        eps: float = 1e-6,
    ):
        self.eps = eps
        self.agg_window = max(1, int(agg_window))
        self.dwell_windows = max(0, int(dwell_windows))

        residuals = np.clip(np.asarray(train_residuals, dtype=np.float64), 0.0, None)
        if residuals.size == 0:
            raise ValueError("train_residuals must not be empty")

        # Calibrate on the SAME aggregation we apply live (the crux of Lever #1).
        agg = _moving_average(residuals, self.agg_window)
        log_agg = np.log(agg + self.eps)
        self.t_high = float(np.percentile(log_agg, p_high))
        self.t_low = float(np.percentile(log_agg, p_low))

        # Live state: rolling residual buffer (O(1) mean via running sum),
        # hysteresis latch, dwell counter, and last aggregate value (for display).
        self._buf: deque[float] = deque(maxlen=self.agg_window)
        self._running_sum = 0.0
        self._raw_alarm = False      # hysteresis state on the aggregate
        self._dwell = 0
        self.alarm_state = False     # confirmed (post-dwell) state
        self.last_agg = 0.0

    def _push(self, value: float) -> float:
        v = max(float(value), 0.0)
        if len(self._buf) == self._buf.maxlen:
            self._running_sum -= self._buf[0]  # evicted by append below
        self._buf.append(v)
        self._running_sum += v
        return self._running_sum / len(self._buf)

    def update(self, residuals: np.ndarray) -> tuple[bool, float]:
        """Feed one window's smoothed residuals; returns (confirmed_alarm, aggregate)."""
        residuals_array = np.clip(np.asarray(residuals, dtype=np.float64), 0.0, None)
        agg = self.last_agg
        for r in residuals_array:
            agg = self._push(r)
        self.last_agg = agg

        # Log-hysteresis on the aggregate.
        log_agg = float(np.log(agg + self.eps))
        if not self._raw_alarm:
            if log_agg > self.t_high:
                self._raw_alarm = True
        else:
            if log_agg < self.t_low:
                self._raw_alarm = False

        # Dwell: confirm only after the raised state persists.
        if self._raw_alarm:
            self._dwell = min(self._dwell + 1, self.dwell_windows)
            if self._dwell >= self.dwell_windows:
                self.alarm_state = True
        else:
            self._dwell = 0
            self.alarm_state = False

        return self.alarm_state, agg