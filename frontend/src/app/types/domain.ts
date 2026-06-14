export type AppMode = 'standby' | 'training' | 'detection' | 'replay';
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type DeviceStatus = 'NORMAL' | 'ANOMALY';
export type TrainingPhase = 'capturing' | 'training' | 'completed' | 'failed' | 'cancelled';
export type ReplayPhase = 'preparing' | 'running' | 'completed' | 'failed' | 'cancelled';

// WebSocket message shapes
export interface SensorMessage {
  type: 'sensor_data';
  mode: AppMode;
  device_id: string;
  timestamp: number;
  samples: number[];
  label?: number;        // ground-truth label for this frame (replay only)
  frame_index?: number;  // replay frame index
}

export interface InferenceMessage {
  type: 'inference_result';
  device_id: string;
  max_residual: number;
  is_anomaly: boolean;
  t_high: number;
  t_low: number;
  true_label?: number;   // ground-truth label echoed back by replay
  frame_index?: number;  // replay frame index
}

export interface TrainingProgressMessage {
  type: 'training_progress';
  id: string;
  name: string;
  device_id: string;
  notes: string | null;
  duration_minutes: number;
  started_at: string;
  capture_ends_at: string;
  phase: TrainingPhase;
  samples_captured: number;
  windows_train: number | null;
  windows_val: number | null;
  current_epoch: number;
  total_epochs: number;
  metrics: TrainingMetrics | null;
  error: string | null;
}

export interface ReplayProgressMessage {
  type: 'replay_progress';
  id: string;
  file: string;
  device_id: string;
  speed: number;
  max_frames: number | null;
  started_at: string;
  phase: ReplayPhase;
  frames_emitted: number;
  total_frames: number | null;
  samples_emitted: number;
  true_anomaly_frames: number;
  error: string | null;
}

export type WsMessage =
  | SensorMessage
  | InferenceMessage
  | TrainingProgressMessage
  | ReplayProgressMessage;

// Client-side device state, built from the WS stream
export interface DeviceState {
  device_id: string;
  last_seen: number;        // epoch ms
  current_mean: number;     // mean of the last 2048-sample chunk
  status: DeviceStatus;
  last_residual: number;
  t_high: number;           // log-space trigger threshold from last inference_result
  t_low: number;            // log-space release threshold from last inference_result
  sparkline: number[];      // rolling means for the last N messages
}

// Chart data points
export interface SensorChartPoint {
  t: number;
  value: number;
}

export interface ResidualChartPoint {
  t: number;
  residual: number;
  threshold: number;    // exp(t_high) — pre-computed for chart reference line
  is_anomaly: boolean;
}

// REST API shapes
export interface SystemConfig {
  id: number;
  p_high: number;
  p_low: number;
  active_inference_model: string | null;
  updated_at: string;
}

export interface AnomalyEvent {
  id: string;
  device_id: string;
  started_at: string;
  ended_at: string | null;
  max_residual: number;
  threshold: number;        // t_high in log-space (as stored by backend)
  model_version: string;
  details: Record<string, unknown>;
}

// View-model derived from SystemConfig — keeps component props stable
export interface DetectionSettings {
  p_high: number;
  p_low: number;
}

export interface ModelInfo {
  name: string;
  device_id: string;
  trained_at: string | null;
  epochs_run: number | null;
  samples_captured: number | null;
  windows_train: number | null;
  windows_val: number | null;
  val_mae: number | null;
  val_mse: number | null;
  val_rmse: number | null;
  notes: string | null;
}

export interface TrainingMetrics {
  mae: number;
  mse: number;
  rmse: number;
  r2: number;
}

export interface TrainingStatus {
  id: string;
  name: string;
  device_id: string;
  notes: string | null;
  duration_minutes: number;
  started_at: string;
  capture_ends_at: string;
  phase: TrainingPhase;
  samples_captured: number;
  windows_train: number | null;
  windows_val: number | null;
  current_epoch: number;
  total_epochs: number;
  metrics: TrainingMetrics | null;
  error: string | null;
}

export interface HealthStatus {
  api: string;
  redis: string;
}

// ── Replay ─────────────────────────────────────────────────────────────────────

export interface DatasetInfo {
  name: string;
  size_bytes: number;
  format: string;
  has_labels: boolean;
  total_samples: number | null;
  total_frames: number | null;
  anomaly_types: string[];
  has_anomalies: boolean;
}

export interface ReplayStatus {
  id: string;
  file: string;
  device_id: string;
  speed: number;
  max_frames: number | null;
  started_at: string;
  phase: ReplayPhase;
  frames_emitted: number;
  total_frames: number | null;
  samples_emitted: number;
  true_anomaly_frames: number;
  error: string | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const EPS = 1e-6;

// Severity cut points, expressed as how many hysteresis bands the residual sits
// above the trigger threshold (see getSeverity). Tune these to taste.
const SEVERITY_BANDS = { CRITICAL: 3.0, HIGH: 1.5, MEDIUM: 0.5 };

/**
 * Classify an anomaly's severity from its peak residual.
 *
 * The detector triggers when the log-residual crosses the per-device threshold
 * `t_high` (the p_high percentile of that device's training residuals) and
 * releases at `t_low` (p_low). We measure severity as how far the residual
 * exceeds the trigger, normalized by that device's own hysteresis band
 * `(t_high - t_low)`:
 *
 *     z = (log(max_residual) - t_high) / (t_high - t_low)
 *
 * z is 0 right at the trigger point and grows as the residual pushes deeper
 * into the tail. Because the band is derived from each device's own residual
 * distribution, the same severity label means the same *degree* of abnormality
 * regardless of the device's absolute current draw — a noisy high-power device
 * and a quiet low-power one are graded on their own scales.
 */
export function getSeverity(max_residual: number, t_high: number, t_low: number): Severity {
  const log_r = Math.log(Math.max(max_residual, 0) + EPS);
  // Hysteresis band width in log-space. Fall back to a unit scale if the band
  // is degenerate or t_low is missing (e.g. legacy events without it).
  const band = t_high - t_low > 1e-3 ? t_high - t_low : Math.max(Math.abs(t_high), 1);
  const z = (log_r - t_high) / band;
  if (z >= SEVERITY_BANDS.CRITICAL) return 'CRITICAL';
  if (z >= SEVERITY_BANDS.HIGH)     return 'HIGH';
  if (z >= SEVERITY_BANDS.MEDIUM)   return 'MEDIUM';
  return 'LOW';
}

export function getSeverityColor(severity: Severity): string {
  switch (severity) {
    case 'CRITICAL': return '#EF4444';
    case 'HIGH':     return '#F97316';
    case 'MEDIUM':   return '#F59E0B';
    case 'LOW':      return '#10B981';
  }
}

export function formatTimestamp(dateStr: string | Date): string {
  const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;
  return date.toLocaleTimeString('en-US', { hour12: false });
}

export function formatRelativeTime(ms: number): string {
  const seconds = Math.floor((Date.now() - ms) / 1000);
  if (seconds < 0) return 'just now';        // clock skew / future timestamp
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
