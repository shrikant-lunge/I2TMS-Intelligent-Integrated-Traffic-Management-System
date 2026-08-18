/**
 * I²TMS — live-video.js  (Screen 9: Live Junction Video)
 *
 * Data source: /api/live_demo_stats?part=N  →  static/videos/part-N.json
 * Videos:      static/videos/part-N-result.mp4  (4 parts)
 *
 * Auto-rotate:   cycles part 1 → 2 → 3 → 4 → 1 every ROTATE_INTERVAL ms
 * Junction dropdown: cosmetic — selects which junction label to show
 *                    (all junctions use the same rotating demo footage)
 * Stats panel:   PCU, Unique Tracked, Est. Queue, vehicle breakdown
 *                all sourced from the real detection JSON — NO random values
 */

(function () {
  'use strict';

  /* ── Config ─────────────────────────────────────────────────── */
  var TOTAL_PARTS     = 4;
  var ROTATE_INTERVAL = 15000;  // 15 s per part (video is ~10–30s long)
  var POLL_INTERVAL   = 2000;   // re-fetch stats every 2 s (or on part change)

  /* ── State ──────────────────────────────────────────────────── */
  var currentPart     = 1;
  var isAutoRotate    = true;
  var isRecording     = false;
  var isPTZOpen       = false;
  var isCamDropOpen   = false;
  var rotateTimer     = null;
  var pollTimer       = null;

  /* ── Vehicle type colours / icons ───────────────────────────── */
  var TYPE_META = {
    car:        { label: 'Car',        color: '#3B82F6', bg: '#DBEAFE' },
    motorcycle: { label: 'Motorcycle', color: '#8B5CF6', bg: '#EDE9FE' },
    truck:      { label: 'Truck',      color: '#F59E0B', bg: '#FEF3C7' },
    bus:        { label: 'Bus',        color: '#10B981', bg: '#D1FAE5' },
    auto:       { label: 'Auto',       color: '#EF4444', bg: '#FEE2E2' },
  };

  /* ── DOM refs ────────────────────────────────────────────────── */
  var elSelect      = document.getElementById('lv-junction-select');
  var elJuncName    = document.getElementById('lv-junction-name');
  var elCamLabel    = document.getElementById('lv-camera-label');
  var elLiveBadge   = document.getElementById('lv-live-badge');
  var elStateBadge  = document.getElementById('lv-state-badge');
  var elStateText   = document.getElementById('lv-state-text');
  var elPartLabel   = document.getElementById('lv-part-label');
  var elPcu         = document.getElementById('lv-pcu');
  var elVCount      = document.getElementById('lv-vcount');
  var elQueue       = document.getElementById('lv-queue');
  var elBreakdown   = document.getElementById('lv-breakdown');
  var elLastUpdated = document.getElementById('lv-last-updated');
  var elCam         = document.getElementById('lv-cam');
  var elRecBadge    = document.getElementById('lv-rec-badge');
  var elPtzOverlay  = document.getElementById('lv-ptz-overlay');
  var elCamDropdown = document.getElementById('lv-cam-dropdown');

  var btnAutoRotate = document.getElementById('btn-autorotate');
  var btnSnapshot   = document.getElementById('btn-snapshot');
  var btnRecord     = document.getElementById('btn-record');
  var btnPTZ        = document.getElementById('btn-ptz');
  var btnChangeCam  = document.getElementById('btn-change-cam');
  var btnFullscreen = document.getElementById('lv-fullscreen-btn');

  /* ── Junction dropdown (label only — all junctions share demo footage) */
  if (elSelect) {
    elSelect.addEventListener('change', function () {
      var key = this.value;
      if (elJuncName) elJuncName.textContent = key;
      // Advance to next part on manual junction change
      currentPart = (currentPart % TOTAL_PARTS) + 1;
      loadPart(currentPart);
      if (isAutoRotate) { stopRotate(); startRotate(); }
    });
  }

  /* ── Part loader ─────────────────────────────────────────────── */
  function loadPart(part) {
    currentPart = part;

    // Swap video source
    if (elCam) {
      var newSrc = '/static/videos/part-' + part + '-result.mp4';
      if (elCam.src.indexOf('part-' + part + '-result') === -1) {
        elCam.src = newSrc;
        elCam.load();
        elCam.play().catch(function(){});
      }
    }

    // Update part label
    if (elPartLabel) elPartLabel.textContent = 'Part ' + part + ' / ' + TOTAL_PARTS;

    // Fetch stats for this part
    fetchDemoStats(part);
  }

  /* ── Stats fetch ─────────────────────────────────────────────── */
  function fetchDemoStats(part) {
    fetch('/api/live_demo_stats?part=' + part, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { renderStats(data); setOnline(true); })
      .catch(function (e) {
        console.warn('[live-video] stats fetch error:', e);
        setOnline(false);
      });
  }

  /* ── Stats renderer ──────────────────────────────────────────── */
  function renderStats(data) {
    // Traffic state badge
    var level = (data.traffic_level || 'LOW').toLowerCase();
    if (elStateBadge) elStateBadge.className = 'lv-state-badge badge-' + level;
    if (elStateText)  elStateText.textContent = (data.congestion_level || level).toUpperCase();

    // Scalar metrics
    if (elPcu)    elPcu.textContent    = data.pcu != null ? data.pcu : '—';
    if (elVCount) elVCount.textContent = data.total_vehicles != null ? data.total_vehicles : '—';
    if (elQueue)  elQueue.textContent  = data.queue_length != null ? data.queue_length + ' veh' : '—';

    // Vehicle type breakdown bars
    if (elBreakdown) {
      var counts  = data.vehicle_counts || {};
      var total   = data.total_vehicles || 1;
      var types   = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });

      elBreakdown.innerHTML = types.map(function (type) {
        var count  = counts[type] || 0;
        var pct    = Math.round((count / total) * 100);
        var meta   = TYPE_META[type] || { label: type, color: '#6B7280', bg: '#F3F4F6' };
        return (
          '<div style="display:flex;align-items:center;gap:7px;">' +
            '<span style="font-size:11px;font-weight:600;color:#374151;min-width:68px;flex-shrink:0;">' + esc(meta.label) + '</span>' +
            '<div style="flex:1;background:#F3F4F6;border-radius:99px;height:7px;overflow:hidden;min-width:0;">' +
              '<div style="width:' + pct + '%;height:100%;background:' + meta.color + ';border-radius:99px;transition:width 0.5s ease;"></div>' +
            '</div>' +
            '<span style="font-size:11px;font-weight:700;color:' + meta.color + ';min-width:28px;text-align:right;flex-shrink:0;">' + count + '</span>' +
          '</div>'
        );
      }).join('');
    }

    // Timestamp
    var now = new Date();
    var h = now.getHours(), m = String(now.getMinutes()).padStart(2,'0'),
        s = String(now.getSeconds()).padStart(2,'0');
    var ampm = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12;
    if (elLastUpdated) elLastUpdated.textContent = h + ':' + m + ':' + s + ' ' + ampm;
  }

  /* ── Online badge ────────────────────────────────────────────── */
  function setOnline(on) {
    if (!elLiveBadge) return;
    var txt = elLiveBadge.querySelector('span:last-child');
    elLiveBadge.classList.toggle('offline', !on);
    if (txt) txt.textContent = on ? 'LIVE — DEMONSTRATION' : 'OFFLINE';
  }

  /* ── Auto-rotate ─────────────────────────────────────────────── */
  function startRotate() {
    stopRotate();
    rotateTimer = setInterval(function () {
      currentPart = (currentPart % TOTAL_PARTS) + 1;
      loadPart(currentPart);
    }, ROTATE_INTERVAL);
  }

  function stopRotate() {
    if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null; }
  }

  function applyAutoRotateUI(on) {
    if (!btnAutoRotate) return;
    btnAutoRotate.classList.toggle('active', on);
    btnAutoRotate.setAttribute('aria-pressed', String(on));
    btnAutoRotate.title = on ? 'Auto-rotate ON (15s)' : 'Auto-rotate OFF';
  }

  if (btnAutoRotate) {
    btnAutoRotate.addEventListener('click', function () {
      isAutoRotate = !isAutoRotate;
      applyAutoRotateUI(isAutoRotate);
      if (isAutoRotate) startRotate(); else stopRotate();
    });
  }

  /* ── Snapshot ────────────────────────────────────────────────── */
  if (btnSnapshot) {
    btnSnapshot.addEventListener('click', function () {
      // Canvas-based snapshot from video element
      if (elCam && elCam.tagName === 'VIDEO' && elCam.readyState >= 2) {
        var canvas = document.createElement('canvas');
        canvas.width  = elCam.videoWidth  || 640;
        canvas.height = elCam.videoHeight || 360;
        canvas.getContext('2d').drawImage(elCam, 0, 0);
        var link = document.createElement('a');
        link.download = 'snapshot_part' + currentPart + '_' + Date.now() + '.jpg';
        link.href = canvas.toDataURL('image/jpeg', 0.92);
        link.click();
      }
      flashBtn(this);
    });
  }

  /* ── Record toggle ───────────────────────────────────────────── */
  if (btnRecord) {
    btnRecord.addEventListener('click', function () {
      isRecording = !isRecording;
      if (elRecBadge) elRecBadge.classList.toggle('visible', isRecording);
      this.classList.toggle('rec-active', isRecording);
    });
  }

  /* ── PTZ ─────────────────────────────────────────────────────── */
  if (btnPTZ) {
    btnPTZ.addEventListener('click', function () {
      isPTZOpen = !isPTZOpen;
      if (elPtzOverlay) elPtzOverlay.classList.toggle('visible', isPTZOpen);
      this.classList.toggle('active', isPTZOpen);
      if (isPTZOpen && isCamDropOpen) { isCamDropOpen = false; if (elCamDropdown) elCamDropdown.classList.remove('visible'); }
    });
  }
  ['ptz-up','ptz-down','ptz-left','ptz-right','ptz-center','ptz-zoom-in','ptz-zoom-out'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', function (e) { e.stopPropagation(); flashBtn(this); });
  });

  /* ── Change Camera ───────────────────────────────────────────── */
  if (btnChangeCam) {
    btnChangeCam.addEventListener('click', function () {
      isCamDropOpen = !isCamDropOpen;
      if (elCamDropdown) elCamDropdown.classList.toggle('visible', isCamDropOpen);
      this.classList.toggle('active', isCamDropOpen);
      if (isCamDropOpen && isPTZOpen) { isPTZOpen = false; if (elPtzOverlay) elPtzOverlay.classList.remove('visible'); }
    });
  }
  document.querySelectorAll('.lv-cam-option').forEach(function (opt) {
    opt.addEventListener('click', function (e) {
      e.stopPropagation();
      var cam = this.getAttribute('data-cam');
      if (elCamLabel) elCamLabel.textContent = cam;
      document.querySelectorAll('.lv-cam-option').forEach(function (o) { o.classList.remove('active'); });
      this.classList.add('active');
      isCamDropOpen = false;
      if (elCamDropdown) elCamDropdown.classList.remove('visible');
    });
  });

  /* ── Full Screen ─────────────────────────────────────────────── */
  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', function () {
      var panel = document.getElementById('lv-video-panel');
      if (!panel) return;
      if (document.fullscreenElement) document.exitFullscreen().catch(function(){});
      else panel.requestFullscreen().catch(function(){});
    });
  }
  document.addEventListener('fullscreenchange', function () {
    if (!btnFullscreen) return;
    var nodes = btnFullscreen.childNodes;
    var last = nodes[nodes.length - 1];
    if (last && last.nodeType === 3) last.textContent = document.fullscreenElement ? ' Exit Full Screen' : ' Full Screen';
  });

  /* ── Click-outside overlays ──────────────────────────────────── */
  document.addEventListener('click', function (e) {
    if (isPTZOpen && elPtzOverlay && !elPtzOverlay.contains(e.target) && e.target !== btnPTZ) {
      isPTZOpen = false; elPtzOverlay.classList.remove('visible'); if (btnPTZ) btnPTZ.classList.remove('active');
    }
    if (isCamDropOpen && elCamDropdown && !elCamDropdown.contains(e.target) && e.target !== btnChangeCam) {
      isCamDropOpen = false; elCamDropdown.classList.remove('visible'); if (btnChangeCam) btnChangeCam.classList.remove('active');
    }
  });

  /* ── Helpers ─────────────────────────────────────────────────── */
  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function flashBtn(btn) {
    btn.style.transform = 'scale(0.9)';
    setTimeout(function () { btn.style.transform = ''; }, 120);
  }

  /* ── Inline dropdown styles ──────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    '.lv-select-wrap{position:relative;display:inline-flex;align-items:center;}',
    '.lv-junction-select{appearance:none;border:1px solid #E5E7EB;border-radius:8px;',
    'padding:8px 32px 8px 12px;font-size:0.88rem;color:#111827;background:#fff;',
    'cursor:pointer;min-width:180px;transition:border-color .2s;}',
    '.lv-junction-select:focus{outline:none;border-color:#0EA5A0;box-shadow:0 0 0 3px rgba(14,165,160,0.15);}',
    '.lv-select-caret{position:absolute;right:8px;pointer-events:none;color:#9CA3AF;}',
    '.lv-select-caret svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;}',
    '.lv-autorotate-btn.active{background:#EFF6FF!important;color:#1D4ED8!important;border-color:#93C5FD!important;}',
  ].join('');
  document.head.appendChild(style);

  /* ── Init ─────────────────────────────────────────────────────── */
  applyAutoRotateUI(isAutoRotate);
  loadPart(1);                     // load part 1 immediately
  if (isAutoRotate) startRotate(); // start auto-rotation

})();
