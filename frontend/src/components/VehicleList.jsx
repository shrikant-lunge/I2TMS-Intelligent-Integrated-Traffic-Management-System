/**
 * VehicleList - Displays currently tracked vehicles.
 */
import React from 'react';

const movementColors = {
  MOVING: '#10b981',
  SLOW: '#f59e0b',
  STOPPED: '#ef4444',
  CLEARING: '#06b6d4',
};

export default function VehicleList({ vehicles = [] }) {
  if (!vehicles || vehicles.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '20px' }}>
        <div className="section-header">
          <span className="icon">🚗</span>
          <h2>Detected Vehicles</h2>
          <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>0</span>
        </div>
        <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '13px' }}>
          No vehicles detected
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div className="section-header">
        <span className="icon">🚗</span>
        <h2>Detected Vehicles</h2>
        <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>
          {vehicles.length}
        </span>
      </div>

      <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {vehicles.map((v) => (
          <div
            key={v.tracking_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '8px 12px',
              background: v.in_corridor
                ? 'rgba(239, 68, 68, 0.06)'
                : 'var(--bg-secondary)',
              borderRadius: '8px',
              border: `1px solid ${v.in_corridor ? 'rgba(239, 68, 68, 0.2)' : 'transparent'}`,
              fontSize: '12px',
            }}
          >
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              background: 'var(--bg-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '14px',
              fontWeight: 700,
              color: 'var(--accent-blue)',
              flexShrink: 0,
            }}>
              {v.tracking_id}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                {v.vehicle_type}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Conf: {(v.confidence * 100).toFixed(0)}%
                {v.blocking_time > 0 && (
                  <span style={{ color: '#f87171', marginLeft: '6px' }}>
                    ⏱ {v.blocking_time.toFixed(1)}s
                  </span>
                )}
              </div>
            </div>

            <div style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '10px',
              fontWeight: 700,
              color: movementColors[v.movement_status] || '#8892b0',
              background: `${movementColors[v.movement_status] || '#8892b0'}15`,
              border: `1px solid ${movementColors[v.movement_status] || '#8892b0'}30`,
            }}>
              {v.movement_status}
            </div>

            {v.in_corridor && (
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: '#ef4444',
                boxShadow: '0 0 6px rgba(239, 68, 68, 0.5)',
                flexShrink: 0,
              }}
              title="In Emergency Corridor"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
