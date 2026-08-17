/**
 * I²TMS — adaptive-signals.js  (Screen 3: Adaptive Signals – Junction View)
 *
 * Responsibilities:
 *   · Instant auto-queue: each file upload is pushed to queue and processed
 *     immediately, without waiting for all four slots.
 *   · Sequential dequeue: only one direction is processed through the AI
 *     pipeline at a time; others wait in queue.
 *   · After AI result: uploaded media is shown in the lane-feed dashboard tile,
 *     stats are updated, and the signal light cycle runs (green → amber → red).
 *   · Wait times shown per direction for non-active signals.
 *   · Decision log panel records every significant event.
 *   · Junction selector, live polling, phase overlay, decision buttons.
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State
  ────────────────────────────────────────────────────────────────────── */
  var junctionNames = {
    'rahate-colony':   'Rahate Colony',
    'shankar-nagar':   'Shankar Nagar',
    'laxmi-nagar-sq':  'Laxmi Nagar Sq.',
    'dikshabhoomi-sq': 'Dikshabhoomi Sq.',
    'law-college-sq':  'Law College Sq.',
    'zero-mile-sq':    'Zero Mile Sq.'
  };

  var selectedJunction   = new URLSearchParams(window.location.search).get('junction') || 'rahate-colony';
  var countdown          = 0;
  var countdownTimer     = null;
  var pollTimer          = null;
  var sequenceRunning    = false;
  var uploadQueue        = [];
  var isProcessingQueue  = false;

  // Slots 0-3 are fixed directions; slot 4 is the "extra" clip
  var uploadSlots = [
    { direction: 'north', file: null, type: null, url: null, result: null },
    { direction: 'east',  file: null, type: null, url: null, result: null },
    { direction: 'south', file: null, type: null, url: null, result: null },
    { direction: 'west',  file: null, type: null, url: null, result: null },
    { direction: 'north', file: null, type: null, url: null, result: null }  // extra
  ];

  var directionOrder  = ['north', 'east', 'south', 'west'];
  var directionLabels = { north: 'North', east: 'East', south: 'South', west: 'West' };

  var activePhaseDirection    = null;
  var activePhaseState        = null;    // 'green' | 'yellow' | 'red'
  var activePhaseTimeRemaining = 0;

  /* ──────────────────────────────────────────────────────────────────────
     Junction selector
  ────────────────────────────────────────────────────────────────────── */
  var junctionSelect = document.getElementById('junction-select');
  if (junctionSelect && junctionSelect.value) selectedJunction = junctionSelect.value;
  if (junctionSelect) {
    junctionSelect.addEventListener('change', function () {
      selectedJunction = this.value;
      var url = new URL(window.location.href);
      url.searchParams.set('junction', selectedJunction);
      history.replaceState(null, '', url.toString());
      updateJunctionLabels();
      countdown = 0;
      fetchAndRender();
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Upload panel  – 5 slots (0-3 fixed direction, 4 extra w/ picker)
  ────────────────────────────────────────────────────────────────────── */
  function initUploadPanel() {
    for (var i = 0; i < 5; i++) {
      (function (slotIndex) {
        var input        = document.getElementById('video-upload-'  + slotIndex);
        var imagePreview = document.getElementById('image-preview-' + slotIndex);
        var videoPreview = document.getElementById('video-preview-' + slotIndex);
        var meta         = document.getElementById('upload-meta-'   + slotIndex);

        if (!input) return;

        // Extra slot (4) — direction driven by select
        if (slotIndex === 4) {
          var dirPicker = document.getElementById('extra-slot-dir-4');
          if (dirPicker) {
            dirPicker.addEventListener('change', function () {
              uploadSlots[4].direction = this.value;
            });
          }
        }

        input.addEventListener('change', function () {
          var file = input.files && input.files[0] ? input.files[0] : null;
          var slot = uploadSlots[slotIndex];

          if (slot.url) { URL.revokeObjectURL(slot.url); slot.url = null; }

          slot.file   = file;
          slot.result = null;
          slot.type   = file ? (file.type || '') : null;

          if (imagePreview) {
            imagePreview.classList.remove('is-visible');
            imagePreview.removeAttribute('src');
          }
          if (videoPreview) {
            videoPreview.classList.remove('is-visible');
            videoPreview.removeAttribute('src');
            videoPreview.load();
          }

          if (file) {
            var objectUrl = URL.createObjectURL(file);
            slot.url = objectUrl;

            if (slot.type && slot.type.indexOf('image/') === 0) {
              if (imagePreview) {
                imagePreview.src = objectUrl;
                imagePreview.classList.add('is-visible');
              }
            } else if (videoPreview) {
              videoPreview.src = objectUrl;
              videoPreview.classList.add('is-visible');
              videoPreview.load();
              videoPreview.play().catch(function () {});
            }
          }

          if (meta) {
            meta.textContent = file
              ? (file.name + ' · ' + Math.round(file.size / 1024) + ' KB')
              : 'No file selected';
          }

          setSlotState(slotIndex, file ? 'has-file' : 'missing');
          setSlotStatus(slotIndex, file ? 'Queued — waiting for pipeline' : 'Waiting for file');
          updateSequenceReadiness();

          if (file) {
            if (uploadQueue.indexOf(slotIndex) === -1) uploadQueue.push(slotIndex);
            processUploadQueue();
          }
        });
      })(i);
    }

    var processBtn = document.getElementById('btn-process-first');
    if (processBtn) {
      processBtn.addEventListener('click', function () {
        uploadSlots.forEach(function (slot, index) {
          if (slot.file && uploadQueue.indexOf(index) === -1) uploadQueue.push(index);
        });
        processUploadQueue();
      });
    }

    updateSequenceReadiness();
  }

  /* ──────────────────────────────────────────────────────────────────────
     Upload card helpers
  ────────────────────────────────────────────────────────────────────── */
  function getSlotCard(slotIndex) {
    return document.querySelector('.upload-card[data-slot="' + slotIndex + '"]');
  }

  function setSlotState(slotIndex, state) {
    var card = getSlotCard(slotIndex);
    if (!card) return;
    card.classList.remove('has-file', 'processing', 'completed', 'missing');
    if (state) card.classList.add(state);
  }

  function setSlotStatus(slotIndex, message) {
    var el = document.getElementById('slot-status-' + slotIndex);
    if (el) el.textContent = message;
  }

  function updateSequenceReadiness() {
    var readyCount = uploadSlots.filter(function (s) { return !!s.file; }).length;
    var processBtn = document.getElementById('btn-process-first');
    setUploadStatus(sequenceRunning
      ? 'Processing…'
      : (readyCount > 0 ? readyCount + ' upload(s) ready' : 'Waiting for uploads'));

    if (processBtn) {
      processBtn.disabled  = sequenceRunning && readyCount === 0;
      processBtn.textContent = sequenceRunning ? 'Running…' : 'Run Sequence';
    }
  }

  function setUploadStatus(message) {
    var el = document.getElementById('upload-status');
    if (el) el.textContent = message;
  }

  /* ──────────────────────────────────────────────────────────────────────
     Queue processor
  ────────────────────────────────────────────────────────────────────── */
  function processUploadQueue() {
    if (isProcessingQueue || uploadQueue.length === 0) return;

    isProcessingQueue = true;
    sequenceRunning   = true;
    updateSequenceReadiness();
    stopLivePolling();

    var slotIndex = uploadQueue.shift();

    runSequenceStep(slotIndex)
      .then(function () {
        isProcessingQueue = false;
        if (uploadQueue.length > 0) {
          processUploadQueue();        // process next item
        } else {
          sequenceRunning = false;
          setUploadStatus('All queued clips processed');
          showToast('Signal sequence complete', 'success');
          updateSequenceReadiness();
          startLivePolling();
          fetchAndRender();
        }
      })
      .catch(function (err) {
        console.warn('[I²TMS adaptive-signals] sequence error:', err);
        addDecisionLog('error', 'Pipeline error: ' + (err && err.message ? err.message : 'unknown'));
        isProcessingQueue = false;
        sequenceRunning   = false;
        setUploadStatus('Sequence failed');
        showToast('Sequence failed while processing uploads', 'error');
        updateSequenceReadiness();
        startLivePolling();
        fetchAndRender();
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Single-step: process one slot through the pipeline
  ────────────────────────────────────────────────────────────────────── */
  function runSequenceStep(slotIndex) {
    var slot = uploadSlots[slotIndex];
    if (!slot || !slot.file) return Promise.resolve();

    var direction     = slot.direction;
    var directionName = directionLabels[direction] || direction;
    var formData      = new FormData();
    var file          = slot.file;

    setSlotState(slotIndex, 'processing');
    setSlotStatus(slotIndex, 'Analysing ' + directionName + '…');
    setUploadStatus('AI pipeline: ' + directionName + '…');
    setLaneState(direction, 'upload-active');

    // Show uploaded media immediately in the dashboard tile (before API returns)
    setLaneMedia(direction, slot.url, slot.type);
    showCurrentDirection(direction, 0, 'red');   // show RED while calculating

    addDecisionLog('compute',
      'Rahate Colony · ' + directionName + '\nRunning AI pipeline — vehicle detection, PCU, Webster…');

    formData.append('junction_name', 'Rahate Colony Square');
    formData.append('direction', direction);
    formData.append('file', file, file.name);

    return fetch('/api/signal/compute/green-time', {
      method:      'POST',
      credentials: 'same-origin',
      body:        formData,
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        slot.result = data;
        applySlotResult(slotIndex, data);
        renderSequenceSummary();

        var greenTime   = (data && data.signal && data.signal.green_time) || 15;
        var vc          = (data && data.vehicle_count) || {};
        var pcu         = (data && data.pcu) || {};
        var cong        = (data && data.congestion) || {};
        var traffic     = (data && data.traffic_state) || {};
        var webster     = (data && data.webster) || {};

        // Build reason string from key factors
        var reasons = [];
        if (cong.level === 'HIGH')   reasons.push('High congestion');
        if (cong.level === 'MEDIUM') reasons.push('Medium congestion');
        if (traffic.queue_length && traffic.queue_length >= 8) reasons.push('Long queue (' + traffic.queue_length + ')');
        if (traffic.waiting_time && traffic.waiting_time >= 8) reasons.push('High wait time');
        if (pcu.demand && pcu.demand >= 16) reasons.push('High PCU demand');
        if (!reasons.length) reasons.push('Low traffic demand');

        var logMsg =
          'Rahate Colony · ' + directionName + '\n' +
          'Vehicles: ' + (vc.total !== undefined ? vc.total : '—') + '\n' +
          'PCU: ' + (pcu.demand !== undefined ? pcu.demand : '—') + '\n' +
          'Density: ' + (traffic.traffic_level || '—') + '\n' +
          'Congestion: ' + (cong.level || '—') + '\n' +
          'Green allocated: ' + greenTime + 's\n' +
          'Reason: ' + reasons.join(', ');

        addDecisionLog('green', logMsg);

        return runDynamicSignalCycle(direction, greenTime);
      })
      .then(function () {
        setSlotState(slotIndex, 'completed');
        setSlotStatus(slotIndex, directionName + ' ✓ cycle done');
        setLaneState(direction, 'upload-complete');
        addDecisionLog('done', 'Rahate Colony · ' + directionName + '\nSignal cycle complete — next direction queued.');
      });
  }


  /* ──────────────────────────────────────────────────────────────────────
     Lane media helpers — show image or video in dashboard tile
  ────────────────────────────────────────────────────────────────────── */
  function setLaneMedia(direction, objectUrl, fileType) {
    if (!objectUrl) return;

    var imgEl = document.getElementById('lane-img-' + direction);
    var vidEl = document.getElementById('lane-vid-' + direction);

    // Reset both
    if (imgEl) { imgEl.classList.remove('is-visible'); imgEl.removeAttribute('src'); }
    if (vidEl) { vidEl.classList.remove('is-visible'); vidEl.removeAttribute('src'); vidEl.load(); }

    if (fileType && fileType.indexOf('image/') === 0) {
      if (imgEl) { imgEl.src = objectUrl; imgEl.classList.add('is-visible'); }
    } else {
      if (vidEl) {
        vidEl.src = objectUrl;
        vidEl.classList.add('is-visible');
        vidEl.load();
        vidEl.play().catch(function () {});
      }
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     API fetch + render cycle (live polling)
  ────────────────────────────────────────────────────────────────────── */
  function fetchAndRender() {
    if (sequenceRunning) return;

    fetch('/api/junction_signal?junction=' + encodeURIComponent(selectedJunction), {
      credentials: 'same-origin',
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        setConnectionStatus(true);
        if (Math.abs(data.time_remaining - countdown) > 3 || countdown <= 0) {
          countdown = data.time_remaining;
          startCountdown();
        }
        renderPhaseOverlay(data);
        renderTrafficState(data.traffic_state  || {});
        renderSignalPlan(data.recommended_plan || []);
        renderLaneQuadrants(data.lanes || []);
        if (data.junction) updateJunctionLabels(data.junction);
        updateCameraFeed(data.camera_url || '');
      })
      .catch(function (err) {
        setConnectionStatus(false);
        console.warn('[I²TMS adaptive-signals] fetch error:', err);
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Connection-status indicator (LIVE badge)
  ────────────────────────────────────────────────────────────────────── */
  function setConnectionStatus(isOnline) {
    var badge = document.getElementById('as-live-badge');
    if (!badge) return;
    var textSpan = badge.querySelector('span:last-child');
    if (isOnline) {
      badge.classList.remove('offline');
      if (textSpan) textSpan.textContent = 'LIVE';
    } else {
      badge.classList.add('offline');
      if (textSpan) textSpan.textContent = 'OFFLINE';
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Countdown timer (local, synced each poll)
  ────────────────────────────────────────────────────────────────────── */
  function startCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    updateCountdownDisplay(countdown);
    countdownTimer = setInterval(function () {
      if (countdown > 0) { countdown--; updateCountdownDisplay(countdown); }
    }, 1000);
  }

  function updateCountdownDisplay(val) {
    var el = document.getElementById('phase-countdown');
    if (el) el.textContent = val + 's';
  }

  /* ──────────────────────────────────────────────────────────────────────
     Phase overlay
  ────────────────────────────────────────────────────────────────────── */
  function renderPhaseOverlay(data) {
    setText('phase-label', data.current_phase  || '—');
    setText('cycle-time',  data.cycle_time_sec || '—');
    updateCountdownDisplay(countdown);

    var emgIndicator = document.getElementById('emg-priority-indicator');
    if (emgIndicator) emgIndicator.style.display = data.emergency_priority ? 'inline-block' : 'none';

    // Update mini lamp-stack inside hidden overlay (used for JS reference only)
    var light    = (data.light || 'green').toLowerCase();
    var lampRed  = document.getElementById('lamp-red');
    var lampAmber = document.getElementById('lamp-amber');
    var lampGreen = document.getElementById('lamp-green');
    if (lampRed)   lampRed.setAttribute  ('data-active', String(light === 'red'));
    if (lampAmber) lampAmber.setAttribute('data-active', String(light === 'amber'));
    if (lampGreen) lampGreen.setAttribute('data-active', String(light === 'green'));
  }

  /* ──────────────────────────────────────────────────────────────────────
     Traffic State tiles
  ────────────────────────────────────────────────────────────────────── */
  function renderTrafficState(state) {
    setText('m-pcu',   state.pcu_overall   !== undefined ? state.pcu_overall   : '—');
    setText('m-queue', state.queue_length_m !== undefined ? state.queue_length_m : '—');
    setText('m-speed', state.avg_speed      !== undefined ? state.avg_speed      : '—');

    var densEl = document.getElementById('m-density');
    if (densEl && state.density) {
      var d = state.density.toLowerCase();
      densEl.innerHTML = '<span class="badge badge-' + esc(d) + '">' + cap(d) + '</span>';
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Recommended Signal Plan bars
  ────────────────────────────────────────────────────────────────────── */
  function renderSignalPlan(plan) {
    var container = document.getElementById('signal-plan');
    if (!container || !plan.length) return;

    var maxDur = Math.max.apply(null, plan.map(function (p) { return p.duration_sec; }));
    container.innerHTML = plan.map(function (p) {
      var pct = maxDur > 0 ? ((p.duration_sec / maxDur) * 100).toFixed(1) : '0';
      return (
        '<div class="phase-row">' +
          '<span class="phase-name">' + esc(p.phase) + '</span>' +
          '<div class="phase-bar-track"><div class="phase-bar-fill" style="width:' + pct + '%"></div></div>' +
          '<span class="phase-duration">' + esc(String(p.duration_sec)) + 's</span>' +
        '</div>'
      );
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Apply pipeline result to upload card + traffic state panel
  ────────────────────────────────────────────────────────────────────── */
  function applySlotResult(slotIndex, result) {
    if (!result) return;
    var slot      = uploadSlots[slotIndex];
    var vehicle   = result.vehicle_count  || {};
    var traffic   = result.traffic_state  || {};
    var pcu       = result.pcu            || {};
    var congestion = result.congestion    || {};
    var signal    = result.signal         || {};
    var direction = slot ? slot.direction : 'north';
    var directionName = directionLabels[direction] || direction;

    // Update global traffic state panel
    setText('m-pcu',   pcu.demand       !== undefined ? pcu.demand       : '—');
    setText('m-queue', traffic.queue_length !== undefined ? traffic.queue_length : '—');
    setText('m-speed', traffic.average_speed !== undefined ? traffic.average_speed : '—');

    var densEl = document.getElementById('m-density');
    if (densEl) {
      var dl = (traffic.traffic_level || congestion.level || 'LOW').toLowerCase();
      densEl.innerHTML = '<span class="badge badge-' + esc(dl) + '">' + cap(dl) + '</span>';
    }

    // Update Webster signal plan
    if (result.webster && result.webster.signal_plan && result.webster.signal_plan.length) {
      renderSignalPlan(result.webster.signal_plan.map(function (item) {
        return {
          phase: item.direction_label || item.direction || 'Phase',
          duration_sec: item.green_time_sec || signal.green_time || 0,
        };
      }));
    }

    // Update lane card stats (Vehicles, Density, PCU)
    var laneCard = document.querySelector('.lane-card[data-direction="' + escAttr(direction) + '"]');
    if (laneCard) {
      laneCard.classList.add('focused-upload');
      setScopedText(laneCard, '[data-count]',   vehicle.total   !== undefined ? vehicle.total   : '—');
      setScopedText(laneCard, '[data-density]', congestion.level || traffic.traffic_level || '—');
      setScopedText(laneCard, '[data-pcu]',     pcu.demand      !== undefined ? pcu.demand      : '—');
    }

    // Update pipeline result panel
    var resultPanel = document.getElementById('pipeline-result');
    if (resultPanel) resultPanel.innerHTML = renderSequenceSummaryHtml();

    setSlotStatus(slotIndex,
      directionName + ' · ' + (vehicle.total !== undefined ? vehicle.total : '—') + ' veh · PCU ' +
      (pcu.demand !== undefined ? pcu.demand : '—') + ' · ' +
      (signal.green_time !== undefined ? signal.green_time : '—') + 's green');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Sequence summary HTML
  ────────────────────────────────────────────────────────────────────── */
  function renderSequenceSummaryHtml() {
    var rows = uploadSlots.slice(0, 4).map(function (slot) {
      var result   = slot.result || {};
      var signal   = result.signal || {};
      var traffic  = result.traffic_state || {};
      var pcu      = result.pcu || {};
      var congestion = result.congestion || {};
      var vc       = result.vehicle_count || {};
      var hasResult = !!signal.green_time;

      var label    = directionLabels[slot.direction] || slot.direction;
      var status   = hasResult ? ('Green ' + signal.green_time + 's') : (slot.file ? 'Processing…' : 'Waiting');
      var count    = vc.total !== undefined ? vc.total : '—';
      var pcuVal   = pcu.demand !== undefined ? pcu.demand : '—';
      var density  = congestion.level || traffic.traffic_level || '—';

      var valueColor = hasResult ? '#059669' : '#6B7280';

      return (
        '<div class="sequence-step">' +
          '<span class="sequence-step-label">' + esc(label) + '</span>' +
          '<span class="sequence-step-value" style="color:' + (hasResult ? '#059669' : '#1A2942') + '">' + esc(status) + '</span>' +
          '<div class="upload-meta" style="margin-left:auto;text-align:right;font-size:11px;">' +
            esc(String(count)) + ' veh &middot; PCU&nbsp;' + esc(String(pcuVal)) +
            (density !== '—' ? ' &middot; ' + esc(density) : '') +
          '</div>' +
        '</div>'
      );
    }).join('');

    return '<div class="sequence-progress">' + rows + '</div>';
  }


  function renderSequenceSummary() {
    var resultPanel = document.getElementById('pipeline-result');
    if (resultPanel) resultPanel.innerHTML = renderSequenceSummaryHtml();
  }

  /* ──────────────────────────────────────────────────────────────────────
     Lane state helpers
  ────────────────────────────────────────────────────────────────────── */
  function setLaneState(direction, state) {
    var laneCard = document.querySelector('.lane-card[data-direction="' + escAttr(direction) + '"]');
    if (!laneCard) return;
    laneCard.classList.remove('upload-ready', 'upload-active', 'upload-complete');
    if (state) laneCard.classList.add(state);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Wait-time calculation (for red signals)
  ────────────────────────────────────────────────────────────────────── */
  function getGreenTimeFor(direction) {
    var slot = null;
    for (var i = 0; i < uploadSlots.length; i++) {
      if (uploadSlots[i].direction === direction && uploadSlots[i].result) {
        slot = uploadSlots[i];
        break;
      }
    }
    if (slot && slot.result && slot.result.signal && slot.result.signal.green_time !== undefined) {
      return slot.result.signal.green_time;
    }
    return 30;
  }

  function calculateWaitTime(dir) {
    if (dir === activePhaseDirection) return 0;

    var order      = ['north', 'east', 'south', 'west'];
    var activeIdx  = order.indexOf(activePhaseDirection);
    var targetIdx  = order.indexOf(dir);
    if (activeIdx === -1 || targetIdx === -1) return 0;

    var totalWait  = 0;
    var currentIdx = activeIdx;

    while (currentIdx !== targetIdx) {
      if (currentIdx === activeIdx) {
        totalWait += activePhaseTimeRemaining;
      } else {
        var dirAtIdx = order[currentIdx];
        totalWait += getGreenTimeFor(dirAtIdx) + 5;   // green + 3s amber + 2s red clearance
      }
      currentIdx = (currentIdx + 1) % 4;
    }
    return Math.round(totalWait);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Update all lane-card stats grid displays
  ────────────────────────────────────────────────────────────────────── */
  function updateAllLaneDisplays() {
    updateCountdownDisplay(countdown);

    directionOrder.forEach(function (dir) {
      var card = document.querySelector('.lane-card[data-direction="' + dir + '"]');
      if (!card) return;

      var signalValEl = card.querySelector('[data-signal]');
      var timerEl     = card.querySelector('[data-time]');

      if (dir === activePhaseDirection) {
        var phaseText = 'GREEN';
        var colClass  = 'val-green';
        if (activePhaseState === 'yellow') { phaseText = 'AMBER';  colClass = 'val-yellow'; }
        else if (activePhaseState === 'red') { phaseText = 'RED';  colClass = 'val-red'; }

        if (signalValEl) { signalValEl.textContent = phaseText; signalValEl.className = 'lane-stat-value ' + colClass; }
        if (timerEl)     timerEl.textContent = activePhaseTimeRemaining + 's';
      } else {
        var waitTime = calculateWaitTime(dir);
        if (signalValEl) { signalValEl.textContent = 'RED'; signalValEl.className = 'lane-stat-value val-red'; }
        if (timerEl)     timerEl.textContent = (waitTime > 0 ? waitTime + 's' : '—');
      }
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Show current direction in overlay + update all lane bulbs
  ────────────────────────────────────────────────────────────────────── */
  function showCurrentDirection(direction, seconds, light) {
    renderPhaseOverlay({
      current_phase:      (directionLabels[direction] || direction).toUpperCase(),
      cycle_time_sec:     seconds,
      light:              light || 'green',
      emergency_priority: false,
    });

    // Update lane-card signal bulbs for every direction
    document.querySelectorAll('.lane-card').forEach(function (card) {
      var d     = card.getAttribute('data-direction');
      var bulbs = card.querySelectorAll('.signal-bulb');
      bulbs.forEach(function (b) { b.classList.remove('active'); });

      var activeLight = (d === direction) ? (light || 'green') : 'red';
      var activeBulb  = card.querySelector('.signal-bulb.' + activeLight);
      if (activeBulb) activeBulb.classList.add('active');
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Dynamic signal cycle: Green → Amber → Red
  ────────────────────────────────────────────────────────────────────── */
  function runDynamicSignalCycle(direction, greenTime) {
    activePhaseDirection = direction;
    return new Promise(function (resolve) {

      // 1. GREEN phase
      activePhaseState = 'green';
      showCurrentDirection(direction, greenTime, 'green');
      addDecisionLog('green', (directionLabels[direction] || direction) + ': GREEN for ' + greenTime + 's');

      runPhaseCountdown(greenTime).then(function () {
        // 2. AMBER phase
        activePhaseState = 'yellow';
        showCurrentDirection(direction, 3, 'amber');
        addDecisionLog('yellow', (directionLabels[direction] || direction) + ': AMBER 3s');
        return runPhaseCountdown(3);
      }).then(function () {
        // 3. RED clearance
        activePhaseState = 'red';
        showCurrentDirection(direction, 2, 'red');
        addDecisionLog('red', (directionLabels[direction] || direction) + ': RED clearance 2s');
        return runPhaseCountdown(2);
      }).then(function () {
        resolve();
      });
    });
  }

  function runPhaseCountdown(seconds) {
    var duration = Math.max(0, Math.round(Number(seconds) || 0));
    clearCountdown();
    countdown                = duration;
    activePhaseTimeRemaining = duration;
    updateAllLaneDisplays();

    return new Promise(function (resolve) {
      if (duration <= 0) { resolve(); return; }

      countdownTimer = setInterval(function () {
        if (activePhaseTimeRemaining > 0) {
          activePhaseTimeRemaining--;
          countdown = activePhaseTimeRemaining;
          updateAllLaneDisplays();
        }
        if (activePhaseTimeRemaining <= 0) {
          clearCountdown();
          resolve();
        }
      }, 1000);
    });
  }

  function clearCountdown() {
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  }

  function stopLivePolling()  {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  function startLivePolling() {
    if (!pollTimer) pollTimer = setInterval(fetchAndRender, 3000);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Directional quadrant lane cards (live-poll data)
  ────────────────────────────────────────────────────────────────────── */
  function renderLaneQuadrants(lanes) {
    if (!lanes.length) return;

    lanes.forEach(function (lane) {
      var key  = String(lane.direction || '').toLowerCase();
      var card = document.querySelector('.lane-card[data-direction="' + escAttr(key) + '"]');
      if (!card) return;

      setScopedText(card, '[data-count]',   lane.count);
      setScopedText(card, '[data-density]', lane.density);
      setScopedText(card, '[data-pcu]',     lane.pcu !== undefined ? lane.pcu : '—');

      var light    = String(lane.signal || 'red').toLowerCase();
      var phaseText = 'RED';
      var colClass  = 'val-red';
      if (light === 'green') { phaseText = 'GREEN'; colClass = 'val-green'; }
      else if (light === 'amber') { phaseText = 'AMBER'; colClass = 'val-yellow'; }

      var signalValEl = card.querySelector('[data-signal]');
      var timerEl     = card.querySelector('[data-time]');
      if (signalValEl) { signalValEl.textContent = phaseText; signalValEl.className = 'lane-stat-value ' + colClass; }
      if (timerEl)     timerEl.textContent = (lane.time_sec !== undefined ? lane.time_sec + 's' : '—');

      var bulbs = card.querySelectorAll('.signal-bulb');
      bulbs.forEach(function (b) { b.classList.remove('active'); });
      var activeBulb = card.querySelector('.signal-bulb.' + light);
      if (activeBulb) activeBulb.classList.add('active');
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Camera feed
  ────────────────────────────────────────────────────────────────────── */
  function updateCameraFeed(url) {
    if (!url) return;
    var cam = document.getElementById('junction-cam');
    if (cam && cam.src !== url) cam.src = url;
  }

  /* ──────────────────────────────────────────────────────────────────────
     Decision Log panel
  ────────────────────────────────────────────────────────────────────── */
  function addDecisionLog(type, message) {
    var container = document.getElementById('decision-log');
    if (!container) return;

    // Remove empty placeholder
    var emptyEl = container.querySelector('.decision-log-empty');
    if (emptyEl) emptyEl.remove();

    var now = new Date();
    var timeStr = ('0' + now.getHours()).slice(-2) + ':' +
                  ('0' + now.getMinutes()).slice(-2) + ':' +
                  ('0' + now.getSeconds()).slice(-2);

    // Split message on \n — first line is title, rest are detail lines
    var lines = message.split('\n');
    var title  = lines[0] || '';
    var details = lines.slice(1);

    var detailHtml = '';
    if (details.length) {
      detailHtml = '<div class="decision-log-detail">' +
        details.map(function (l) { return '<span>' + esc(l) + '</span>'; }).join('') +
      '</div>';
    }

    var entry = document.createElement('div');
    entry.className = 'decision-log-entry type-' + esc(type);
    entry.innerHTML =
      '<span class="decision-log-dot"></span>' +
      '<div class="decision-log-body">' +
        '<span class="decision-log-title">' + esc(title) + '</span>' +
        detailHtml +
      '</div>' +
      '<span class="decision-log-time">' + esc(timeStr) + '</span>';

    // Prepend (newest at top)
    container.insertBefore(entry, container.firstChild);

    // Keep max 40 entries
    var entries = container.querySelectorAll('.decision-log-entry');
    if (entries.length > 40) {
      for (var i = 40; i < entries.length; i++) entries[i].remove();
    }
  }


  var clearLogBtn = document.getElementById('btn-clear-log');
  if (clearLogBtn) {
    clearLogBtn.addEventListener('click', function () {
      var container = document.getElementById('decision-log');
      if (container) {
        container.innerHTML = '<div class="decision-log-empty">No decisions recorded yet.</div>';
      }
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Action helper (POST)
  ────────────────────────────────────────────────────────────────────── */
  function postAction(endpoint, body) {
    return fetch(endpoint, {
      method:      'POST',
      credentials: 'same-origin',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify(body),
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Decision buttons
  ────────────────────────────────────────────────────────────────────── */
  var btnApply    = document.getElementById('btn-apply');
  var btnHold     = document.getElementById('btn-hold');
  var btnOverride = document.getElementById('btn-override');

  if (btnApply) {
    btnApply.addEventListener('click', function () {
      btnApply.disabled = true;
      postAction('/api/apply_plan', { junction: selectedJunction })
        .then(function (data) {
          showToast(data.message || 'Plan applied', 'success');
          addDecisionLog('done', 'Plan applied for ' + (junctionNames[selectedJunction] || selectedJunction));
          fetchAndRender();
        })
        .catch(function () { showToast('Error applying plan', 'error'); })
        .finally(function () { btnApply.disabled = false; });
    });
  }

  if (btnHold) {
    btnHold.addEventListener('click', function () {
      btnHold.disabled = true;
      postAction('/api/hold_current', { junction: selectedJunction })
        .then(function (data) {
          showToast(data.message || 'Holding current phase');
          addDecisionLog('compute', 'Holding current phase');
        })
        .catch(function () { showToast('Error holding plan', 'error'); })
        .finally(function () { btnHold.disabled = false; });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Manual Override Modal
  ────────────────────────────────────────────────────────────────────── */
  var modalOverlay = document.getElementById('modal-overlay');
  var modalError   = document.getElementById('modal-error');

  function openModal() {
    var labelText = junctionNames[selectedJunction] || selectedJunction;
    var el1 = document.getElementById('override-junction-name');
    var el2 = document.getElementById('modal-junction-label');
    if (el1) el1.textContent = labelText;
    if (el2) el2.textContent = labelText;
    if (modalError) modalError.textContent = '';
    modalOverlay.classList.add('open');
    modalOverlay.removeAttribute('aria-hidden');
    var firstInput = document.getElementById('override-phase');
    if (firstInput) setTimeout(function () { firstInput.focus(); }, 80);
  }

  function closeModal() {
    modalOverlay.classList.remove('open');
    modalOverlay.setAttribute('aria-hidden', 'true');
    if (modalError) modalError.textContent = '';
  }

  if (btnOverride) btnOverride.addEventListener('click', openModal);

  var modalCloseBtn  = document.getElementById('modal-close');
  var modalCancelBtn = document.getElementById('btn-modal-cancel') || document.getElementById('cancel-override');
  if (modalCloseBtn)  modalCloseBtn.addEventListener('click', closeModal);
  if (modalCancelBtn) modalCancelBtn.addEventListener('click', closeModal);

  if (modalOverlay) {
    modalOverlay.addEventListener('click', function (e) { if (e.target === modalOverlay) closeModal(); });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('open')) closeModal();
  });

  var btnModalApply = document.getElementById('btn-modal-apply');
  if (btnModalApply) {
    btnModalApply.addEventListener('click', function () {
      var phase    = document.getElementById('override-phase').value;
      var durRaw   = document.getElementById('override-duration').value;
      var duration = parseInt(durRaw, 10);

      if (!duration || duration < 5 || duration > 180) {
        if (modalError) modalError.textContent = 'Duration must be between 5 and 180 seconds.';
        return;
      }

      btnModalApply.disabled = true;
      postAction('/api/manual_override', {
        junction:     selectedJunction,
        phase:        phase,
        duration_sec: duration,
      })
        .then(function (data) {
          closeModal();
          showToast(data.message || 'Override applied', 'success');
          addDecisionLog('done', 'Manual override: ' + phase + ' for ' + duration + 's');
          countdown = duration;
          startCountdown();
          setText('phase-label', phase);
          fetchAndRender();
        })
        .catch(function () {
          if (modalError) modalError.textContent = 'Error applying override. Please try again.';
        })
        .finally(function () { btnModalApply.disabled = false; });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Toast notifications
  ────────────────────────────────────────────────────────────────────── */
  function showToast(msg, type) {
    var t = document.createElement('div');
    t.className = 'as-toast' + (type ? ' ' + type : '');
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { t.classList.add('visible'); });
    });
    setTimeout(function () {
      t.classList.remove('visible');
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 300);
    }, 3200);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Utility helpers
  ────────────────────────────────────────────────────────────────────── */
  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = (value !== undefined && value !== null) ? String(value) : '—';
  }

  function setScopedText(root, selector, value) {
    var el = root.querySelector(selector);
    if (el) el.textContent = (value !== undefined && value !== null) ? String(value) : '—';
  }

  function getJunctionName() { return junctionNames[selectedJunction] || selectedJunction; }

  function updateJunctionLabels(serverName) {
    var label = serverName || getJunctionName();
    setText('video-junction-label', label);
    setText('override-junction-name', label);
  }

  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

  function esc(s) {
    return String(s)
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;')
      .replace(/'/g,  '&#39;');
  }

  function escAttr(s) {
    return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Boot
  ────────────────────────────────────────────────────────────────────── */
  initUploadPanel();
  updateJunctionLabels();
  fetchAndRender();
  startLivePolling();

})();
