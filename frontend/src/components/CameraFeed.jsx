/**
 * CameraFeed - Displays MJPEG camera feed from backend with detection overlays.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  getCameraFeedUrl,
  getAnprFeedUrl,
  scanUploadedVideoWithAnpr,
  stopCamera,
  uploadVideo,
} from '../services/api';

export default function CameraFeed({ cameraStatus, vehicleCount }) {
  const [imgError, setImgError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [scanStatus, setScanStatus] = useState('');
  const [scanError, setScanError] = useState('');
  const [plates, setPlates] = useState([]);
  const [anprVideo, setAnprVideo] = useState('');
  const [localPreview, setLocalPreview] = useState('');
  const [anprPlaybackError, setAnprPlaybackError] = useState(false);
  const [anprStreamLoaded, setAnprStreamLoaded] = useState(false);
  const inputRef = useRef(null);
  const isRunning = Boolean(
    cameraStatus?.running || cameraStatus?.camera_status === 'RUNNING' || cameraStatus?.status === 'RUNNING'
  );
  const cameraMode = cameraStatus?.camera_mode || cameraStatus?.mode || 'UNKNOWN';

  useEffect(() => () => {
    if (localPreview) URL.revokeObjectURL(localPreview);
  }, [localPreview]);

  const handleVideoSelected = async (event) => {
    const video = event.target.files?.[0];
    if (!video) return;

    setUploading(true);
    setScanError('');
    setScanStatus(`Uploading ${video.name}...`);
    setPlates([]);
    setAnprVideo('');
    setAnprPlaybackError(false);
    setAnprStreamLoaded(false);
    setLocalPreview(URL.createObjectURL(video));

    try {
      await stopCamera().catch(() => {});
      const uploaded = await uploadVideo(video);
      setScanStatus('Running the supplied ANPR model, SORT tracker, and OCR...');
      const result = await scanUploadedVideoWithAnpr(uploaded.filename);
      setPlates(result.plates || []);
      setAnprVideo(getAnprFeedUrl(result.video_filename));
      setScanStatus(`${result.message || 'ANPR scan completed.'} Loading annotated video...`);
    } catch (error) {
      setScanError(error.response?.data?.detail || error.message || 'Video processing failed');
      setScanStatus('');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', height: '100%' }}>
      <div className="section-header">
        <span className="icon">📹</span>
        <h2>Camera Feed</h2>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          {isRunning && (
            <span className={`badge ${cameraMode === 'LIVE CAMERA' || cameraMode === 'LIVE_CAMERA' ? 'badge-green' : 'badge-blue'}`}>
              {cameraMode}
            </span>
          )}
          <span className={`badge ${isRunning ? 'badge-green' : 'badge-red'}`}>
            {isRunning ? '● LIVE' : '○ OFFLINE'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
        <input ref={inputRef} type="file" accept="video/mp4,video/x-msvideo,video/x-matroska,video/quicktime,video/webm,.mp4,.avi,.mkv,.mov,.webm" onChange={handleVideoSelected} style={{ display: 'none' }} />
        <button type="button" className="btn btn-primary" disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? 'PROCESSING VIDEO…' : 'UPLOAD VIDEO & SCAN PLATES'}
        </button>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>MP4, AVI, MKV, MOV, or WEBM</span>
      </div>

      {(scanStatus || scanError) && (
        <div style={{ marginBottom: '12px', fontSize: '13px', color: scanError ? '#ff6b6b' : 'var(--text-secondary)' }}>
          {scanError || scanStatus}
        </div>
      )}

      <div
        style={{
          position: 'relative',
          width: '100%',
          paddingTop: '56.25%', /* 16:9 aspect ratio */
          background: 'var(--bg-secondary)',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
          border: '1px solid var(--border-color)',
        }}
      >
        {anprVideo ? (
          <img
            key={anprVideo}
            src={anprVideo}
            alt="Annotated ANPR video with vehicle and number plate boxes"
            onLoad={() => {
              setAnprStreamLoaded(true);
              setLocalPreview('');
              setScanStatus('Showing the complete ANPR-annotated video.');
            }}
            onError={() => setAnprPlaybackError(true)}
            style={{
              position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
              objectFit: 'contain', opacity: anprStreamLoaded ? 1 : 0,
            }}
          />
        ) : localPreview ? (
          <video
            src={localPreview}
            controls
            autoPlay
            muted
            loop
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
          />
        ) : isRunning && !imgError ? (
          <img
            src={getCameraFeedUrl()}
            alt="Camera feed with vehicle detection overlays"
            onError={() => setImgError(true)}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              objectFit: 'contain',
            }}
          />
        ) : (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
            }}
          >
            <div style={{ fontSize: '48px', opacity: 0.3 }}>📷</div>
            <div style={{ fontSize: '14px', color: 'var(--text-muted)', textAlign: 'center' }}>
              {imgError ? 'Camera feed disconnected' : 'Camera not started'}
              <br />
              <span style={{ fontSize: '12px' }}>
                Start an emergency or click "Start Camera Only"
              </span>
            </div>
          </div>
        )}

        {/* Vehicle count overlay */}
        {isRunning && (
          <div
            style={{
              position: 'absolute',
              bottom: '8px',
              right: '8px',
              padding: '4px 10px',
              background: 'rgba(0, 0, 0, 0.7)',
              borderRadius: '6px',
              fontSize: '11px',
              color: 'var(--text-primary)',
              backdropFilter: 'blur(4px)',
            }}
          >
            🚗 {vehicleCount || 0} vehicles
          </div>
        )}
      </div>

      {anprVideo && !anprPlaybackError && (
        <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
          {anprStreamLoaded
            ? 'Showing the complete ANPR-annotated recording (vehicle boxes and plate labels included).'
            : 'Preparing annotated ANPR video playback...'}
        </div>
      )}
      {anprPlaybackError && (
        <div style={{ marginTop: '10px', fontSize: '12px', color: '#ff6b6b' }}>
          The annotated playback stream could not load. Upload the video again after restarting the backend.
        </div>
      )}

      {plates.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px' }}>Recognized number plates ({plates.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {plates.map((plate) => (
              <span key={plate.plate_number} className="badge badge-blue">
                {plate.plate_number} {plate.plate_confidence ? `(${Math.round(plate.plate_confidence * 100)}%)` : ''}
              </span>
            ))}
          </div>
        </div>
      )}
      {!uploading && anprStreamLoaded && plates.length === 0 && (
        <div style={{ marginTop: '14px', fontSize: '13px', color: 'var(--text-muted)' }}>
          The ANPR model completed the video, but no plate text met the supplied project's strict Indian registration format.
        </div>
      )}
    </div>
  );
}
