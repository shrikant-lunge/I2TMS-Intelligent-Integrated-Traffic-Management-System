/**
 * ViolationPanel - Displays violation cards with evidence preview and challan generation.
 */
import React, { useState } from 'react';
import { generateChallan } from '../services/api';
import EvidenceViewer from './EvidenceViewer';
import ChallanCard from './ChallanCard';

export default function ViolationPanel({ violations = [] }) {
  const [selectedViolation, setSelectedViolation] = useState(null);
  const [challans, setChallans] = useState({});
  const [generating, setGenerating] = useState({});

  const handleGenerateChallan = async (violationId) => {
    setGenerating((prev) => ({ ...prev, [violationId]: true }));
    try {
      const result = await generateChallan(violationId);
      setChallans((prev) => ({ ...prev, [violationId]: result.challan }));
    } catch (err) {
      console.error('Challan generation failed:', err);
    } finally {
      setGenerating((prev) => ({ ...prev, [violationId]: false }));
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div className="section-header">
        <span className="icon">🚨</span>
        <h2>Violations</h2>
        <span className={`badge ${violations.length > 0 ? 'badge-red' : 'badge-green'}`} style={{ marginLeft: 'auto' }}>
          {violations.length}
        </span>
      </div>

      {violations.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '30px 20px',
          color: 'var(--text-muted)',
          fontSize: '13px',
        }}>
          <div style={{ fontSize: '32px', marginBottom: '8px', opacity: 0.3 }}>🛡️</div>
          No violations detected
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '500px', overflowY: 'auto' }}>
          {violations.map((v) => (
            <div key={v.violation_id} className="card" style={{ padding: '14px' }}>
              {/* Violation Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                <div>
                  <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--accent-blue)', marginBottom: '2px' }}>
                    {v.violation_id}
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 700 }}>
                    {v.violation_type?.replace(/_/g, ' ') || 'Corridor Blocking'}
                  </div>
                </div>
                <span className={`badge ${
                  v.status === 'VERIFIED' ? 'badge-green' :
                  v.status === 'NEEDS_REVIEW' ? 'badge-amber' :
                  v.status === 'CHALLAN_GENERATED' ? 'badge-purple' :
                  'badge-blue'
                }`}>
                  {v.status}
                </span>
              </div>

              {/* Details Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '6px',
                fontSize: '12px',
                marginBottom: '10px',
              }}>
                <DetailItem label="Vehicle" value={`ID:${v.vehicle_tracking_id} · ${v.vehicle_type || 'Unknown'}`} />
                <DetailItem label="Plate" value={v.plate_number || 'UNKNOWN'} mono />
                <DetailItem label="Confidence" value={`${((v.detection_confidence || 0) * 100).toFixed(0)}%`} />
                <DetailItem label="Blocking" value={`${v.blocking_duration?.toFixed(1) || '?'}s · ${v.movement_status || '?'}`} />
                <DetailItem label="Time" value={v.timestamp ? new Date(v.timestamp).toLocaleTimeString() : 'N/A'} />
                <DetailItem label="Plate Conf" value={v.plate_confidence ? `${(v.plate_confidence * 100).toFixed(0)}%` : 'N/A'} />
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => setSelectedViolation(v)}
                >
                  🔍 View Evidence
                </button>

                {v.status !== 'CHALLAN_GENERATED' && !challans[v.violation_id] && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleGenerateChallan(v.violation_id)}
                    disabled={generating[v.violation_id]}
                  >
                    {generating[v.violation_id] ? '⏳...' : '📋 Generate Simulated Challan'}
                  </button>
                )}
              </div>

              {/* Generated Challan */}
              {challans[v.violation_id] && (
                <div style={{ marginTop: '10px' }}>
                  <ChallanCard challan={challans[v.violation_id]} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Evidence Viewer Modal */}
      {selectedViolation && (
        <EvidenceViewer
          violation={selectedViolation}
          onClose={() => setSelectedViolation(null)}
        />
      )}
    </div>
  );
}

function DetailItem({ label, value, mono }) {
  return (
    <div style={{ padding: '4px 8px', background: 'var(--bg-secondary)', borderRadius: '4px' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>{label}: </span>
      <span style={{
        fontWeight: 600,
        fontSize: '11px',
        fontFamily: mono ? 'monospace' : 'inherit',
      }}>
        {value}
      </span>
    </div>
  );
}
