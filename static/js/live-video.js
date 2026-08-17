/**
 * I²TMS — live-video.js  (Screen 9: Live Junction Video)
 *
 * Responsibilities:
 *   · Read ?junction= param from URL, default 'A'
 *   · Junction pill switching (updates URL, re-fetches stats)
 *   · Poll /api/live_video_stats every 2 s — render stats panel
 *   · Snapshot button → POST /api/snapshot → trigger download
 *   · Record button → toggle UI state + POST /api/toggle_recording
 *     → pulsing REC badge over video while active
 *   · PTZ button → toggle PTZ overlay on video
 *   · Change Camera button → toggle camera picker overlay
 *   · Full Screen button → requestFullscreen on video panel
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State
  ────────────────────────────────────────────────────────────────────── */
  var selectedJunction = (typeof LV_INITIAL_JUNCTION !== 'undefined')
    ? LV_INITIAL_JUNCTION
    : (new URLSearchParams(window.location.search).get('junction') || 'A');

  var selectedCamera  = 'Camera 01';
  var isRecording     = false;
  var isPTZOpen       = false;
  var isCamDropOpen   = false;
  var pollTimer       = null;
  var POLL_INTERVAL   = 2000;  // ms

  /* ──────────────────────────────────────────────────────────────────────
     DOM refs
  ────────────────────────────────────────────────────────────────────── */
  var elJunctionName  = document.getElementById('lv-junction-name');
  var elCameraLabel   = document.getElementById('lv-camera-label');
  var elLiveBadge     = document.getElementById('lv-live-badge');
  var elStateBadge    = document.getElementById('lv-state-badge');
  var elStateText     = document.getElementById('lv-state-text');
  var elPcu           = document.getElementById('lv-pcu');
  var elQueue         = document.getElementById('lv-queue');
  var elSpeed         = document.getElementById('lv-speed');
  var elLastUpdated   = document.getElementById('lv-last-updated');
  var elCam           = document.getElementById('lv-cam');
  var elVideoPanel    = document.getElementById('lv-video-panel');
  var elRecBadge      = document.getElementById('lv-rec-badge');
  var elPtzOverlay    = document.getElementById('lv-ptz-overlay');
  var elCamDropdown   = document.getElementById('lv-cam-dropdown');

  var btnSnapshot     = document.getElementById('btn-snapshot');
  var btnRecord       = document.getElementById('btn-record');
  var btnPTZ          = document.getElementById('btn-ptz');
  var btnChangeCam    = document.getElementById('btn-change-cam');
  var btnFullscreen   = document.getElementById('lv-fullscreen-btn');

  /* ──────────────────────────────────────────────────────────────────────
     Junction pill switching
  ────────────────────────────────────────────────────────────────────── */
  var pills = document.querySelectorAll('.lv-junction-pill');
  pills.forEach(function (pill) {
    pill.addEventListener('click', function () {
      var j = this.getAttribute('data-junction');
      if (j === selectedJunction) return;
      selectedJunction = j;

      // Update pill active state
      pills.forEach(function (p) { p.classList.remove('active'); });
      this.classList.add('active');

      // Update URL (bookmarkable, no page reload)
      var url = new URL(window.location.href);
      url.searchParams.set('junction', selectedJunction);
      history.replaceState(null, '', url.toString());

      // Reset recording state on junction switch
      if (isRecording) toggleRecordingOff();

      // Immediately re-fetch
      fetchAndRender();
    });
  });

  /* ──────────────────────────────────────────────────────────────────────
     API fetch + render
  ────────────────────────────────────────────────────────────────────── */
  function fetchAndRender() {
    fetch('/api/live_video_stats?junction=' + encodeURIComponent(selectedJunction), {
      credentials: 'same-origin',
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        setOnline(true);
        renderStats(data);
      })
      .catch(function (err) {
        setOnline(false);
        console.warn('[I²TMS live-video] fetch error:', err);
      });
  }

  function renderStats(data) {
    // Junction heading
    if (elJunctionName) elJunctionName.textContent = data.junction || ('Junction ' + selectedJunction);
    if (elCameraLabel)  elCameraLabel.textContent  = data.camera_label || selectedCamera;

    // Camera feed (only swap if URL changed and is non-empty)
    if (elCam && data.camera_url && elCam.src !== data.camera_url) {
      elCam.src = data.camera_url;
    }

    // Traffic state badge
    var state = (data.traffic_state || 'low').toLowerCase();
    var stateLabel = state.charAt(0).toUpperCase() + state.slice(1);
    if (elStateBadge) {
      elStateBadge.className = 'lv-state-badge badge-' + state;
    }
    if (elStateText) elStateText.textContent = stateLabel;

    // Metrics
    if (elPcu)  setText('lv-pcu',   data.pcu + '');
    if (elQueue) {
      var qEl = document.getElementById('lv-queue');
      if (qEl) qEl.innerHTML = data.queue_length_m + ' <span class="lv-stat-unit">m</span>';
    }
    if (elSpeed) {
      var spEl = document.getElementById('lv-speed');
      if (spEl) spEl.innerHTML = data.avg_speed_kmh + ' <span class="lv-stat-unit">km/h</span>';
    }

    // Last updated timestamp
    if (elLastUpdated) elLastUpdated.textContent = data.last_updated || '—';
  }

  /* ──────────────────────────────────────────────────────────────────────
     Live badge / online indicator
  ────────────────────────────────────────────────────────────────────── */
  function setOnline(isOnline) {
    if (!elLiveBadge) return;
    var textSpan = elLiveBadge.querySelector('span:last-child');
    if (isOnline) {
      elLiveBadge.classList.remove('offline');
      if (textSpan) textSpan.textContent = 'LIVE';
    } else {
      elLiveBadge.classList.add('offline');
      if (textSpan) textSpan.textContent = 'OFFLINE';
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Polling
  ────────────────────────────────────────────────────────────────────── */
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchAndRender, POLL_INTERVAL);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Snapshot
  ────────────────────────────────────────────────────────────────────── */
  if (btnSnapshot) {
    btnSnapshot.addEventListener('click', function () {
      // POST /api/snapshot — server returns image bytes with Content-Disposition
      // Use a temporary form submit trick to trigger browser download
      var form = document.createElement('form');
      form.method  = 'POST';
      form.action  = '/api/snapshot?junction=' + encodeURIComponent(selectedJunction);
      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);

      // Visual feedback
      flashBtn(btnSnapshot);
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Record toggle
  ────────────────────────────────────────────────────────────────────── */
  if (btnRecord) {
    btnRecord.addEventListener('click', function () {
      isRecording = !isRecording;
      applyRecordingUI(isRecording);

      fetch('/api/toggle_recording', {
        method:      'POST',
        credentials: 'same-origin',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ junction: selectedJunction, recording: isRecording }),
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          // Sync with server-confirmed state
          isRecording = !!data.recording;
          applyRecordingUI(isRecording);
        })
        .catch(function (err) {
          console.warn('[I²TMS live-video] toggle_recording error:', err);
        });
    });
  }

  function applyRecordingUI(recording) {
    if (elRecBadge) {
      elRecBadge.classList.toggle('visible', recording);
      elRecBadge.setAttribute('aria-hidden', String(!recording));
    }
    if (btnRecord) {
      btnRecord.classList.toggle('rec-active', recording);
      btnRecord.title = recording ? 'Stop Recording' : 'Record';
      btnRecord.setAttribute('aria-label', recording ? 'Stop recording' : 'Toggle recording');
    }
  }

  function toggleRecordingOff() {
    isRecording = false;
    applyRecordingUI(false);
    fetch('/api/toggle_recording', {
      method:      'POST',
      credentials: 'same-origin',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({ junction: selectedJunction, recording: false }),
    }).catch(function () {});
  }

  /* ──────────────────────────────────────────────────────────────────────
     PTZ toggle
  ────────────────────────────────────────────────────────────────────── */
  if (btnPTZ) {
    btnPTZ.addEventListener('click', function () {
      isPTZOpen = !isPTZOpen;
      togglePTZ(isPTZOpen);
      // Close cam dropdown if open
      if (isPTZOpen && isCamDropOpen) {
        isCamDropOpen = false;
        toggleCamDrop(false);
      }
    });
  }

  function togglePTZ(open) {
    if (elPtzOverlay) {
      elPtzOverlay.classList.toggle('visible', open);
      elPtzOverlay.setAttribute('aria-hidden', String(!open));
    }
    if (btnPTZ) btnPTZ.classList.toggle('active', open);
  }

  // PTZ button actions (mock feedback only)
  ['ptz-up','ptz-down','ptz-left','ptz-right','ptz-center','ptz-zoom-in','ptz-zoom-out'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        console.log('[I²TMS PTZ]', id, '— junction', selectedJunction);
        flashBtn(this);
      });
    }
  });

  /* ──────────────────────────────────────────────────────────────────────
     Change Camera
  ────────────────────────────────────────────────────────────────────── */
  if (btnChangeCam) {
    btnChangeCam.addEventListener('click', function () {
      isCamDropOpen = !isCamDropOpen;
      toggleCamDrop(isCamDropOpen);
      // Close PTZ if open
      if (isCamDropOpen && isPTZOpen) {
        isPTZOpen = false;
        togglePTZ(false);
      }
    });
  }

  function toggleCamDrop(open) {
    if (elCamDropdown) {
      elCamDropdown.classList.toggle('visible', open);
      elCamDropdown.setAttribute('aria-hidden', String(!open));
    }
    if (btnChangeCam) btnChangeCam.classList.toggle('active', open);
  }

  // Camera option selection
  var camOptions = document.querySelectorAll('.lv-cam-option');
  camOptions.forEach(function (opt) {
    opt.addEventListener('click', function (e) {
      e.stopPropagation();
      var cam = this.getAttribute('data-cam');
      selectedCamera = cam;

      // Update UI
      camOptions.forEach(function (o) { o.classList.remove('active'); });
      this.classList.add('active');
      if (elCameraLabel) elCameraLabel.textContent = cam;

      // Close dropdown
      isCamDropOpen = false;
      toggleCamDrop(false);
    });
  });

  /* ──────────────────────────────────────────────────────────────────────
     Full Screen
  ────────────────────────────────────────────────────────────────────── */
  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', function () {
      var panel = document.getElementById('lv-video-panel');
      if (!panel) return;
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(function () {});
      } else {
        panel.requestFullscreen().catch(function (err) {
          console.warn('[I²TMS live-video] fullscreen error:', err);
        });
      }
    });
  }

  // Update fullscreen button label on change
  document.addEventListener('fullscreenchange', function () {
    if (!btnFullscreen) return;
    var textNode = btnFullscreen.childNodes[1];
    if (document.fullscreenElement) {
      if (textNode) textNode.textContent = 'Exit Full Screen';
    } else {
      if (textNode) textNode.textContent = 'Full Screen';
    }
  });

  /* ──────────────────────────────────────────────────────────────────────
     Click-outside to close overlays
  ────────────────────────────────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    // Close PTZ if click is outside video area
    if (isPTZOpen && elPtzOverlay && !elPtzOverlay.contains(e.target) && e.target !== btnPTZ) {
      isPTZOpen = false;
      togglePTZ(false);
    }
    // Close cam dropdown if click is outside
    if (isCamDropOpen && elCamDropdown && !elCamDropdown.contains(e.target) && e.target !== btnChangeCam) {
      isCamDropOpen = false;
      toggleCamDrop(false);
    }
  });

  /* ──────────────────────────────────────────────────────────────────────
     Utility helpers
  ────────────────────────────────────────────────────────────────────── */
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function flashBtn(btn) {
    btn.style.transform = 'scale(0.92)';
    setTimeout(function () { btn.style.transform = ''; }, 130);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Init
  ────────────────────────────────────────────────────────────────────── */
  fetchAndRender();
  startPolling();

})();
