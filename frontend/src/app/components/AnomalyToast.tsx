import { AlertTriangle, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Severity, getSeverityColor } from '../types/domain';

interface AnomalyToastProps {
  isVisible: boolean;
  deviceId: string;
  maxResidual: number;
  severity: Severity;
  onClose: () => void;
}

export function AnomalyToast({ isVisible, deviceId, maxResidual, severity, onClose }: AnomalyToastProps) {
  const color = getSeverityColor(severity);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: -20, x: 20 }}
          animate={{ opacity: 1, y: 0, x: 0 }}
          exit={{ opacity: 0, y: -20, x: 20 }}
          className="fixed top-20 right-6 rounded p-4 shadow-2xl z-50"
          style={{ backgroundColor: '#161B22', border: `1px solid ${color}`, minWidth: '300px', maxWidth: '380px' }}
        >
          <div className="flex items-start gap-3">
            <div
              className="w-9 h-9 rounded flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: `${color}20` }}
            >
              <AlertTriangle className="w-4 h-4" style={{ color }} />
            </div>

            <div className="flex-1">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="font-semibold mb-0.5" style={{ fontSize: '13px', color }}>
                    ANOMALY DETECTED
                  </div>
                  <div style={{ fontSize: '10px', color: '#8B949E' }}>
                    {new Date().toLocaleTimeString()}
                  </div>
                </div>
                <button onClick={onClose} className="p-1 rounded hover:bg-white/10 transition-colors">
                  <X className="w-4 h-4" style={{ color: '#8B949E' }} />
                </button>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between">
                  <span style={{ fontSize: '11px', color: '#8B949E' }}>Device:</span>
                  <span style={{ fontSize: '11px', color: '#C9D1D9' }}>{deviceId}</span>
                </div>
                <div className="flex justify-between">
                  <span style={{ fontSize: '11px', color: '#8B949E' }}>Residual:</span>
                  <span className="font-semibold" style={{ fontSize: '11px', color }}>
                    {maxResidual.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span style={{ fontSize: '11px', color: '#8B949E' }}>Severity:</span>
                  <span
                    className="font-semibold px-1.5 py-0.5 rounded"
                    style={{ fontSize: '10px', color, backgroundColor: `${color}20`, border: `1px solid ${color}` }}
                  >
                    {severity}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-dismiss progress bar */}
          <motion.div className="mt-3 h-1 rounded-full" style={{ backgroundColor: '#30363D' }}>
            <motion.div
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{ duration: 5, ease: 'linear' }}
              className="h-full rounded-full"
              style={{ backgroundColor: color }}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
