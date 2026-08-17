/**
 * EvidenceViewer - Modal/panel to view violation evidence images.
 */
import React, { useState } from 'react';
import { getEvidenceUrl } from '../services/api';

export default function EvidenceViewer({ violation, onClose }) {
  const [activeTab, setActiveTab] = useState('full_frame');

  if (!violation) return null;

  const tabs = [
    { id: 'full_frame', label: '📸 Full Frame', icon: '🖼️' },
    { id: 'vehicle', label: '🚗 Vehicle Crop', icon: '🚗' },
    { id: 'plate', label: '🔢 Number Plate', icon: '🔢' },
  ];

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.8)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="glass-panel"
        style={{
          maxWidth: '800px',
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          padding: '24px',
          animation: 'slide-up 0.3s ease',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700 }}>Evidence Viewer</h2>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              {violation.violation_id}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '4px', marginBottom: '16px' }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === tab.id ? 'var(--accent-blue)' : 'var(--bg-secondary)',
                color: activeTab === tab.id ? 'white' : 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'var(--font-family)',
                transition: 'all 0.2s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Image */}
        <div style={{
          background: 'var(--bg-secondary)',
          borderRadius: '12px',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
          minHeight: '300px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <img
            src={getEvidenceUrl(violation.violation_id, activeTab)}
            alt={`Evidence: ${activeTab}`}
            style={{
              maxWidth: '100%',
              maxHeight: '400px',
              objectFit: 'contain',
            }}
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'flex';
            }}
          />
          <div style={{
            display: 'none',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '8px',
            padding: '40px',
            color: 'var(--text-muted)',
          }}>
            <span style={{ fontSize: '32px' }}>🖼️</span>
            <span style={{ fontSize: '13px' }}>Image not available</span>
          </div>
        </div>

        {/* Violation Details */}
        <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Vehicle Type: </span>
            <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{violation.vehicle_type || 'Unknown'}</span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Plate: </span>
            <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{violation.plate_number || 'UNKNOWN'}</span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Confidence: </span>
            <span style={{ fontWeight: 600 }}>{((violation.detection_confidence || 0) * 100).toFixed(0)}%</span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Blocking: </span>
            <span style={{ fontWeight: 600 }}>{violation.blocking_duration?.toFixed(1) || '?'}s</span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Movement: </span>
            <span style={{ fontWeight: 600 }}>{violation.movement_status || 'Unknown'}</span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Status: </span>
            <span className={`badge ${violation.status === 'VERIFIED' ? 'badge-green' : violation.status === 'NEEDS_REVIEW' ? 'badge-amber' : 'badge-blue'}`}>
              {violation.status}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
