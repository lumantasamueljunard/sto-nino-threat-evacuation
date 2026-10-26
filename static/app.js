/* ============================================================
   SENTINEL — app.js
   Handles: Live polling, pill navigation, map views,
            building floor plans, camera grid, sidebar controls
   ============================================================ */

const API = '';  // Same origin — FastAPI serves both static and API

// ── State ──────────────────────────────────────────────────
let appState = {
  tab: 'map',
  mapView: 'campus',
  selectedBuilding: null,
  gatesBlocked: [],
  camFilter: 'outside',
  snapshot: null,
  devices: {},
  detections: [],
  rooms: [],
};

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  startClock();
  await loadRooms();
  await loadScenarios();
  await loadDevices();
  await refresh();
  setInterval(refresh, 5000);
});

// ── Clock ──────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById('topbar-time');
  const tick = () => {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-US', { hour12: false });
    requestAnimationFrame(() => setTimeout(tick, 1000));
  };
  tick();
}

// ── Toast ──────────────────────────────────────────────────
let toastTimer = null;
function toast(msg, type = 'info', duration = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, duration);
}

// ── API helpers ────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(API + path, options);
    if (!res.ok) throw new Error(await res.text());
    return await res.json();
  } catch (e) {
    console.error('API error:', path, e);
    return null;
  }
}

// ── Load Static Data ───────────────────────────────────────
async function loadRooms() {
  const data = await apiFetch('/api/rooms');
  if (!data) return;
  appState.rooms = data.rooms;

  const sel = document.getElementById('sb-room-select');
  sel.innerHTML = data.rooms.map(r =>
    `<option value="${r}">${friendlyRoom(r)}</option>`
  ).join('');
  sel.addEventListener('change', () => updateEgressCard(sel.value));
  if (data.rooms.length) updateEgressCard(data.rooms[0]);
}

async function loadScenarios() {
  const data = await apiFetch('/api/scenarios');
  if (!data) return;

  const sel = document.getElementById('sb-scenario-select');
  const labels = {
    all_clear: 'All Clear (Normal Campus Day)',
  };
  sel.innerHTML = data.scenarios.map(s => {
    const label = labels[s] || s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    return `<option value="${s}">${label}</option>`;
  }).join('');

  sel.addEventListener('change', async () => {
    const res = await apiFetch('/api/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: sel.value }),
    });
    if (res?.ok) {
      toast(`Scenario loaded: ${sel.options[sel.selectedIndex].text}`, 'info');
      await refresh();
    }
  });
}

async function loadDevices() {
  const data = await apiFetch('/api/devices');
  if (!data) return;
  appState.devices = data.devices;
}

// ── Main Refresh Loop ──────────────────────────────────────
async function refresh() {
  const [snap, status, detData] = await Promise.all([
    apiFetch('/api/snapshot'),
    apiFetch('/api/status'),
    apiFetch('/api/detections'),
  ]);

  if (snap)     appState.snapshot = snap;
  if (detData)  appState.detections = detData.detections || [];

  if (status) {
    appState.gatesBlocked = status.unavailable_gates || [];
    updateTopBar(status);
    updateSidebar(status);
    updateGateBtns(status);
  }

  if (snap) {
    updateMetrics(snap);
    updateRoomsTable(snap);
    updateEventLog(snap);
    updateBuildingBadges(snap);
    updateMapArrows(snap);
    updateEgressCard(document.getElementById('sb-room-select').value);
  }

  if (appState.tab === 'cctv') {
    renderCamGrid();
  }

  if (appState.tab === 'map' && appState.mapView !== 'campus') {
    renderBuildingFloors(appState.selectedBuilding, snap);
  }
}

// ── Top Bar ────────────────────────────────────────────────
function updateTopBar(status) {
  const dot = document.getElementById('topbar-dot');
  const txt = document.getElementById('topbar-status-text');
  const lvl = status.status.toLowerCase();
  dot.className = `live-dot ${lvl === 'normal' ? '' : lvl}`;
  txt.textContent = status.status_label.split('—')[0].trim();
  txt.style.color = lvl === 'critical' ? 'var(--c-red)' : lvl === 'warning' ? 'var(--c-amber)' : 'var(--c-green)';
}

