import { useState, useEffect, useRef } from 'react';
import { ConfigNavbar } from '../components/ConfigNavbar';
import { Sliders, Cpu, BrainCircuit, ToggleLeft } from 'lucide-react';
import {
  AppMode, DetectionSettings, ModelInfo, TrainingStatus, TrainingPhase, WsMessage,
} from '../types/domain';
import { configService } from '../services/configService';
import { modelService } from '../services/modelService';
import { trainingService, TrainingStartPayload } from '../services/trainingService';
import { stateService } from '../services/stateService';
import { dashboardWs } from '../services/websocket';

const CARD = {
  backgroundColor: '#161B22',
  border: '1px solid rgba(255,255,255,0.08)',
};

// ── Reusable helpers ─────────────────────────────────────────────────────────

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full"
      style={{ backgroundColor: ok ? '#10B981' : '#EF4444' }}
    />
  );
}

function CardTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <span style={{ color: '#00D4FF' }}>{icon}</span>
      <h2 className="font-semibold" style={{ fontSize: '15px', color: '#FFFFFF' }}>{title}</h2>
    </div>
  );
}

// ── Mode Card ─────────────────────────────────────────────────────────────────

// REPLAY is controlled from the Replay page, so it is not an option here — but the
// colour/label maps must stay exhaustive over AppMode.
const MODES: AppMode[] = ['standby', 'training', 'detection'];
const MODE_COLOR: Record<AppMode, string> = {
  standby:   '#6B7378',
  training:  '#F59E0B',
  detection: '#00D4FF',
  replay:    '#A371F7',
};
const MODE_LABEL: Record<AppMode, string> = {
  standby:   'STANDBY',
  training:  'TRAINING',
  detection: 'DETECTION',
  replay:    'REPLAY',
};

function ModeCard({ currentMode, onChange }: { currentMode: AppMode; onChange: (m: AppMode) => void }) {
  const [loading, setLoading] = useState(false);

  const handleSet = async (mode: AppMode) => {
    if (mode === currentMode || loading) return;
    setLoading(true);
    try {
      await stateService.set(mode);
      onChange(mode);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg p-6" style={CARD}>
      <CardTitle icon={<ToggleLeft className="w-5 h-5" />} title="System Mode" />
      <div className="grid grid-cols-3 gap-3">
        {MODES.map(mode => {
          const active = mode === currentMode;
          const color = MODE_COLOR[mode];
          return (
            <button
              key={mode}
              onClick={() => handleSet(mode)}
              disabled={loading}
              className="py-3 rounded font-semibold transition-all hover:opacity-90 disabled:opacity-50"
              style={{
                backgroundColor: active ? `${color}25` : '#0D1117',
                border: `1px solid ${active ? color : '#30363D'}`,
                color: active ? color : '#8B949E',
                fontSize: '12px',
              }}
            >
              {MODE_LABEL[mode]}
            </button>
          );
        })}
      </div>
      <p style={{ fontSize: '11px', color: '#8B949E', marginTop: '12px' }}>
        DETECTION runs inference. TRAINING is set automatically when training starts.
      </p>
    </div>
  );
}

// ── Threshold Card ────────────────────────────────────────────────────────────

function ThresholdCard({ settings, onSaved }: { settings: DetectionSettings | null; onSaved: (s: DetectionSettings) => void }) {
  const [pHigh, setPHigh] = useState(95);
  const [pLow, setPLow]   = useState(85);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]  = useState(false);

  useEffect(() => {
    if (settings) { setPHigh(settings.p_high); setPLow(settings.p_low); }
  }, [settings]);

  const handleSave = async () => {
    if (pLow >= pHigh) return;
    setSaving(true);
    try {
      await configService.updateSystemConfig({ p_high: pHigh, p_low: pLow });
      onSaved({ p_high: pHigh, p_low: pLow });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const invalid = pLow >= pHigh;

  return (
    <div className="rounded-lg p-6" style={CARD}>
      <CardTitle icon={<Sliders className="w-5 h-5" />} title="Detection Thresholds" />

      <div className="space-y-5">
        <div>
          <div className="flex justify-between mb-2">
            <label style={{ fontSize: '13px', color: '#C9D1D9' }}>Trigger threshold (p_high)</label>
            <span className="font-semibold" style={{ fontSize: '14px', color: '#EF4444' }}>p{pHigh}</span>
          </div>
          <input
            type="range" min={85} max={99} step={1} value={pHigh}
            onChange={e => setPHigh(+e.target.value)}
            className="w-full h-2 rounded-lg appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #EF4444 0%, #EF4444 ${((pHigh - 85) / 14) * 100}%, #30363D ${((pHigh - 85) / 14) * 100}%, #30363D 100%)`,
            }}
          />
          <div className="flex justify-between mt-1">
            <span style={{ fontSize: '10px', color: '#8B949E' }}>p85 (sensitive)</span>
            <span style={{ fontSize: '10px', color: '#8B949E' }}>p99 (conservative)</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between mb-2">
            <label style={{ fontSize: '13px', color: '#C9D1D9' }}>Clear threshold (p_low)</label>
            <span className="font-semibold" style={{ fontSize: '14px', color: '#F59E0B' }}>p{pLow}</span>
          </div>
          <input
            type="range" min={70} max={94} step={1} value={pLow}
            onChange={e => setPLow(+e.target.value)}
            className="w-full h-2 rounded-lg appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #F59E0B 0%, #F59E0B ${((pLow - 70) / 24) * 100}%, #30363D ${((pLow - 70) / 24) * 100}%, #30363D 100%)`,
            }}
          />
          <div className="flex justify-between mt-1">
            <span style={{ fontSize: '10px', color: '#8B949E' }}>p70</span>
            <span style={{ fontSize: '10px', color: '#8B949E' }}>p94</span>
          </div>
        </div>

        {invalid && (
          <p style={{ fontSize: '11px', color: '#EF4444' }}>p_low must be less than p_high</p>
        )}

        <div className="p-3 rounded" style={{ backgroundColor: '#0D1117' }}>
          <p style={{ fontSize: '12px', color: '#8B949E' }}>
            Alarm triggers when residual exceeds the <strong style={{ color: '#EF4444' }}>p{pHigh}</strong> percentile
            of training residuals, and clears below <strong style={{ color: '#F59E0B' }}>p{pLow}</strong>.
            Changes take effect immediately for new inference windows.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || invalid}
          className="w-full py-2.5 rounded font-semibold transition-all hover:opacity-90 disabled:opacity-50"
          style={{ backgroundColor: saved ? '#10B981' : '#00D4FF', color: '#0D1117', fontSize: '13px' }}
        >
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Apply Thresholds'}
        </button>
      </div>
    </div>
  );
}

