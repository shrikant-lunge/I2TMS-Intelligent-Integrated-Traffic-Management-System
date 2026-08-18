/**
 * I²TMS — reports.js (Screen 11: Reports Module)
 *
 * Responsibilities:
 *   · Handle report type card selection (toggle .selected)
 *   · Enable/disable GENERATE REPORT button accordingly
 *   · Show/hide custom date range pickers inline
 *   · Trigger report generation via POST /api/generate_report
 *   · Render report preview summary & stats dynamically
 *   · Update PDF/CSV download links in preview card
 */

(function () {
  'use strict';

  /* ──────────────────────────────────────────────────────────────────────
     State variables
  ────────────────────────────────────────────────────────────────────── */
  var selectedType = null;
  var timeRange    = 'this_week';

  /* ──────────────────────────────────────────────────────────────────────
     DOM Elements
  ────────────────────────────────────────────────────────────────────── */
  var cards          = document.querySelectorAll('.rp-card');
  var generateBtn    = document.getElementById('rp-btn-generate');
  var rangeSelect    = document.getElementById('time-range-select');
  var customDatesRow = document.getElementById('custom-range-fields');
  var startDateInput = document.getElementById('range-start');
  var endDateInput   = document.getElementById('range-end');
  var errorBanner    = document.getElementById('rp-error-banner');
  var previewCard    = document.getElementById('rp-preview-card');
  var previewTitle   = document.getElementById('rp-preview-title');
  var previewStats   = document.getElementById('rp-preview-stats');
  var pdfDownloadBtn = document.getElementById('rp-btn-pdf');
  var csvDownloadBtn = document.getElementById('rp-btn-csv');

  /* Set initial time range */
  if (rangeSelect) {
    timeRange = rangeSelect.value;
  }

  /* Set default dates to today/yesterday for custom range */
  var todayStr = new Date().toISOString().split('T')[0];
  if (startDateInput) startDateInput.value = todayStr;
  if (endDateInput) endDateInput.value = todayStr;

  /* ──────────────────────────────────────────────────────────────────────
     Card Selection
  ────────────────────────────────────────────────────────────────────── */
  cards.forEach(function (card) {
    card.addEventListener('click', function () {
      // Remove selected class from others
      cards.forEach(function (c) { c.classList.remove('selected'); });
      
      // Select this card
      this.classList.add('selected');
      selectedType = this.getAttribute('data-type');

      // Enable generate button
      if (generateBtn) {
        generateBtn.removeAttribute('disabled');
      }

      // Proactively hide previous preview card if selecting a new type
      if (previewCard) {
        previewCard.hidden = true;
      }
      clearError();
    });
  });

  /* ──────────────────────────────────────────────────────────────────────
     Time Range Select Toggle
  ────────────────────────────────────────────────────────────────────── */
  if (rangeSelect) {
    rangeSelect.addEventListener('change', function () {
      timeRange = this.value;
      if (timeRange === 'custom') {
        if (customDatesRow) customDatesRow.hidden = false;
      } else {
        if (customDatesRow) customDatesRow.hidden = true;
      }
      clearError();
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     Generate Report Handler
  ────────────────────────────────────────────────────────────────────── */
  if (generateBtn) {
    generateBtn.addEventListener('click', function () {
      if (!selectedType) return;
      clearError();

      var startVal = null;
      var endVal = null;

      // Handle custom range validation
      if (timeRange === 'custom') {
        startVal = startDateInput ? startDateInput.value : '';
        endVal = endDateInput ? endDateInput.value : '';

        if (!startVal || !endVal) {
          showError('Please select both start and end dates for custom range.');
          return;
        }

        if (new Date(startVal) > new Date(endVal)) {
          showError('Start date cannot be after the end date.');
          return;
        }
      }

      // Update button visual state
      generateBtn.setAttribute('disabled', 'true');
      generateBtn.textContent = 'Generating…';

      var payload = {
        report_type: selectedType,
        time_range: timeRange,
        range_start: startVal,
        range_end: endVal
      };

      fetch('/api/generate_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) {
            throw new Error(err.error || 'Server error occurred during generation.');
          });
        }
        return res.json();
      })
      .then(function (data) {
        renderReportPreview(data);
      })
      .catch(function (err) {
        showError(err.message || 'Failed to connect to generation service.');
      })
      .finally(function () {
        generateBtn.removeAttribute('disabled');
        generateBtn.textContent = 'GENERATE REPORT';
      });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     UI Render Functions
  ────────────────────────────────────────────────────────────────────── */
  function renderReportPreview(data) {
    if (!previewCard) return;

    // Title
    if (previewTitle && data.summary) {
      previewTitle.textContent = data.summary.title || 'Generated Report';
    }

    // Stats Grid
    if (previewStats && data.summary && data.summary.stats) {
      var statsHtml = data.summary.stats.map(function (stat) {
        return '<div class="rp-stat-tile">'
          + '<span class="rp-stat-label">' + escapeHtml(stat.label) + '</span>'
          + '<span class="rp-stat-value">' + escapeHtml(stat.value) + '</span>'
          + '</div>';
      }).join('');
      previewStats.innerHTML = statsHtml;
    }

    // Download buttons
    if (pdfDownloadBtn) {
      pdfDownloadBtn.setAttribute('href', data.download_pdf_url || '#');
    }
    if (csvDownloadBtn) {
      csvDownloadBtn.setAttribute('href', data.download_csv_url || '#');
    }

    // Reveal panel & scroll into view
    previewCard.hidden = false;
    previewCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function showError(msg) {
    if (errorBanner) {
      errorBanner.textContent = msg;
      errorBanner.hidden = false;
    }
  }

  function clearError() {
    if (errorBanner) {
      errorBanner.hidden = true;
      errorBanner.textContent = '';
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

})();