// ── Sidebar ────────────────────────────────────────────────
function updateSidebar(status) {
  const badge = document.getElementById('sb-status-badge');
  const label = document.getElementById('sb-status-label');
  const sub   = document.getElementById('sb-status-sub');
  const lvl = status.status.toLowerCase();

  badge.className = `sb-status-badge ${lvl === 'normal' ? 'normal' : lvl === 'warning' ? 'warning' : 'critical'}`;
  label.textContent = status.status_label;
  sub.textContent = `${status.known_incidents} active incident${status.known_incidents !== 1 ? 's' : ''}`;
}

function updateGateBtns(status) {
  const blocked = status.unavailable_gates || [];
  ['GATE-W', 'GATE-NE'].forEach(g => {
    const short = g === 'GATE-W' ? 'w' : 'ne';
    const btn  = document.getElementById(`gate-${short}-btn`);
    const stat = document.getElementById(`gate-${short}-status`);
    const isBlocked = blocked.includes(g);
    btn.className  = `gate-btn ${isBlocked ? 'blocked' : 'open'}`;
    stat.textContent = isBlocked ? 'BLOCKED' : 'OPEN';
  });

  // Data tab gate badges
  const dW  = document.getElementById('d-gate-w');
  const dNE = document.getElementById('d-gate-ne');
  if (dW)  { dW.className  = blocked.includes('GATE-W')  ? 'badge blocked' : 'badge safe'; dW.textContent  = blocked.includes('GATE-W')  ? '🔴 BLOCKED' : '🟢 OPEN'; }
  if (dNE) { dNE.className = blocked.includes('GATE-NE') ? 'badge blocked' : 'badge safe'; dNE.textContent = blocked.includes('GATE-NE') ? '🔴 BLOCKED' : '🟢 OPEN'; }
}

async function updateEgressCard(roomId) {
  if (!roomId || !appState.snapshot) return;
  const r = appState.snapshot.routes?.[roomId];
  if (!r) return;

  const card      = document.getElementById('sb-egress-card');
  const doorEl    = document.getElementById('egress-door');
  const pathEl    = document.getElementById('egress-path');
  const gateEl    = document.getElementById('egress-gate');
  const greenColor = 'var(--c-green)';
  const redColor   = 'var(--c-red)';
  const amberColor = 'var(--c-amber)';

  if (r.status === 'MODELED_ROUTE_AVAILABLE') {
    card.className = 'egress-card safe';
    const strokeColor = greenColor;
    setEgressIcons(strokeColor);
    doorEl.textContent = `Exit via: ${r.door_label || r.door || '—'}`;
    pathEl.textContent = `Follow corridor → descend stairs to ground floor`;
    gateEl.textContent = `Assemble at: ${r.gate === 'GATE-W' ? 'West Gate (GATE-W)' : 'Northeast Gate (GATE-NE)'}`;
  } else if (r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE') {
    card.className = 'egress-card warning';
    setEgressIcons(amberColor);
    doorEl.textContent = 'HOLD — Shelter in Place';
    pathEl.textContent = 'Direct corridor has an active hazard nearby.';
    gateEl.textContent = 'Await authorized campus security guidance.';
  } else {
    card.className = 'egress-card critical';
    setEgressIcons(redColor);
    doorEl.textContent = 'NO CONFIRMED ROUTE';
    pathEl.textContent = 'All exits or gates are currently blocked.';
    gateEl.textContent = 'Follow authorized emergency personnel.';
  }
}

function setEgressIcons(color) {
  document.querySelectorAll('.egress-icon').forEach(svg => {
    svg.setAttribute('stroke', color);
  });
}

// ── Gate Toggle ────────────────────────────────────────────
async function toggleGate(gateName) {
  const blocked = [...appState.gatesBlocked];
  const idx = blocked.indexOf(gateName);
  if (idx >= 0) blocked.splice(idx, 1);
  else blocked.push(gateName);

  const res = await apiFetch('/api/gates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unavailable_gates: blocked }),
  });
  if (res?.ok) {
    toast(`${gateName} ${blocked.includes(gateName) ? 'blocked' : 'reopened'}`, blocked.includes(gateName) ? 'error' : 'success');
    await refresh();
  }
}