// ── Model Management Card ─────────────────────────────────────────────────────

function ModelCard({
  models, activeModel, onActivated,
}: {
  models: ModelInfo[];
  activeModel: string;
  onActivated: (name: string) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string>('');

  const activate = async (name: string) => {
    setBusy(name); setError('');
    try {
      await configService.updateSystemConfig({ active_inference_model: name });
      onActivated(name);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-lg p-6" style={CARD}>
      <CardTitle icon={<Cpu className="w-5 h-5" />} title="Model Management" />

      {error && (
        <div className="mb-3 p-3 rounded" style={{ backgroundColor: '#EF444420', border: '1px solid #EF4444' }}>
          <p style={{ fontSize: '12px', color: '#EF4444' }}>{error}</p>
        </div>
      )}

      {models.length === 0 ? (
        <p style={{ fontSize: '12px', color: '#8B949E' }}>No model bundles found.</p>
      ) : (
        <div className="space-y-2">
          {models.map(m => {
            const isActive = m.name === activeModel;
            return (
              <div
                key={m.name}
                className="flex items-center gap-3 p-3 rounded"
                style={{ backgroundColor: '#0D1117', border: `1px solid ${isActive ? '#00D4FF40' : '#30363D'}` }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-medium truncate" style={{ fontSize: '13px', color: '#C9D1D9' }}>
                      {m.name}
                    </span>
                    {isActive && (
                      <span className="px-1.5 py-0.5 rounded text-xs font-semibold"
                        style={{ backgroundColor: '#00D4FF20', color: '#00D4FF', fontSize: '9px' }}>
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '10px', color: '#8B949E' }}>
                    {m.trained_at ? new Date(m.trained_at).toLocaleString() : 'Built-in'}
                    {m.val_mae  != null && ` · MAE ${m.val_mae.toFixed(5)}`}
                    {m.val_rmse != null && ` · RMSE ${m.val_rmse.toFixed(5)}`}
                  </div>
                </div>

                {!isActive && (
                  <button
                    onClick={() => activate(m.name)}
                    disabled={busy === m.name}
                    className="px-2.5 py-1 rounded text-xs font-medium transition-all hover:opacity-80 disabled:opacity-40 flex-shrink-0"
                    style={{ backgroundColor: '#00D4FF20', color: '#00D4FF', border: '1px solid #00D4FF' }}
                  >
                    {busy === m.name ? '...' : 'Activate'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Training Card ─────────────────────────────────────────────────────────────

function TrainingCard({ onNewModel }: { onNewModel: () => void }) {
  const [status, setStatus]     = useState<TrainingStatus | null>(null);
  const [form, setForm]         = useState<TrainingStartPayload>({ name: '', device_id: '', duration_minutes: 20 });
  const [error, setError]       = useState('');
  const [starting, setStarting] = useState(false);

  // Initial status fetch
  useEffect(() => {
    trainingService.status().then(s => setStatus(s)).catch(() => {});
  }, []);

  // Live updates via WebSocket (training_progress messages)
  useEffect(() => {
    return dashboardWs.onMessage((msg: WsMessage) => {
      if (msg.type !== 'training_progress') return;
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { type, ...sessionFields } = msg;
      setStatus(sessionFields as TrainingStatus);
      if (sessionFields.phase === 'completed') onNewModel();
    });
  }, [onNewModel]);

  const handleStart = async () => {
    if (!form.device_id.trim() || !form.name.trim()) {
      setError('Device ID and model name are required.');
      return;
    }
    setError(''); setStarting(true);
    try {
      // Silently clear any previous terminal session so backend accepts the new one
      await trainingService.clear().catch(() => {});
      const s = await trainingService.start(form);
      setStatus(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const handleCancel = async () => {
    try { await trainingService.cancel(); }
    catch (e: any) { setError(e.message); }
  };

  const phase: TrainingPhase | null = status?.phase ?? null;

  // Derive progress values not returned by the API
  const samplesTarget = status ? status.duration_minutes * 60 * 2048 : 1;
  const progressPct   = status ? Math.min(100, (status.samples_captured / samplesTarget) * 100) : 0;

  return (
    <div className="rounded-lg p-6" style={CARD}>
      <CardTitle icon={<BrainCircuit className="w-5 h-5" />} title="Train New Model" />

      {error && (
        <div className="mb-4 p-3 rounded" style={{ backgroundColor: '#EF444420', border: '1px solid #EF4444' }}>
          <p style={{ fontSize: '12px', color: '#EF4444' }}>{error}</p>
        </div>
      )}

      {/* IDLE / FAILED / CANCELLED — show form */}
      {(phase === null || phase === 'failed' || phase === 'cancelled') && (
        <div className="space-y-4">
          {phase === 'cancelled' && (
            <div className="p-3 rounded" style={{ backgroundColor: '#F59E0B15', border: '1px solid #F59E0B' }}>
              <p style={{ fontSize: '12px', color: '#F59E0B' }}>Previous training was cancelled.</p>
            </div>
          )}

          <div className="space-y-1">
            <label style={{ fontSize: '12px', color: '#8B949E' }}>Device ID</label>
            <input
              type="text"
              value={form.device_id}
              onChange={e => setForm(f => ({ ...f, device_id: e.target.value }))}
              placeholder="e.g. rpi3b-node01"
              className="w-full px-3 py-2 rounded border bg-transparent focus:outline-none focus:border-cyan-500 transition-colors"
              style={{ borderColor: '#30363D', color: '#C9D1D9', fontSize: '13px' }}
            />
          </div>
          <div className="space-y-1">
            <label style={{ fontSize: '12px', color: '#8B949E' }}>Model Name</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. rpi3b-v2"
              className="w-full px-3 py-2 rounded border bg-transparent focus:outline-none focus:border-cyan-500 transition-colors"
              style={{ borderColor: '#30363D', color: '#C9D1D9', fontSize: '13px' }}
            />
          </div>
          <div className="space-y-1">
            <label style={{ fontSize: '12px', color: '#8B949E' }}>
              Capture Duration — {form.duration_minutes} min
            </label>
            <input
              type="range" min={1} max={180} step={1}
              value={form.duration_minutes}
              onChange={e => setForm(f => ({ ...f, duration_minutes: +e.target.value }))}
              className="w-full h-2 rounded-lg appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, #00D4FF 0%, #00D4FF ${((form.duration_minutes - 1) / 179) * 100}%, #30363D ${((form.duration_minutes - 1) / 179) * 100}%, #30363D 100%)`,
              }}
            />
            <div className="flex justify-between">
              <span style={{ fontSize: '10px', color: '#8B949E' }}>1 min</span>
              <span style={{ fontSize: '10px', color: '#8B949E' }}>180 min</span>
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={starting}
            className="w-full py-2.5 rounded font-semibold transition-all hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: '#00D4FF', color: '#0D1117', fontSize: '13px' }}
          >
            {starting ? 'Starting...' : 'Start Capture & Train'}
          </button>

          {phase === 'failed' && status?.error && (
            <p style={{ fontSize: '11px', color: '#8B949E' }}>Last error: {status.error}</p>
          )}
        </div>
      )}

      {/* CAPTURING */}
      {phase === 'capturing' && status && (
        <div className="space-y-4">
          <div className="p-3 rounded" style={{ backgroundColor: '#0D1117' }}>
            <div className="flex justify-between mb-1">
              <span style={{ fontSize: '12px', color: '#C9D1D9' }}>Capturing sensor data</span>
              <span style={{ fontSize: '12px', color: '#00D4FF' }}>{progressPct.toFixed(1)}%</span>
            </div>
            <div className="w-full h-2 rounded-full" style={{ backgroundColor: '#30363D' }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${progressPct}%`, backgroundColor: '#00D4FF' }}
              />
            </div>
            <div className="flex justify-between mt-1">
              <span style={{ fontSize: '10px', color: '#8B949E' }}>
                {status.samples_captured.toLocaleString()} / {samplesTarget.toLocaleString()} samples
              </span>
              <span style={{ fontSize: '10px', color: '#8B949E' }}>{status.device_id}</span>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="w-full py-2 rounded font-medium transition-all hover:opacity-90"
            style={{ border: '1px solid #EF4444', color: '#EF4444', fontSize: '12px' }}
          >
            Cancel Capture
          </button>
        </div>
      )}

      {/* TRAINING */}
      {phase === 'training' && status && (
        <div className="space-y-4">
          <div className="p-3 rounded" style={{ backgroundColor: '#0D1117' }}>
            <div className="flex items-center gap-2 mb-3">
              <div
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: '#F59E0B' }}
              />
              <span style={{ fontSize: '12px', color: '#F59E0B' }}>Training in progress</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span style={{ fontSize: '11px', color: '#8B949E' }}>Model</span>
                <span style={{ fontSize: '11px', color: '#C9D1D9' }}>{status.name}</span>
              </div>
              {status.current_epoch > 0 && (
                <div className="flex justify-between">
                  <span style={{ fontSize: '11px', color: '#8B949E' }}>Epoch</span>
                  <span style={{ fontSize: '11px', color: '#C9D1D9' }}>
                    {status.current_epoch} / {status.total_epochs}
                  </span>
                </div>
              )}
            </div>
          </div>
          <p style={{ fontSize: '11px', color: '#8B949E' }}>
            Model fitting cannot be interrupted. The system will return to STANDBY automatically when done.
          </p>
        </div>
      )}

      {/* COMPLETED */}
      {phase === 'completed' && status && (
        <div className="space-y-4">
          <div className="p-3 rounded" style={{ backgroundColor: '#10B98115', border: '1px solid #10B981' }}>
            <p className="font-semibold mb-2" style={{ fontSize: '13px', color: '#10B981' }}>
              Training complete!
            </p>
            {status.metrics && (
              <div className="space-y-1">
                {Object.entries(status.metrics).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span style={{ fontSize: '11px', color: '#8B949E' }}>{k.toUpperCase()}</span>
                    <span style={{ fontSize: '11px', color: '#C9D1D9' }}>{v.toFixed(6)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => setStatus(null)}
            className="w-full py-2 rounded font-medium transition-all hover:opacity-90"
            style={{ border: '1px solid #30363D', color: '#C9D1D9', fontSize: '12px' }}
          >
            Train Another Model
          </button>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function Configuration() {
  const [appMode, setAppMode]                   = useState<AppMode>('standby');
  const [detectionSettings, setDetectionSettings] = useState<DetectionSettings | null>(null);
  const [models, setModels]                     = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel]           = useState('');

  useEffect(() => {
    stateService.get().then(r => setAppMode(r.mode)).catch(() => {});
    configService.getSystemConfig()
      .then(cfg => {
        setDetectionSettings({ p_high: cfg.p_high, p_low: cfg.p_low });
        setActiveModel(cfg.active_inference_model ?? '');
      })
      .catch(() => {});
    modelService.list().then(setModels).catch(() => {});
  }, []);

  const refreshModels = () => {
    modelService.list().then(setModels).catch(() => {});
    configService.getSystemConfig()
      .then(cfg => setActiveModel(cfg.active_inference_model ?? ''))
      .catch(() => {});
  };

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#0D1117' }}>
      <ConfigNavbar />
      <div className="flex-1 overflow-auto py-8">
        <div className="max-w-[820px] mx-auto px-6 flex flex-col gap-6">
          <ModeCard currentMode={appMode} onChange={setAppMode} />
          <ThresholdCard settings={detectionSettings} onSaved={setDetectionSettings} />
          <ModelCard
            models={models}
            activeModel={activeModel}
            onActivated={name => setActiveModel(name)}
          />
          <TrainingCard onNewModel={refreshModels} />
        </div>
      </div>
    </div>
  );
}
