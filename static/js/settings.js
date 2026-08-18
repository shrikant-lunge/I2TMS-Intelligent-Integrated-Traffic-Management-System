/**
 * I²TMS — settings.js (Screen 12: Settings Module)
 *
 * Responsibilities:
 *   · Tab switching (General, Junctions, Signals, VMS, Users, Notifications shortcut)
 *   · Load / Update SystemSettings (General and Signals forms)
 *   · CRUD support for Junctions, VMS Boards, and User Accounts
 *   · Poll /api/system_status health-check footer every 15 seconds
 */

(function () {
  'use strict';

  /* ── State variables ── */
  var activeTab = 'general';
  var isResetting = false;

  /* ──────────────────────────────────────────────────────────────────────
     DOM Elements & Tab Switching
  ────────────────────────────────────────────────────────────────────── */
  var tabButtons = document.querySelectorAll('.se-tab-btn');
  var tabPanels  = document.querySelectorAll('.se-tab-panel');

  tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tabId = this.getAttribute('data-tab');
      if (!tabId) return;

      // Handle special Notifications shortcut tab click
      if (tabId === 'notifications') {
        switchToTab('general');
        // Scroll to notifications section
        var targetSection = document.getElementById('panel-notifications-container');
        if (targetSection) {
          targetSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
          targetSection.classList.add('flash-highlight');
          setTimeout(function() {
            targetSection.classList.remove('flash-highlight');
          }, 1500);
        }
        return;
      }

      switchToTab(tabId);
    });
  });

  function switchToTab(tabId) {
    activeTab = tabId;
    tabButtons.forEach(function (b) {
      if (b.getAttribute('data-tab') === tabId) {
        b.classList.add('active');
        b.setAttribute('aria-selected', 'true');
      } else {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      }
    });

    tabPanels.forEach(function (p) {
      if (p.id === 'panel-' + tabId) {
        p.classList.add('active');
      } else {
        p.classList.remove('active');
      }
    });

    // Refresh tab data when switching to it
    if (tabId === 'junctions') fetchJunctions();
    if (tabId === 'vms') fetchVMSBoards();
    if (tabId === 'users') fetchUsers();
    if (tabId === 'drivers') fetchDrivers();
  }

  /* ──────────────────────────────────────────────────────────────────────
     1. Load & Save System Settings (General & Signals tabs)
  ────────────────────────────────────────────────────────────────────── */
  var generalForm    = document.getElementById('form-system-settings');
  var signalsForm    = document.getElementById('form-signal-timing');
  var genSuccess     = document.getElementById('general-success-banner');
  var sigSuccess     = document.getElementById('signals-success-banner');

  function fetchSystemSettings() {
    fetch('/api/settings')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        // Populate General inputs
        var tzSelect = document.getElementById('se-timezone');
        var refreshInput = document.getElementById('se-refresh-interval');
        var defaultDashboard = document.getElementById('se-default-dashboard');
        var unitsSelect = document.getElementById('se-units');

        if (tzSelect) tzSelect.value = data.time_zone;
        if (refreshInput) refreshInput.value = data.data_refresh_interval_sec;
        if (defaultDashboard) defaultDashboard.value = data.default_dashboard_view;
        if (unitsSelect) unitsSelect.value = data.units;

        // Populate Toggles
        var toggleEmail = document.getElementById('toggle-email');
        var toggleSms = document.getElementById('toggle-sms');
        var togglePush = document.getElementById('toggle-push');
        var toggleEmergency = document.getElementById('toggle-emergency');

        if (toggleEmail) toggleEmail.checked = data.email_alerts;
        if (toggleSms) toggleSms.checked = data.sms_alerts;
        if (togglePush) togglePush.checked = data.push_notifications;
        if (toggleEmergency) toggleEmergency.checked = data.emergency_alerts;

        // Populate Signals defaults
        var cycleInput = document.getElementById('se-cycle-time');
        var minInput = document.getElementById('se-min-phase');
        var maxInput = document.getElementById('se-max-phase');

        if (cycleInput) cycleInput.value = data.default_cycle_time_sec;
        if (minInput) minInput.value = data.min_phase_duration_sec;
        if (maxInput) maxInput.value = data.max_phase_duration_sec;
      })
      .catch(function (err) { console.warn('Failed to load settings:', err); });
  }

  // Save General settings
  if (generalForm) {
    generalForm.addEventListener('submit', function (e) {
      e.preventDefault();
      saveSettingsBatch({
        time_zone: document.getElementById('se-timezone').value,
        data_refresh_interval_sec: parseInt(document.getElementById('se-refresh-interval').value, 10),
        default_dashboard_view: document.getElementById('se-default-dashboard').value,
        units: document.getElementById('se-units').value,
        email_alerts: document.getElementById('toggle-email').checked,
        sms_alerts: document.getElementById('toggle-sms').checked,
        push_notifications: document.getElementById('toggle-push').checked,
        emergency_alerts: document.getElementById('toggle-emergency').checked
      }, genSuccess);
    });
  }

  // Save Signal settings
  if (signalsForm) {
    signalsForm.addEventListener('submit', function (e) {
      e.preventDefault();
      saveSettingsBatch({
        default_cycle_time_sec: parseInt(document.getElementById('se-cycle-time').value, 10),
        min_phase_duration_sec: parseInt(document.getElementById('se-min-phase').value, 10),
        max_phase_duration_sec: parseInt(document.getElementById('se-max-phase').value, 10)
      }, sigSuccess);
    });
  }

  // Watch toggles and auto-save on switch toggle
  ['toggle-email', 'toggle-sms', 'toggle-push', 'toggle-emergency'].forEach(function (id) {
    var toggleEl = document.getElementById(id);
    if (toggleEl) {
      toggleEl.addEventListener('change', function () {
        // Auto-save toggle batch on check change
        saveSettingsBatch({
          email_alerts: document.getElementById('toggle-email').checked,
          sms_alerts: document.getElementById('toggle-sms').checked,
          push_notifications: document.getElementById('toggle-push').checked,
          emergency_alerts: document.getElementById('toggle-emergency').checked
        }, null);
      });
    }
  });

  function saveSettingsBatch(payload, successBanner) {
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (successBanner) {
        successBanner.hidden = false;
        setTimeout(function () { successBanner.hidden = true; }, 3000);
      }
    })
    .catch(function (err) { console.warn('Failed to save settings:', err); });
  }

  /* ──────────────────────────────────────────────────────────────────────
     2. Junctions CRUD
  ────────────────────────────────────────────────────────────────────── */
  var addJunctionBtn = document.getElementById('btn-add-junction');
  var junctionsBody  = document.getElementById('table-junctions-body');
  var junctionForm   = document.getElementById('form-junction');

  function fetchJunctions() {
    fetch('/api/junctions')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!junctionsBody) return;
        if (!data.length) {
          junctionsBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#9CA3AF">No junctions configured</td></tr>';
          return;
        }
        junctionsBody.innerHTML = data.map(function (j) {
          var dotColor = j.status === 'high' ? 'high' : (j.status === 'moderate' ? 'moderate' : 'low');
          var statusText = j.status.toUpperCase();
          var typeText = j.junction_type === 't-point' ? 'T-Point (3)' : 'Square (4)';
          
          return '<tr>'
            + '<td><strong>' + escapeHtml(j.name) + '</strong><div style="font-size:11px;color:#6B7280;margin-top:2px;">' + typeText + '</div></td>'
            + '<td><span class="status-indicator-text"><span class="status-dot-sm ' + dotColor + '"></span>' + statusText + '</span></td>'
            + '<td><code>' + (j.lat && j.lng ? escapeHtml(j.lat + ', ' + j.lng) : '—') + '</code></td>'
            + '<td><code>' + escapeHtml(j.camera_thumbnail_url || '—') + '</code></td>'
            + '<td>' + escapeHtml(j.last_updated) + '</td>'
            + '<td style="text-align:right"><button class="btn-outline btn-xs" onclick="openEditJunction(' + j.id + ', \'' + escapeHtml(j.name) + '\', \'' + j.status + '\', \'' + escapeHtml(j.camera_thumbnail_url) + '\', \'' + (j.junction_type || 'square') + '\', ' + (j.lat || null) + ', ' + (j.lng || null) + ')">Edit</button></td>'
            + '</tr>';
        }).join('');
      });
  }

  window.updateJunctionSignalHint = function(val) {
    var hint = document.getElementById('junction-signal-hint');
    if (hint) {
      if (val === 't-point') hint.textContent = 'This junction manages 3 main signals.';
      else hint.textContent = 'This junction manages 4 main signals.';
    }
  };

  if (addJunctionBtn) {
    addJunctionBtn.addEventListener('click', function () {
      document.getElementById('modal-junction-title').textContent = 'Add New Junction';
      document.getElementById('modal-junction-id').value = '';
      document.getElementById('modal-junction-name').value = '';
      document.getElementById('modal-junction-status').value = 'low';
      document.getElementById('modal-junction-type').value = 'square';
      document.getElementById('modal-junction-lat').value = '';
      document.getElementById('modal-junction-lng').value = '';
      document.getElementById('modal-junction-url').value = '';
      updateJunctionSignalHint('square');
      openModal('modal-junction');
    });
  }

  window.openEditJunction = function (id, name, status, url, type, lat, lng) {
    document.getElementById('modal-junction-title').textContent = 'Edit Junction Details';
    document.getElementById('modal-junction-id').value = id;
    document.getElementById('modal-junction-name').value = name;
    document.getElementById('modal-junction-status').value = status;
    document.getElementById('modal-junction-type').value = type;
    document.getElementById('modal-junction-lat').value = lat !== null ? lat : '';
    document.getElementById('modal-junction-lng').value = lng !== null ? lng : '';
    document.getElementById('modal-junction-url').value = url;
    updateJunctionSignalHint(type);
    openModal('modal-junction');
  };

  if (junctionForm) {
    junctionForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var id = document.getElementById('modal-junction-id').value;
      var name = document.getElementById('modal-junction-name').value;
      var status = document.getElementById('modal-junction-status').value;
      var type = document.getElementById('modal-junction-type').value;
      var lat = document.getElementById('modal-junction-lat').value;
      var lng = document.getElementById('modal-junction-lng').value;
      var url = document.getElementById('modal-junction-url').value;

      var endpoint = id ? '/api/junctions/' + id : '/api/junctions';
      var method = id ? 'PUT' : 'POST';

      fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, status: status, camera_thumbnail_url: url, junction_type: type, lat: lat ? parseFloat(lat) : null, lng: lng ? parseFloat(lng) : null })
      })
      .then(function (res) { return res.json(); })
      .then(function () {
        closeModal('modal-junction');
        fetchJunctions();
      });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     3. VMS CRUD
  ────────────────────────────────────────────────────────────────────── */
  var addVmsBtn = document.getElementById('btn-add-vms');
  var vmsBody   = document.getElementById('table-vms-body');
  var vmsForm   = document.getElementById('form-vms');

  function fetchVMSBoards() {
    fetch('/api/vms_boards')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!vmsBody) return;
        if (!data.length) {
          vmsBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9CA3AF">No VMS boards configured</td></tr>';
          return;
        }
        vmsBody.innerHTML = data.map(function (v) {
          var dotColor = v.status === 'active' ? 'active' : 'offline';
          return '<tr>'
            + '<td><strong>' + escapeHtml(v.vms_id) + '</strong></td>'
            + '<td>' + escapeHtml(v.location) + '</td>'
            + '<td><code>' + (v.lat && v.lng ? escapeHtml(v.lat + ', ' + v.lng) : '—') + '</code></td>'
            + '<td><span class="status-indicator-text"><span class="status-dot-sm ' + dotColor + '"></span>' + v.status.toUpperCase() + '</span></td>'
            + '<td><code>' + escapeHtml(v.current_message || '—') + '</code></td>'
            + '<td style="text-align:right"><button class="btn-outline btn-xs" onclick="openEditVMS(' + v.id + ', \'' + escapeHtml(v.vms_id) + '\', \'' + escapeHtml(v.location) + '\', \'' + v.status + '\', \'' + escapeHtml(v.current_message) + '\', ' + (v.lat || null) + ', ' + (v.lng || null) + ')">Edit</button></td>'
            + '</tr>';
        }).join('');
      });
  }

  if (addVmsBtn) {
    addVmsBtn.addEventListener('click', function () {
      document.getElementById('modal-vms-title').textContent = 'Add New VMS Board';
      document.getElementById('modal-vms-db-id').value = '';
      document.getElementById('modal-vms-id').value = '';
      document.getElementById('modal-vms-location').value = '';
      document.getElementById('modal-vms-lat').value = '';
      document.getElementById('modal-vms-lng').value = '';
      document.getElementById('modal-vms-status').value = 'active';
      document.getElementById('modal-vms-message').value = '';
      openModal('modal-vms');
    });
  }

  window.openEditVMS = function (id, vmsId, location, status, message, lat, lng) {
    document.getElementById('modal-vms-title').textContent = 'Edit VMS Board';
    document.getElementById('modal-vms-db-id').value = id;
    document.getElementById('modal-vms-id').value = vmsId;
    document.getElementById('modal-vms-location').value = location;
    document.getElementById('modal-vms-lat').value = lat !== null ? lat : '';
    document.getElementById('modal-vms-lng').value = lng !== null ? lng : '';
    document.getElementById('modal-vms-status').value = status;
    document.getElementById('modal-vms-message').value = message;
    openModal('modal-vms');
  };

  if (vmsForm) {
    vmsForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var id = document.getElementById('modal-vms-db-id').value;
      var location = document.getElementById('modal-vms-location').value;
      var lat = document.getElementById('modal-vms-lat').value;
      var lng = document.getElementById('modal-vms-lng').value;
      var status = document.getElementById('modal-vms-status').value;
      var message = document.getElementById('modal-vms-message').value;

      var endpoint = id ? '/api/vms_boards/' + id : '/api/vms_boards';
      var method = id ? 'PUT' : 'POST';

      fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: location, status: status, current_message: message, lat: lat ? parseFloat(lat) : null, lng: lng ? parseFloat(lng) : null })
      })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) { alert(err.error || 'Server error saving VMS board.'); });
        }
        return res.json();
      })
      .then(function (data) {
        if (data) {
          closeModal('modal-vms');
          fetchVMSBoards();
        }
      });
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     4. Users Administration CRUD (Admin only)
  ────────────────────────────────────────────────────────────────────── */
  var addUserBtn = document.getElementById('btn-add-user');
  var usersBody  = document.getElementById('table-users-body');
  var userForm   = document.getElementById('form-user');
  var resetForm  = document.getElementById('form-reset-password');

  // Show/hide Mobile field depending on selected role
  window.toggleDriverMobileField = function (role) {
    var field = document.getElementById('field-driver-mobile');
    var mobileInput = document.getElementById('modal-user-mobile');
    if (!field) return;
    if (role === 'driver') {
      field.style.display = '';
      if (mobileInput) mobileInput.required = true;
    } else {
      field.style.display = 'none';
      if (mobileInput) mobileInput.required = false;
    }
  };

  function fetchUsers() {
    if (!usersBody) return; // Non-admin users don't render this panel
    fetch('/api/users')
      .then(function (res) {
        if (res.status === 403) throw new Error('Forbidden');
        return res.json();
      })
      .then(function (data) {
        // Filter out driver accounts from the main users table
        var nonDrivers = data.filter(function (u) { return u.role !== 'driver'; });
        usersBody.innerHTML = nonDrivers.map(function (u) {
          var roleBadge = u.role === 'admin' ? 'Administrator' : 'Operator';
          return '<tr>'
            + '<td><strong>' + escapeHtml(u.username) + '</strong></td>'
            + '<td>' + roleBadge + '</td>'
            + '<td>' + escapeHtml(u.last_login) + '</td>'
            + '<td>' + escapeHtml(u.created_at) + '</td>'
            + '<td style="text-align:right">'
            +   '<button class="btn-outline btn-xs" onclick="openResetPassword(' + u.id + ', \'' + escapeHtml(u.username) + '\')" style="margin-right:8px">Reset Pass</button>'
            +   '<button class="btn-outline btn-xs btn-delete" onclick="deactivateUser(' + u.id + ', \'' + escapeHtml(u.username) + '\')">Deactivate</button>'
            + '</td>'
            + '</tr>';
        }).join('');
      })
      .catch(function (e) {
        console.warn('[settings users admin] fetch error:', e);
      });
  }

  if (addUserBtn) {
    addUserBtn.addEventListener('click', function () {
      document.getElementById('modal-user-username').value = '';
      document.getElementById('modal-user-password').value = '';
      document.getElementById('modal-user-role').value = 'operator';
      var mobileInput = document.getElementById('modal-user-mobile');
      if (mobileInput) mobileInput.value = '';
      toggleDriverMobileField('operator');
      openModal('modal-user');
    });
  }

  if (userForm) {
    userForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var username = document.getElementById('modal-user-username').value;
      var password = document.getElementById('modal-user-password').value;
      var role = document.getElementById('modal-user-role').value;
      var mobileEl = document.getElementById('modal-user-mobile');
      var mobile = mobileEl ? mobileEl.value.trim() : '';

      if (role === 'driver' && !mobile) {
        alert('Mobile number is required for Driver accounts.');
        return;
      }

      var payload = { username: username, password: password, role: role };
      if (mobile) payload.mobile = mobile;

      fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) { alert(err.error || 'Server error creating user.'); });
        }
        return res.json();
      })
      .then(function (data) {
        if (data) {
          closeModal('modal-user');
          fetchUsers();
          fetchDrivers(); // refresh drivers table too
        }
      });
    });
  }

  window.openResetPassword = function (id, username) {
    document.getElementById('modal-reset-user-id').value = id;
    document.getElementById('modal-reset-username').textContent = username;
    document.getElementById('modal-reset-new-password').value = '';
    openModal('modal-reset');
  };

  if (resetForm) {
    resetForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var id = document.getElementById('modal-reset-user-id').value;
      var password = document.getElementById('modal-reset-new-password').value;

      fetch('/api/users/' + id + '/reset_password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: password })
      })
      .then(function (res) { return res.json(); })
      .then(function () {
        closeModal('modal-reset');
        alert('Password reset successfully!');
      });
    });
  }

  window.deactivateUser = function (id, username) {
    if (confirm('Are you sure you want to deactivate user: ' + username + '? This will permanently remove the account.')) {
      fetch('/api/users/' + id + '/deactivate', { method: 'POST' })
        .then(function (res) {
          if (!res.ok) {
            return res.json().then(function (err) { throw new Error(err.error); });
          }
          return res.json();
        })
        .then(function () {
          fetchUsers();
        })
        .catch(function (err) {
          alert(err.message || 'Failed to deactivate user.');
        });
    }
  };

  /* ──────────────────────────────────────────────────────────────────────
     5. Driver Accounts (Admin only)
  ────────────────────────────────────────────────────────────────────── */
  var driversBody  = document.getElementById('table-drivers-body');
  var addDriverBtn = document.getElementById('btn-add-driver');

  function fetchDrivers() {
    if (!driversBody) return;
    fetch('/api/users')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var drivers = data.filter(function (u) { return u.role === 'driver'; });
        if (!drivers.length) {
          driversBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#6B7280;padding:20px;">No driver accounts yet. Click "+ Add Driver" to create one.</td></tr>';
          return;
        }
        driversBody.innerHTML = drivers.map(function (u) {
          return '<tr>'
            + '<td><strong>' + escapeHtml(u.username) + '</strong></td>'
            + '<td>' + (u.mobile ? escapeHtml(u.mobile) : '<span style="color:#6B7280">—</span>') + '</td>'
            + '<td>' + escapeHtml(u.last_login) + '</td>'
            + '<td>' + escapeHtml(u.created_at) + '</td>'
            + '<td style="text-align:right">'
            +   '<button class="btn-outline btn-xs" onclick="openResetPassword(' + u.id + ', \'' + escapeHtml(u.username) + '\')" style="margin-right:8px">Reset Pass</button>'
            +   '<button class="btn-outline btn-xs btn-delete" onclick="deactivateUser(' + u.id + ', \'' + escapeHtml(u.username) + '\')">Remove</button>'
            + '</td></tr>';
        }).join('');
      })
      .catch(function (e) { console.warn('[settings drivers] fetch error:', e); });
  }

  // "+ Add Driver" opens the same modal pre-set to Driver role
  if (addDriverBtn) {
    addDriverBtn.addEventListener('click', function () {
      document.getElementById('modal-user-username').value = '';
      document.getElementById('modal-user-password').value = '';
      document.getElementById('modal-user-role').value = 'driver';
      var mobileInput = document.getElementById('modal-user-mobile');
      if (mobileInput) mobileInput.value = '';
      toggleDriverMobileField('driver');
      openModal('modal-user');
    });
  }

  /* ──────────────────────────────────────────────────────────────────────
     6. System Health Status Polling
  ────────────────────────────────────────────────────────────────────── */
  function pollSystemStatus() {
    fetch('/api/system_status')
      .then(function (res) { return res.json(); })
      .then(function (data) {
        // Update dots and text
        updateStatusDot('status-backend', 'lbl-backend', data.backend);
        updateStatusDot('status-database', 'lbl-database', data.database);
        updateStatusDot('status-ai', 'lbl-ai', data.ai_service);

        // Update timestamp
        var statusTime = document.getElementById('se-status-time');
        if (statusTime) {
          statusTime.textContent = data.last_updated || '—';
        }
      })
      .catch(function (err) {
        // In case server fails, show offline status
        updateStatusDot('status-backend', 'lbl-backend', 'offline');
        updateStatusDot('status-database', 'lbl-database', 'offline');
        updateStatusDot('status-ai', 'lbl-ai', 'offline');
      });
  }

  function updateStatusDot(dotId, lblId, status) {
    var dot = document.getElementById(dotId);
    var lbl = document.getElementById(lblId);

    if (dot) {
      if (status === 'online') {
        dot.className = 'indicator-dot online';
      } else {
        dot.className = 'indicator-dot offline';
      }
    }

    if (lbl) {
      lbl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
  }

  /* ──────────────────────────────────────────────────────────────────────
     Modal Global Utilities
  ────────────────────────────────────────────────────────────────────── */
  window.openModal = function (id) {
    var m = document.getElementById(id);
    if (m) m.hidden = false;
  };

  window.closeModal = function (id) {
    var m = document.getElementById(id);
    if (m) m.hidden = true;
  };

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ──────────────────────────────────────────────────────────────────────
     Initialization
  ────────────────────────────────────────────────────────────────────── */
  fetchSystemSettings();
  pollSystemStatus();
  setInterval(pollSystemStatus, 15000);

})();
