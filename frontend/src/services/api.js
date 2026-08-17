/**
 * API Service - Centralized API client for backend communication.
 */
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' },
});

// ---- Emergency ----
export const startEmergency = (data) =>
  api.post('/emergency/start', data).then(r => r.data);

export const stopEmergency = () =>
  api.post('/emergency/stop').then(r => r.data);

export const updateEmergencyLocation = (lat, lon) =>
  api.post('/emergency/location', { latitude: lat, longitude: lon }).then(r => r.data);

export const getEmergencyStatus = () =>
  api.get('/emergency/status').then(r => r.data);

// ---- Camera ----
export const startCamera = (source, mode = 'LIVE_CAMERA') =>
  api.post('/camera/start', null, { params: { source, mode } }).then(r => r.data);

export const stopCamera = () =>
  api.post('/camera/stop').then(r => r.data);

export const getCameraStatus = () =>
  api.get('/camera/status').then(r => r.data);

export const getVehicles = () =>
  api.get('/camera/vehicles').then(r => r.data);

export const scanPlates = ({ source, mode = 'LIVE_CAMERA' }) =>
  api.post('/camera/scan', null, { params: { source, mode } }).then(r => r.data);

export const uploadVideo = (video) => {
  const formData = new FormData();
  formData.append('video', video);
  return api.post('/camera/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  }).then(r => r.data);
};

export const scanUploadedVideoWithAnpr = (source) =>
  api.post('/camera/anpr/scan', null, { params: { source }, timeout: 600000 }).then(r => r.data);

export const getAnprVideoUrl = (filename) =>
  `${API_BASE}/camera/anpr-video/${encodeURIComponent(filename)}`;

export const getAnprFeedUrl = (filename) =>
  `${API_BASE}/camera/anpr-feed/${encodeURIComponent(filename)}`;

export const getStoredPlates = () =>
  api.get('/camera/plates').then(r => r.data);

// Camera feed URL (MJPEG stream)
export const getCameraFeedUrl = () => `${API_BASE}/camera/feed`;

// ---- Routes ----
export const calculateRoute = (data) =>
  api.post('/routes/calculate', data).then(r => r.data);

export const getCurrentRoute = () =>
  api.get('/routes/current').then(r => r.data);

// ---- Violations ----
export const getViolations = (eventId) => {
  const params = eventId ? { emergency_event_id: eventId } : {};
  return api.get('/violations', { params }).then(r => r.data);
};

export const getLiveViolations = () =>
  api.get('/violations/live').then(r => r.data);

export const getViolation = (id) =>
  api.get(`/violations/${id}`).then(r => r.data);

// ---- Challans ----
export const generateChallan = (violationId) =>
  api.post('/challans/generate', { violation_id: violationId }).then(r => r.data);

export const getChallans = () =>
  api.get('/challans').then(r => r.data);

export const getChallan = (id) =>
  api.get(`/challans/${id}`).then(r => r.data);

// ---- Health ----
export const getHealth = () =>
  api.get('/health').then(r => r.data);

export const getInfo = () =>
  api.get('/info').then(r => r.data);

// ---- Evidence image URLs ----
export const getEvidenceUrl = (violationId, type) =>
  `${API_BASE}/evidence/${violationId}/${type}.jpg`;

export default api;
