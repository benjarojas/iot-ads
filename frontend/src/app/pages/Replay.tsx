import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity, ArrowLeft, Database, Play, Square, FileWarning, CheckCircle2,
} from 'lucide-react';
import { useNavigate } from 'react-router';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart, ReferenceLine,
} from 'recharts';
import {
  AppMode, DatasetInfo, ReplayStatus, ReplayPhase, WsMessage,
} from '../types/domain';
import { dashboardWs } from '../services/websocket';
import { datasetService } from '../services/datasetService';
import { replayService } from '../services/replayService';
import { stateService } from '../services/stateService';

const CARD = { backgroundColor: '#161B22', border: '1px solid rgba(255,255,255,0.08)' };
const MAX_POINTS = 150;

interface ChartPoint {
  i: number;          // frame index (x-axis)
  residual: number;
  threshold: number;
  truth: number;      // 0 / 1 ground truth
  pred: number;       // 0 / 1 predicted
  current: number;    // mean current for the frame
}

interface Confusion { tp: number; fp: number; tn: number; fn: number; }
const ZERO: Confusion = { tp: 0, fp: 0, tn: 0, fn: 0 };

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

// ── Navbar ──────────────────────────────────────────────────────────────────────

function ReplayNavbar() {
  const navigate = useNavigate();
  return (
    <div className="h-16 border-b flex items-center justify-between px-6" style={{ backgroundColor: '#161B22', borderColor: '#30363D' }}>
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded" style={{ backgroundColor: '#00D4FF20' }}>
          <Activity className="w-6 h-6" style={{ color: '#00D4FF' }} />
        </div>
        <div>
          <div className="font-semibold tracking-tight" style={{ fontSize: '14px', color: '#00D4FF' }}>IoT-ADS</div>
          <div style={{ fontSize: '11px', color: '#8B949E' }}>Energy-based Side-Channel Monitor</div>
        </div>
      </div>
      <div className="font-semibold tracking-tight" style={{ fontSize: '16px', color: '#FFFFFF' }}>Dataset Replay</div>
      <button
        onClick={() => navigate('/')}
        className="px-4 py-2 rounded border flex items-center gap-2 transition-colors hover:bg-white/5"
        style={{ borderColor: '#00D4FF', color: '#00D4FF' }}
      >
        <ArrowLeft className="w-4 h-4" />
        <span style={{ fontSize: '13px' }}>Return to Dashboard</span>
      </button>
    </div>
  );
}

// ── Confusion matrix + metrics ───────────────────────────────────────────────────

function MetricsCard({ c }: { c: Confusion }) {
  const total = c.tp + c.fp + c.tn + c.fn;
  const acc  = total ? (c.tp + c.tn) / total : 0;
  const prec = c.tp + c.fp ? c.tp / (c.tp + c.fp) : 0;
  const rec  = c.tp + c.fn ? c.tp / (c.tp + c.fn) : 0;
  const f1   = prec + rec ? (2 * prec * rec) / (prec + rec) : 0;

  const Cell = ({ label, value, good }: { label: string; value: number; good: boolean }) => (
    <div className="rounded p-3 text-center" style={{ backgroundColor: '#0D1117', border: `1px solid ${good ? '#10B98140' : '#EF444440'}` }}>
      <div style={{ fontSize: '10px', color: '#8B949E' }}>{label}</div>
      <div className="font-semibold" style={{ fontSize: '20px', color: good ? '#10B981' : '#EF4444' }}>{value}</div>
    </div>
  );

  const Metric = ({ label, v }: { label: string; v: number }) => (
    <div className="flex justify-between">
      <span style={{ fontSize: '12px', color: '#8B949E' }}>{label}</span>
      <span className="font-semibold" style={{ fontSize: '12px', color: '#C9D1D9' }}>{(v * 100).toFixed(1)}%</span>
    </div>
  );

  return (
    <div className="rounded-lg p-6" style={CARD}>
      <div className="flex items-center gap-3 mb-4">
        <CheckCircle2 className="w-5 h-5" style={{ color: '#00D4FF' }} />
        <h2 className="font-semibold" style={{ fontSize: '15px', color: '#FFFFFF' }}>Prediction vs Ground Truth</h2>
      </div>
      <p style={{ fontSize: '10px', color: '#8B949E', marginBottom: '12px' }}>
        Window-level, evaluated against the default model. {total.toLocaleString()} windows scored.
      </p>
      <div className="grid grid-cols-2 gap-2 mb-2">
        <Cell label="True Positive"  value={c.tp} good />
        <Cell label="False Positive" value={c.fp} good={false} />
        <Cell label="False Negative" value={c.fn} good={false} />
        <Cell label="True Negative"  value={c.tn} good />
      </div>
      <div className="space-y-1.5 mt-4">
        <Metric label="Accuracy"  v={acc} />
        <Metric label="Precision" v={prec} />
        <Metric label="Recall"    v={rec} />
        <Metric label="F1 score"  v={f1} />
      </div>
    </div>
  );
}

