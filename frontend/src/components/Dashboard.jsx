/**
 * Dashboard - Main dashboard layout composing all panels.
 */
import React from 'react';
import EmergencyControl from './EmergencyControl';
import CameraFeed from './CameraFeed';
import MapView from './MapView';
import VehicleList from './VehicleList';
import ViolationPanel from './ViolationPanel';

export default function Dashboard({
  emergencyStatus,
  cameraStatus,
  vehicles,
  violations,
  deviceLocation,
  onEmergencyUpdate,
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '340px minmax(0, 1.2fr) 380px',
      gridTemplateRows: 'auto minmax(540px, 1.2fr) auto',
      gap: '16px',
      minHeight: 'calc(100vh - 72px)',
      padding: '16px',
      overflow: 'visible',
      alignItems: 'start',
    }}>
      {/* Left Column: Emergency Control + Vehicles */}
      <div style={{
        gridRow: '1 / 4',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        overflowY: 'auto',
      }}>
        <EmergencyControl
          emergencyStatus={emergencyStatus}
          onUpdate={onEmergencyUpdate}
        />
        <VehicleList vehicles={vehicles} />
      </div>

      {/* Center: Camera Feed */}
      <div style={{ gridColumn: '2', gridRow: '1 / 2' }}>
        <CameraFeed
          cameraStatus={cameraStatus || emergencyStatus}
          vehicleCount={vehicles?.length || 0}
        />
      </div>

      {/* Center: Map */}
      <div style={{ gridColumn: '2', gridRow: '2 / 4', minHeight: '620px', display: 'flex', alignSelf: 'stretch' }}>
        <MapView emergencyStatus={emergencyStatus} deviceLocation={deviceLocation} />
      </div>

      {/* Right Column: Violations */}
      <div style={{
        gridColumn: '3',
        gridRow: '1 / 4',
        overflowY: 'auto',
      }}>
        <ViolationPanel violations={violations} />
      </div>
    </div>
  );
}
