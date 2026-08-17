/**
 * EmergencyControl - Start/stop emergency with destination input.
 */
import React, { useState, useEffect } from 'react';
import { startEmergency, stopEmergency, startCamera, scanPlates, getStoredPlates } from '../services/api';
import StatusIndicator from './StatusIndicator';

const DEFAULT_CURRENT_LOCATION = { lat: 21.1458, lon: 79.0882, label: 'Nagpur Medical College' };

export default function EmergencyControl({ emergencyStatus, onUpdate }) {
  const [destination, setDestination] = useState('AIIMS Nagpur');
  const [currentLocation, setCurrentLocation] = useState(DEFAULT_CURRENT_LOCATION);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cameraMode, setCameraMode] = useState('LIVE_CAMERA');
  const [videoPath, setVideoPath] = useState('');
  const [scanMessage, setScanMessage] = useState('');
  const [plateRecords, setPlateRecords] = useState([]);

  const isActive = emergencyStatus?.status === 'ACTIVE';

  useEffect(() => {
    if (!navigator?.geolocation) return;

    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setCurrentLocation({
          lat: coords.latitude,
          lon: coords.longitude,
          label: 'Current Location',
        });
      },
      () => {
        setCurrentLocation(DEFAULT_CURRENT_LOCATION);
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
    );
  }, []);

  const handleStart = async () => {
    if (!destination.trim()) {
      setError('Please enter a destination');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await startEmergency({
        destination: destination.trim(),
        current_lat: currentLocation?.lat ?? DEFAULT_CURRENT_LOCATION.lat,
        current_lon: currentLocation?.lon ?? DEFAULT_CURRENT_LOCATION.lon,
        ambulance_id: 'AMB-DEFAULT-01',
      });
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to start emergency');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await stopEmergency();
      if (onUpdate) onUpdate(result);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to stop emergency');
    } finally {
      setLoading(false);
    }
  };

  const handleStartCamera = async () => {
    try {
      setError('');
      setScanMessage('');
      const source = cameraMode === 'VIDEO_FILE' ? videoPath : '0';
      await startCamera(source || undefined, cameraMode);
      if (cameraMode === 'VIDEO_FILE') {
        setScanMessage(`Video mode started with source: ${source || 'auto-detected video'}`);
      }
    } catch (err) {
      console.error('Camera start failed:', err);
      setError(err?.response?.data?.detail || 'Camera start failed');
    }
  };

  const handleScanPlates = async () => {
    try {
      setError('');
      const source = cameraMode === 'VIDEO_FILE' ? videoPath : '0';
      const result = await scanPlates({ source: source || undefined, mode: cameraMode });
      setScanMessage(result?.message || 'Plate scanning completed');

      const platesData = await getStoredPlates();
      setPlateRecords(platesData?.plates || []);
    } catch (err) {
      console.error('Plate scan failed:', err);
      setError(err?.response?.data?.detail || 'Plate scanning failed');
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div className="section-header">
        <span className="icon">🚑</span>
        <h2>Emergency Control</h2>
      </div>

      <StatusIndicator
        status={emergencyStatus?.status || 'INACTIVE'}
        eventId={emergencyStatus?.emergency_event_id}
      />

      <div style={{ marginTop: '16px' }}>
        <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
          SOURCE: CURRENT LOCATION
        </label>
        <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '8px', fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
          📍 {currentLocation?.label || 'Current location'}
          <span style={{ fontSize: '11px', opacity: 0.6, marginLeft: '8px' }}>
            ({Number(currentLocation?.lat ?? DEFAULT_CURRENT_LOCATION.lat).toFixed(4)}, {Number(currentLocation?.lon ?? DEFAULT_CURRENT_LOCATION.lon).toFixed(4)})
          </span>
        </div>

        <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
          DESTINATION
        </label>
        <input
          className="input"
          type="text"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="Enter any destination (e.g., AIIMS Nagpur, Airport, 21.1260, 79.0467)"
          disabled={isActive || loading}
          style={{ marginBottom: '12px' }}
        />

        {emergencyStatus?.routing_mode && (
          <div style={{ marginBottom: '12px' }}>
            <span className={`badge ${emergencyStatus.routing_mode === 'OSRM' ? 'badge-green' : 'badge-amber'}`}>
              ROUTING MODE: {emergencyStatus.routing_mode}
            </span>
          </div>
        )}

        {emergencyStatus?.camera_mode && (
          <div style={{ marginBottom: '12px' }}>
            <span className={`badge ${emergencyStatus.camera_mode === 'LIVE CAMERA' ? 'badge-green' : 'badge-blue'}`}>
              📹 {emergencyStatus.camera_mode}
            </span>
          </div>
        )}

        {error && (
          <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', fontSize: '12px', color: '#f87171', marginBottom: '12px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            ⚠️ {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {!isActive ? (
            <button
              className="btn btn-success"
              onClick={handleStart}
              disabled={loading}
              style={{ flex: 1 }}
            >
              {loading ? '⏳ Starting...' : '🚨 START EMERGENCY ROUTE'}
            </button>
          ) : (
            <button
              className="btn btn-emergency"
              onClick={handleStop}
              disabled={loading}
              style={{ flex: 1 }}
            >
              {loading ? '⏳ Stopping...' : '⏹ END EMERGENCY'}
            </button>
          )}
        </div>

        {!isActive && (
          <div style={{ marginTop: '12px', padding: '12px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: 700 }}>📹 CAMERA MODE</div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
              <button
                className={`btn ${cameraMode === 'LIVE_CAMERA' ? 'btn-success' : 'btn-outline'}`}
                onClick={() => setCameraMode('LIVE_CAMERA')}
                style={{ flex: 1 }}
              >
                Live Camera
              </button>
              <button
                className={`btn ${cameraMode === 'VIDEO_FILE' ? 'btn-success' : 'btn-outline'}`}
                onClick={() => setCameraMode('VIDEO_FILE')}
                style={{ flex: 1 }}
              >
                Recorded Video
              </button>
            </div>

            {cameraMode === 'VIDEO_FILE' && (
              <input
                className="input"
                type="text"
                value={videoPath}
                onChange={(e) => setVideoPath(e.target.value)}
                placeholder="Enter full video path (e.g. D:\\Project\\TMS\\data\\videos\\demo.mp4)"
                style={{ marginBottom: '10px' }}
              />
            )}

            <button
              className="btn btn-outline"
              onClick={handleStartCamera}
              style={{ width: '100%', marginBottom: '8px' }}
            >
              📷 Start Camera
            </button>

            <button
              className="btn btn-success"
              onClick={handleScanPlates}
              style={{ width: '100%' }}
            >
              🔍 Scan Number Plates
            </button>
          </div>
        )}

        {(scanMessage || plateRecords.length > 0) && (
          <div style={{ marginTop: '12px', padding: '10px 12px', background: 'rgba(14,165,233,0.08)', borderRadius: '8px', border: '1px solid rgba(14,165,233,0.2)', fontSize: '12px', color: 'var(--text-primary)' }}>
            {scanMessage && <div style={{ marginBottom: '8px' }}>{scanMessage}</div>}
            {plateRecords.length > 0 && (
              <div>
                <div style={{ fontWeight: 700, marginBottom: '6px' }}>Detected plates:</div>
                <ul style={{ margin: 0, paddingLeft: '16px', display: 'grid', gap: '4px' }}>
                  {plateRecords.slice(0, 6).map((plate) => (
                    <li key={plate.id}>{plate.plate_number}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Emergency Info */}
      {isActive && emergencyStatus && (
        <div style={{ marginTop: '16px', padding: '12px', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>EMERGENCY DETAILS</div>
          <div style={{ display: 'grid', gap: '4px', fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Ambulance</span>
              <span>{emergencyStatus.ambulance_id}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Destination</span>
              <span>{emergencyStatus.destination}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Vehicles Detected</span>
              <span>{emergencyStatus.vehicles_detected || 0}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Violations</span>
              <span style={{ color: emergencyStatus.violations_count > 0 ? '#f87171' : 'inherit' }}>
                {emergencyStatus.violations_count || 0}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Next Junction */}
      {isActive && emergencyStatus?.next_junction && (
        <div style={{ marginTop: '8px', padding: '12px', background: 'rgba(245, 158, 11, 0.08)', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
          <div style={{ fontSize: '11px', color: 'var(--accent-amber)', fontWeight: 700, marginBottom: '4px' }}>
            🚦 NEXT JUNCTION
          </div>
          <div style={{ fontSize: '13px', fontWeight: 600 }}>
            {emergencyStatus.next_junction.name}
          </div>
          {emergencyStatus.next_junction.distance_km !== undefined && (
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {emergencyStatus.next_junction.distance_km?.toFixed(2)} km away
              {' · '}
              <span className={`badge badge-${emergencyStatus.next_junction.status === 'EMERGENCY_PRIORITY' ? 'red' : 'green'}`}>
                {emergencyStatus.next_junction.status}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
