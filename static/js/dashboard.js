/**
 * I²TMS — dashboard.js
 *
 * Polls /api/dashboard_summary every 10 s and renders:
 *   · Stat cards  (total/active junctions, congestion, active corridors)
 *   · Live junction cards
 *   · Traffic trend line chart  (Chart.js 4.x)  — DB-backed, no random data
 *   · Recent Emergency Corridors list
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
            label:            'High',
            data:             [],
            borderColor:      '#EF4444',
            borderWidth:      2,
            pointRadius:      0,
            pointHoverRadius: 4,
            fill:             false,
            tension:          0.4,
          },
          {
            label:            'Medium',
            data:             [],
            borderColor:      '#F59E0B',
            borderWidth:      2,
            pointRadius:      0,
            pointHoverRadius: 4,
            fill:             false,
            tension:          0.4,
          },
          {
            label:            'Low',
            data:             [],
            borderColor:      '#10B981',
            borderWidth:      2,
            pointRadius:      0,
            pointHoverRadius: 4,
            fill:             false,
            tension:          0.4,
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
            border: { display: false },
            grid:   { color: '#F3F4F6' },
            ticks: {
              color:    '#9CA3AF',
              font:     { size: 11, family: 'Inter, sans-serif' },
              stepSize: 10,
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
        renderJunctions(data.live_junctions    || []);
        updateChart(data.traffic_trend         || {});
        renderCorridors(data.recent_corridors  || []);
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
      var status   = (j.status || 'low').toLowerCase();
      var label    = cap(status);
      var jid      = 'junction-' + esc(j.name.replace(/\s+/g, '').toLowerCase());
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
    if (!trendChart) return;

    // No data state — show message overlay instead of empty chart
    var wrap = document.querySelector('.chart-wrap');
    var emptyOverlay = document.getElementById('trend-empty-state');

    if (!trend.labels || trend.labels.length === 0) {
      if (!emptyOverlay && wrap) {
        var overlay = document.createElement('div');
        overlay.id = 'trend-empty-state';
        overlay.style.cssText =
          'position:absolute;inset:0;display:flex;align-items:center;' +
          'justify-content:center;background:rgba(255,255,255,0.92);' +
          'border-radius:8px;z-index:2;padding:16px;text-align:center;';
        overlay.innerHTML =
          '<p style="color:#6B7280;font-size:13px;line-height:1.5;max-width:280px;">' +
          (trend.empty_message ||
            'No historical traffic data available yet. ' +
            'Data will appear once the adaptive-signal pipeline processes its first feed.') +
          '</p>';
        wrap.style.position = 'relative';
        wrap.appendChild(overlay);
      }
      return;
    }

    // Remove empty overlay if present
    if (emptyOverlay) emptyOverlay.remove();

    trendChart.data.labels           = trend.labels;
    trendChart.data.datasets[0].data = trend.high   || [];
    trendChart.data.datasets[1].data = trend.medium || [];
    trendChart.data.datasets[2].data = trend.low    || [];
    trendChart.update('none');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Recent Emergency Corridors list
  ────────────────────────────────────────────────────────────────────── */
  var STATUS_ICON = {
    ACTIVE:    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="14" height="14"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    COMPLETED: '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="14" height="14"><polyline points="20 6 9 17 4 12"/></svg>',
    CLOSED:    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  };

  function renderCorridors(corridors) {
    var list = document.getElementById('corridors-list');
    if (!list) return;

    if (!corridors.length) {
      list.innerHTML =
        '<p style="color:#6B7280;font-size:13px;text-align:center;padding:28px 0">' +
        'No emergency corridors yet</p>';
      return;
    }

    list.innerHTML = corridors.map(function (c) {
      var status    = (c.status || 'CLOSED').toUpperCase();
      var statusCls = status.toLowerCase();
      var icon      = STATUS_ICON[status] || STATUS_ICON['CLOSED'];
      var dest      = c.destination || '—';
      var src       = c.source      || '—';
      var saved     = c.time_saved  != null ? c.time_saved + ' min saved' : '';

      return (
        '<a href="' + esc(c.detail_url || '#') + '" class="alert-row corridor-row" style="text-decoration:none;">' +
          '<div class="alert-icon corridor-status-' + statusCls + '" aria-hidden="true">' + icon + '</div>' +
          '<div class="alert-body">' +
            '<div class="alert-type">' + esc(dest) + '</div>' +
            '<div class="alert-location" style="font-size:11px;color:#6B7280">' +
              esc(src) +
              (saved ? ' &bull; <span style="color:#10B981">' + esc(saved) + '</span>' : '') +
            '</div>' +
          '</div>' +
          '<div class="alert-time">' +
            '<span class="corridor-badge corridor-badge-' + statusCls + '">' + esc(status) + '</span>' +
            '<div style="font-size:11px;color:#9CA3AF;margin-top:4px">' + esc(c.time || '') + '</div>' +
          '</div>' +
        '</a>'
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
