export type AppMode = 'standby' | 'training' | 'detection';
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type DeviceStatus = 'NORMAL' | 'ANOMALY';
export type TrainingPhase = 'capturing' | 'training' | 'completed' | 'failed' | 'cancelled';

// WebSocket message shapes
export interface SensorMessage {
  type: 'sensor_data';
  mode: AppMode;
  device_id: string;
  timestamp: number;
  samples: number[];
}

export interface InferenceMessage {
  type: 'inference_result';
  device_id: string;
  max_residual: number;
  is_anomaly: boolean;
  t_high: number;
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

export type WsMessage = SensorMessage | InferenceMessage | TrainingProgressMessage;

// Client-side device state, built from the WS stream
export interface DeviceState {
  device_id: string;
  last_seen: number;        // epoch ms
  current_mean: number;     // mean of the last 2048-sample chunk
  status: DeviceStatus;
  last_residual: number;
  t_high: number;           // log-space threshold from last inference_result
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

// ── Helpers ──────────────────────────────────────────────────────────────────

const EPS = 1e-6;
export function getSeverity(max_residual: number, threshold: number): Severity {
  if (threshold <= 0) return 'LOW';
  const log_r = Math.log(Math.max(max_residual, 0) + EPS);
  const ratio = log_r / threshold;
  if (ratio >= 2.0) return 'CRITICAL';
  if (ratio >= 1.5) return 'HIGH';
  if (ratio >= 1.2) return 'MEDIUM';
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
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}
