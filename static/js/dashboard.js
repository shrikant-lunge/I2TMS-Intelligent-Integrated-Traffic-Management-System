/**
 * I²TMS — dashboard.js
 *
 * Polls /api/dashboard_summary every 10 s and renders:
 *   · Stat cards  (total/active junctions, congestion, corridors)
 *   · Live junction cards (camera thumb, name, congestion badge)
 *   · Traffic trend line chart  (Chart.js 4.x)
 *   · Recent alerts list
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     Chart.js initialisation
  ────────────────────────────────────────────────────────────────────── */
  var trendChart = null;

  function initChart() {
    var canvas = document.getElementById('trend-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    trendChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label:           'High',
            data:            [],
            borderColor:     '#EF4444',
            borderWidth:     2,
            pointRadius:     0,
            pointHoverRadius: 4,
            fill:            false,
            tension:         0.4,
          },
          {
            label:           'Medium',
            data:            [],
            borderColor:     '#F59E0B',
            borderWidth:     2,
            pointRadius:     0,
            pointHoverRadius: 4,
            fill:            false,
            tension:         0.4,
          },
          {
            label:           'Low',
            data:            [],
            borderColor:     '#10B981',
            borderWidth:     2,
            pointRadius:     0,
            pointHoverRadius: 4,
            fill:            false,
            tension:         0.4,
          },
        ],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1A2942',
            titleColor:      '#fff',
            bodyColor:       'rgba(255,255,255,0.82)',
            padding:         10,
            cornerRadius:    8,
            boxPadding:      4,
          },
        },
        scales: {
          x: {
            grid:   { display: false },
            border: { display: false },
            ticks: {
              color:         '#9CA3AF',
              font:          { size: 11, family: 'Inter, sans-serif' },
              maxTicksLimit: 8,
              maxRotation:   0,
            },
          },
          y: {
            min:    0,
            max:    100,
            border: { display: false },
            grid:   { color: '#F3F4F6' },
            ticks: {
              color:     '#9CA3AF',
              font:      { size: 11, family: 'Inter, sans-serif' },
              stepSize:  25,
            },
          },
        },
        animation: { duration: 400 },
      },
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Fetch + render cycle
  ────────────────────────────────────────────────────────────────────── */
  function fetchAndRender() {
    fetch('/api/dashboard_summary', { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        renderStatCards(data);
        renderJunctions(data.live_junctions  || []);
        updateChart(data.traffic_trend       || {});
        renderAlerts(data.recent_alerts      || []);
      })
      .catch(function (err) {
        console.warn('[I²TMS dashboard] fetch error:', err);
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Stat cards
  ────────────────────────────────────────────────────────────────────── */
  function renderStatCards(data) {
    setText('stat-total-junctions',  data.total_junctions);
    setText('stat-active-junctions', data.active_junctions);
    setText('stat-active-corridors', data.active_corridors);

    var congEl = document.getElementById('stat-avg-congestion');
    if (congEl && data.avg_congestion !== undefined) {
      var level = String(data.avg_congestion).toLowerCase();
      congEl.innerHTML =
        '<span class="congestion-badge ' + esc(level) + '">' +
          esc(data.avg_congestion) +
        '</span>';
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Live junction cards
  ────────────────────────────────────────────────────────────────────── */
  function renderJunctions(junctions) {
    var grid = document.getElementById('junction-grid');
    if (!grid) return;

    if (!junctions.length) {
      grid.innerHTML =
        '<p style="color:#6B7280;font-size:13px;grid-column:1/-1;padding:8px 0">' +
        'No junction data available.</p>';
      return;
    }

    grid.innerHTML = junctions.map(function (j) {
      var status  = (j.status || 'low').toLowerCase();
      var label   = cap(status);
      var jid     = 'junction-' + esc(j.name.replace(/\s+/g, '').toLowerCase());
      /* Use real feed URL when available; fall back to static placeholder.
         TODO: swap /static/img/camera-placeholder.jpg for the live MJPEG/
         snapshot URL once teammates' detection pipeline exposes it. */
      var thumbSrc = j.thumbnail_url || '/static/img/camera-placeholder.jpg';
      var camHtml  = '<img src="' + esc(thumbSrc) + '" alt="' + esc(j.name) + ' camera feed" loading="lazy">';

      return (
        '<a href="' + esc(j.link || '#') + '" class="junction-card" id="' + jid + '">' +
          '<div class="junction-thumb">' +
            camHtml +
            '<span class="live-badge" aria-label="Live feed">LIVE</span>' +
          '</div>' +
          '<div class="junction-info">' +
            '<div class="junction-name">' + esc(j.name) + '</div>' +
            '<div class="congestion-dot">' +
              '<span class="dot ' + status + '" aria-hidden="true"></span>' +
              '<span class="text-' + status + '">' + label + '</span>' +
            '</div>' +
          '</div>' +
        '</a>'
      );
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Traffic trend chart
  ────────────────────────────────────────────────────────────────────── */
  function updateChart(trend) {
    if (!trendChart || !trend.labels) return;
    trendChart.data.labels           = trend.labels;
    trendChart.data.datasets[0].data = trend.high   || [];
    trendChart.data.datasets[1].data = trend.medium || [];
    trendChart.data.datasets[2].data = trend.low    || [];
    trendChart.update('none');   // suppress animation on poll updates
  }

  /* ──────────────────────────────────────────────────────────────────────
     Recent alerts list
  ────────────────────────────────────────────────────────────────────── */
  var WARN_ICON =
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>' +
      '<line x1="12" y1="9"  x2="12" y2="13"/>' +
      '<line x1="12" y1="17" x2="12.01" y2="17"/>' +
    '</svg>';

  function renderAlerts(alerts) {
    var list = document.getElementById('alerts-list');
    if (!list) return;

    if (!alerts.length) {
      list.innerHTML =
        '<p style="color:#6B7280;font-size:13px;text-align:center;padding:28px 0">No active alerts</p>';
      return;
    }

    list.innerHTML = alerts.map(function (a) {
      var sev = (a.severity || 'low').toLowerCase();
      return (
        '<div class="alert-row">' +
          '<div class="alert-icon ' + sev + '" aria-hidden="true">' + WARN_ICON + '</div>' +
          '<div class="alert-body">' +
            '<div class="alert-type">'     + esc(a.type     || '—') + '</div>' +
            '<div class="alert-location">' + esc(a.junction || '—') + '</div>' +
          '</div>' +
          '<div class="alert-time">' + esc(a.time || '') + '</div>' +
        '</div>'
      );
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Utility helpers
  ────────────────────────────────────────────────────────────────────── */
  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = (value !== undefined && value !== null) ? String(value) : '—';
  }

  function cap(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Boot
  ────────────────────────────────────────────────────────────────────── */
  initChart();
  fetchAndRender();
  setInterval(fetchAndRender, 10000);   // poll every 10 s

})();
