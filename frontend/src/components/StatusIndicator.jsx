/**
 * StatusIndicator - Shows emergency active/normal status with animation.
 */
import React from 'react';

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 20px',
    borderRadius: '12px',
    transition: 'all 0.3s ease',
  },
  dot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  label: {
    fontSize: '13px',
    fontWeight: 700,
    letterSpacing: '1px',
    textTransform: 'uppercase',
  },
  eventId: {
    fontSize: '11px',
    opacity: 0.7,
    marginTop: '2px',
    fontFamily: 'monospace',
  },
};

export default function StatusIndicator({ status, eventId }) {
  const isActive = status === 'ACTIVE';

  return (
    <div
      style={{
        ...styles.container,
        background: isActive
          ? 'rgba(239, 68, 68, 0.12)'
          : 'rgba(16, 185, 129, 0.12)',
        border: `1px solid ${isActive ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
      }}
    >
      <div
        style={{
          ...styles.dot,
          background: isActive ? '#ef4444' : '#10b981',
          boxShadow: isActive
            ? '0 0 8px rgba(239, 68, 68, 0.6)'
            : '0 0 8px rgba(16, 185, 129, 0.6)',
          animation: isActive ? 'pulse-emergency 1.5s infinite' : 'none',
        }}
      />
      <div>
        <div
          style={{
            ...styles.label,
            color: isActive ? '#f87171' : '#34d399',
          }}
        >
          {isActive ? '🔴 EMERGENCY ACTIVE' : '🟢 NORMAL'}
        </div>
        {eventId && (
          <div style={styles.eventId}>{eventId}</div>
        )}
      </div>
    </div>
  );
}
