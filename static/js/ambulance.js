/**
 * ambulance.js
 * Logic for the ambulance driver frontend dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const destSelect = document.getElementById('destination');
    const btnCalculate = document.getElementById('btn-calculate');
    const btnStart = document.getElementById('btn-start');
    const btnEnd = document.getElementById('btn-end');
    const routeStats = document.getElementById('route-stats');
    const activeCard = document.getElementById('active-status-card');
    
    const statDistance = document.getElementById('stat-distance');
    const statBaseline = document.getElementById('stat-baseline');
    const statOptimized = document.getElementById('stat-optimized');
    const tripProgress = document.getElementById('trip-progress');
    const tripRemaining = document.getElementById('trip-remaining');
    const speedIndicator = document.getElementById('current-speed');
    
    let map;
    let ambulanceMarker;
    let routePolyline;
    let simulationInterval;
    let currentRequestId = null;
    let currentRouteData = null;
    
    // Initialize map
    initMap();
    
    // Event Listeners
    btnCalculate.addEventListener('click', calculateRoute);
    
    document.getElementById('route-form').addEventListener('submit', (e) => {
        e.preventDefault();
        startEmergency();
    });
    
    btnEnd.addEventListener('click', endEmergency);
    
    function initMap() {
        // Center on VNIT Nagpur default
        map = L.map('ambulance-map').setView([21.1253, 79.0514], 14);
        
        // Dark theme tiles
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);
        
        // Ambulance Icon
        const ambIcon = L.divIcon({
            html: '<div style="background-color: #ff3b30; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px #ff3b30; border: 2px solid white;"><i class="fas fa-ambulance"></i></div>',
            className: 'amb-marker-icon',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
        
        ambulanceMarker = L.marker([21.1253, 79.0514], {icon: ambIcon}).addTo(map);
    }
    
    async function calculateRoute() {
        const dest = destSelect.value;
        if (!dest) {
            alert("Please select a destination");
            return;
        }
        
        const [destLat, destLng] = dest.split(',').map(Number);
        const originLat = 21.1253; // VNIT
        const originLng = 79.0514;
        
        btnCalculate.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Calculating...';
        btnCalculate.disabled = true;
        
        try {
            // In a real app, this would hit our /api/emergency/request endpoint
            // For now, we simulate the OSRM response parsing
            const response = await fetch('/api/emergency_request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vehicle_number: "AMB-MH31-108",
                    vehicle_type: "ambulance",
                    origin: { lat: originLat, lng: originLng, name: "VNIT" },
                    destination: { lat: destLat, lng: destLng, name: "Hospital" }
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                currentRouteData = data.data;
                currentRequestId = currentRouteData.request_id;
                
                // Update UI Stats
                statDistance.innerText = `${currentRouteData.distance_km.toFixed(1)} km`;
                statBaseline.innerText = `${currentRouteData.baseline_eta_min} min`;
                statOptimized.innerText = `${currentRouteData.optimized_eta_min} min`;
                
                routeStats.classList.remove('hidden');
                btnStart.disabled = false;
                
                // Draw route on map
                drawRoute(currentRouteData.geometry);
            } else {
                alert("Failed to calculate route: " + (data.message || "Unknown error"));
            }
        } catch (err) {
            console.error("Routing error:", err);
            // Fallback for UI testing if backend not ready
            mockRoute(originLat, originLng, destLat, destLng);
        } finally {
            btnCalculate.innerHTML = '<i class="fas fa-route"></i> Calculate Route';
            btnCalculate.disabled = false;
        }
    }
    
    function drawRoute(geometryCoords) {
        if (routePolyline) {
            map.removeLayer(routePolyline);
        }
        
        // Swap [lon, lat] to [lat, lon] for Leaflet
        const latLngs = geometryCoords.map(coord => [coord[1], coord[0]]);
        
        routePolyline = L.polyline(latLngs, {
            color: '#66fcf1',
            weight: 6,
            opacity: 0.7,
            dashArray: '10, 10'
        }).addTo(map);
        
        map.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });
    }
    
    async function startEmergency() {
        if (!currentRequestId) return;
        
        btnStart.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Activating...';
        btnStart.disabled = true;
        
        try {
            // Simulated activation
            document.getElementById('route-form').parentElement.classList.add('hidden');
            activeCard.classList.remove('hidden');
            
            // Start GPS simulation loop
            startSimulation();
            
        } catch (err) {
            console.error(err);
            btnStart.innerHTML = '<i class="fas fa-siren-on"></i> ACTIVATE CORRIDOR';
            btnStart.disabled = false;
        }
    }
    
    async function endEmergency() {
        if (!currentRequestId) return;
        
        try {
            await fetch(`/api/emergency_request/${currentRequestId}/end`, { method: 'POST' });
        } catch (e) {
            console.warn(e);
        }
        
        stopSimulation();
        
        // Reset UI
        activeCard.classList.add('hidden');
        document.getElementById('route-form').parentElement.classList.remove('hidden');
        routeStats.classList.add('hidden');
        btnStart.disabled = true;
        destSelect.value = '';
        
        if (routePolyline) {
            map.removeLayer(routePolyline);
        }
        ambulanceMarker.setLatLng([21.1253, 79.0514]);
        map.setView([21.1253, 79.0514], 14);
        currentRequestId = null;
    }
    
    // --- SIMULATION LOGIC ---
    let simIndex = 0;
    
    function startSimulation() {
        if (!currentRouteData || !currentRouteData.geometry) return;
        
        const coords = currentRouteData.geometry;
        simIndex = 0;
        
        simulationInterval = setInterval(() => {
            if (simIndex >= coords.length) {
                endEmergency();
                return;
            }
            
            const [lon, lat] = coords[simIndex];
            ambulanceMarker.setLatLng([lat, lon]);
            map.panTo([lat, lon], { animate: true });
            
            // Random speed for demo
            speedIndicator.innerText = Math.floor(40 + Math.random() * 30);
            
            // Update progress bar
            const pct = (simIndex / coords.length) * 100;
            tripProgress.style.width = `${pct}%`;
            
            const remainingKm = currentRouteData.distance_km * (1 - (pct/100));
            tripRemaining.innerText = `${remainingKm.toFixed(1)} km to go`;
            
            // Send location update to backend to trigger VMS/signals
            updateLocationBackend(lat, lon);
            
            simIndex += 2; // Jump ahead for faster demo
        }, 1000);
    }
    
    function stopSimulation() {
        clearInterval(simulationInterval);
        speedIndicator.innerText = "0";
    }
    
    function updateLocationBackend(lat, lng) {
        if (!currentRequestId) return;
        fetch('/api/emergency/location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request_id: currentRequestId,
                lat: lat,
                lng: lng
            })
        }).catch(e => console.warn(e));
    }
    
    function mockRoute(olat, olng, dlat, dlng) {
        // Fallback generator for UI testing without OSRM
        const points = [];
        const steps = 50;
        for (let i = 0; i <= steps; i++) {
            const lat = olat + (dlat - olat) * (i / steps);
            const lng = olng + (dlng - olng) * (i / steps);
            points.push([lng, lat]); // GeoJSON order
        }
        
        currentRouteData = {
            request_id: 999,
            distance_km: 8.5,
            baseline_eta_min: 24,
            optimized_eta_min: 14,
            geometry: points
        };
        currentRequestId = 999;
        
        statDistance.innerText = `8.5 km`;
        statBaseline.innerText = `24 min`;
        statOptimized.innerText = `14 min`;
        
        routeStats.classList.remove('hidden');
        btnStart.disabled = false;
        drawRoute(points);
    }
});
