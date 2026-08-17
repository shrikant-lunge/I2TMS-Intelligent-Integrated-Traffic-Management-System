/**
 * I²TMS — analytics.js  (Screen 4: Junction Analytics – Detailed)
 *
 * Responsibilities:
 *   · Junction & Time Range dropdown change → update URL & fetch
 *   · Render 4 Stat cards with trend indicators
 *   · Traffic Trend Line Chart (Chart.js 4.x — unfilled lines)
 *   · Vehicle Composition Donut Chart (Chart.js 4.x — center text overlay + legend)
 *   · Signal Plan History table (DB backed from Screen 3 actions)
 *   · Export CSV trigger
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State
  ────────────────────────────────────────────────────────────────────── */
  var urlParams        = new URLSearchParams(window.location.search);
  var selectedJunction = urlParams.get('junction') || 'A';
  var selectedRange    = urlParams.get('range')    || 'today';

  var trendChart = null;
  var donutChart = null;

  /* ──────────────────────────────────────────────────────────────────────
     Dropdown event listeners
  ────────────────────────────────────────────────────────────────────── */
  var junctionSelect = document.getElementById('junction-select');
  var rangeSelect    = document.getElementById('range-select');
  var btnExport      = document.getElementById('btn-export');

  if (junctionSelect) {
    junctionSelect.addEventListener('change', function () {
      selectedJunction = this.value;
      updateUrlAndFetch();
    });
  }

  if (rangeSelect) {
    rangeSelect.addEventListener('change', function () {
      selectedRange = this.value;
      updateUrlAndFetch();
    });
  }

  if (btnExport) {
    btnExport.addEventListener('click', function () {
      var exportUrl = '/api/export_analytics?junction=' + encodeURIComponent(selectedJunction) +
                      '&range=' + encodeURIComponent(selectedRange) + '&format=csv';
      window.location.href = exportUrl;
    });
  }

  function updateUrlAndFetch() {
    var url = new URL(window.location.href);
    url.searchParams.set('junction', selectedJunction);
    url.searchParams.set('range', selectedRange);
    history.replaceState(null, '', url.toString());

    // Update trend range subtitle
    var rangeLabelEl = document.getElementById('trend-range-label');
    if (rangeLabelEl) {
      var rangeMap = { today: 'Today', yesterday: 'Yesterday', '7days': 'Last 7 Days', '30days': 'Last 30 Days' };
      rangeLabelEl.textContent = '(' + (rangeMap[selectedRange] || 'Today') + ')';
    }

    fetchAndRender();
  }

  /* ──────────────────────────────────────────────────────────────────────
     Chart.js Initialisation
  ────────────────────────────────────────────────────────────────────── */
  function initCharts() {
    // 1. Traffic Trend Line Chart
    var trendCanvas = document.getElementById('traffic-trend-chart');
    if (trendCanvas && typeof Chart !== 'undefined') {
      trendChart = new Chart(trendCanvas.getContext('2d'), {
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
              bodyColor:       'rgba(255,255,255,0.85)',
              padding:         10,
              cornerRadius:    8,
            },
          },
          scales: {
            x: {
              grid:   { display: false },
              border: { display: false },
              ticks:  { color: '#9CA3AF', font: { size: 11, family: 'Inter, sans-serif' } },
            },
            y: {
              min:    0,
              max:    100,
              border: { display: false },
              grid:   { color: '#F3F4F6' },
              ticks:  { color: '#9CA3AF', font: { size: 11, family: 'Inter, sans-serif' }, stepSize: 25 },
            },
          },
        },
      });
    }

    // 2. Vehicle Composition Donut Chart
    var donutCanvas = document.getElementById('pcu-donut-chart');
    if (donutCanvas && typeof Chart !== 'undefined') {
      donutChart = new Chart(donutCanvas.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: [],
          datasets: [{
            data:            [],
            backgroundColor: ['#1A2942', '#0EA5A0', '#F59E0B'],
            borderWidth:     0,
            hoverOffset:     4,
          }],
        },
        options: {
          responsive:          true,
          maintainAspectRatio: false,
          cutout:              '74%',
          plugins: {
            legend:  { display: false },
            tooltip: {
              backgroundColor: '#1A2942',
              padding:         8,
              cornerRadius:    6,
              callbacks: {
                label: function (ctx) {
                  return ' ' + ctx.label + ': ' + ctx.parsed + '%';
                },
              },
            },
          },
        },
      });
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Fetch + Render Cycle
  ────────────────────────────────────────────────────────────────────── */
  function fetchAndRender() {
    var query = '?junction=' + encodeURIComponent(selectedJunction) + '&range=' + encodeURIComponent(selectedRange);
    fetch('/api/junction_analytics' + query, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        renderStatCards(data.stats || {});
        renderTrafficTrend(data.traffic_trend || {});
        renderVehicleComposition(data.vehicle_composition || {});
        renderHistoryTable(data.signal_plan_history || []);
      })
      .catch(function (err) {
        console.warn('[I²TMS analytics] fetch error:', err);
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Renderers
  ────────────────────────────────────────────────────────────────────── */
  function renderStatCards(stats) {
    setText('stat-wait-time',   stats.avg_waiting_time_sec !== undefined ? stats.avg_waiting_time_sec + ' sec' : '—');
    setText('stat-queue-length', stats.avg_queue_length_m  !== undefined ? stats.avg_queue_length_m + ' m' : '—');
    setText('stat-throughput',   stats.throughput_veh_hr    !== undefined ? Number(stats.throughput_veh_hr).toLocaleString() + ' veh/hr' : '—');

    // Waiting time trend
    var waitTrendEl = document.getElementById('stat-wait-trend');
    if (waitTrendEl && stats.avg_waiting_trend_pct !== undefined) {
      waitTrendEl.style.display = 'inline-flex';
      setText('stat-wait-pct', Math.abs(stats.avg_waiting_trend_pct) + '%');
    }

    // Queue length trend
    var queueTrendEl = document.getElementById('stat-queue-trend');
    if (queueTrendEl && stats.avg_queue_trend_pct !== undefined) {
      queueTrendEl.style.display = 'inline-flex';
      setText('stat-queue-pct', Math.abs(stats.avg_queue_trend_pct) + '%');
    }

    // Congestion status badge
    var congEl = document.getElementById('stat-congestion');
    if (congEl && stats.congestion_level) {
      var level = String(stats.congestion_level).toLowerCase();
      congEl.innerHTML =
        '<span class="congestion-badge ' + esc(level) + '">' +
          cap(level) +
        '</span>';
    }
  }

  function renderTrafficTrend(trend) {
    if (!trendChart || !trend.labels) return;
    trendChart.data.labels           = trend.labels;
    trendChart.data.datasets[0].data = trend.high   || [];
    trendChart.data.datasets[1].data = trend.medium || [];
    trendChart.data.datasets[2].data = trend.low    || [];
    trendChart.update();
  }

  function renderVehicleComposition(vcomp) {
    var totalVal = vcomp.total_pcu || 48;
    setText('pcu-total-val', totalVal + ' PCU');

    var breakdown = vcomp.breakdown || [];
    if (donutChart) {
      donutChart.data.labels           = breakdown.map(function (b) { return b.type; });
      donutChart.data.datasets[0].data = breakdown.map(function (b) { return b.pct; });
      donutChart.update();
    }

    // Render custom PCU legend swatches
    var legendEl = document.getElementById('pcu-legend');
    if (!legendEl) return;

    var colors = ['#1A2942', '#0EA5A0', '#F59E0B'];
    legendEl.innerHTML = breakdown.map(function (b, idx) {
      var color  = colors[idx % colors.length];
      var weight = b.pcu_weight !== undefined ? ' (' + b.pcu_weight.toFixed(1) + 'x)' : '';
      return (
        '<div class="pcu-legend-item">' +
          '<div class="pcu-item-left">' +
            '<span class="pcu-swatch" style="background:' + color + '"></span>' +
            '<span class="pcu-type-name">' + esc(b.type) + '</span>' +
            '<span class="pcu-weight-tag">' + esc(weight) + '</span>' +
          '</div>' +
          '<span class="pcu-pct-val">' + esc(b.pct) + '%</span>' +
        '</div>'
      );
    }).join('');
  }

  function renderHistoryTable(rows) {
    var tbody = document.getElementById('history-tbody');
    if (!tbody) return;

    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:#9CA3AF;padding:24px 0">No signal history recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function (r) {
      var isOperator = (r.applied_by || '').toLowerCase() === 'operator';
      var badgeClass = isOperator ? 'operator' : 'system';
      var badgeText  = isOperator ? 'Operator' : 'System';

      return (
        '<tr>' +
          '<td style="font-weight:500;color:#111827">' + esc(r.time) + '</td>' +
          '<td>' + esc(r.phase_a) + 's</td>' +
          '<td>' + esc(r.phase_b) + 's</td>' +
          '<td>' + esc(r.phase_c) + 's</td>' +
          '<td>' + esc(r.phase_d) + 's</td>' +
          '<td>' +
            '<span class="applied-badge ' + badgeClass + '">' + esc(badgeText) + '</span>' +
          '</td>' +
        '</tr>'
      );
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Helpers
  ────────────────────────────────────────────────────────────────────── */
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = (val !== undefined && val !== null) ? String(val) : '—';
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
  initCharts();
  fetchAndRender();

  // Refresh analytics view every 30 seconds
  setInterval(fetchAndRender, 30000);

})();
