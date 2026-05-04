import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart, ReferenceLine,
} from 'recharts';
import { SensorChartPoint, ResidualChartPoint } from '../types/domain';

interface RealTimeChartProps {
  deviceId: string | null;
  sensorPoints: SensorChartPoint[];
  residualPoints: ResidualChartPoint[];
}

const fmt = (ms: number) => new Date(ms).toLocaleTimeString('en-US', { hour12: false });

const SensorTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as SensorChartPoint;
  return (
    <div className="p-2 rounded" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
      <div style={{ fontSize: '10px', color: '#8B949E', marginBottom: '2px' }}>{fmt(d.t)}</div>
      <div style={{ fontSize: '11px', color: '#00D4FF' }}>
        Current: {d.value.toFixed(4)} A
      </div>
    </div>
  );
};

const ResidualTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as ResidualChartPoint;
  return (
    <div className="p-2 rounded" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
      <div style={{ fontSize: '10px', color: '#8B949E', marginBottom: '2px' }}>{fmt(d.t)}</div>
      <div style={{ fontSize: '11px', color: d.is_anomaly ? '#EF4444' : '#F59E0B' }}>
        Residual: {d.residual.toFixed(4)}
      </div>
      <div style={{ fontSize: '10px', color: '#8B949E' }}>
        Threshold: {d.threshold.toFixed(4)}
      </div>
    </div>
  );
};

export function RealTimeChart({ deviceId, sensorPoints, residualPoints }: RealTimeChartProps) {
  // Latest threshold value for the reference line
  const latestThreshold = residualPoints.length > 0
    ? residualPoints[residualPoints.length - 1].threshold
    : null;

  const hasData = sensorPoints.length > 0;

  return (
    <div className="h-full flex flex-col p-4" style={{ backgroundColor: '#0D1117' }}>
      {/* Title */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold tracking-tight" style={{ fontSize: '14px', color: '#C9D1D9' }}>
          Energy Consumption — Real-Time
        </h3>
        {deviceId && (
          <span
            className="px-2 py-0.5 rounded"
            style={{ fontSize: '11px', color: '#00D4FF', backgroundColor: '#00D4FF15', border: '1px solid #00D4FF30' }}
          >
            {deviceId}
          </span>
        )}
      </div>

      {/* Main sensor chart */}
      <div className="flex-1 rounded p-4 mb-4" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sensorPoints} margin={{ top: 10, right: 20, left: 0, bottom: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis
                dataKey="t"
                tickFormatter={fmt}
                stroke="#8B949E"
                style={{ fontSize: '10px' }}
                label={{ value: 'Time', position: 'insideBottom', offset: -10, style: { fill: '#8B949E', fontSize: '11px' } }}
              />
              <YAxis
                stroke="#8B949E"
                style={{ fontSize: '10px' }}
                label={{ value: 'Current [A]', angle: -90, position: 'insideLeft', style: { fill: '#8B949E', fontSize: '10px' } }}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <Tooltip content={<SensorTooltip />} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#00D4FF"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="Sensor Reading"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center">
            <p style={{ fontSize: '12px', color: '#8B949E' }}>
              {deviceId ? 'Waiting for sensor data...' : 'Select a device to view data'}
            </p>
          </div>
        )}
      </div>

      {/* Residual chart */}
      <div className="h-48 rounded p-4" style={{ backgroundColor: '#161B22', border: '1px solid #30363D' }}>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="font-medium" style={{ fontSize: '12px', color: '#C9D1D9' }}>
            Residual Signal (EWM Smoothed)
          </h4>
          {latestThreshold !== null && (
            <span style={{ fontSize: '10px', color: '#EF4444' }}>
              threshold: {latestThreshold.toFixed(4)}
            </span>
          )}
        </div>
        {residualPoints.length > 0 ? (
          <ResponsiveContainer width="100%" height="80%">
            <AreaChart data={residualPoints} margin={{ top: 4, right: 20, left: 0, bottom: 20 }}>
              <defs>
                <linearGradient id="residualGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#F59E0B" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
              <XAxis
                dataKey="t"
                tickFormatter={fmt}
                stroke="#8B949E"
                style={{ fontSize: '10px' }}
                label={{ value: 'Time', position: 'insideBottom', offset: -5, style: { fill: '#8B949E', fontSize: '11px' } }}
              />
              <YAxis stroke="#8B949E" style={{ fontSize: '10px' }} tickFormatter={(v: number) => v.toFixed(3)} />
              <Tooltip content={<ResidualTooltip />} />
              {latestThreshold !== null && (
                <ReferenceLine
                  y={latestThreshold}
                  stroke="#EF4444"
                  strokeDasharray="4 3"
                  label={{ value: 'threshold', position: 'right', fill: '#EF4444', fontSize: 9 }}
                />
              )}
              <Area
                type="monotone"
                dataKey="residual"
                stroke="#F59E0B"
                strokeWidth={1.5}
                fill="url(#residualGrad)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-4/5 flex items-center justify-center">
            <p style={{ fontSize: '11px', color: '#8B949E' }}>
              {deviceId ? 'Waiting for inference results...' : ''}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
