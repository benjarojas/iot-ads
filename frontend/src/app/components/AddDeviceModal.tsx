import { X } from 'lucide-react';
import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';

interface AddDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (device: { name: string; sensorId: string; samplingRate: string; model: string }) => void;
}

export function AddDeviceModal({ isOpen, onClose, onAdd }: AddDeviceModalProps) {
  const [formData, setFormData] = useState({
    name: '',
    sensorId: '',
    samplingRate: '2048',
    model: 'CNN-LSTM Hydra T16 CKE',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAdd(formData);
    setFormData({
      name: '',
      sensorId: '',
      samplingRate: '2048',
      model: 'CNN-LSTM Hydra T16 CKE',
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent
        className="sm:max-w-[500px] p-0 gap-0"
        style={{
          backgroundColor: '#161B22',
          border: '1px solid #30363D',
          color: '#C9D1D9',
        }}
      >
        <DialogHeader className="p-6 pb-4" style={{ borderBottom: '1px solid #30363D' }}>
          <div className="flex items-center justify-between">
            <DialogTitle style={{ fontSize: '16px', color: '#C9D1D9', fontWeight: 600 }}>
              Add New Device
            </DialogTitle>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4" style={{ color: '#8B949E' }} />
            </button>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="p-6">
          <div className="space-y-4">
            {/* Device Name */}
            <div>
              <label className="block mb-2" style={{ fontSize: '12px', color: '#8B949E' }}>
                Device Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Raspberry Pi 3B - Node 03"
                required
                className="w-full px-3 py-2 rounded outline-none focus:ring-1 transition-all"
                style={{
                  backgroundColor: '#0D1117',
                  border: '1px solid #30363D',
                  color: '#C9D1D9',
                  fontSize: '12px',
                }}
              />
            </div>

            {/* Sensor ID (MQTT Topic) */}
            <div>
              <label className="block mb-2" style={{ fontSize: '12px', color: '#8B949E' }}>
                Sensor ID (MQTT Topic)
              </label>
              <input
                type="text"
                value={formData.sensorId}
                onChange={(e) => setFormData({ ...formData, sensorId: e.target.value })}
                placeholder="e.g., iot/sensors/current/node03"
                required
                className="w-full px-3 py-2 rounded outline-none focus:ring-1 transition-all"
                style={{
                  backgroundColor: '#0D1117',
                  border: '1px solid #30363D',
                  color: '#C9D1D9',
                  fontSize: '12px',
                }}
              />
            </div>

            {/* Sampling Rate */}
            <div>
              <label className="block mb-2" style={{ fontSize: '12px', color: '#8B949E' }}>
                Sampling Rate (Hz)
              </label>
              <select
                value={formData.samplingRate}
                onChange={(e) => setFormData({ ...formData, samplingRate: e.target.value })}
                className="w-full px-3 py-2 rounded outline-none focus:ring-1 transition-all"
                style={{
                  backgroundColor: '#0D1117',
                  border: '1px solid #30363D',
                  color: '#C9D1D9',
                  fontSize: '12px',
                }}
              >
                <option value="1024">1024 Hz</option>
                <option value="2048">2048 Hz</option>
                <option value="4096">4096 Hz</option>
                <option value="8192">8192 Hz</option>
              </select>
            </div>

            {/* Model Selection */}
            <div>
              <label className="block mb-2" style={{ fontSize: '12px', color: '#8B949E' }}>
                Detection Model
              </label>
              <select
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                className="w-full px-3 py-2 rounded outline-none focus:ring-1 transition-all"
                style={{
                  backgroundColor: '#0D1117',
                  border: '1px solid #30363D',
                  color: '#C9D1D9',
                  fontSize: '12px',
                }}
              >
                <option value="CNN-LSTM Hydra T16 CKE">CNN-LSTM Hydra T16 CKE</option>
                <option value="CNN-GRU Baseline">CNN-GRU Baseline</option>
                <option value="Transformer-based ADS">Transformer-based ADS</option>
                <option value="BiLSTM Ensemble">BiLSTM Ensemble</option>
              </select>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded transition-all hover:bg-white/5"
              style={{
                border: '1px solid #30363D',
                color: '#C9D1D9',
                fontSize: '12px',
                fontWeight: 500,
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 py-2.5 rounded transition-all hover:brightness-110"
              style={{
                backgroundColor: '#00D4FF',
                color: '#0D1117',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
              }}
            >
              Add Device
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
