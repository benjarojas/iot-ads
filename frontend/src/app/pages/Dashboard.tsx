import { useState, useEffect, useCallback, useRef } from 'react';
import { TopNavbar } from '../components/TopNavbar';
import { DevicePanel } from '../components/DevicePanel';
import { RealTimeChart } from '../components/RealTimeChart';
import { MetricsPanel } from '../components/MetricsPanel';
import { AnomalyToast } from '../components/AnomalyToast';
import {
  AppMode, DeviceState, AnomalyEvent, DetectionSettings,
  SensorChartPoint, ResidualChartPoint,
  DeviceStatus, Severity, getSeverity, WsMessage,
} from '../types/domain';
import { dashboardWs } from '../services/websocket';
import { anomalyService } from '../services/anomalyService';
import { configService } from '../services/configService';
import { healthService } from '../services/healthService';
import { stateService } from '../services/stateService';

const MAX_SENSOR_POINTS   = 60;   // 1 per second × 60s
const MAX_RESIDUAL_POINTS = 120;  // 4 per second × 30s
const SPARKLINE_LEN = 16;
const HEALTH_POLL_MS = 10_000;

interface ToastState {
  visible: boolean;
  deviceId: string;
  maxResidual: number;
  severity: Severity;
}

export function Dashboard() {
  const [devices, setDevices]                   = useState<Map<string, DeviceState>>(new Map());
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [sensorData, setSensorData]             = useState<Map<string, SensorChartPoint[]>>(new Map());
  const [residualData, setResidualData]         = useState<Map<string, ResidualChartPoint[]>>(new Map());
  const [anomalyEvents, setAnomalyEvents]       = useState<AnomalyEvent[]>([]);
  const [appMode, setAppMode]                   = useState<AppMode>('standby');
  const [activeModel, setActiveModel]           = useState<string>('');
  const [detectionSettings, setDetectionSettings] = useState<DetectionSettings | null>(null);
  const [lastDataTimestamp, setLastDataTimestamp] = useState<number | null>(null);
  const [backendOk, setBackendOk]               = useState(false);
  const [toast, setToast] = useState<ToastState>({ visible: false, deviceId: '', maxResidual: 0, severity: 'LOW' });

  const prevAnomalyRef = useRef<Map<string, boolean>>(new Map());

  const fetchAnomalyEvents = useCallback(() => {
    anomalyService.list({ limit: 100 }).then(setAnomalyEvents).catch(() => {});
  }, []);

  // ── Health polling ────────────────────────────────────────────────────────
  useEffect(() => {
    const poll = () =>
      healthService.get()
        .then(h => setBackendOk(h.api === 'ok'))
        .catch(() => setBackendOk(false));
    poll();
    const id = setInterval(poll, HEALTH_POLL_MS);
    return () => clearInterval(id);
  }, []);

  // ── Initial data fetch ────────────────────────────────────────────────────
  useEffect(() => {
    fetchAnomalyEvents();
    configService.getSystemConfig()
      .then(cfg => {
        setDetectionSettings({ p_high: cfg.p_high, p_low: cfg.p_low });
        setActiveModel(cfg.active_inference_model ?? '');
      })
      .catch(() => {});
    stateService.get().then(r => setAppMode(r.mode)).catch(() => {});
  }, [fetchAnomalyEvents]);

  // ── WebSocket message handler ─────────────────────────────────────────────
  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type === 'sensor_data') {
      const { device_id, timestamp, samples, mode } = msg;
      const mean = samples.reduce((s, v) => s + v, 0) / samples.length;

      setDevices(prev => {
        const next = new Map(prev);
        const existing = next.get(device_id);
        const sparkline = existing
          ? [...existing.sparkline.slice(-(SPARKLINE_LEN - 1)), mean]
          : [mean];
        next.set(device_id, {
          device_id,
          last_seen: timestamp,
          current_mean: mean,
          status: existing?.status ?? 'NORMAL',
          last_residual: existing?.last_residual ?? 0,
          t_high: existing?.t_high ?? 0,
          sparkline,
        });
        return next;
      });

      setSensorData(prev => {
        const next = new Map(prev);
        const pts = prev.get(device_id) ?? [];
        next.set(device_id, [...pts.slice(-(MAX_SENSOR_POINTS - 1)), { t: timestamp, value: mean }]);
        return next;
      });

      setAppMode(mode);
      setLastDataTimestamp(timestamp);

    } else if (msg.type === 'inference_result') {
      const { device_id, max_residual, is_anomaly, t_high } = msg;
      const status: DeviceStatus = is_anomaly ? 'ANOMALY' : 'NORMAL';
      const thresholdDisplay = Math.exp(t_high);

      setDevices(prev => {
        const next = new Map(prev);
        const existing = next.get(device_id);
        if (existing) {
          next.set(device_id, { ...existing, status, last_residual: max_residual, t_high });
        }
        return next;
      });

      setResidualData(prev => {
        const next = new Map(prev);
        const pts = prev.get(device_id) ?? [];
        next.set(device_id, [
          ...pts.slice(-(MAX_RESIDUAL_POINTS - 1)),
          { t: Date.now(), residual: max_residual, threshold: thresholdDisplay, is_anomaly },
        ]);
        return next;
      });

      const wasAnomaly = prevAnomalyRef.current.get(device_id) ?? false;
      if (!wasAnomaly && is_anomaly) {
        const sev = detectionSettings ? getSeverity(max_residual, t_high) : 'HIGH';
        setToast({ visible: true, deviceId: device_id, maxResidual: max_residual, severity: sev });
        setTimeout(() => setToast(t => ({ ...t, visible: false })), 5500);
        // Re-fetch event log so the new DB record appears
        fetchAnomalyEvents();
      }
      prevAnomalyRef.current.set(device_id, is_anomaly);
    }
  }, [detectionSettings, fetchAnomalyEvents]);

  // ── WebSocket subscription ────────────────────────────────────────────────
  useEffect(() => {
    return dashboardWs.onMessage(handleWsMessage);
  }, [handleWsMessage]);

  // Auto-select first device when devices appear
  useEffect(() => {
    if (selectedDeviceId === null && devices.size > 0) {
      setSelectedDeviceId([...devices.keys()][0]);
    }
  }, [devices, selectedDeviceId]);

  // ── Derived values ────────────────────────────────────────────────────────
  const deviceList   = [...devices.values()];
  const systemStatus = deviceList.some(d => d.status === 'ANOMALY') ? 'ANOMALY' : 'NORMAL';
  const selSensor    = selectedDeviceId ? (sensorData.get(selectedDeviceId)   ?? []) : [];
  const selResidual  = selectedDeviceId ? (residualData.get(selectedDeviceId) ?? []) : [];


  // ── Export / clear handlers ───────────────────────────────────────────────
  const handleExportLog = () => {
    const csv = [
      'id,device_id,started_at,ended_at,max_residual,threshold,model_version',
      ...anomalyEvents.map(e =>
        [e.id, e.device_id, e.started_at, e.ended_at ?? '', e.max_residual, e.threshold, e.model_version].join(',')
      ),
    ].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `anomaly-events-${Date.now()}.csv`;
    a.click();
  };

  const handleClearLog = () => setAnomalyEvents([]);

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#0D1117' }}>
      <TopNavbar
        systemStatus={systemStatus}
        appMode={appMode}
        backendOk={backendOk}
        lastDataTimestamp={lastDataTimestamp}
      />

      <div className="flex-1 grid grid-cols-[20%_50%_30%] overflow-hidden">
        {/* Left: device list */}
        <div className="border-r overflow-hidden" style={{ borderColor: '#30363D' }}>
          <DevicePanel
            devices={deviceList}
            selectedDeviceId={selectedDeviceId}
            onDeviceSelect={setSelectedDeviceId}
          />
        </div>

        {/* Center: chart */}
        <div className="border-r overflow-hidden" style={{ borderColor: '#30363D' }}>
          <RealTimeChart
            deviceId={selectedDeviceId}
            sensorPoints={selSensor}
            residualPoints={selResidual}
          />
        </div>

        {/* Right: metrics + event log */}
        <div className="overflow-hidden">
          <MetricsPanel
            activeModel={activeModel}
            detectionSettings={detectionSettings}
            anomalyEvents={anomalyEvents}
            onClearLog={handleClearLog}
            onExportLog={handleExportLog}
          />
        </div>
      </div>

      <AnomalyToast
        isVisible={toast.visible}
        deviceId={toast.deviceId}
        maxResidual={toast.maxResidual}
        severity={toast.severity}
        onClose={() => setToast(t => ({ ...t, visible: false }))}
      />
    </div>
  );
}
