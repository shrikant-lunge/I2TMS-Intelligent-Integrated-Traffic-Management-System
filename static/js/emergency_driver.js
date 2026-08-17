/**
 * emergency_driver.js
 * Ambulance Driver Navigation Screen — VNIT → Hospital
 *
 * Map markers:
 *   🚦 Junction = traffic-signal icon, changes R/R/G/R when ambulance approaches
 *   📶 VMS      = actual board panel on the map, message flips live
 *   🚑 Ambulance = pulsing red icon that moves along the route
 *   🏥 Destination = hospital pin
 */
(function () {
  'use strict';

  /* ── DOM refs ─────────────────────────────────────────────────── */
  const destSelect      = document.getElementById('drv-dest-select');
  const btnCalculate    = document.getElementById('drv-btn-calculate');
  const btnStart        = document.getElementById('drv-btn-start');
  const btnPause        = document.getElementById('drv-btn-pause');
  const btnReset        = document.getElementById('drv-btn-reset');

  const bannerCalc      = document.getElementById('drv-banner-calculating');
  const bannerActive    = document.getElementById('drv-banner-active');
  const bannerCompleted = document.getElementById('drv-banner-completed');

  const routeStatsEl    = document.getElementById('drv-route-stats');
  const statDist        = document.getElementById('drv-stat-dist');
  const statBaseline    = document.getElementById('drv-stat-baseline');
  const statEta         = document.getElementById('drv-stat-eta');

  const liveInfoEl      = document.getElementById('drv-live-info');
  const liveStatsEl     = document.getElementById('drv-live-stats');
  const completionCard  = document.getElementById('drv-completion-card');

  const nextJuncName    = document.getElementById('drv-next-junc-name');
  const nextJuncDist    = document.getElementById('drv-next-junc-dist');
  const signalDisplay   = document.getElementById('drv-signal-display');
  const signalText      = document.getElementById('drv-signal-text');
  const vmsText         = document.getElementById('drv-vms-text');

  const liveRemaining   = document.getElementById('drv-live-remaining');
  const liveEta         = document.getElementById('drv-live-eta');
  const liveSpeed       = document.getElementById('drv-live-speed');
  const speedVal        = document.getElementById('drv-speed-val');

  const progressBar     = document.getElementById('drv-progress-bar');
  const navBanner       = document.getElementById('drv-nav-banner');
  const navBannerName   = document.getElementById('drv-nav-banner-name');
  const navBannerDist   = document.getElementById('drv-nav-banner-dist');

  const compBaseline    = document.getElementById('drv-comp-baseline');
  const compOptimized   = document.getElementById('drv-comp-optimized');
  const compSaved       = document.getElementById('drv-comp-saved');
  const compJunctions   = document.getElementById('drv-comp-junctions');
  const compVms         = document.getElementById('drv-comp-vms');
  const compAnpr        = document.getElementById('drv-comp-anpr');

  /* ── State ─────────────────────────────────────────────────────── */
  let currentRouteId  = null;
  let corridorId      = null;
  let pollInterval    = null;
  let paused          = false;

  /* ── Map setup ──────────────────────────────────────────────────── */
  const VNIT = [21.123028, 79.051449];

  const map = L.map('drv-map', { zoomControl: true }).setView(VNIT, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 20,
  }).addTo(map);

  /* ── Marker stores ──────────────────────────────────────────────── */
  let routePolyline   = null;
  let ambulanceMarker = null;
  let destMarker      = null;
  let junctionMarkers = {};   // id → { marker, labelEl, signalEl }
  let vmsMarkers      = {};   // id → { marker, boardEl }

  /* ── Ambulance icon ─────────────────────────────────────────────── */
  function makeAmbIcon() {
    return L.divIcon({
      html: `<div class="lf-amb-icon">🚑</div>`,
      className: '',
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });
  }

  /* ── Traffic signal icon ─────────────────────────────────────────
     Renders a miniature traffic light post.
     state: 'normal' | 'green' | 'passed'
     approach: 'north'|'east'|'south'|'west'  (which light is green)
  ──────────────────────────────────────────────────────────────── */
  function makeSignalIcon(status, approach) {
    const isActive  = status === 'active';
    const isPassed  = status === 'passed';
    const isNormal  = status === 'pending' || status === 'normal';

    // Each lens: top=red, mid=amber, bot=green
    // When emergency_green: the approach direction light turns fully green
    const postColor  = isPassed ? '#4ade80' : isActive ? '#22c55e' : '#6b7280';
    const glow       = isActive ? 'drop-shadow(0 0 6px #22c55e)' : 'none';
    const redLit     = isNormal || isPassed ? '#1a1a1a' : '#ff4444';
    const greenLit   = isActive ? '#22ff66' : '#1a1a1a';
    const amberLit   = '#1a1a1a';

    const label = approach ? approach.toUpperCase()[0] : '';

    const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="28" height="48" viewBox="0 0 28 48"
     style="filter:${glow}">
  <!-- post -->
  <rect x="12" y="32" width="4" height="16" rx="1" fill="${postColor}"/>
  <!-- housing -->
  <rect x="4" y="2" width="20" height="30" rx="4" fill="#1c2333" stroke="${postColor}" stroke-width="1.5"/>
  <!-- red lens -->
  <circle cx="14" cy="8"  r="4.5" fill="${redLit}"/>
  <!-- amber lens -->
  <circle cx="14" cy="17" r="4.5" fill="${amberLit}"/>
  <!-- green lens -->
  <circle cx="14" cy="26" r="4.5" fill="${greenLit}"/>
  ${isActive ? `<text x="14" y="46" font-size="5" fill="#22ff66" text-anchor="middle" font-family="monospace">${label}→GRN</text>` : ''}
</svg>`;

    const size = isActive ? [32, 56] : [24, 44];
    return L.divIcon({
      html: svg,
      className: '',
      iconSize: size,
      iconAnchor: [size[0] / 2, size[1]],
    });
  }

  /* ── VMS board icon ──────────────────────────────────────────────
     Renders an LED matrix board directly on the map.
     Flips between normal (green text) and emergency (amber text).
  ──────────────────────────────────────────────────────────────── */
  function makeVmsIcon(message, status) {
    const isEmergency = status === 'emergency_warning';
    const isPassed    = status === 'passed';

    const boardBg      = '#0a1628';
    const borderColor  = isEmergency ? '#ff9500' : isPassed ? '#334155' : '#2a4a7f';
    const textColor    = isEmergency ? '#ff9500' : isPassed ? '#4b5563' : '#66bb6a';
    const glowStyle    = isEmergency ? 'filter:drop-shadow(0 0 5px rgba(255,149,0,0.7));' : '';

    // Sanitise message for HTML
    const lines = (message || '')
      .replace(/\n/g, '<br>')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    const html = `
<div style="
  background:${boardBg};
  border:2px solid ${borderColor};
  border-radius:5px;
  padding:5px 7px;
  font-family:'Courier New',monospace;
  font-size:0.55rem;
  font-weight:700;
  line-height:1.4;
  color:${textColor};
  white-space:nowrap;
  min-width:90px;
  box-shadow:0 2px 10px rgba(0,0,0,0.6);
  ${glowStyle}
  position:relative;
">
  <div style="font-size:0.4rem;color:${borderColor};letter-spacing:0.1em;margin-bottom:2px;">▲ VMS BOARD</div>
  <div>${lines}</div>
  ${isEmergency ? '<div style="font-size:0.4rem;color:#ff9500;margin-top:2px;animation:drv-blink 0.8s step-start infinite;">● ACTIVE</div>' : ''}
</div>`;

    return L.divIcon({
      html,
      className: '',
      iconSize: [96, 50],
      iconAnchor: [48, 50],
    });
  }

  /* ── Destination pin ─────────────────────────────────────────────── */
  function makeDestIcon(name) {
    return L.divIcon({
      html: `<div style="background:#EF4444;color:#fff;border:2px solid #fff;border-radius:6px;padding:5px 9px;font-size:0.65rem;font-weight:700;white-space:nowrap;box-shadow:0 3px 10px rgba(0,0,0,0.5);">🏥 ${name}</div>`,
      className: '',
      iconAnchor: [0, 0],
    });
  }

  /* ── Ambulance marker init ───────────────────────────────────────── */
  ambulanceMarker = L.marker(VNIT, {
    icon: makeAmbIcon(),
    zIndexOffset: 1000,
  }).addTo(map);

  /* ── Clock ───────────────────────────────────────────────────────── */
  const clockEl = document.getElementById('drv-clock');
  function tick() {
    clockEl.textContent = new Date().toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }
  tick();
  setInterval(tick, 1000);

  /* ── Show / hide ─────────────────────────────────────────────────── */
  function show(el) { el && el.classList.remove('drv-hidden'); }
  function hide(el) { el && el.classList.add('drv-hidden'); }

  /* ── Load destinations ───────────────────────────────────────────── */
  async function loadDestinations() {
    try {
      const res  = await fetch('/api/emergency/destinations');
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

  /* ── Calculate route ─────────────────────────────────────────────── */
  async function calculateRoute() {
    const destId = destSelect.value;
    if (!destId) { alert('Please select a hospital destination.'); return; }

    clearMapLayers();
    hide(bannerActive);
    hide(bannerCompleted);
    show(bannerCalc);
    btnCalculate.disabled = true;
    btnCalculate.innerHTML = '<span class="drv-spin">⟳</span> Calculating…';
    hide(routeStatsEl);
    hide(btnStart);

    // ~2s deliberate pause for demo visibility
    await sleep(2000);

    try {
      const res  = await fetch('/api/emergency/route', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ destination_id: destId }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.message);

      const data    = json.data;
      currentRouteId = data.route_id;

      statDist.textContent     = `${data.distance_km.toFixed(1)} km`;
      statBaseline.textContent = `${data.baseline_duration_minutes} min`;
      statEta.textContent      = `${data.optimized_duration_minutes} min`;

      drawRoute(data);
      show(routeStatsEl);
      show(btnStart);
      hide(bannerCalc);

    } catch (err) {
      console.error('Route calc failed:', err);
      hide(bannerCalc);
      alert('Route calculation failed: ' + err.message);
    } finally {
      btnCalculate.disabled = false;
      btnCalculate.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 6h18M3 18h18"/></svg>
        CALCULATE EMERGENCY ROUTE`;
    }
  }

  /* ── Draw all map layers ─────────────────────────────────────────── */
  function drawRoute(data) {
    clearMapLayers();

    // Route polyline
    const geometry = data.geometry || [];
    if (geometry.length > 1) {
      const latLngs = geometry.map(c => [c[1], c[0]]);
      routePolyline = L.polyline(latLngs, {
        color: '#39d0c8', weight: 5, opacity: 0.85,
      }).addTo(map);
      map.fitBounds(routePolyline.getBounds(), { padding: [60, 60] });
    }

    // Destination
    const dest = data.destination;
    if (dest && dest.lat) {
      destMarker = L.marker([dest.lat, dest.lon], {
        icon: makeDestIcon(dest.name || 'Hospital'),
      }).addTo(map);
    }

    // Junction markers — traffic signal icons
    (data.junctions || []).forEach(j => {
      if (!j.lat || j.lat === 0) return;
      const m = L.marker([j.lat, j.lon], {
        icon: makeSignalIcon('pending', j.ambulance_approach || ''),
        zIndexOffset: 200,
      })
        .bindTooltip(`<b>${j.name}</b><br>Seq ${j.sequence}`, {
          permanent: false, direction: 'top', offset: [0, -10],
        })
        .addTo(map);
      junctionMarkers[j.id] = m;
    });

    // VMS markers — board panels
    (data.vms || []).forEach(v => {
      if (!v.lat || v.lat === 0) return;
      const msg = 'DRIVE CAUTIOUSLY\nHAVE A GOOD DAY';
      const m = L.marker([v.lat, v.lon], {
        icon: makeVmsIcon(msg, 'normal'),
        zIndexOffset: 100,
      })
        .bindTooltip(`<b>${v.name}</b>`, {
          permanent: false, direction: 'top', offset: [0, -10],
        })
        .addTo(map);
      vmsMarkers[v.id] = m;
    });

    // Ambulance back to source
    const src = data.source;
    ambulanceMarker.setLatLng(src && src.lat ? [src.lat, src.lon] : VNIT);
  }

  function clearMapLayers() {
    if (routePolyline) { map.removeLayer(routePolyline); routePolyline = null; }
    if (destMarker)    { map.removeLayer(destMarker);    destMarker    = null; }
    Object.values(junctionMarkers).forEach(m => map.removeLayer(m));
    Object.values(vmsMarkers).forEach(m => map.removeLayer(m));
    junctionMarkers = {};
    vmsMarkers = {};
  }

  /* ── Start emergency ─────────────────────────────────────────────── */
  async function startEmergency() {
    if (!currentRouteId) return;
    btnStart.disabled = true;
    btnStart.innerHTML = '<span class="drv-spin">⟳</span> Activating…';

    try {
      const res  = await fetch('/api/emergency/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ route_id: currentRouteId }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.message);

      corridorId = json.data.corridor_id;

      hide(bannerCalc);
      hide(bannerCompleted);
      show(bannerActive);
      hide(routeStatsEl);
      hide(btnStart);
      show(btnPause);
      show(btnReset);
      show(liveInfoEl);
      show(liveStatsEl);
      hide(completionCard);

      startPolling();
    } catch (err) {
      console.error('Start failed:', err);
      btnStart.disabled = false;
      btnStart.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
        </svg> START EMERGENCY`;
      alert('Failed to start: ' + err.message);
    }
  }

  /* ── Pause / Resume ──────────────────────────────────────────────── */
  async function togglePause() {
    if (paused) {
      await fetch('/api/emergency/resume', { method: 'POST' });
      paused = false;
      btnPause.textContent = '⏸ PAUSE';
    } else {
      await fetch('/api/emergency/pause', { method: 'POST' });
      paused = true;
      btnPause.textContent = '▶ RESUME';
    }
  }

  /* ── Reset ───────────────────────────────────────────────────────── */
  async function resetCorridor() {
    stopPolling();
    await fetch('/api/emergency/reset', { method: 'POST' });

    corridorId = null;
    currentRouteId = null;
    paused = false;

    hide(bannerActive);
    hide(bannerCalc);
    hide(bannerCompleted);
    hide(routeStatsEl);
    hide(btnStart);
    hide(btnPause);
    hide(btnReset);
    hide(liveInfoEl);
    hide(liveStatsEl);
    hide(completionCard);
    hide(navBanner);

    btnPause.textContent = '⏸ PAUSE';
    btnCalculate.disabled = false;
    destSelect.value = '';
    speedVal.textContent = '0';
    progressBar.style.width = '0%';
    setSignalNormal();
    setVmsNormal();

    clearMapLayers();
    ambulanceMarker.setLatLng(VNIT);
    map.setView(VNIT, 13);
  }

  /* ── Polling ─────────────────────────────────────────────────────── */
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
      const res  = await fetch('/api/emergency/status');
      const json = await res.json();
      if (json.status !== 'success') return;
      applyStatus(json.data);
    } catch (_) { /* ignore network blips */ }
  }

  /* ── Apply status snapshot ───────────────────────────────────────── */
  function applyStatus(d) {
    if (!d) return;
    const amb = d.ambulance || {};

    // Move ambulance
    if (amb.lat && amb.lat !== 0) {
      ambulanceMarker.setLatLng([amb.lat, amb.lon]);
    }

    // Speedometer
    const spd = amb.speed_kmh || 0;
    speedVal.textContent  = spd;
    liveSpeed.textContent = `${spd} km/h`;

    // Progress
    const pct = amb.route_progress_pct || 0;
    progressBar.style.width = `${pct}%`;

    // Distance / ETA
    liveRemaining.textContent = `${(amb.distance_remaining_km || 0).toFixed(1)} km`;
    liveEta.textContent       = `${(amb.eta_minutes || 0).toFixed(0)} min`;

    // Next junction banner
    if (d.next_junction) {
      nextJuncName.textContent  = d.next_junction;
      nextJuncDist.textContent  = d.next_junction_distance_km != null
        ? `${d.next_junction_distance_km} km` : '';
      navBannerName.textContent = d.next_junction;
      navBannerDist.textContent = d.next_junction_distance_km
        ? `${d.next_junction_distance_km} km` : '';
      show(navBanner);
    } else {
      nextJuncName.textContent = '—';
      hide(navBanner);
    }

    // Signal panel
    if (d.signal_phase === 'green') {
      setSignalGreen(d.current_junction || '');
    } else {
      setSignalNormal();
    }

    // VMS panel
    const msg        = d.current_vms_message || 'DRIVE CAUTIOUSLY\nHAVE A GOOD DAY';
    const isEmergVms = msg.includes('CLEAR');
    vmsText.textContent = msg;
    vmsText.className   = `drv-vms-text ${isEmergVms ? 'emergency' : 'normal'}`;

    // ── Update junction markers (traffic signal icons) ──────────────
    (d.junctions || []).forEach(j => {
      const m = junctionMarkers[j.id];
      if (!m) return;
      m.setIcon(makeSignalIcon(j.status, j.ambulance_approach));
      // Show tooltip on active
      if (j.status === 'active') {
        m.openTooltip();
      }
    });

    // ── Update VMS board panels ────────────────────────────────────
    (d.vms_boards || []).forEach(v => {
      const m = vmsMarkers[v.id];
      if (!m) return;
      m.setIcon(makeVmsIcon(v.message, v.status));
    });

    // Completion
    if (d.state === 'CORRIDOR_COMPLETED') {
      onCompleted(d);
    }
  }

  function setSignalGreen(juncName) {
    signalDisplay.className = 'drv-signal-display green-priority';
    signalText.textContent  = `🚦 EMERGENCY PRIORITY — GREEN CORRIDOR${juncName ? ' @ ' + juncName : ''}`;
  }
  function setSignalNormal() {
    signalDisplay.className = 'drv-signal-display normal';
    signalText.textContent  = 'Normal signal operation';
  }
  function setVmsNormal() {
    vmsText.textContent = 'DRIVE CAUTIOUSLY\nHAVE A GOOD DAY';
    vmsText.className   = 'drv-vms-text normal';
  }

  /* ── Completion ──────────────────────────────────────────────────── */
  function onCompleted(d) {
    stopPolling();
    hide(bannerActive);
    show(bannerCompleted);
    hide(liveInfoEl);
    hide(btnPause);
    show(btnReset);
    speedVal.textContent    = '0';
    progressBar.style.width = '100%';
    setSignalNormal();
    setVmsNormal();

    const s = d.stats || {};
    compBaseline.textContent  = `${s.baseline_duration_minutes || '—'} min`;
    compOptimized.textContent = `${s.optimized_duration_minutes || '—'} min`;
    compSaved.textContent     = `${s.time_saved_minutes || '—'} min`;
    compJunctions.textContent = s.junctions_prioritised || 0;
    compVms.textContent       = s.vms_activated || 0;
    compAnpr.textContent      = s.anpr_detections || 0;
    show(completionCard);
  }

  /* ── Event listeners ─────────────────────────────────────────────── */
  destSelect.addEventListener('change', () => {
    btnCalculate.disabled = !destSelect.value;
  });
  btnCalculate.addEventListener('click', calculateRoute);
  btnStart.addEventListener('click',     startEmergency);
  btnPause.addEventListener('click',     togglePause);
  btnReset.addEventListener('click',     resetCorridor);

  /* ── Util ────────────────────────────────────────────────────────── */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── Init ────────────────────────────────────────────────────────── */
  loadDestinations();

})();