// ── Label timeline strip ─────────────────────────────────────────────────────────

function TimelineStrip({ label, points, pick }: { label: string; points: ChartPoint[]; pick: (p: ChartPoint) => number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 flex-shrink-0 text-right" style={{ fontSize: '10px', color: '#8B949E' }}>{label}</span>
      <div className="flex-1 flex gap-px h-4 overflow-hidden rounded">
        {points.map((p, idx) => (
          <div key={idx} className="flex-1" style={{ backgroundColor: pick(p) ? '#EF4444' : '#21392b', minWidth: '1px' }} title={`frame ${p.i}`} />
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────────

export function Replay() {
  const [datasets, setDatasets]   = useState<DatasetInfo[]>([]);
  const [selected, setSelected]   = useState<string>('');
  const [deviceId, setDeviceId]   = useState<string>('');
  const [speed, setSpeed]         = useState<number>(1);
  const [maxFrames, setMaxFrames] = useState<string>('');
  const [status, setStatus]       = useState<ReplayStatus | null>(null);
  const [error, setError]         = useState<string>('');
  const [busy, setBusy]           = useState(false);
  const [appMode, setAppMode]     = useState<AppMode>('standby');

  const [points, setPoints]       = useState<ChartPoint[]>([]);
  const [confusion, setConfusion] = useState<Confusion>(ZERO);

  // Per-frame current mean, keyed so inference results can attach truth/pred to it.
  const frameTruth = useRef<Map<number, number>>(new Map());
  const frameMean  = useRef<Map<number, number>>(new Map());

  const resetAccumulators = useCallback(() => {
    setPoints([]);
    setConfusion(ZERO);
    frameTruth.current.clear();
    frameMean.current.clear();
  }, []);

  // ── Initial load ────────────────────────────────────────────────────────────
  useEffect(() => {
    datasetService.list().then(setDatasets).catch(() => {});
    replayService.status().then(s => setStatus(s)).catch(() => {});
    stateService.get().then(r => setAppMode(r.mode)).catch(() => {});
  }, []);

  // ── WebSocket handler ─────────────────────────────────────────────────────────
  const handleWs = useCallback((msg: WsMessage) => {
    if (msg.type === 'replay_progress') {
      const { type, ...rest } = msg;
      void type;
      setStatus(rest as ReplayStatus);
      if (rest.phase === 'running' || rest.phase === 'preparing') setAppMode('replay');
      if (rest.phase === 'completed' || rest.phase === 'cancelled' || rest.phase === 'failed') {
        setAppMode('standby');
      }
    } else if (msg.type === 'sensor_data' && msg.mode === 'replay') {
      if (msg.frame_index !== undefined) {
        const mean = msg.samples.reduce((s, v) => s + v, 0) / msg.samples.length;
        frameMean.current.set(msg.frame_index, mean);
        if (msg.label !== undefined) frameTruth.current.set(msg.frame_index, msg.label);
      }
    } else if (msg.type === 'inference_result' && msg.true_label !== undefined) {
      const truth = msg.true_label;
      const pred  = msg.is_anomaly ? 1 : 0;
      const fi    = msg.frame_index ?? -1;

      // Window-level confusion update.
      setConfusion(c => ({
        tp: c.tp + (pred && truth ? 1 : 0),
        fp: c.fp + (pred && !truth ? 1 : 0),
        fn: c.fn + (!pred && truth ? 1 : 0),
        tn: c.tn + (!pred && !truth ? 1 : 0),
      }));

      setPoints(prev => {
        const next = [...prev, {
          i: fi,
          residual: msg.max_residual,
          threshold: Math.exp(msg.t_high),
          truth,
          pred,
          current: frameMean.current.get(fi) ?? 0,
        }];
        return next.slice(-MAX_POINTS);
      });
    }
  }, []);

  useEffect(() => dashboardWs.onMessage(handleWs), [handleWs]);

  // ── Actions ─────────────────────────────────────────────────────────────────
  const handleStart = async () => {
    if (!selected) { setError('Select a dataset first.'); return; }
    setError(''); setBusy(true);
    try {
      await replayService.clear().catch(() => {});   // drop any terminal session
      resetAccumulators();
      const s = await replayService.start({
        file: selected,
        device_id: deviceId.trim() || undefined,
        speed,
        max_frames: maxFrames ? Number(maxFrames) : null,
      });
      setStatus(s);
      setAppMode('replay');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    try { await replayService.cancel(); }
    catch (e: any) { setError(e.message); }
  };

  const phase: ReplayPhase | null = status?.phase ?? null;
  const isPreparing = phase === 'preparing';
  const isRunning = phase === 'running' || isPreparing;
  const blockedByMode = appMode !== 'standby' && appMode !== 'replay';

  const progressPct = status?.total_frames
    ? Math.min(100, (status.frames_emitted / status.total_frames) * 100)
    : null;

  const selectedInfo = datasets.find(d => d.name === selected);
  const latestThreshold = points.length ? points[points.length - 1].threshold : null;

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#0D1117' }}>
      <ReplayNavbar />
      <div className="flex-1 overflow-auto py-6">
        <div className="max-w-[1200px] mx-auto px-6 grid grid-cols-[380px_1fr] gap-6">

          {/* ── Left column: setup + metrics ── */}
          <div className="flex flex-col gap-6">
            {/* Dataset picker */}
            <div className="rounded-lg p-6" style={CARD}>
              <div className="flex items-center gap-3 mb-4">
                <Database className="w-5 h-5" style={{ color: '#00D4FF' }} />
                <h2 className="font-semibold" style={{ fontSize: '15px', color: '#FFFFFF' }}>Datasets</h2>
              </div>

              {datasets.length === 0 ? (
                <p style={{ fontSize: '12px', color: '#8B949E' }}>
                  No datasets found. Place .csv (with a matching <code>_legend.csv</code>) or .ndjson files in the
                  server's replay data directory.
                </p>
              ) : (
                <div className="space-y-2 max-h-[260px] overflow-auto">
                  {datasets.map(d => {
                    const active = d.name === selected;
                    return (
                      <button
                        key={d.name}
                        onClick={() => { setSelected(d.name); setError(''); }}
                        disabled={isRunning}
                        className="w-full text-left p-3 rounded transition-all hover:opacity-90 disabled:opacity-50"
                        style={{ backgroundColor: '#0D1117', border: `1px solid ${active ? '#00D4FF' : '#30363D'}` }}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium truncate" style={{ fontSize: '13px', color: active ? '#00D4FF' : '#C9D1D9' }}>{d.name}</span>
                          <span style={{ fontSize: '10px', color: '#8B949E' }}>{fmtBytes(d.size_bytes)}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1" style={{ fontSize: '10px', color: '#8B949E' }}>
                          <span className="px-1.5 py-0.5 rounded" style={{ backgroundColor: '#30363D40' }}>{d.format}</span>
                          {d.has_labels
                            ? <span style={{ color: '#10B981' }}>labelled</span>
                            : <span style={{ color: '#8B949E' }}>no labels</span>}
                          {d.total_frames != null && <span>{d.total_frames.toLocaleString()} frames</span>}
                          {d.has_anomalies && <span style={{ color: '#EF4444' }}>{d.anomaly_types.join(', ') || 'anomalies'}</span>}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="rounded-lg p-6" style={CARD}>
              <h2 className="font-semibold mb-4" style={{ fontSize: '15px', color: '#FFFFFF' }}>Replay Settings</h2>

              {error && (
                <div className="mb-4 p-3 rounded" style={{ backgroundColor: '#EF444420', border: '1px solid #EF4444' }}>
                  <p style={{ fontSize: '12px', color: '#EF4444' }}>{error}</p>
                </div>
              )}
              {blockedByMode && (
                <div className="mb-4 p-3 rounded flex items-center gap-2" style={{ backgroundColor: '#F59E0B15', border: '1px solid #F59E0B' }}>
                  <FileWarning className="w-4 h-4" style={{ color: '#F59E0B' }} />
                  <p style={{ fontSize: '11px', color: '#F59E0B' }}>System is in {appMode.toUpperCase()} mode. Replay requires STANDBY.</p>
                </div>
              )}

              <div className="space-y-4">
                <div className="space-y-1">
                  <label style={{ fontSize: '12px', color: '#8B949E' }}>Device ID (optional)</label>
                  <input
                    type="text" value={deviceId} disabled={isRunning}
                    onChange={e => setDeviceId(e.target.value)}
                    placeholder={selectedInfo ? selectedInfo.name.replace(/\.[^.]+$/, '') : 'dataset name'}
                    className="w-full px-3 py-2 rounded border bg-transparent focus:outline-none focus:border-cyan-500 transition-colors disabled:opacity-50"
                    style={{ borderColor: '#30363D', color: '#C9D1D9', fontSize: '13px' }}
                  />
                </div>

                <div className="space-y-1">
                  <label style={{ fontSize: '12px', color: '#8B949E' }}>Speed — {speed}× real-time</label>
                  <input
                    type="range" min={1} max={20} step={1} value={speed} disabled={isRunning}
                    onChange={e => setSpeed(+e.target.value)}
                    className="w-full h-2 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                    style={{ background: `linear-gradient(to right, #00D4FF 0%, #00D4FF ${((speed - 1) / 19) * 100}%, #30363D ${((speed - 1) / 19) * 100}%, #30363D 100%)` }}
                  />
                  <p style={{ fontSize: '10px', color: '#8B949E' }}>1× = real-time (1 frame = 1 s @ 2048 Hz). Higher speeds are capped by inference throughput.</p>
                </div>

                <div className="space-y-1">
                  <label style={{ fontSize: '12px', color: '#8B949E' }}>Max frames (optional)</label>
                  <input
                    type="number" min={1} value={maxFrames} disabled={isRunning}
                    onChange={e => setMaxFrames(e.target.value)}
                    placeholder="entire file"
                    className="w-full px-3 py-2 rounded border bg-transparent focus:outline-none focus:border-cyan-500 transition-colors disabled:opacity-50"
                    style={{ borderColor: '#30363D', color: '#C9D1D9', fontSize: '13px' }}
                  />
                </div>

                {!isRunning ? (
                  <button
                    onClick={handleStart}
                    disabled={busy || blockedByMode || !selected}
                    className="w-full py-2.5 rounded font-semibold transition-all hover:opacity-90 disabled:opacity-40 flex items-center justify-center gap-2"
                    style={{ backgroundColor: '#00D4FF', color: '#0D1117', fontSize: '13px' }}
                  >
                    <Play className="w-4 h-4" />
                    {busy ? 'Starting...' : 'Start Replay'}
                  </button>
                ) : (
                  <button
                    onClick={handleCancel}
                    className="w-full py-2.5 rounded font-medium transition-all hover:opacity-90 flex items-center justify-center gap-2"
                    style={{ border: '1px solid #EF4444', color: '#EF4444', fontSize: '13px' }}
                  >
                    <Square className="w-4 h-4" />
                    Stop Replay
                  </button>
                )}

                {phase && phase !== 'running' && (
                  <p style={{ fontSize: '11px', color: phase === 'failed' ? '#EF4444' : '#8B949E' }}>
                    Last run: {phase}{status?.error ? ` — ${status.error}` : ''}
                  </p>
                )}
              </div>
            </div>

            <MetricsCard c={confusion} />
          </div>

          {/* ── Right column: live charts ── */}
          <div className="flex flex-col gap-6">
            {/* Progress */}
            <div className="rounded-lg p-5" style={CARD}>
              <div className="flex items-center justify-between mb-2">
                <span style={{ fontSize: '13px', color: '#C9D1D9' }}>
                  {status ? status.file : 'No replay running'}
                </span>
                <span style={{ fontSize: '12px', color: isRunning ? '#00D4FF' : '#8B949E' }}>
                  {isPreparing
                    ? 'Loading & downsampling 48828 → 2048 Hz…'
                    : status ? `${status.frames_emitted.toLocaleString()}${status.total_frames ? ` / ${status.total_frames.toLocaleString()}` : ''} frames` : ''}
                </span>
              </div>
              <div className="w-full h-2 rounded-full" style={{ backgroundColor: '#30363D' }}>
                <div className="h-full rounded-full transition-all"
                  style={{ width: `${progressPct ?? 0}%`, backgroundColor: isRunning ? '#00D4FF' : '#30363D' }} />
              </div>
              {status && (
                <div className="flex justify-between mt-2" style={{ fontSize: '10px', color: '#8B949E' }}>
                  <span>{status.device_id} · {status.speed} fps</span>
                  <span style={{ color: '#EF4444' }}>{status.true_anomaly_frames.toLocaleString()} true-anomaly frames</span>
                </div>
              )}
            </div>

            {/* Current waveform */}
            <div className="rounded-lg p-4" style={{ ...CARD, height: '230px' }}>
              <h3 className="font-medium mb-2" style={{ fontSize: '13px', color: '#C9D1D9' }}>Replayed Current (mean per frame)</h3>
              {points.length ? (
                <ResponsiveContainer width="100%" height="88%">
                  <LineChart data={points} margin={{ top: 6, right: 16, left: 0, bottom: 6 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                    <XAxis dataKey="i" stroke="#8B949E" style={{ fontSize: '10px' }} />
                    <YAxis stroke="#8B949E" style={{ fontSize: '10px' }} tickFormatter={(v: number) => v.toFixed(2)} />
                    <Tooltip contentStyle={{ backgroundColor: '#161B22', border: '1px solid #30363D', fontSize: '11px' }} />
                    <Line type="monotone" dataKey="current" stroke="#00D4FF" strokeWidth={1.5} dot={false} isAnimationActive={false} name="Current [A]" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-4/5 flex items-center justify-center"><p style={{ fontSize: '12px', color: '#8B949E' }}>Waiting for replay data…</p></div>
              )}
            </div>

            {/* Residual + threshold */}
            <div className="rounded-lg p-4" style={{ ...CARD, height: '230px' }}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium" style={{ fontSize: '13px', color: '#C9D1D9' }}>Residual vs Threshold</h3>
                {latestThreshold !== null && <span style={{ fontSize: '10px', color: '#EF4444' }}>threshold: {latestThreshold.toFixed(4)}</span>}
              </div>
              {points.length ? (
                <ResponsiveContainer width="100%" height="85%">
                  <AreaChart data={points} margin={{ top: 6, right: 16, left: 0, bottom: 6 }}>
                    <defs>
                      <linearGradient id="resGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#F59E0B" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                    <XAxis dataKey="i" stroke="#8B949E" style={{ fontSize: '10px' }} />
                    <YAxis stroke="#8B949E" style={{ fontSize: '10px' }} tickFormatter={(v: number) => v.toFixed(3)} />
                    <Tooltip contentStyle={{ backgroundColor: '#161B22', border: '1px solid #30363D', fontSize: '11px' }} />
                    {latestThreshold !== null && <ReferenceLine y={latestThreshold} stroke="#EF4444" strokeDasharray="4 3" />}
                    <Area type="monotone" dataKey="residual" stroke="#F59E0B" strokeWidth={1.5} fill="url(#resGrad)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-4/5 flex items-center justify-center"><p style={{ fontSize: '12px', color: '#8B949E' }}>Waiting for inference results…</p></div>
              )}
            </div>

            {/* Truth vs prediction timeline */}
            <div className="rounded-lg p-4 space-y-2" style={CARD}>
              <div className="flex items-center justify-between mb-1">
                <h3 className="font-medium" style={{ fontSize: '13px', color: '#C9D1D9' }}>Ground Truth vs Prediction</h3>
                <span style={{ fontSize: '10px', color: '#8B949E' }}>red = anomaly</span>
              </div>
              <TimelineStrip label="Truth" points={points} pick={p => p.truth} />
              <TimelineStrip label="Pred"  points={points} pick={p => p.pred} />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
