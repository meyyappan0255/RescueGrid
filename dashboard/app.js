// dashboard/app.js — RescueGrid Live Dashboard
// ─────────────────────────────────────────────────────────────

const SERVER_WS  = "ws://localhost:8000/ws/dashboard";
const MAP_CENTER = [13.0827, 80.2707];   // Default: Chennai
const MAP_ZOOM   = 14;

// ── Map setup ────────────────────────────────────────────────
const map = L.map("map").setView(MAP_CENTER, MAP_ZOOM);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap contributors",
  maxZoom: 19,
}).addTo(map);

// ── Marker stores ─────────────────────────────────────────────
const ambulanceMarkers = {};  // id → L.marker
const junctionMarkers  = {};  // id → L.circleMarker

// ── Icons ─────────────────────────────────────────────────────
const ambulanceIcon = L.divIcon({
  html: `<div style="font-size:24px;filter:drop-shadow(0 0 4px red)">🚑</div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  className: "",
});

function junctionColor(state) {
  return { emergency: "#e63946", normal: "#2dc653", failsafe: "#f4a261" }[state] || "#8899aa";
}

// ── WebSocket ─────────────────────────────────────────────────
let ws;
let reconnectDelay = 2000;

function connect() {
  const statusEl = document.getElementById("connStatus");
  statusEl.textContent = "● Connecting…";
  statusEl.className   = "conn-status";

  ws = new WebSocket(SERVER_WS);

  ws.onopen = () => {
    console.log("WebSocket connected");
    statusEl.textContent = "● Live";
    statusEl.className   = "conn-status connected";
    reconnectDelay = 2000;
    // Keep-alive ping every 20s
    setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), 20000);
  };

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      updateAmbulances(data.ambulances || []);
      updateJunctions(data.junctions  || []);
      document.getElementById("lastUpdate").textContent =
        "Last update: " + new Date(data.timestamp).toLocaleTimeString();
    } catch (e) {
      console.error("Parse error:", e);
    }
  };

  ws.onerror = (err) => {
    console.error("WS error:", err);
    statusEl.textContent = "● Error";
    statusEl.className   = "conn-status error";
  };

  ws.onclose = () => {
    statusEl.textContent = `● Reconnecting in ${reconnectDelay / 1000}s…`;
    statusEl.className   = "conn-status error";
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };
}

// ── Update functions ──────────────────────────────────────────

function updateAmbulances(list) {
  const container = document.getElementById("ambulanceList");
  container.innerHTML = "";

  if (list.length === 0) {
    container.innerHTML = '<div class="meta" style="padding:4px">No active ambulances</div>';
  }

  list.forEach(amb => {
    if (amb.latitude == null) return;

    // Map marker
    const latlng = [amb.latitude, amb.longitude];
    if (ambulanceMarkers[amb.ambulance_id]) {
      ambulanceMarkers[amb.ambulance_id].setLatLng(latlng);
    } else {
      ambulanceMarkers[amb.ambulance_id] = L.marker(latlng, { icon: ambulanceIcon })
        .addTo(map)
        .bindPopup(`<b>${amb.ambulance_id}</b>`);
    }
    ambulanceMarkers[amb.ambulance_id].setRotationAngle?.(amb.heading || 0);
    ambulanceMarkers[amb.ambulance_id]
      .bindPopup(
        `<b>${amb.ambulance_id}</b><br>` +
        `Speed: ${amb.speed_kmh?.toFixed(1)} km/h<br>` +
        `Criticality: ${amb.criticality}/5<br>` +
        `Priority: ${amb.priority_active ? "🔴 ACTIVE" : "Normal"}`
      );

    // Sidebar card
    const card = document.createElement("div");
    card.className = `card ${amb.priority_active ? "priority" : "normal"}`;
    card.innerHTML = `
      <div class="id">${amb.ambulance_id}</div>
      <div class="meta">
        ${amb.speed_kmh?.toFixed(1) ?? "0"} km/h &nbsp;|&nbsp;
        Crit: ${amb.criticality}/5
      </div>
      ${amb.priority_active
        ? '<span class="badge priority">🚨 PRIORITY</span>'
        : '<span class="badge normal">Normal</span>'}
    `;
    card.onclick = () => map.setView(latlng, 16);
    container.appendChild(card);
  });
}

function updateJunctions(list) {
  const container = document.getElementById("junctionList");
  container.innerHTML = "";

  list.forEach(jn => {
    const latlng = [jn.lat, jn.lon];
    const color  = junctionColor(jn.state);

    if (junctionMarkers[jn.junction_id]) {
      junctionMarkers[jn.junction_id]
        .setLatLng(latlng)
        .setStyle({ color, fillColor: color });
    } else {
      junctionMarkers[jn.junction_id] = L.circleMarker(latlng, {
        radius: 10, color, fillColor: color,
        fillOpacity: 0.85, weight: 2,
      }).addTo(map).bindPopup(`<b>${jn.name || jn.junction_id}</b><br>State: ${jn.state}`);
    }

    // Sidebar card
    const card = document.createElement("div");
    card.className = `card ${jn.state}`;
    card.innerHTML = `
      <div class="id">${jn.name || jn.junction_id}</div>
      <div class="meta">${jn.junction_id}</div>
      <span class="badge ${jn.state}">${jn.state.toUpperCase()}</span>
    `;
    card.onclick = () => map.setView(latlng, 17);
    container.appendChild(card);
  });
}

// ── Boot ──────────────────────────────────────────────────────
connect();