// ── Reset ──────────────────────────────────────────────────
async function resetAll() {
  const res = await apiFetch('/api/reset', { method: 'POST' });
  if (res?.ok) {
    document.getElementById('sb-scenario-select').value = 'all_clear';
    toast('Campus reset to All-Clear normal state', 'success');
    await refresh();
  }
}

// ── MQTT Broadcast ─────────────────────────────────────────
async function broadcastMQTT() {
  toast('Broadcasting to ESP32 via MQTT…', 'info');
  const res = await apiFetch('/api/mqtt/broadcast');
  if (res?.ok) toast('ESP32 signal sent successfully', 'success');
  else toast('MQTT broadcast failed — check network', 'error');
}

// ── Pill Tab Navigation ────────────────────────────────────
function switchTab(tab) {
  appState.tab = tab;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.getElementById(`pill-${tab}`).classList.add('active');

  if (tab === 'cctv') renderCamGrid();
  if (tab === 'data' && appState.snapshot) {
    updateMetrics(appState.snapshot);
    updateRoomsTable(appState.snapshot);
  }
}

// ── Map Sub-Navigation ─────────────────────────────────────
function switchMapView(view) {
  ['campus', 'b1', 'b2', 'b3'].forEach(v => {
    document.getElementById(`mapbtn-${v}`)?.classList.toggle('active', v === view);
  });

  appState.mapView = view;

  if (view === 'campus') {
    document.getElementById('view-campus').style.display = '';
    document.getElementById('view-building').style.display = 'none';
    appState.selectedBuilding = null;
  } else {
    const bNum = view === 'b1' ? 1 : view === 'b2' ? 2 : 3;
    appState.selectedBuilding = bNum;
    document.getElementById('view-campus').style.display = 'none';
    document.getElementById('view-building').style.display = '';
    renderBuildingFloors(bNum, appState.snapshot);
  }
}

