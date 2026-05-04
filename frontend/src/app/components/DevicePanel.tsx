import { Cpu } from 'lucide-react';
import { motion } from 'motion/react';
import { DeviceState, formatRelativeTime } from '../types/domain';

interface DevicePanelProps {
  devices: DeviceState[];
  selectedDeviceId: string | null;
  onDeviceSelect: (id: string) => void;
}

export function DevicePanel({ devices, selectedDeviceId, onDeviceSelect }: DevicePanelProps) {
  return (
    <div className="h-full flex flex-col p-4" style={{ backgroundColor: '#0D1117' }}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold tracking-tight" style={{ fontSize: '14px', color: '#C9D1D9' }}>
          Monitored Devices
        </h3>
        <span style={{ fontSize: '11px', color: '#8B949E' }}>
          {devices.length} online
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar">
        {devices.length === 0 ? (
          <div className="py-12 text-center">
            <Cpu className="w-8 h-8 mx-auto mb-2" style={{ color: '#30363D' }} />
            <p style={{ fontSize: '12px', color: '#8B949E' }}>
              Waiting for sensor data...
            </p>
            <p style={{ fontSize: '10px', color: '#484F58', marginTop: '4px' }}>
              Devices appear automatically when MQTT messages arrive
            </p>
          </div>
        ) : (
          devices.map((device) => (
            <motion.div
              key={device.device_id}
              whileHover={{ scale: 1.02 }}
              onClick={() => onDeviceSelect(device.device_id)}
              className="p-4 rounded cursor-pointer transition-all"
              style={{
                backgroundColor: selectedDeviceId === device.device_id ? '#1C2128' : '#161B22',
                border: `1px solid ${selectedDeviceId === device.device_id ? '#00D4FF' : '#30363D'}`,
              }}
            >
              {/* Device ID and last seen */}
              <div className="flex items-start gap-3 mb-3">
                <div
                  className="w-8 h-8 rounded flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: '#00D4FF20' }}
                >
                  <Cpu className="w-4 h-4" style={{ color: '#00D4FF' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate" style={{ fontSize: '12px', color: '#C9D1D9' }}>
                    {device.device_id}
                  </div>
                  <div style={{ fontSize: '10px', color: '#8B949E' }}>
                    {formatRelativeTime(device.last_seen)}
                  </div>
                </div>
              </div>

              {/* Status badge */}
              <div className="mb-3">
                {device.status === 'ANOMALY' ? (
                  <motion.div
                    animate={{ opacity: [1, 0.6, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded"
                    style={{ backgroundColor: '#EF444420', border: '1px solid #EF4444' }}
                  >
                    <motion.div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: '#EF4444' }}
                      animate={{ scale: [1, 1.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    <span className="font-semibold" style={{ fontSize: '10px', color: '#EF4444' }}>
                      ANOMALY
                    </span>
                  </motion.div>
                ) : (
                  <div
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded"
                    style={{ backgroundColor: '#10B98120', border: '1px solid #10B981' }}
                  >
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#10B981' }} />
                    <span className="font-semibold" style={{ fontSize: '10px', color: '#10B981' }}>
                      NORMAL
                    </span>
                  </div>
                )}
              </div>

              {/* Current mean */}
              <div className="mb-2">
                <div className="font-bold" style={{ fontSize: '20px', color: '#00D4FF' }}>
                  {device.current_mean.toFixed(3)} A
                </div>
              </div>

              {/* Sparkline */}
              <div className="flex items-end gap-0.5 h-8">
                {device.sparkline.map((v, idx) => {
                  const max = Math.max(...device.sparkline, 0.001);
                  return (
                    <div
                      key={idx}
                      className="flex-1 rounded-t"
                      style={{
                        backgroundColor: device.status === 'ANOMALY' ? '#EF4444' : '#00D4FF',
                        height: `${(v / max) * 100}%`,
                        opacity: 0.3 + (idx / device.sparkline.length) * 0.7,
                      }}
                    />
                  );
                })}
              </div>
            </motion.div>
          ))
        )}
      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #0D1117; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #30363D; border-radius: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #484F58; }
      `}</style>
    </div>
  );
}
