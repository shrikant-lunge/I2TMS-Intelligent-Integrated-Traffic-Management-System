/**
 * App - Root application component.
 * Manages polling and state, renders Dashboard.
 */
import React, { useState, useCallback, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import { usePolling } from './hooks/usePolling';
import {
  getEmergencyStatus,
  getVehicles,
  getLiveViolations,
  getHealth,
  updateEmergencyLocation,
  getCameraStatus,
} from './services/api';
import './App.css';

function App() {
  const [connected, setConnected] = useState(false);
  const [emergencyData, setEmergencyData] = useState(null);
  const [vehicleData, setVehicleData] = useState([]);
  const [violationData, setViolationData] = useState([]);
  const [deviceLocation, setDeviceLocation] = useState(null);
  const [cameraData, setCameraData] = useState(null);

  // Polling functions
  const fetchStatus = useCallback(() => getEmergencyStatus(), []);
  const fetchVehicles = useCallback(() => getVehicles(), []);
  const fetchViolations = useCallback(() => getLiveViolations(), []);
  const fetchHealth = useCallback(() => getHealth(), []);
  const fetchCameraStatus = useCallback(() => getCameraStatus(), []);

  const syncLocationToBackend = useCallback(async (lat, lon) => {
    try {
      await updateEmergencyLocation(lat, lon);
    } catch (error) {
      console.warn('Location sync failed:', error);
    }
  }, []);

  // Poll emergency status every 1.5s
  const { data: statusData } = usePolling(fetchStatus, 1500, connected);
  // Poll vehicles every 1s
  const { data: vData } = usePolling(fetchVehicles, 1000, connected);
  // Poll violations every 2s
  const { data: vioData } = usePolling(fetchViolations, 2000, connected);
  // Health check every 5s
  const { data: healthData, error: healthError } = usePolling(fetchHealth, 5000, true);
  // Camera status every 1s
  const { data: cameraStatusData } = usePolling(fetchCameraStatus, 1000, connected);

  // Update connection status
  useEffect(() => {
    if (healthData) {
      setConnected(true);
    }
    if (healthError) {
      setConnected(false);
    }
  }, [healthData, healthError]);

  useEffect(() => {
    if (!navigator?.geolocation) return;

    const watchId = navigator.geolocation.watchPosition(
      ({ coords }) => {
        const nextLocation = {
          lat: coords.latitude,
          lon: coords.longitude,
        };
        setDeviceLocation(nextLocation);

        if (emergencyData?.status === 'ACTIVE') {
          syncLocationToBackend(nextLocation.lat, nextLocation.lon);
        }
      },
      () => {
        setDeviceLocation(null);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [emergencyData?.status, syncLocationToBackend]);

  // Update state from polling
  useEffect(() => {
    if (statusData) setEmergencyData(statusData);
  }, [statusData]);

  useEffect(() => {
    if (vData?.vehicles) setVehicleData(vData.vehicles);
  }, [vData]);

  useEffect(() => {
    if (cameraStatusData) setCameraData(cameraStatusData);
  }, [cameraStatusData]);

  useEffect(() => {
    if (vioData?.violations) setViolationData(vioData.violations);
  }, [vioData]);

  const handleEmergencyUpdate = () => {
    // Force re-fetch
    setTimeout(() => {
      fetchStatus().then(setEmergencyData).catch(() => {});
      fetchViolations().then((d) => d?.violations && setViolationData(d.violations)).catch(() => {});
    }, 500);
  };

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="app-header">
        <div className="header-left">
          <div className="header-logo">🚑</div>
          <div>
            <h1 className="header-title">Smart Ambulance Emergency Corridor</h1>
            <p className="header-subtitle">Vehicle Violation Detection & Enforcement System</p>
          </div>
        </div>
        <div className="header-right">
          <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
            <div className="connection-dot" />
            {connected ? 'Connected' : 'Connecting...'}
          </div>
          <div className="header-info">
            <span className="badge badge-purple">PROTOTYPE</span>
          </div>
        </div>
      </header>

      {/* Dashboard */}
      {connected ? (
        <Dashboard
          emergencyStatus={emergencyData}
          cameraStatus={cameraData}
          vehicles={vehicleData}
          violations={violationData}
          deviceLocation={deviceLocation}
          onEmergencyUpdate={handleEmergencyUpdate}
        />
      ) : (
        <div className="connecting-screen">
          <div className="connecting-spinner" />
          <h2>Connecting to Backend Server</h2>
          <p>Make sure the backend is running at <code>http://localhost:8000</code></p>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px' }}>
            PowerShell: <code>cd backend; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000</code>
          </p>
        </div>
      )}
    </div>
  );
}

export default App;
