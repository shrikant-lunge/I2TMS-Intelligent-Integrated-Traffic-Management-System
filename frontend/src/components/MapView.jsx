/**
 * MapView - Displays route on OpenStreetMap using Leaflet.
 */
import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Custom ambulance icon
const ambulanceIcon = L.divIcon({
  className: 'ambulance-marker',
  html: '<div style="font-size:24px;text-shadow:0 2px 8px rgba(0,0,0,0.5);">🚑</div>',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
});

const destIcon = L.divIcon({
  className: 'dest-marker',
  html: '<div style="font-size:20px;text-shadow:0 2px 8px rgba(0,0,0,0.5);">🏥</div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

// Auto-center map on ambulance
function MapUpdater({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.setView(center, map.getZoom(), { animate: true });
    }
  }, [center, map]);
  return null;
}

export default function MapView({ emergencyStatus, deviceLocation }) {
  const route = emergencyStatus?.route || [];
  const junctions = emergencyStatus?.junctions || [];
  const currentLat = Number(deviceLocation?.lat ?? emergencyStatus?.current_lat ?? 21.1458);
  const currentLon = Number(deviceLocation?.lon ?? emergencyStatus?.current_lon ?? 79.0882);
  const destLat = emergencyStatus?.dest_lat;
  const destLon = emergencyStatus?.dest_lon;
  const isActive = emergencyStatus?.status === 'ACTIVE';

  const routeLatLngs = route.map(([lon, lat]) => [lat, lon]);
  const hasFallbackRoute = routeLatLngs.length === 0 && Number.isFinite(destLat) && Number.isFinite(destLon);
  const routePositions = hasFallbackRoute ? [[currentLat, currentLon], [destLat, destLon]] : routeLatLngs;
  const center = [currentLat, currentLon];

  return (
    <div className="glass-panel" style={{ padding: '20px', height: '100%', minHeight: '620px', display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div className="section-header">
        <span className="icon">🗺️</span>
        <h2>Route Map</h2>
        {isActive && emergencyStatus?.routing_mode && (
          <span className={`badge ${emergencyStatus.routing_mode === 'OSRM' ? 'badge-green' : 'badge-amber'}`} style={{ marginLeft: 'auto' }}>
            {emergencyStatus.routing_mode}
          </span>
        )}
      </div>

      <div style={{ flex: 1, minHeight: '520px', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)' }}>
        <MapContainer
          center={center}
          zoom={14}
          style={{ height: '100%', width: '100%', minHeight: '520px' }}
          zoomControl={false}
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapUpdater center={center} />

          {/* Route polyline */}
          {routePositions.length > 1 && (
            <Polyline
              positions={routePositions}
              pathOptions={{
                color: isActive ? '#ef4444' : '#3b82f6',
                weight: 4,
                opacity: 0.8,
                dashArray: isActive ? null : '10 5',
              }}
            />
          )}

          {/* Ambulance marker */}
          <Marker position={center} icon={ambulanceIcon}>
            <Popup>
              <strong>Ambulance</strong><br />
              {emergencyStatus?.ambulance_id || 'AMB-DEFAULT-01'}<br />
              <small>{currentLat.toFixed(4)}, {currentLon.toFixed(4)}</small>
            </Popup>
          </Marker>

          {/* Destination marker */}
          {destLat && destLon && (
            <Marker position={[destLat, destLon]} icon={destIcon}>
              <Popup>
                <strong>Destination</strong><br />
                {emergencyStatus?.destination}
              </Popup>
            </Marker>
          )}

          {/* Junction markers */}
          {junctions.map((j, i) => (
            <CircleMarker
              key={i}
              center={[j.lat, j.lon]}
              radius={j.status === 'EMERGENCY_PRIORITY' ? 8 : 5}
              pathOptions={{
                color: j.status === 'EMERGENCY_PRIORITY' ? '#ef4444' : '#3b82f6',
                fillColor: j.status === 'EMERGENCY_PRIORITY' ? '#ef4444' : '#3b82f6',
                fillOpacity: 0.7,
                weight: 2,
              }}
            >
              <Popup>
                <strong>{j.name}</strong><br />
                Status: {j.status || 'NORMAL'}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
