/**
 * I²TMS — decision-logs.js  (Screen 5: Decision Logs)
 *
 * Responsibilities:
 *   · Dropdown filter changes → update URL params, reset page to 1, fetch
 *   · Fetch /api/decision_logs with pagination state
 *   · Render paginated rows with manual_override visual border highlights
 *   · Render pagination footer with dynamic page buttons (‹, 1, 2, ..., ›)
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State
  ────────────────────────────────────────────────────────────────────── */
  var urlParams        = new URLSearchParams(window.location.search);
  var selectedJunction = urlParams.get('junction') || 'all';
  var selectedRange    = urlParams.get('range')    || 'today';
  var selectedType     = urlParams.get('type')     || 'all';
  var currentPage      = parseInt(urlParams.get('page') || '1', 10);
  var perPage          = 5; // Rows per page

  /* ──────────────────────────────────────────────────────────────────────
     DOMElements
  ────────────────────────────────────────────────────────────────────── */
  var jFilter = document.getElementById('junction-filter');
  var rFilter = document.getElementById('range-filter');
  var tFilter = document.getElementById('type-filter');

  // Synchronise selectors with initial state
  if (jFilter) jFilter.value = selectedJunction;
  if (rFilter) rFilter.value = selectedRange;
  if (tFilter) tFilter.value = selectedType;

  /* ──────────────────────────────────────────────────────────────────────
     Listeners
  ────────────────────────────────────────────────────────────────────── */
  if (jFilter) {
    jFilter.addEventListener('change', function () {
      selectedJunction = this.value;
      currentPage = 1;
      updateUrlAndFetch();
    });
  }

  if (rFilter) {
    rFilter.addEventListener('change', function () {
      selectedRange = this.value;
      currentPage = 1;
      updateUrlAndFetch();
    });
  }

  if (tFilter) {
    tFilter.addEventListener('change', function () {
      selectedType = this.value;
      currentPage = 1;
      updateUrlAndFetch();
    });
  }

  function updateUrlAndFetch() {
    var url = new URL(window.location.href);
    url.searchParams.set('junction', selectedJunction);
    url.searchParams.set('range', selectedRange);
    url.searchParams.set('type', selectedType);
    url.searchParams.set('page', currentPage);
    history.replaceState(null, '', url.toString());

    fetchAndRender();
  }

  /* ──────────────────────────────────────────────────────────────────────
     Fetch + Render
  ────────────────────────────────────────────────────────────────────── */
  function fetchAndRender() {
    var query = '?junction=' + encodeURIComponent(selectedJunction) +
                '&range=' + encodeURIComponent(selectedRange) +
                '&type=' + encodeURIComponent(selectedType) +
                '&page=' + currentPage +
                '&per_page=' + perPage;

    fetch('/api/decision_logs' + query, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        renderTable(data.rows || []);
        renderPagination(data.pagination || {});
      })
      .catch(function (err) {
        console.warn('[I²TMS decision-logs] fetch error:', err);
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Table Renderer
  ────────────────────────────────────────────────────────────────────── */
  function renderTable(rows) {
    var tbody = document.getElementById('dl-tbody');
    if (!tbody) return;

    if (!rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:#9CA3AF;padding:32px 0">No decision logs found matching selected filters.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function (r) {
      var moduleVal   = (r.decision_type || 'adaptive_signal').toLowerCase();
      var isOverride  = moduleVal === 'manual_override';
      var isEmergency = moduleVal === 'emergency_corridor' || moduleVal === 'emergency';

      var rowClass    = '';
      if (isOverride)  rowClass = ' class="dl-row-override"';
      else if (isEmergency) rowClass = ' class="dl-row-emergency"';

      var decText  = r.decision || 'Adaptive';
      var decBadge = isOverride ? 'manual_override' : isEmergency ? 'emergency' : 'adaptive';

      var appliedBy  = r.applied_by || 'System';
      var appLower   = appliedBy.toLowerCase();
      var appClass   = appLower === 'operator' ? 'operator' : appLower === 'emergency' ? 'emergency' : 'system';

      // Direction badge
      var dirHtml = r.direction && r.direction !== '—'
        ? '<span class="dir-badge">' + esc(r.direction.toUpperCase()) + '</span> '
        : '';

      // Traffic / congestion pills
      var tLevel  = (r.traffic_level  || '').toUpperCase();
      var cLevel  = (r.congestion_level || '').toUpperCase();
      var tClass  = tLevel === 'HIGH' ? 'high' : tLevel === 'MEDIUM' ? 'medium' : 'low';
      var levelHtml = tLevel
        ? '<span class="level-pill ' + tClass + '">' + esc(tLevel) + '</span>'
        : '';

      // Green time
      var greenHtml = r.green_time && r.green_time !== '—'
        ? '<span style="color:#10B981;font-weight:600">' + esc(r.green_time) + 's</span>'
        : '';

      // PCU
      var pcuHtml = r.pcu && r.pcu !== '—'
        ? '<span style="color:#6B7280;font-size:11px">PCU ' + esc(r.pcu) + '</span>'
        : '';

      var planHtml = r.recommended_plan
        ? '<span class="plan-summary">' + esc(r.recommended_plan) + '</span>'
        : '—';

      return (
        '<tr' + rowClass + '>' +
          '<td style="font-weight:500;color:#111827">' + esc(r.time) + '</td>' +
          '<td>' +
            '<div style="font-weight:600;color:#4B5563">' + esc(r.junction) + '</div>' +
            '<div style="font-size:11px;color:#9CA3AF;margin-top:2px">' + dirHtml + levelHtml + '</div>' +
          '</td>' +
          '<td>' +
            '<span class="badge-decision ' + decBadge + '">' + esc(decText) + '</span>' +
          '</td>' +
          '<td>' +
            planHtml +
            '<div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">' +
              greenHtml + pcuHtml +
            '</div>' +
          '</td>' +
          '<td>' +
            '<span class="applied-badge ' + appClass + '">' + esc(appliedBy) + '</span>' +
          '</td>' +
        '</tr>'
      );
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Pagination Footer Renderer
  ────────────────────────────────────────────────────────────────────── */
  function renderPagination(pag) {
    var footer   = document.getElementById('dl-pagination-footer');
    var info     = document.getElementById('dl-pagination-info');
    var controls = document.getElementById('dl-pagination-controls');
    if (!footer || !info || !controls) return;

    if (pag.total_rows === 0) {
      footer.style.display = 'none';
      return;
    }
    footer.style.display = 'flex';

    // Update range label (e.g. 1-5 of 12)
    var startVal = (pag.current_page - 1) * pag.per_page + 1;
    var endVal   = Math.min(startVal + pag.per_page - 1, pag.total_rows);

    document.getElementById('pag-start').textContent = startVal;
    document.getElementById('pag-end').textContent   = endVal;
    document.getElementById('pag-total').textContent = pag.total_rows;

    // Build buttons
    var html = [];

    // Prev Button
    var prevDisabled = pag.current_page <= 1;
    html.push(
      '<button class="dl-page-btn' + (prevDisabled ? ' disabled' : '') + '"' +
      ' data-page="' + (pag.current_page - 1) + '"' + (prevDisabled ? ' disabled' : '') + '>' +
        '‹' +
      '</button>'
    );

    // Numbered pages
    for (var i = 1; i <= pag.total_pages; i++) {
      var isActive = i === pag.current_page;
      html.push(
        '<button class="dl-page-btn' + (isActive ? ' active' : '') + '"' +
        ' data-page="' + i + '">' +
          i +
        '</button>'
      );
    }

    // Next Button
    var nextDisabled = pag.current_page >= pag.total_pages;
    html.push(
      '<button class="dl-page-btn' + (nextDisabled ? ' disabled' : '') + '"' +
      ' data-page="' + (pag.current_page + 1) + '"' + (nextDisabled ? ' disabled' : '') + '>' +
        '›' +
      '</button>'
    );

    controls.innerHTML = html.join('');

    // Click handler for controls
    var buttons = controls.querySelectorAll('.dl-page-btn');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var page = parseInt(this.getAttribute('data-page'), 10);
        if (page && page !== currentPage) {
          currentPage = page;
          updateUrlAndFetch();
        }
      });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Helpers
  ────────────────────────────────────────────────────────────────────── */
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
  fetchAndRender();

})();
