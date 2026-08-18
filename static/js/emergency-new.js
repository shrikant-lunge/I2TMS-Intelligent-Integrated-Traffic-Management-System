/* =========================================================
   I²TMS — Emergency Module (Screen 6-new) JS
   emergency-new.js — handles geocoding, autocomplete, and state updates
   ========================================================= */

(function() {
  'use strict';

  const form = document.getElementById('request-form-state');
  const createdState = document.getElementById('request-created-state');
  const submitBtn = document.getElementById('submit-btn');
  const formBanner = document.getElementById('form-banner');

  let currentLoc = { name: '', lat: null, lng: null };
  let destLoc = { name: '', lat: null, lng: null };

  // ---- Autocomplete ----
  function attachAutocomplete(inputEl, dropdownEl, targetLoc) {
    let debounceTimer;
    inputEl.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      targetLoc.lat = null; targetLoc.lng = null; // invalidate until a suggestion is picked
      const q = inputEl.value.trim();
      if (q.length < 2) { dropdownEl.hidden = true; return; }
      debounceTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
          const results = await res.json();
          renderDropdown(results);
        } catch (e) { dropdownEl.hidden = true; }
      }, 300);
    });

    function renderDropdown(results) {
      if (!results.length) { dropdownEl.hidden = true; return; }
      dropdownEl.innerHTML = results.map((r, i) =>
        `<div class="ac-row" data-i="${i}">${r.name}</div>`
      ).join('');
      dropdownEl.hidden = false;
      dropdownEl.querySelectorAll('.ac-row').forEach((row, i) => {
        row.addEventListener('click', () => {
          inputEl.value = results[i].name;
          targetLoc.name = results[i].name;
          targetLoc.lat = results[i].lat;
          targetLoc.lng = results[i].lng;
          dropdownEl.hidden = true;
          clearFieldError(inputEl.id);
        });
      });
    }

    document.addEventListener('click', (e) => {
      if (!inputEl.contains(e.target) && !dropdownEl.contains(e.target)) dropdownEl.hidden = true;
    });
  }

  const currentLocInput = document.getElementById('current-location');
  const currentLocDropdown = document.getElementById('current-location-dropdown');
  const destInput = document.getElementById('destination');
  const destDropdown = document.getElementById('destination-dropdown');

  if (currentLocInput && currentLocDropdown) {
    attachAutocomplete(currentLocInput, currentLocDropdown, currentLoc);
  }
  if (destInput && destDropdown) {
    attachAutocomplete(destInput, destDropdown, destLoc);
  }

  // ---- GPS ----
  const gpsBtn = document.getElementById('gps-btn');
  if (gpsBtn) {
    gpsBtn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        showFieldError('current-location', "Geolocation not supported by this browser.");
        return;
      }
      gpsBtn.classList.add('loading');
      navigator.geolocation.getCurrentPosition(async (pos) => {
        gpsBtn.classList.remove('loading');
        const { latitude, longitude } = pos.coords;
        try {
          const res = await fetch(`/api/reverse_geocode?lat=${latitude}&lng=${longitude}`);
          const data = await res.json();
          const input = document.getElementById('current-location');
          input.value = data.display_name;
          currentLoc = { name: data.display_name, lat: latitude, lng: longitude };
          clearFieldError('current-location');
        } catch (e) {
          showFieldError('current-location', "Couldn't resolve your location — enter it manually.");
        }
      }, () => {
        gpsBtn.classList.remove('loading');
        showFieldError('current-location', "Location access denied — enter it manually.");
      });
    });
  }

  // ---- Priority note ----
  const prioritySelect = document.getElementById('priority');
  if (prioritySelect) {
    prioritySelect.addEventListener('change', (e) => {
      const notes = { high: '• High — Urgent dispatch', medium: '• Medium — Standard priority', low: '• Low — Routine transport' };
      const noteEl = document.getElementById('priority-note');
      if (noteEl) noteEl.textContent = notes[e.target.value] || '';
    });
  }

  // ---- Validation ----
  function showFieldError(inputId, message) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const fieldGroup = input.closest('.field');
    if (!fieldGroup) return;
    const errorEl = fieldGroup.querySelector('.field-error');
    input.classList.add('is-invalid');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.hidden = false;
    }
  }

  function clearFieldError(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.classList.remove('is-invalid');
    const fieldGroup = input.closest('.field');
    if (!fieldGroup) return;
    const errorEl = fieldGroup.querySelector('.field-error');
    if (errorEl) errorEl.hidden = true;
  }

  function validateForm() {
    let valid = true;
    clearFieldError('vehicle-number');
    clearFieldError('current-location');
    clearFieldError('destination');

    const vNum = document.getElementById('vehicle-number').value.trim();
    const cLoc = document.getElementById('current-location').value.trim();
    const dLoc = document.getElementById('destination').value.trim();

    if (!vNum) {
      showFieldError('vehicle-number', "Please enter a vehicle number.");
      valid = false;
    }
    if (!cLoc) {
      showFieldError('current-location', "Please enter a current location.");
      valid = false;
    } else if (!currentLoc.name) {
      // User typed something but didn't pick a suggestion
      currentLoc.name = cLoc;
    }
    if (!dLoc) {
      showFieldError('destination', "Please enter a destination.");
      valid = false;
    } else if (!destLoc.name) {
      // User typed something but didn't pick a suggestion
      destLoc.name = dLoc;
    }

    if (valid && cLoc === dLoc) {
      showFieldError('destination', "Destination must differ from current location.");
      valid = false;
    }

    return valid;
  }

  // ---- Clear invalid highlights on input typing ----
  ['vehicle-number', 'current-location', 'destination'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', () => clearFieldError(id));
    }
  });

  // ---- Submit ----
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      formBanner.hidden = true;
      if (!validateForm()) return;

      submitBtn.disabled = true;
      submitBtn.textContent = "FINDING ROUTE…";

      try {
        const payload = {
          vehicle_type: document.getElementById('vehicle-type').value,
          vehicle_number: document.getElementById('vehicle-number').value.trim(),
          current_location: currentLoc.name,
          current_lat: currentLoc.lat,
          current_lng: currentLoc.lng,
          destination: destLoc.name,
          destination_lat: destLoc.lat,
          destination_lng: destLoc.lng,
          priority: document.getElementById('priority').value,
        };

        const res = await fetch('/api/emergency_request', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || "Request failed");
        }

        const data = await res.json();
        showCreatedState(data);
      } catch (err) {
        formBanner.textContent = "Couldn't compute a route — check the locations and try again.";
        formBanner.hidden = false;
        console.error(err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "FIND SHORTEST ROUTE";
      }
    });
  }

  let lastCreatedRequestId = null;
  let leafletMap = null;

  // ---- Show created request ----
  function showCreatedState(data) {
    lastCreatedRequestId = data.request_id;
    const vTypeSelect = document.getElementById('vehicle-type');
    const vTypeLabel = vTypeSelect.selectedOptions[0] ? vTypeSelect.selectedOptions[0].textContent : 'Ambulance';

    document.getElementById('cs-vehicle').textContent = vTypeLabel;
    document.getElementById('cs-vehicle-number').textContent = document.getElementById('vehicle-number').value.trim();
    document.getElementById('cs-distance').textContent = `${data.distance_km} km`;
    document.getElementById('cs-eta').textContent = `${data.eta_min} min`;
    document.getElementById('cs-signals').textContent = data.signals_on_route;
    document.getElementById('cs-vms').textContent = data.vms_on_route;
    document.getElementById('cs-from').textContent = currentLoc.name || document.getElementById('current-location').value;
    document.getElementById('cs-to').textContent = destLoc.name || document.getElementById('destination').value;

    form.hidden = true;
    createdState.hidden = false;
    document.getElementById('route-map-state').hidden = true; // reset if reused
  }

  const viewRouteBtn = document.getElementById('btn-view-route');
  if (viewRouteBtn) {
    viewRouteBtn.addEventListener('click', async () => {
      const routeSection = document.getElementById('route-map-state');
      routeSection.hidden = false;
      routeSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

      // Reset header status class
      const rmStatus = document.getElementById('rm-status');
      if (rmStatus) {
        rmStatus.textContent = 'Active';
        rmStatus.className = 'status-pill status-active';
      }

      try {
        const res = await fetch(`/api/emergency_request/${lastCreatedRequestId}`);
        const data = await res.json();

        document.getElementById('rm-vehicle-number').textContent = data.vehicle_number;
        document.getElementById('rm-eta').textContent = `${data.route_eta_min} min`;
        document.getElementById('rm-distance').textContent = `${data.route_distance_km} km`;
        document.getElementById('rm-checkpoints').textContent = `${data.signals_on_route} Signals · ${data.vms_on_route} VMS`;

        initRouteMap(data);
        renderCorridorDetails(data);
      } catch (e) {
        console.error("Failed to load request details for route map:", e);
      }
    });
  }

  // ---- Render corridor detail stats + tables ----
  function renderCorridorDetails(data) {
    const distEl = document.getElementById('rm-distance-remaining');
    if (distEl) distEl.textContent = `${data.distance_remaining_km ?? data.route_distance_km} km`;

    const etaEl = document.getElementById('rm-eta-stat');
    if (etaEl) etaEl.textContent = `${data.route_eta_min} min`;

    const sigEl = document.getElementById('rm-signals-ahead');
    if (sigEl) sigEl.textContent = (data.upcoming_signals || []).length;

    const vmsEl = document.getElementById('rm-vms-ahead');
    if (vmsEl) vmsEl.textContent = (data.active_vms || []).length;

    const signalsBody = document.getElementById('upcoming-signals-body');
    if (signalsBody) {
      const signals = data.upcoming_signals || [];
      signalsBody.innerHTML = signals.length
        ? signals.map((s, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${s.junction}</td>
            <td>${s.distance_km} km</td>
            <td class="${s.status === 'Priority Active' ? 'status-priority-active' : 'status-normal'}">${s.status}</td>
            <td>${s.time_to_reach_min} min</td>
          </tr>`).join('')
        : '<tr><td colspan="5" style="color:#9CA3AF;text-align:center;padding:16px">No signals data available</td></tr>';
    }

    const vmsBody = document.getElementById('active-vms-body');
    if (vmsBody) {
      const vmsList = data.active_vms || [];
      vmsBody.innerHTML = vmsList.length
        ? vmsList.map((v, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${v.vms_id}</td>
            <td>${v.location}</td>
            <td>${v.message}</td>
            <td class="status-vms-active">${v.status}</td>
          </tr>`).join('')
        : '<tr><td colspan="5" style="color:#9CA3AF;text-align:center;padding:16px">No VMS data available</td></tr>';
    }
  }

  function initRouteMap(data) {
    const mapEl = document.getElementById('route-map-canvas');
    if (!mapEl) return;
    if (leafletMap) { leafletMap.remove(); }
    
    const centerLat = data.current_lat || 21.1458;
    const centerLng = data.current_lng || 79.0882;
    leafletMap = L.map(mapEl).setView([centerLat, centerLng], 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { 
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' 
    }).addTo(leafletMap);

    const routeCoords = data.route_geometry || [[data.current_lat, data.current_lng], [data.destination_lat, data.destination_lng]];
    
    // Draw polyline
    L.polyline(routeCoords, { color: '#1A2942', weight: 5, opacity: 0.8 }).addTo(leafletMap);
    
    // Markers
    L.marker([data.current_lat, data.current_lng]).addTo(leafletMap).bindPopup('Starting Point').openPopup();
    L.marker([data.destination_lat, data.destination_lng]).addTo(leafletMap).bindPopup('Destination');
    
    leafletMap.fitBounds(routeCoords, { padding: [35, 35] });
  }

  const endCorridorBtn = document.getElementById('btn-end-corridor');
  if (endCorridorBtn) {
    endCorridorBtn.addEventListener('click', async () => {
      try {
        await fetch(`/api/emergency_request/${lastCreatedRequestId}/end`, { method: 'POST' });
        const rmStatus = document.getElementById('rm-status');
        if (rmStatus) {
          rmStatus.textContent = 'Ended';
          rmStatus.classList.replace('status-active', 'status-ended');
        }
      } catch (e) {
        console.error("Failed to end corridor:", e);
      }
    });
  }

  const newRequestBtn = document.getElementById('btn-new-request');
  if (newRequestBtn) {
    newRequestBtn.addEventListener('click', () => {
      createdState.hidden = true;
      document.getElementById('route-map-state').hidden = true;
      form.hidden = false;
      document.querySelectorAll('input').forEach(i => i.value = '');
      currentLoc = { name: '', lat: null, lng: null };
      destLoc = { name: '', lat: null, lng: null };
      formBanner.hidden = true;
    });
  }

  // ---- Check for request_id query parameter on load ----
  async function checkQueryParamOnLoad() {
    const params = new URLSearchParams(window.location.search);
    const reqId = params.get('request_id');
    if (!reqId) return;

    lastCreatedRequestId = reqId;
    form.hidden = true;
    createdState.hidden = true;

    const routeSection = document.getElementById('route-map-state');
    if (routeSection) routeSection.hidden = false;

    try {
      const res = await fetch(`/api/emergency_request/${reqId}`);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();

      document.getElementById('rm-vehicle-number').textContent = data.vehicle_number;
      document.getElementById('rm-eta').textContent = `${data.route_eta_min} min`;
      document.getElementById('rm-distance').textContent = `${data.route_distance_km} km`;
      document.getElementById('rm-checkpoints').textContent = `${data.signals_on_route} Signals · ${data.vms_on_route} VMS`;

      const rmStatus = document.getElementById('rm-status');
      if (rmStatus) {
        if (data.status === 'active') {
          rmStatus.textContent = 'Active';
          rmStatus.className = 'status-pill status-active';
        } else {
          rmStatus.textContent = 'Ended';
          rmStatus.className = 'status-pill status-ended';
        }
      }

      initRouteMap(data);
      renderCorridorDetails(data);
    } catch (e) {
      console.error("Failed to load requested emergency request details on load:", e);
    }
  }

  // Run onload check
  checkQueryParamOnLoad();

})();
