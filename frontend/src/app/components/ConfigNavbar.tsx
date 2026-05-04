import { Activity, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router';

export function ConfigNavbar() {
  const navigate = useNavigate();

  return (
    <div className="h-16 border-b flex items-center justify-between px-6" style={{
      backgroundColor: '#161B22',
      borderColor: '#30363D'
    }}>
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

      {/* Center: Page Title */}
      <div className="flex items-center">
        <div className="font-semibold tracking-tight" style={{ fontSize: '16px', color: '#FFFFFF' }}>
          System Configuration
        </div>
      </div>

      {/* Right: Back Button */}
      <button
        onClick={() => navigate('/')}
        className="px-4 py-2 rounded border flex items-center gap-2 transition-colors hover:bg-white/5"
        style={{
          borderColor: '#00D4FF',
          color: '#00D4FF'
        }}
      >
        <ArrowLeft className="w-4 h-4" />
        <span style={{ fontSize: '13px' }}>Return to Dashboard</span>
      </button>
    </div>
  );
}
