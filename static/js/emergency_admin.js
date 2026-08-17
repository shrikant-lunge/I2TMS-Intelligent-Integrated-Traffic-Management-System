/**
 * emergency_admin.js
 * Admin / NMC Control Room — Emergency Green Corridor monitoring screen
 *
 * Responsibilities:
 *   - Load destinations into select
 *   - POST /api/emergency/route  (with ~2s demo delay), draw route preview map
 *   - POST /api/emergency/start  → switch to monitor panel
 *   - Poll /api/emergency/status every 1 second
 *   - Update: ambulance marker, junction markers, VMS markers, signal indicator,
 *             live stats, junction list, VMS board, progress bar
 *   - ANPR: start video playback on trigger, emit log entries progressively
 *     in sync with video currentTime from anpr_detections.json
 *   - Pause / Resume / Reset controls
 *   - Completion: show ETA comparison card
 */
(function () {
  'use strict';

  /* ── DOM refs — setup panel ──────────────────────────────────── */
  const destSelect     = document.getElementById('ec-dest-select');
  const btnCalculate   = document.getElementById('ec-btn-calculate');
  const routeReadyAct  = document.getElementById('ec-route-ready-actions');
  const routeSummary   = document.getElementById('ec-route-summary');
  const btnStart       = document.getElementById('ec-btn-start');
  const routingBadge   = document.getElementById('ec-routing-mode-badge');

  /* ── DOM refs — monitor panel ────────────────────────────────── */
  const setupPanel     = document.getElementById('ec-setup-panel');
  const monitorPanel   = document.getElementById('ec-monitor-panel');

  const corridorPill   = document.getElementById('ec-corridor-pill');
  const pillText       = document.getElementById('ec-pill-text');
  const mapPill        = document.getElementById('ec-map-pill');

  const btnPause       = document.getElementById('ec-btn-pause');
  const btnReset       = document.getElementById('ec-btn-reset');

  const progressBar    = document.getElementById('ec-progress-bar');
  const progressLabel  = document.getElementById('ec-progress-label');
  const destLabelBar   = document.getElementById('ec-dest-label-bar');

  const liveSpeed      = document.getElementById('ec-live-speed');
  const liveEta        = document.getElementById('ec-live-eta');
  const liveDist       = document.getElementById('ec-live-dist');
  const livePct        = document.getElementById('ec-live-pct');

  const signalIndicator= document.getElementById('ec-signal-indicator');
  const signalText     = document.getElementById('ec-signal-text');
  const currentJunc    = document.getElementById('ec-current-junc');
  const nextJunc       = document.getElementById('ec-next-junc');
  const nextJuncDist   = document.getElementById('ec-next-junc-dist');

  const vmsLabel       = document.getElementById('ec-vms-label');
  const vmsText        = document.getElementById('ec-vms-text');

  const junctionList   = document.getElementById('ec-junction-list');

  /* ANPR */
  const anprWaiting    = document.getElementById('ec-anpr-waiting');
  const anprVideoWrap  = document.getElementById('ec-anpr-video-wrap');
  const anprVideo      = document.getElementById('ec-anpr-video');
  const anprPill       = document.getElementById('ec-anpr-pill');
  const anprHistory    = document.getElementById('ec-anpr-history');
  const anprEmpty      = document.getElementById('ec-anpr-empty');
  const anprCountPill  = document.getElementById('ec-anpr-count-pill');

  /* ETA card */
  const etaCard        = document.getElementById('ec-eta-card');
  const completionBanner = document.getElementById('ec-completion-banner');
  const etaBaseline    = document.getElementById('ec-eta-baseline');
  const etaOptimized   = document.getElementById('ec-eta-optimized');
  const etaSaved       = document.getElementById('ec-eta-saved');
  const statJunctions  = document.getElementById('ec-stat-junctions');
  const statVms        = document.getElementById('ec-stat-vms');
  const statAnpr       = document.getElementById('ec-stat-anpr');

  /* ── State ───────────────────────────────────────────────────── */
  let currentRouteId   = null;
  let corridorId       = null;
  let pollInterval     = null;
  let paused           = false;
  let anprDetections   = [];     // pre-loaded from /api/emergency/anpr-detections
  let anprEmitted      = new Set();
  let anprStarted      = false;
  let anprLogCount     = 0;

  /* ── Leaflet maps ────────────────────────────────────────────── */
  const VNIT = [21.123028, 79.051449];
  const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  const OSM_ATTR  = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  // Setup / preview map
  let setupMap         = null;
  let setupPolyline    = null;
  let setupDestMarker  = null;

  // Monitor map
  let monMap           = null;
  let monPolyline      = null;
  let monAmbMarker     = null;
  let monDestMarker    = null;
  let monJuncMarkers   = {};
  let monVmsMarkers    = {};

  function initSetupMap() {
    if (setupMap) return;
    setupMap = L.map('ec-admin-map').setView(VNIT, 12);
    L.tileLayer(OSM_TILES, { attribution: OSM_ATTR }).addTo(setupMap);
    // Source marker
    L.marker(VNIT)
      .bindTooltip('📍 VNIT Nagpur (Source)', { permanent: true, direction: 'right', offset: [12, 0] })
      .addTo(setupMap);
  }

  function initMonitorMap() {
    if (monMap) return;
    monMap = L.map('ec-admin-map-monitor').setView(VNIT, 12);
    L.tileLayer(OSM_TILES, { attribution: OSM_ATTR }).addTo(monMap);

    monAmbMarker = L.marker(VNIT, {
      icon: L.divIcon({ html: '<div class="lf-amb-icon">🚑</div>', className: '', iconSize: [36, 36], iconAnchor: [18, 18] }),
      zIndexOffset: 1000,
    }).addTo(monMap);
  }

  /* ── Icon factories ──────────────────────────────────────────── */
  function junctionIcon(status, approach) {
    const isActive = status === 'active';
    const isPassed = status === 'passed';
    const postColor = isPassed ? '#4ade80' : isActive ? '#22c55e' : '#6b7280';
    const glow      = isActive ? 'filter:drop-shadow(0 0 6px #22c55e);' : '';
    const redLit    = isActive ? '#ff4444' : '#1a1a1a';
    const greenLit  = isActive ? '#22ff66' : '#1a1a1a';
    const label     = approach ? approach.toUpperCase()[0] : '';

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="42" viewBox="0 0 28 48"
      style="${glow}">
      <rect x="12" y="32" width="4" height="16" rx="1" fill="${postColor}"/>
      <rect x="4" y="2" width="20" height="30" rx="4" fill="#1c2333" stroke="${postColor}" stroke-width="1.5"/>
      <circle cx="14" cy="8"  r="4.5" fill="${redLit}"/>
      <circle cx="14" cy="17" r="4.5" fill="#1a1a1a"/>
      <circle cx="14" cy="26" r="4.5" fill="${greenLit}"/>
      ${isActive ? `<text x="14" y="46" font-size="5" fill="#22ff66" text-anchor="middle" font-family="monospace">${label}→GRN</text>` : ''}
    </svg>`;
    const size = isActive ? [28, 50] : [22, 40];
    return L.divIcon({ html: svg, className: '', iconSize: size, iconAnchor: [size[0]/2, size[1]] });
  }

  function vmsIcon(message, status) {
    const isEmergency = status === 'emergency_warning';
    const isPassed    = status === 'passed';
    const borderColor = isEmergency ? '#ff9500' : isPassed ? '#334155' : '#2a4a7f';
    const textColor   = isEmergency ? '#ff9500' : isPassed ? '#4b5563' : '#66bb6a';
    const glowStyle   = isEmergency ? 'filter:drop-shadow(0 0 5px rgba(255,149,0,0.7));' : '';
    const lines = (message || '').replace(/\n/g, '<br>');
    const html = `<div style="background:#0a1628;border:2px solid ${borderColor};border-radius:5px;
      padding:4px 6px;font-family:'Courier New',monospace;font-size:0.5rem;font-weight:700;
      line-height:1.4;color:${textColor};white-space:nowrap;min-width:80px;
      box-shadow:0 2px 8px rgba(0,0,0,0.5);${glowStyle}">
      <div style="font-size:0.38rem;color:${borderColor};letter-spacing:0.1em;margin-bottom:1px;">▲ VMS</div>
      <div>${lines}</div>
    </div>`;
    return L.divIcon({ html, className: '', iconSize: [88, 48], iconAnchor: [44, 48] });
  }

  function destIcon(name) {
    return L.divIcon({
      html: `<div style="background:#EF4444;color:#fff;border:2px solid #fff;border-radius:6px;padding:4px 8px;font-size:0.65rem;font-weight:700;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,0.4);">🏥 ${name}</div>`,
      className: '', iconAnchor: [0, 0],
    });
  }

  /* ── Helper: show / hide ─────────────────────────────────────── */
  function show(el) { el && el.classList.remove('ec-hidden'); }
  function hide(el) { el && el.classList.add('ec-hidden'); }

  /* ── Load destinations ───────────────────────────────────────── */
  async function loadDestinations() {
    try {
      const res = await fetch('/api/emergency/destinations');
      const json = await res.json();
      if (json.status !== 'success') return;
      json.destinations.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = d.name;
        destSelect.appendChild(opt);
      });
      btnCalculate.disabled = false;
    } catch (e) {
      console.error('loadDestinations:', e);
    }
  }

  /* ── Pre-load ANPR detections ─────────────────────────────────── */
  async function loadAnprDetections() {
    try {
      const res = await fetch('/api/emergency/anpr-detections');
      const json = await res.json();
      if (json.status === 'success') {
        anprDetections = json.data.detections || [];
      }
    } catch (e) {
      console.warn('Could not pre-load ANPR detections:', e);
    }
  }

  /* ── Calculate route ─────────────────────────────────────────── */
  async function calculateRoute() {
    const destId = destSelect.value;
    if (!destId) { alert('Please select a hospital destination.'); return; }

    btnCalculate.disabled = true;
    btnCalculate.innerHTML = '<span style="display:inline-block;animation:spin 1s linear infinite">⟳</span> Calculating…';
    hide(routeReadyAct);

    // ~2s demo delay
    await sleep(2000);

    try {
      const res = await fetch('/api/emergency/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destination_id: destId }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.message);

      const data = json.data;
      currentRouteId = data.route_id;

      // Show routing mode badge
      if (routingBadge) {
        routingBadge.textContent = data.routing_mode || 'OSRM';
        routingBadge.style.display = '';
        routingBadge.className = 'ec-pill ec-pill-ready';
      }

      // Draw preview map
      initSetupMap();
      drawSetupMap(data);

      // Summary line
      routeSummary.innerHTML =
        `<strong>${data.source.name}</strong> → <strong>${data.destination.name}</strong><br>
         ${data.distance_km.toFixed(1)} km &nbsp;·&nbsp;
         Baseline: <strong>${data.baseline_duration_minutes} min</strong> &nbsp;·&nbsp;
         Optimised: <strong style="color:var(--ec-teal)">${data.optimized_duration_minutes} min</strong><br>
         Junctions: ${(data.junctions || []).length} &nbsp;·&nbsp; VMS: ${(data.vms || []).length}`;

      destLabelBar.textContent = data.destination.name || 'Hospital';

      show(routeReadyAct);

    } catch (err) {
      console.error('Route calc failed:', err);
      alert('Route calculation failed: ' + err.message);
    } finally {
      btnCalculate.disabled = false;
      btnCalculate.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12h18M3 6h18M3 18h18"/></svg> CALCULATE EMERGENCY ROUTE`;
    }
  }

  function drawSetupMap(data) {
    if (setupPolyline)    { setupMap.removeLayer(setupPolyline); }
    if (setupDestMarker)  { setupMap.removeLayer(setupDestMarker); }

    const geometry = data.geometry || [];
    if (geometry.length > 1) {
      const latLngs = geometry.map(c => [c[1], c[0]]);
      setupPolyline = L.polyline(latLngs, { color: '#0EA5A0', weight: 5, opacity: 0.8 }).addTo(setupMap);
      setupMap.fitBounds(setupPolyline.getBounds(), { padding: [50, 50] });
    }

    const dest = data.destination;
    if (dest && dest.lat) {
      setupDestMarker = L.marker([dest.lat, dest.lon], { icon: destIcon(dest.name) }).addTo(setupMap);
    }

    // Draw junction pins on setup map
    (data.junctions || []).forEach(j => {
      if (!j.lat || j.lat === 0) return;
      L.marker([j.lat, j.lon], { icon: junctionIcon('pending', j.ambulance_approach) })
        .bindTooltip(`<b>${j.name}</b>`, { permanent: false }).addTo(setupMap);
    });
    (data.vms || []).forEach(v => {
      if (!v.lat || v.lat === 0) return;
      L.marker([v.lat, v.lon], { icon: vmsIcon('DRIVE CAUTIOUSLY\nHAVE A GOOD DAY', 'normal') })
        .bindTooltip(`<b>${v.name}</b>`, { permanent: false }).addTo(setupMap);
    });
  }

  /* ── Start emergency ─────────────────────────────────────────── */
  async function startEmergency() {
    if (!currentRouteId) return;
    btnStart.disabled = true;
    btnStart.innerHTML = '<span style="display:inline-block;animation:spin 1s linear infinite">⟳</span> Activating…';

    try {
      const res = await fetch('/api/emergency/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ route_id: currentRouteId }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.message);

      corridorId = json.data.corridor_id;

      // Switch panels
      hide(setupPanel);
      show(monitorPanel);

      // Pill → active
      setPillActive();

      // Init monitor map
      initMonitorMap();

      // Start polling
      startPolling();

    } catch (err) {
      console.error('Start failed:', err);
      btnStart.disabled = false;
      btnStart.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> START EMERGENCY CORRIDOR`;
      alert('Failed to start corridor: ' + err.message);
    }
  }

  /* ── Pause / Resume ──────────────────────────────────────────── */
  async function togglePause() {
    if (paused) {
      await fetch('/api/emergency/resume', { method: 'POST' });
      paused = false;
      btnPause.innerHTML = '⏸ Pause';
    } else {
      await fetch('/api/emergency/pause', { method: 'POST' });
      paused = true;
      btnPause.innerHTML = '▶ Resume';
      if (anprStarted && !anprVideo.paused) {
        anprVideo.pause();
      }
    }
  }

  /* ── Reset ───────────────────────────────────────────────────── */
  async function resetCorridor() {
    stopPolling();
    await fetch('/api/emergency/reset', { method: 'POST' });

    corridorId = null;
    currentRouteId = null;
    paused = false;
    anprStarted = false;
    anprEmitted = new Set();
    anprLogCount = 0;

    // ANPR video
    if (anprVideo) { anprVideo.pause(); anprVideo.currentTime = 0; }
    show(anprWaiting);
    hide(anprVideoWrap);
    setPillIdle();
    anprPill.textContent = 'Waiting…';
    anprPill.className = 'ec-pill ec-pill-idle';
    anprHistory.innerHTML = '<div class="ec-anpr-empty" id="ec-anpr-empty">No detections yet</div>';
    anprCountPill.textContent = '0 detections';
    anprCountPill.className = 'ec-pill ec-pill-idle';

    // Reset ETA card
    hide(etaCard);
    hide(completionBanner);

    // Reset map markers
    if (monMap) {
      Object.values(monJuncMarkers).forEach(m => monMap.removeLayer(m));
      Object.values(monVmsMarkers).forEach(m => monMap.removeLayer(m));
      if (monPolyline)   { monMap.removeLayer(monPolyline); }
      if (monDestMarker) { monMap.removeLayer(monDestMarker); }
      monJuncMarkers = {};
      monVmsMarkers  = {};
      monPolyline    = null;
      monDestMarker  = null;
      if (monAmbMarker) monAmbMarker.setLatLng(VNIT);
    }

    // Switch back to setup
    show(setupPanel);
    hide(monitorPanel);
    btnPause.innerHTML = '⏸ Pause';
    progressBar.style.width = '0%';
    progressLabel.textContent = '0%';
    setSignalNormal();
    setVmsNormal();
    junctionList.innerHTML = '<div style="color:var(--ec-muted);font-size:0.85rem;">No route loaded.</div>';
  }

  /* ── Poll ────────────────────────────────────────────────────── */
  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchStatus, 1000);
    fetchStatus();
  }

  function stopPolling() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  }

  async function fetchStatus() {
    try {
      const res = await fetch('/api/emergency/status');
      const json = await res.json();
      if (json.status !== 'success') return;
      applyStatus(json.data);
    } catch (e) { /* ignore */ }
  }

  /* ── Apply full status snapshot ──────────────────────────────── */
  function applyStatus(d) {
    if (!d) return;

    const amb   = d.ambulance || {};
    const stats = d.stats || {};

    /* Ambulance position */
    if (monAmbMarker && amb.lat && amb.lat !== 0) {
      monAmbMarker.setLatLng([amb.lat, amb.lon]);
    }

    /* Live stats */
    liveSpeed.textContent = `${amb.speed_kmh || 0} km/h`;
    liveEta.textContent   = `${(amb.eta_minutes || 0).toFixed(0)} min`;
    liveDist.textContent  = `${(amb.distance_remaining_km || 0).toFixed(1)} km`;
    const pct = (amb.route_progress_pct || 0).toFixed(1);
    livePct.textContent   = `${pct}%`;

    /* Progress bar */
    progressBar.style.width = `${pct}%`;
    progressLabel.textContent = `${pct}%`;

    /* Route draw on monitor map (first time) */
    if (monMap && !monPolyline && d.route_id) {
      fetchAndDrawMonitorMap(d);
    }

    /* Signal */
    if (d.signal_phase === 'green') {
      setSignalGreen(d.current_junction);
    } else {
      setSignalNormal();
    }

    /* Junctions text */
    currentJunc.textContent = d.current_junction || '—';
    nextJunc.textContent    = d.next_junction    || '—';
    nextJuncDist.textContent = d.next_junction_distance_km != null
      ? `${d.next_junction_distance_km} km away` : '';

    /* VMS */
    const vmsMsg     = d.current_vms_message || 'DRIVE CAUTIOUSLY\nHAVE A GOOD DAY';
    const isEmergVms = vmsMsg.includes('CLEAR');
    vmsText.textContent  = vmsMsg;
    vmsText.className    = `ec-vms-text ${isEmergVms ? 'emergency' : 'normal'}`;
    if (d.active_vms_name) {
      vmsLabel.textContent = d.active_vms_name;
    } else {
      vmsLabel.textContent = 'Active Route VMS';
    }

    /* Junction list */
    renderJunctionList(d.junctions || []);

    /* Update map markers */
    updateMapMarkers(d.junctions || [], d.vms_boards || []);

    /* ANPR */
    const anpr = d.anpr || {};
    if (anpr.started && !anprStarted) {
      startAnprDemo();
    }
    if (anprStarted) {
      syncAnprLog(anpr.history || []);
    }

    /* ETA stats */
    statJunctions.textContent = stats.junctions_prioritised || 0;
    statVms.textContent       = stats.vms_activated || 0;
    statAnpr.textContent      = stats.anpr_detections || 0;

    /* Completion */
    if (d.state === 'CORRIDOR_COMPLETED') {
      onCompleted(d);
    }
  }

  /* ── Fetch route geometry and draw on monitor map ─────────────── */
  async function fetchAndDrawMonitorMap(d) {
    /* Re-call calculate_route endpoint to get geometry again */
    /* We only have route_id; re-fetch from /api/emergency/status which
       includes source/destination — build a minimal polyline from those */
    try {
      const src  = d.source;
      const dest = d.destination;

      if (!src || !dest) return;

      /* Draw route geometry: fetch the latest status which has the geometry
         stored in the corridor service.  We call /api/emergency/route again
         with the known destination but that would reset state.
         Instead, we rely on the fact that the monitor map is initialised ONCE
         and the corridor_service keeps geometry in memory.
         We call /api/emergency/route in a non-destructive way if state is
         already EMERGENCY_STARTED — the service will return cached data. */

      /* Simpler: just draw source→dest line from known coords */
      const latLngs = [[src.lat, src.lon], [dest.lat, dest.lon]];
      monPolyline = L.polyline(latLngs, {
        color: '#0EA5A0', weight: 5, opacity: 0.8,
      }).addTo(monMap);
      monMap.fitBounds(monPolyline.getBounds(), { padding: [60, 60] });

      /* Destination marker */
      monDestMarker = L.marker([dest.lat, dest.lon], { icon: destIcon(dest.name) }).addTo(monMap);

    } catch (e) {
      console.warn('Monitor map draw error:', e);
    }
  }

  /* ── Update junction & VMS markers on monitor map ─────────────── */
  function updateMapMarkers(junctions, vmsList) {
    if (!monMap) return;

    junctions.forEach(j => {
      if (!j.lat || j.lat === 0) return;
      if (!monJuncMarkers[j.id]) {
        monJuncMarkers[j.id] = L.marker([j.lat, j.lon], {
          icon: junctionIcon(j.status, j.ambulance_approach),
          zIndexOffset: 200,
        })
          .bindTooltip(`<b>${j.name}</b><br>Seq ${j.sequence}`, { permanent: false, direction: 'top', offset: [0, -10] })
          .addTo(monMap);
      } else {
        monJuncMarkers[j.id].setIcon(junctionIcon(j.status, j.ambulance_approach));
      }
    });

    vmsList.forEach(v => {
      if (!v.lat || v.lat === 0) return;
      if (!monVmsMarkers[v.id]) {
        monVmsMarkers[v.id] = L.marker([v.lat, v.lon], {
          icon: vmsIcon(v.message, v.status),
          zIndexOffset: 100,
        })
          .bindTooltip(`<b>${v.name}</b>`, { permanent: false, direction: 'top', offset: [0, -10] })
          .addTo(monMap);
      } else {
        monVmsMarkers[v.id].setIcon(vmsIcon(v.message, v.status));
      }
    });
  }

  /* ── Junction list sidebar ────────────────────────────────────── */
  function renderJunctionList(junctions) {
    if (!junctions.length) {
      junctionList.innerHTML = '<div style="color:var(--ec-muted);font-size:0.82rem;">No junction data.</div>';
      return;
    }
    junctionList.innerHTML = junctions.map(j => `
      <div class="ec-junction-item ${j.status}">
        <span class="ec-junction-badge ${j.status}">${j.status.toUpperCase()}</span>
        <span class="ec-junction-name">${j.name}</span>
        <span class="ec-junction-approach">${j.ambulance_approach || ''}</span>
      </div>
    `).join('');
  }

  /* ── Signal helpers ───────────────────────────────────────────── */
  function setSignalGreen(juncName) {
    signalIndicator.className = 'ec-signal-indicator green';
    signalText.textContent = `🚦 EMERGENCY PRIORITY — GREEN${juncName ? ' @ ' + juncName : ''}`;
  }
  function setSignalNormal() {
    signalIndicator.className = 'ec-signal-indicator normal';
    signalText.textContent = 'Normal adaptive signal operation';
  }
  function setVmsNormal() {
    vmsText.textContent = 'DRIVE CAUTIOUSLY\nHAVE A GOOD DAY';
    vmsText.className = 'ec-vms-text normal';
  }

  /* ── Status pill helpers ─────────────────────────────────────── */
  function setPillActive() {
    corridorPill.className = 'ec-pill ec-pill-active';
    pillText.textContent = 'ACTIVE';
  }
  function setPillIdle() {
    corridorPill.className = 'ec-pill ec-pill-idle';
    pillText.textContent = 'IDLE';
  }
  function setPillCompleted() {
    corridorPill.className = 'ec-pill ec-pill-completed';
    pillText.textContent = 'COMPLETED';
  }

  /* ── ANPR video + log sync ────────────────────────────────────── */
  function startAnprDemo() {
    if (anprStarted) return;
    anprStarted = true;

    hide(anprWaiting);
    show(anprVideoWrap);

    anprPill.textContent = 'LIVE';
    anprPill.className = 'ec-pill ec-pill-active';

    anprVideo.currentTime = 0;
    anprVideo.play().catch(() => {
      /* Autoplay blocked — that's fine, user can click play manually */
    });

    // Poll video currentTime to emit detections progressively
    const syncLoop = setInterval(() => {
      if (!anprStarted) { clearInterval(syncLoop); return; }

      const t = anprVideo.currentTime;

      anprDetections.forEach((det, idx) => {
        if (anprEmitted.has(idx)) return;
        if (t >= det.timestamp_sec) {
          anprEmitted.add(idx);
          addAnprLogEntry(det);
        }
      });

      // If video ended, stop sync
      if (anprVideo.ended) {
        clearInterval(syncLoop);
        anprPill.textContent = 'COMPLETED';
        anprPill.className = 'ec-pill ec-pill-completed';
      }
    }, 250); // check 4×/sec — fine-grained enough at 30fps video
  }

  /**
   * Sync ANPR history from backend status (for admin screen which may be
   * opened mid-session).  Entries the server already emitted but the
   * frontend hasn't shown are added in one shot.
   */
  function syncAnprLog(serverHistory) {
    if (!serverHistory.length) return;

    serverHistory.forEach(entry => {
      const key = `srv_${entry.frame}_${entry.plate}`;
      if (anprEmitted.has(key)) return;
      anprEmitted.add(key);
      // Don't double-add with video-sync; only use server data if video not playing
      if (!anprStarted) {
        addAnprLogEntry({
          plate:          entry.plate,
          confidence:     entry.confidence,
          is_primary:     entry.is_primary,
          car_id:         entry.car_id,
          source:         entry.source,
          frame_number:   entry.frame,
          timestamp_sec:  entry.timestamp_sec,
          log_time:       entry.log_time,
        });
      }
    });
  }

  function addAnprLogEntry(det) {
    anprLogCount++;

    // Remove "no detections" placeholder
    const emptyEl = anprHistory.querySelector('.ec-anpr-empty');
    if (emptyEl) emptyEl.remove();

    const time = det.log_time || new Date().toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    const confPct = Math.round((det.confidence || 0) * 100);
    const isPrimary = det.is_primary || false;

    const entry = document.createElement('div');
    entry.className = `ec-anpr-entry new-entry${isPrimary ? ' primary' : ''}`;
    entry.innerHTML = `
      <div class="ec-anpr-dot"></div>
      <span class="ec-anpr-time">${time}</span>
      <div>
        <div class="ec-anpr-plate">${det.plate}</div>
        <div class="ec-anpr-source">${det.source || 'Ambulance CCTV'}</div>
      </div>
      <span class="ec-anpr-conf">${confPct}%</span>
    `;

    // Prepend — newest at top
    anprHistory.insertBefore(entry, anprHistory.firstChild);

    // Remove 'new-entry' highlight after animation
    setTimeout(() => entry.classList.remove('new-entry'), 1200);

    // Update count badge
    anprCountPill.textContent = `${anprLogCount} detection${anprLogCount !== 1 ? 's' : ''}`;
    anprCountPill.className = 'ec-pill ec-pill-active';

    // Update global stat
    if (statAnpr) statAnpr.textContent = anprLogCount;
  }

  /* ── Completion ──────────────────────────────────────────────── */
  function onCompleted(d) {
    stopPolling();
    setPillCompleted();

    if (mapPill) {
      mapPill.className = 'ec-pill ec-pill-completed';
      mapPill.innerHTML = '<span class="dot"></span> COMPLETED';
    }

    const stats = d.stats || {};
    etaBaseline.textContent  = `${stats.baseline_duration_minutes || '—'} min`;
    etaOptimized.textContent = `${stats.optimized_duration_minutes || '—'} min`;
    etaSaved.textContent     = `${stats.time_saved_minutes || '—'} min`;
    statJunctions.textContent = stats.junctions_prioritised || 0;
    statVms.textContent       = stats.vms_activated || 0;
    statAnpr.textContent      = stats.anpr_detections || anprLogCount;

    show(etaCard);
    show(completionBanner);

    setSignalNormal();
    setVmsNormal();
    progressBar.style.width = '100%';
    progressLabel.textContent = '100%';
  }

  /* ── Event listeners ─────────────────────────────────────────── */
  destSelect.addEventListener('change', () => {
    btnCalculate.disabled = destSelect.value === '';
  });

  btnCalculate.addEventListener('click', calculateRoute);
  btnStart.addEventListener('click', startEmergency);
  btnPause.addEventListener('click', togglePause);
  btnReset.addEventListener('click', resetCorridor);

  /* ── Util ────────────────────────────────────────────────────── */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── Init ────────────────────────────────────────────────────── */
  initSetupMap();
  loadDestinations();
  loadAnprDetections();

})();