// ── Building Floor Plan Renderer ───────────────────────────
function renderBuildingFloors(bNum, snapshot) {
  if (!bNum) return;
  const buildings = { 1: [4, 5], 2: [4, 3], 3: [2, 2] };
  const images    = { 1: '/static/b1_floor_plan.jpg', 2: '/static/b2_floor_plan.jpg', 3: '/static/b3_floor_plan.jpg' };
  const [floors, roomsPerFloor] = buildings[bNum];

  document.getElementById('bld-view-title').textContent = `Building ${bNum}`;
  document.getElementById('bld-view-sub').textContent =
    `${floors} Floor${floors > 1 ? 's' : ''} · ${roomsPerFloor} Classroom${roomsPerFloor > 1 ? 's' : ''} per floor · ESP32 nodes at stairwells`;

  const grid = document.getElementById('floor-grid');
  grid.style.gridTemplateColumns = floors > 1 ? '1fr 1fr' : '1fr';

  let anyBlocked = false;
  let anyCritical = false;

  grid.innerHTML = '';
  for (let f = 1; f <= floors; f++) {
    const pCode = `B${bNum}-F${f}`;

    // Arrow config per building
    const imgW = 1024;
    let stairLX, stairRX, doorY, corrY;
    if (bNum === 1) {
      stairLX = 115; stairRX = 920; doorY = 295; corrY = 340;
    } else if (bNum === 2) {
      stairLX = 100; stairRX = 940; doorY = 300; corrY = 345;
    } else {
      stairLX = 100; stairRX = 940; doorY = 280; corrY = 325;
    }

    const imgH = bNum === 1 ? 502 : bNum === 2 ? 523 : 436;

    // Collect arrows and hold badges for all rooms on this floor
    let arrows = '';
    let holdBadges = '';
    let floorSafe = true;
    let floorCritical = false;

    for (let r = 1; r <= roomsPerFloor; r++) {
      const rmId = `${pCode}-R${r}`;
      const rm = snapshot?.routes?.[rmId];
      if (!rm) continue;

      // Room door X position
      let rmX;
      if (bNum === 1) {
        // 5 rooms, stair on both sides. rooms start after left stair ~145
        rmX = 145 + (r - 0.5) * ((920 - 145) / roomsPerFloor);
      } else if (bNum === 2) {
        rmX = 140 + (r - 0.5) * ((940 - 140) / roomsPerFloor);
      } else {
        rmX = 140 + (r - 0.5) * ((940 - 140) / roomsPerFloor);
      }

      if (rm.status === 'MODELED_ROUTE_AVAILABLE') {
        const useLeft = rm.route?.some(n => n.includes('STAIR-L')) || r <= roomsPerFloor / 2;
        const targetX = useLeft ? stairLX : stairRX;
        arrows += `
          <path d="M ${rmX} ${doorY} L ${rmX} ${corrY} L ${targetX} ${corrY}"
            fill="none" stroke="oklch(55% 0.18 145)" stroke-width="3.5"
            stroke-dasharray="8,5" marker-end="url(#arr-f-${bNum}-${f})">
            <animate attributeName="stroke-dashoffset" from="26" to="0" dur="0.7s" repeatCount="indefinite"/>
          </path>`;
      } else if (rm.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE') {
        floorSafe = false;
        holdBadges += `
          <rect x="${rmX - 22}" y="100" width="44" height="18" rx="4" fill="oklch(50% 0.22 25)" opacity="0.9"/>
          <text x="${rmX}" y="113" text-anchor="middle" fill="white" font-size="10" font-weight="700" font-family="DM Sans, sans-serif">HOLD</text>`;
      } else if (rm.status === 'NO_CONFIRMED_ROUTE') {
        floorSafe = false;
        floorCritical = true;
      }
    }

    if (floorCritical) anyCritical = true;
    if (!floorSafe) anyBlocked = true;

    const badgeClass = floorCritical ? 'critical' : !floorSafe ? 'warning' : 'safe';
    const badgeText  = floorCritical ? '🔴 Blocked' : !floorSafe ? '🟡 Caution' : '🟢 Safe';

    const card = document.createElement('div');
    card.className = 'floor-card';
    card.innerHTML = `
      <div class="floor-card-header">
        <div>
          <span class="floor-card-title">Floor ${f}</span>
          <span class="floor-card-code"> · ${pCode}</span>
        </div>
        <span class="badge ${badgeClass}">${badgeText}</span>
      </div>
      <div class="floor-card-img-wrap" style="position:relative;">
        <img src="${images[bNum]}" alt="Floor ${f} Plan" style="width:100%; display:block;" />
        <svg viewBox="0 0 ${imgW} ${imgH}" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker id="arr-f-${bNum}-${f}" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
              <polygon points="0 0, 7 3.5, 0 7" fill="oklch(55% 0.18 145)"/>
            </marker>
          </defs>
          ${arrows}
          ${holdBadges}
          <!-- ESP32 nodes at stairwells -->
          <circle cx="${stairLX}" cy="${corrY}" r="10" fill="oklch(52% 0.20 255)"/>
          <text x="${stairLX}" y="${corrY + 4}" text-anchor="middle" fill="white" font-size="8" font-weight="700" font-family="DM Sans, sans-serif">ESP</text>
          <circle cx="${stairRX}" cy="${corrY}" r="10" fill="oklch(52% 0.20 255)"/>
          <text x="${stairRX}" y="${corrY + 4}" text-anchor="middle" fill="white" font-size="8" font-weight="700" font-family="DM Sans, sans-serif">ESP</text>
        </svg>
      </div>`;
    grid.appendChild(card);
  }

  // Update building view badge
  const bldBadge = document.getElementById('bld-view-badge');
  bldBadge.className = `badge ${anyCritical ? 'critical' : anyBlocked ? 'warning' : 'safe'}`;
  bldBadge.textContent = anyCritical ? '🔴 Hazard Detected' : anyBlocked ? '🟡 Partial Obstruction' : '🟢 All Floors Safe';
}

// ── Map Arrow Color Update (based on gate/threat state) ────
function updateMapArrows(snapshot) {
  // Update building status dots in subnav
  [1, 2, 3].forEach(b => {
    const dot = document.getElementById(`dot-b${b}`);
    if (!dot) return;
    const hasCritical = Object.entries(snapshot.routes || {}).some(
      ([rm, r]) => rm.startsWith(`B${b}-`) && r.status !== 'MODELED_ROUTE_AVAILABLE'
    );
    dot.style.background = hasCritical ? 'var(--c-red)' : 'var(--c-green)';
  });
}

