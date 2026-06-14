import { Activity, Settings, Wifi, WifiOff, Database } from 'lucide-react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router';
import { AppMode, DeviceStatus } from '../types/domain';

interface TopNavbarProps {
  systemStatus: DeviceStatus;
  appMode: AppMode;
  backendOk: boolean;
  lastDataTimestamp: number | null;
}

const MODE_STYLES: Record<AppMode, { bg: string; border: string; text: string; label: string }> = {
  standby:   { bg: '#6B737820', border: '#6B7378', text: '#6B7378', label: 'STANDBY'   },
  training:  { bg: '#F59E0B20', border: '#F59E0B', text: '#F59E0B', label: 'TRAINING'  },
  detection: { bg: '#00D4FF20', border: '#00D4FF', text: '#00D4FF', label: 'DETECTION' },
  replay:    { bg: '#A371F720', border: '#A371F7', text: '#A371F7', label: 'REPLAY'    },
};

export function TopNavbar({ systemStatus, appMode, backendOk, lastDataTimestamp }: TopNavbarProps) {
  const navigate = useNavigate();
  const mode = MODE_STYLES[appMode];

  const formatTime = (ms: number) =>
    new Date(ms).toLocaleTimeString('en-US', { hour12: false });

  return (
    <div
      className="h-16 border-b flex items-center justify-between px-6 flex-shrink-0"
      style={{ backgroundColor: '#161B22', borderColor: '#30363D' }}
    >
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded" style={{ backgroundColor: '#00D4FF20' }}>
          <Activity className="w-6 h-6" style={{ color: '#00D4FF' }} />
        </div>
        <div>
          <div className="font-semibold tracking-tight" style={{ fontSize: '14px', color: '#00D4FF' }}>
            IoT-ADS
          </div>
          <div style={{ fontSize: '11px', color: '#8B949E' }}>
            Energy-based Side-Channel Monitor
          </div>
        </div>
      </div>

      {/* Center: Anomaly status + App mode */}
      <div className="flex items-center gap-3">
        {systemStatus === 'ANOMALY' ? (
          <motion.div
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="px-5 py-1.5 rounded flex items-center gap-2"
            style={{ backgroundColor: '#EF444420', border: '1px solid #EF4444' }}
          >
            <motion.div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: '#EF4444' }}
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="font-semibold tracking-wide" style={{ fontSize: '13px', color: '#EF4444' }}>
              ANOMALY DETECTED
            </span>
          </motion.div>
        ) : (
          <div
            className="px-5 py-1.5 rounded flex items-center gap-2"
            style={{ backgroundColor: '#10B98120', border: '1px solid #10B981' }}
          >
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }} />
            <span className="font-semibold tracking-wide" style={{ fontSize: '13px', color: '#10B981' }}>
              NORMAL
            </span>
          </div>
        )}

        {/* App mode badge */}
        <div
          className="px-3 py-1.5 rounded flex items-center gap-1.5"
          style={{ backgroundColor: mode.bg, border: `1px solid ${mode.border}` }}
        >
          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: mode.text }} />
          <span className="font-medium tracking-wide" style={{ fontSize: '11px', color: mode.text }}>
            {mode.label}
          </span>
        </div>
      </div>

      {/* Right: MQTT status, last update, settings */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          {backendOk ? (
            <>
              <Wifi className="w-4 h-4" style={{ color: '#10B981' }} />
              <span style={{ fontSize: '11px', color: '#10B981' }}>Backend</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4" style={{ color: '#EF4444' }} />
              <span style={{ fontSize: '11px', color: '#EF4444' }}>Backend</span>
            </>
          )}
        </div>
        <div className="h-4 w-px" style={{ backgroundColor: '#30363D' }} />
        <div style={{ fontSize: '11px', color: '#8B949E' }}>
          {lastDataTimestamp ? `Last update: ${formatTime(lastDataTimestamp)}` : 'No data yet'}
        </div>
        <button
          onClick={() => navigate('/replay')}
          className="p-2 rounded hover:bg-white/5 transition-colors"
          title="Dataset Replay"
        >
          <Database className="w-4 h-4" style={{ color: '#8B949E' }} />
        </button>
        <button
          onClick={() => navigate('/config')}
          className="p-2 rounded hover:bg-white/5 transition-colors"
          title="Settings"
        >
          <Settings className="w-4 h-4" style={{ color: '#8B949E' }} />
        </button>
      </div>
    </div>
  );
}
