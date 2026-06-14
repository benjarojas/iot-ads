import { Download, Trash2, Activity } from 'lucide-react';
import { AnomalyEvent, DetectionSettings, getSeverity, getSeverityColor, formatTimestamp } from '../types/domain';

interface MetricsPanelProps {
  activeModel: string;
  detectionSettings: DetectionSettings | null;
  anomalyEvents: AnomalyEvent[];
  onClearLog: () => void;
  onExportLog: () => void;
}

export function MetricsPanel({
  activeModel,
  detectionSettings,
  anomalyEvents,
  onClearLog,
  onExportLog,
}: MetricsPanelProps) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 custom-scrollbar" style={{ backgroundColor: '#0D1117' }}>

      {/* Model & Threshold Info */}
      <div className="rounded p-4" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4" style={{ color: '#00D4FF' }} />
          <h4 className="font-semibold" style={{ fontSize: '14px', color: '#C9D1D9' }}>
            Detection Status
          </h4>
        </div>

        {/* Active model */}
        <div className="mb-4 p-3 rounded" style={{ backgroundColor: '#0D1117' }}>
          <div style={{ fontSize: '10px', color: '#8B949E', marginBottom: '4px' }}>Active Model</div>
          <div className="font-semibold truncate" style={{ fontSize: '13px', color: '#00D4FF' }}>
            {activeModel || '—'}
          </div>
        </div>

        {/* Threshold pills */}
        {detectionSettings ? (
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded p-3 text-center" style={{ backgroundColor: '#0D1117' }}>
              <div className="font-bold" style={{ fontSize: '18px', color: '#EF4444' }}>
                p{detectionSettings.p_high}
              </div>
              <div style={{ fontSize: '10px', color: '#8B949E', marginTop: '2px' }}>Trigger</div>
            </div>
            <div className="rounded p-3 text-center" style={{ backgroundColor: '#0D1117' }}>
              <div className="font-bold" style={{ fontSize: '18px', color: '#F59E0B' }}>
                p{detectionSettings.p_low}
              </div>
              <div style={{ fontSize: '10px', color: '#8B949E', marginTop: '2px' }}>Clear</div>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '11px', color: '#8B949E', textAlign: 'center' }}>
            Loading thresholds...
          </div>
        )}
      </div>

      {/* Anomaly Event Log */}
      <div className="rounded p-4" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold" style={{ fontSize: '14px', color: '#C9D1D9' }}>
            Anomaly Event Log
          </h4>
          <span style={{ fontSize: '10px', color: '#8B949E' }}>
            {anomalyEvents.length} events
          </span>
        </div>

        {anomalyEvents.length > 0 ? (
          <div className="overflow-x-auto mb-4">
            <div className="min-w-full">
              {/* Header */}
              <div className="grid grid-cols-4 gap-1 pb-2 mb-2" style={{ borderBottom: '1px solid #30363D' }}>
                {['Time', 'Device', 'Residual', 'Severity'].map(h => (
                  <div key={h} style={{ fontSize: '9px', color: '#8B949E', fontWeight: 600 }}>{h}</div>
                ))}
              </div>

              {/* Rows */}
              <div className="space-y-1 max-h-96 overflow-y-auto custom-scrollbar">
                {anomalyEvents.map((ev) => {
                  // ev.threshold is the log-space trigger (t_high); t_low lives in details.
                  const tLow = typeof ev.details?.t_low === 'number' ? ev.details.t_low : ev.threshold;
                  const severity = getSeverity(ev.max_residual, ev.threshold, tLow);
                  const color = getSeverityColor(severity);
                  return (
                    <div
                      key={ev.id}
                      className="grid grid-cols-4 gap-1 py-1.5 rounded px-1 hover:bg-white/5 transition-colors"
                    >
                      <div style={{ fontSize: '9px', color: '#C9D1D9' }}>
                        {formatTimestamp(ev.started_at)}
                      </div>
                      <div style={{ fontSize: '9px', color: '#C9D1D9' }} className="truncate">
                        {ev.device_id}
                      </div>
                      <div style={{ fontSize: '9px', color: '#00D4FF' }}>
                        {ev.max_residual.toFixed(3)}
                      </div>
                      <div>
                        <span
                          className="inline-block px-1.5 py-0.5 rounded"
                          style={{
                            fontSize: '8px',
                            fontWeight: 600,
                            color,
                            backgroundColor: `${color}20`,
                            border: `1px solid ${color}`,
                          }}
                        >
                          {severity}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center mb-4">
            <div style={{ fontSize: '11px', color: '#8B949E' }}>No anomaly events logged</div>
          </div>
        )}

        {/* Actions */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onExportLog}
            className="py-2 rounded flex items-center justify-center gap-2 transition-all hover:bg-white/5"
            style={{ border: '1px solid #30363D', color: '#C9D1D9', fontSize: '11px' }}
          >
            <Download className="w-3.5 h-3.5" />
            Export
          </button>
          <button
            onClick={onClearLog}
            className="py-2 rounded flex items-center justify-center gap-2 transition-all hover:bg-white/5"
            style={{ border: '1px solid #30363D', color: '#EF4444', fontSize: '11px' }}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        </div>
      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #0D1117; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #30363D; border-radius: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #484F58; }
      `}</style>
    </div>
  );
}