// ── Metrics ────────────────────────────────────────────────
function updateMetrics(snap) {
  const counts = snap.counts || {};
  setText('m-safe',      counts['MODELED_ROUTE_AVAILABLE'] ?? '—');
  setText('m-hold',      counts['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? '—');
  setText('m-blocked',   counts['NO_CONFIRMED_ROUTE'] ?? '—');
  setText('m-incidents', snap.known_incident_count ?? '—');
}

function updateBuildingBadges(snap) {
  [1, 2, 3].forEach(b => {
    const el = document.getElementById(`b${b}-badge`);
    if (!el) return;
    const hasCrit = Object.entries(snap.routes || {}).some(
      ([rm, r]) => rm.startsWith(`B${b}-`) && r.status !== 'MODELED_ROUTE_AVAILABLE'
    );
    el.innerHTML = hasCrit
      ? '<span class="badge critical">🔴 Alert</span>'
      : '<span class="badge safe">🟢 Normal</span>';
  });
}

// ── Rooms Table ────────────────────────────────────────────
function updateRoomsTable(snap) {
  const tbody = document.getElementById('rooms-table-body');
  if (!tbody) return;

  const routes = snap.routes || {};
  const rows = Object.entries(routes).map(([rm, r]) => {
    const statusClass = r.status === 'MODELED_ROUTE_AVAILABLE' ? 'safe'
      : r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE' ? 'hold'
      : 'blocked';
    const statusLabel = r.status === 'MODELED_ROUTE_AVAILABLE' ? '🟢 Safe Route'
      : r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE' ? '🟡 Shelter in Place'
      : '🔴 No Route';

    return `<tr>
      <td><span class="room-code">${rm}</span></td>
      <td><span class="badge ${statusClass}">${statusLabel}</span></td>
      <td><span class="gate-code">${r.gate || '—'}</span></td>
      <td>${r.door_label || '—'}</td>
      <td>${r.route?.length ?? '—'}</td>
    </tr>`;
  });

  tbody.innerHTML = rows.join('') || '<tr><td colspan="5" style="text-align:center; color:var(--c-muted); padding:20px;">No data.</td></tr>';

  const badge = document.getElementById('table-status-badge');
  const lvl = snap.global_status?.toLowerCase() || 'normal';
  badge.className = `badge ${lvl === 'normal' ? 'safe' : lvl === 'warning' ? 'warning' : 'critical'}`;
  badge.textContent = lvl === 'normal' ? '🟢 All Clear' : lvl === 'warning' ? '🟡 Caution' : '🔴 Emergency';
}

// ── Event Log ──────────────────────────────────────────────
function updateEventLog(snap) {
  const el = document.getElementById('event-log');
  if (!el) return;
  const events = snap.events || [];
  if (!events.length) {
    el.innerHTML = '<div class="empty-state"><p>No active incidents. Campus status normal.</p></div>';
    return;
  }
  el.innerHTML = `<div class="event-list">${events.map(ev => `
    <div class="event-item ${ev.level.toLowerCase()}">
      <div class="event-dot ${ev.level.toLowerCase()}"></div>
      <div class="event-text">
        <b>${ev.device_id}</b> — ${ev.level}<br>
        <span style="color:var(--c-muted);">Event: <code style="font-family:IBM Plex Mono,monospace;font-size:10px;">${ev.event_id}</code></span>
        ${ev.location ? `<br><span style="color:var(--c-muted);">Location: ${ev.location}</span>` : ''}
      </div>
    </div>`).join('')}</div>`;
}

// ── CCTV Grid ──────────────────────────────────────────────
function filterCams(group) {
  appState.camFilter = group;
  document.querySelectorAll('.cam-filter-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`camf-${group}`)?.classList.add('active');
  renderCamGrid();
}

function renderCamGrid() {
  const grid = document.getElementById('cam-grid');
  if (!grid) return;

  const filter = appState.camFilter;
  const allDevices = appState.devices;
  const detections = appState.detections || [];

  const filtered = Object.values(allDevices).filter(d => {
    const isOutdoor = d.kind === 'outdoor';
    const b1 = d.device_id.startsWith('B1') && !isOutdoor;
    const b2 = d.device_id.startsWith('B2') && !isOutdoor;
    const b3 = d.device_id.startsWith('B3') && !isOutdoor;
    if (filter === 'outside') return isOutdoor;
    if (filter === 'b1') return b1;
    if (filter === 'b2') return b2;
    if (filter === 'b3') return b3;
    return false;
  });

  if (!filtered.length) {
    grid.innerHTML = '<div class="empty-state"><p>No devices in this group.</p></div>';
    return;
  }

  grid.innerHTML = filtered.map(d => {
    const match = detections.filter(r => r.device_id === d.device_id);
    const latest = match[match.length - 1];
    const hasAlert = !!latest;
    const clf = latest?.classification || {};
    const scores = latest?.scores || {};
    const lvl = clf.level || 'NORMAL';
    const badgeClass = lvl === 'CRITICAL' ? 'critical' : lvl === 'WARNING' ? 'warning' : 'safe';
    const badgeText  = lvl === 'CRITICAL' ? '🔴 THREAT' : lvl === 'WARNING' ? '🟡 WARNING' : '🟢 Normal';

    const coverage = d.covered_rooms?.length
      ? d.covered_rooms.join(', ')
      : (d.covered_node || 'Perimeter');

    const videoSection = hasAlert ? `
      <div class="cam-video-row">
        <div>
          <video src="/videos-project/test_video.mp4" controls muted playsinline
            style="width:100%; border-radius:6px; border:1px solid var(--c-border);"
            onloadedmetadata="this.currentTime=0;">
          </video>
        </div>
        <div class="cam-scores">
          <div style="font-size:11px; font-weight:700; color:var(--c-navy); margin-bottom:8px;">AI Threat Scoreboard</div>
          <div class="cam-score-row"><span>Threat Index</span><span class="cam-score-val threat">${clf.index?.toFixed(1) ?? '—'} / 100</span></div>
          <div class="cam-score-row"><span>Object (O)</span><span class="cam-score-val">${scores.object ?? clf.object ?? '—'}</span></div>
          <div class="cam-score-row"><span>Pose (P)</span><span class="cam-score-val">${scores.pose ?? clf.pose ?? '—'}</span></div>
          <div class="cam-score-row"><span>Acoustic (A)</span><span class="cam-score-val">${scores.acoustic ?? clf.acoustic ?? '—'}</span></div>
          <div class="cam-score-row"><span>Verified</span><span class="cam-score-val ${clf.verified ? 'threat' : ''}">${clf.verified ? 'YES' : 'Awaiting Review'}</span></div>
        </div>
      </div>` : `
      <div style="background:var(--c-bg); border:1px solid var(--c-border); border-radius:6px; padding:12px 14px; text-align:center; margin-top:8px;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--c-placeholder)" stroke-width="1.5" style="margin-bottom:6px; display:block; margin-left:auto; margin-right:auto;">
          <path d="M15 10l4.553-2.07A1 1 0 0121 8.86v6.28a1 1 0 01-1.447.93L15 14M4 8h11a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p style="font-size:11px; color:var(--c-muted);">No suspicious indicators — feed normal</p>
      </div>`;

    return `
    <div class="cam-card ${hasAlert ? 'alert' : ''}">
      <div class="cam-card-header">
        <span class="cam-id">${d.device_id}</span>
        <span class="badge ${badgeClass}">${badgeText}</span>
      </div>
      <div class="cam-body">
        <div class="cam-coverage">Coverage: <b>${coverage}</b></div>
        ${videoSection}
      </div>
    </div>`;
  }).join('');
}

// ── Utility ────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function friendlyRoom(id) {
  // "B1-F2-R3" → "Building 1 · Floor 2 · Room 3"
  const m = id.match(/^B(\d+)-F(\d+)-R(\d+)$/);
  if (!m) return id;
  return `Building ${m[1]} · Floor ${m[2]} · Room ${m[3]}`;
}
