/**
 * I²TMS — incidents-alerts.js  (Screen 10: Incidents & Alerts)
 *
 * Responsibilities:
 *   · Read filter state from URL params; sync dropdowns
 *   · Fetch /api/incidents_alerts on load, on any filter/page change
 *   · Poll every 10 s so emergency dispatches appear without manual refresh
 *   · Render alert rows (system alerts + emergency dispatches merged)
 *   · Render pagination footer (matching Screen 5 pattern)
 *   · Clickable rows for emergency dispatches → /emergency/new?request_id=<id>
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State
  ────────────────────────────────────────────────────────────────────── */
  var urlParams      = new URLSearchParams(window.location.search);
  var selectedType   = urlParams.get('type')     || 'all';
  var selectedSev    = urlParams.get('severity') || 'all';
  var selectedRange  = urlParams.get('range')    || 'today';
  var currentPage    = parseInt(urlParams.get('page') || '1', 10);
  var perPage        = 5;
  var pollTimer      = null;
  var POLL_MS        = 10000;

  /* ──────────────────────────────────────────────────────────────────────
     DOM refs
  ────────────────────────────────────────────────────────────────────── */
  var typeFilter  = document.getElementById('ia-type-filter');
  var sevFilter   = document.getElementById('ia-severity-filter');
  var rangeFilter = document.getElementById('ia-range-filter');
  var listBody    = document.getElementById('ia-list-body');
  var emptyState  = document.getElementById('ia-empty-state');
  var pagFooter   = document.getElementById('ia-pagination-footer');
  var pagInfo     = document.getElementById('ia-pagination-info');
  var pagStart    = document.getElementById('ia-pag-start');
  var pagEnd      = document.getElementById('ia-pag-end');
  var pagTotal    = document.getElementById('ia-pag-total');
  var pagControls = document.getElementById('ia-pagination-controls');
  var liveBadge   = document.getElementById('ia-live-badge');

  /* ── Sync selects to initial URL state ── */
  if (typeFilter)  typeFilter.value  = selectedType;
  if (sevFilter)   sevFilter.value   = selectedSev;
  if (rangeFilter) rangeFilter.value = selectedRange;

  /* ──────────────────────────────────────────────────────────────────────
     Filter change listeners
  ────────────────────────────────────────────────────────────────────── */
  if (typeFilter) {
    typeFilter.addEventListener('change', function () {
      selectedType = this.value;
      currentPage = 1;
      pushStateAndFetch();
    });
  }
  if (sevFilter) {
    sevFilter.addEventListener('change', function () {
      selectedSev = this.value;
      currentPage = 1;
      pushStateAndFetch();
    });
  }
  if (rangeFilter) {
    rangeFilter.addEventListener('change', function () {
      selectedRange = this.value;
      currentPage = 1;
      pushStateAndFetch();
    });
  }

  function pushStateAndFetch() {
    var url = new URL(window.location.href);
    url.searchParams.set('type',     selectedType);
    url.searchParams.set('severity', selectedSev);
    url.searchParams.set('range',    selectedRange);
    url.searchParams.set('page',     currentPage);
    history.replaceState(null, '', url.toString());
    fetchAndRender();
  }

  /* ──────────────────────────────────────────────────────────────────────
     Fetch + Render
  ────────────────────────────────────────────────────────────────────── */
  function buildApiUrl() {
    return '/api/incidents_alerts'
      + '?type='     + encodeURIComponent(selectedType)
      + '&severity=' + encodeURIComponent(selectedSev)
      + '&range='    + encodeURIComponent(selectedRange)
      + '&page='     + currentPage
      + '&per_page=' + perPage;
  }

  function fetchAndRender() {
    fetch(buildApiUrl(), { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        setOnline(true);
        renderRows(data.rows || []);
        renderPagination(data.pagination || {});
      })
      .catch(function (err) {
        setOnline(false);
        console.warn('[I²TMS incidents-alerts] fetch error:', err);
      });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Render rows
  ────────────────────────────────────────────────────────────────────── */
  function renderRows(rows) {
    if (!listBody) return;

    if (!rows.length) {
      listBody.innerHTML = '';
      if (emptyState) emptyState.hidden = false;
      if (pagFooter)  pagFooter.style.display = 'none';
      return;
    }

    if (emptyState) emptyState.hidden = true;

    listBody.innerHTML = rows.map(function (row) {
      var isEmergency = row.severity === 'high' && (row.type && row.type.toLowerCase().includes('emergency'));
      var clickable   = !!row.request_id;
      var href        = clickable ? '/emergency/new?request_id=' + encodeURIComponent(row.request_id) : null;

      var iconHtml;
      if (isEmergency) {
        iconHtml = '<div class="ia-row-icon ia-icon-emergency">' + row.icon + '</div>';
      } else {
        var svgColor = row.severity === 'high'   ? '#DC2626'
                     : row.severity === 'medium' ? '#D97706'
                     : '#6366F1';
        var bgClass  = row.severity === 'high'   ? 'ia-icon-high'
                     : row.severity === 'medium' ? 'ia-icon-medium'
                     : 'ia-icon-low';
        iconHtml = '<div class="ia-row-icon ' + bgClass + '">'
          + '<svg class="ia-triangle-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"'
          + ' stroke="' + svgColor + '" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
          + '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
          + '<line x1="12" y1="9" x2="12" y2="13"/>'
          + '<line x1="12" y1="17" x2="12.01" y2="17"/>'
          + '</svg>'
          + '</div>';
      }

      var statusLower = (row.status || '').toLowerCase();
      var badgeClass  = statusLower === 'active'   ? 'ia-badge-active'
                      : statusLower === 'resolved' ? 'ia-badge-resolved'
                      : 'ia-badge-resolved';
      var badgeLabel  = row.status || '—';

      var titleText = escapeHtml(row.type   || '—');
      var subText   = escapeHtml(row.location || '—');

      var inner = iconHtml
        + '<div class="ia-row-body">'
        +   '<div class="ia-row-title">' + titleText + '</div>'
        +   '<div class="ia-row-sub">'   + subText   + '</div>'
        + '</div>'
        + '<div class="ia-row-meta">'
        +   '<span class="ia-row-time">' + escapeHtml(row.time || '—') + '</span>'
        +   '<span class="ia-status-badge ' + badgeClass + '">' + escapeHtml(badgeLabel) + '</span>'
        + '</div>';

      if (clickable) {
        return '<a href="' + href + '" class="ia-row clickable" title="View emergency dispatch">' + inner + '</a>';
      }
      return '<div class="ia-row">' + inner + '</div>';
    }).join('');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Render pagination
  ────────────────────────────────────────────────────────────────────── */
  function renderPagination(pag) {
    if (!pagFooter) return;
    var total      = pag.total_rows   || 0;
    var totalPages = pag.total_pages  || 1;
    var page       = pag.current_page || 1;
    var pp         = pag.per_page     || perPage;

    if (total === 0) {
      pagFooter.style.display = 'none';
      return;
    }

    pagFooter.style.display = 'flex';
    var startItem = (page - 1) * pp + 1;
    var endItem   = Math.min(page * pp, total);
    if (pagStart) pagStart.textContent = startItem;
    if (pagEnd)   pagEnd.textContent   = endItem;
    if (pagTotal) pagTotal.textContent = total;

    if (!pagControls) return;

    var html = '';

    // Prev button
    html += '<button class="ia-page-btn' + (page <= 1 ? ' disabled' : '') + '"'
      + (page > 1 ? ' data-page="' + (page - 1) + '"' : '')
      + ' aria-label="Previous page">&#8249;</button>';

    // Page number buttons (sliding window of ±2)
    var lo = Math.max(1, page - 2);
    var hi = Math.min(totalPages, page + 2);
    // Always show first page
    if (lo > 1) {
      html += '<button class="ia-page-btn" data-page="1">1</button>';
      if (lo > 2) html += '<span class="ia-page-btn disabled" style="border:none;background:none;cursor:default">…</span>';
    }
    for (var p = lo; p <= hi; p++) {
      html += '<button class="ia-page-btn' + (p === page ? ' active' : '') + '"'
        + (p !== page ? ' data-page="' + p + '"' : '')
        + '>' + p + '</button>';
    }
    // Always show last page
    if (hi < totalPages) {
      if (hi < totalPages - 1) html += '<span class="ia-page-btn disabled" style="border:none;background:none;cursor:default">…</span>';
      html += '<button class="ia-page-btn" data-page="' + totalPages + '">' + totalPages + '</button>';
    }

    // Next button
    html += '<button class="ia-page-btn' + (page >= totalPages ? ' disabled' : '') + '"'
      + (page < totalPages ? ' data-page="' + (page + 1) + '"' : '')
      + ' aria-label="Next page">&#8250;</button>';

    pagControls.innerHTML = html;

    // Wire page buttons
    pagControls.querySelectorAll('[data-page]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        currentPage = parseInt(this.getAttribute('data-page'), 10);
        pushStateAndFetch();
        // Scroll list into view
        if (listBody) listBody.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     LIVE badge / online status
  ────────────────────────────────────────────────────────────────────── */
  function setOnline(isOnline) {
    if (!liveBadge) return;
    var textSpan = liveBadge.querySelector('span:last-child');
    if (isOnline) {
      liveBadge.classList.remove('offline');
      if (textSpan) textSpan.textContent = 'LIVE';
    } else {
      liveBadge.classList.add('offline');
      if (textSpan) textSpan.textContent = 'OFFLINE';
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     10-second polling
  ────────────────────────────────────────────────────────────────────── */
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(fetchAndRender, POLL_MS);
  }

  /* ──────────────────────────────────────────────────────────────────────
     Utility
  ────────────────────────────────────────────────────────────────────── */
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Init
  ────────────────────────────────────────────────────────────────────── */
  fetchAndRender();
  startPolling();

})();
