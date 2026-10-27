/* ============================================================
   SENTINEL — app.js
   Campus Safety Command System
   Strict ISO 7010 semantics, clean SVG vector graphics, zero emojis
   ============================================================ */

const API = '';

// ── Application State ──────────────────────────────────────
let appState = {
  tab: 'map',
  mapView: 'campus',
  selectedBuilding: null,
  gatesBlocked: [],
  manualBlocks: [],
  camFilter: 'outside',
  snapshot: null,
  devices: {},
  detections: [],
  rooms: [],
  lastStatus: 'NORMAL',
  audioEnabled: true,
};

// ── Web Audio Synthesizer for Emergency Alerts ────────────
let audioCtx = null;
function getAudioContext() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function playWarningTone() {
  if (!appState.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
    osc.frequency.setValueAtTime(880.00, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (e) {
    console.warn('Audio notice:', e);
  }
}

function playEmergencySiren() {
  if (!appState.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.linearRampToValueAtTime(1100, now + 0.25);
    osc.frequency.linearRampToValueAtTime(600, now + 0.5);
    osc.frequency.linearRampToValueAtTime(1100, now + 0.75);
    osc.frequency.linearRampToValueAtTime(600, now + 1.0);
    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 1.0);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 1.0);
  } catch (e) {
    console.warn('Siren audio error:', e);
  }
}

function toggleAudio() {
  appState.audioEnabled = !appState.audioEnabled;
  const btn = document.getElementById('mute-btn');
  const label = document.getElementById('mute-label');
  const icon = document.getElementById('mute-icon');

  if (appState.audioEnabled) {
    btn.classList.remove('active');
    label.textContent = 'Audio ON';
    icon.innerHTML = `
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
    `;
    toast('Emergency sound alarms enabled', 'info');
    getAudioContext();
  } else {
    btn.classList.add('active');
    label.textContent = 'Audio Muted';
    icon.innerHTML = `
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>
    `;
    toast('Sound alarms muted', 'warning');
  }
}

// ── Application Initialization ─────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  startClock();
  await loadRooms();
  await loadScenarios();
  await loadDevices();
  populateBlockDropdowns();
  await refresh();
  setInterval(refresh, 5000);
});

// ── System Clock ───────────────────────────────────────────
function startClock() {
  const el = document.getElementById('topbar-time');
  const tick = () => {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-US', { hour12: false });
    requestAnimationFrame(() => setTimeout(tick, 1000));
  };
  tick();
}

// ── Toast Notifications ────────────────────────────────────
let toastTimer = null;
function toast(msg, type = 'info', duration = 3500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, duration);
}

// ── API Fetch Helper ───────────────────────────────────────
async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(API + path, options);
    if (!res.ok) throw new Error(await res.text());
    return await res.json();
  } catch (e) {
    console.error('API Error:', path, e);
    return null;
  }
}

// ── Load Dropdowns & Metadata ──────────────────────────────
async function loadRooms() {
  const data = await apiFetch('/api/rooms');
  if (!data) return;
  appState.rooms = data.rooms;

  const sel = document.getElementById('sb-room-select');
  sel.innerHTML = data.rooms.map(r =>
    `<option value="${r}">${formatRoomLabel(r)}</option>`
  ).join('');
  sel.addEventListener('change', () => {
    updateEgressCard(sel.value);
    if (appState.tab === 'map' && appState.mapView !== 'campus') {
      renderBuildingFloors(appState.selectedBuilding, appState.snapshot);
    }
  });
  if (data.rooms.length) updateEgressCard(data.rooms[0]);
}

async function loadScenarios() {
  const data = await apiFetch('/api/scenarios');
  if (!data) return;

  const sel = document.getElementById('sb-scenario-select');
  const labels = {
    all_clear: 'All Clear (Normal Baseline)',
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
      toast(`Emergency Scenario Loaded: ${sel.options[sel.selectedIndex].text}`, 'info');
      await refresh();
    }
  });
}

async function loadDevices() {
  const data = await apiFetch('/api/devices');
  if (!data) return;
  appState.devices = data.devices;
}

// ── Populate Sidebar Hazard Block Selectors ────────────────
function populateBlockDropdowns() {
  const roomSel     = document.getElementById('sb-block-room');
  const stairSel    = document.getElementById('sb-block-stair');
  const corridorSel = document.getElementById('sb-block-corridor');

  // Rooms
  const buildings = { 1: [4, 5], 2: [4, 3], 3: [2, 2] };
  let roomOpts = '<option value="">+ Block a Classroom…</option>';
  for (const [b, [floors, count]] of Object.entries(buildings)) {
    for (let f = 1; f <= floors; f++) {
      for (let r = 1; r <= count; r++) {
        const id = `B${b}-F${f}-R${r}`;
        roomOpts += `<option value="${id}">${id} (B${b}-F${f})</option>`;
      }
    }
  }
  if (roomSel) roomSel.innerHTML = roomOpts;

  // Corridors
  let corrOpts = '<option value="">+ Block Corridor Area…</option>';
  for (const [b, [floors, count]] of Object.entries(buildings)) {
    for (let f = 1; f <= floors; f++) {
      for (let c = 0; c <= count; c++) {
        const id = `B${b}-F${f}-C${c}`;
        const loc = c === 0 ? 'West End' : c === count ? 'East End' : `Bay ${c}`;
        corrOpts += `<option value="${id}">B${b}-F${f} Corridor (${loc})</option>`;
      }
    }
  }
  if (corridorSel) corridorSel.innerHTML = corrOpts;

  // Stairwells
  let stairOpts = '<option value="">+ Close a Stairwell…</option>';
  for (const [b, [floors]] of Object.entries(buildings)) {
    for (let f = 1; f <= floors; f++) {
      stairOpts += `<option value="B${b}-F${f}-STAIR-L">Building ${b} Floor ${f} Left Stair</option>`;
      stairOpts += `<option value="B${b}-F${f}-STAIR-R">Building ${b} Floor ${f} Right Stair</option>`;
    }
  }
  if (stairSel) stairSel.innerHTML = stairOpts;
}

async function handleRoomBlock(roomId) {
  if (!roomId) return;
  if (!appState.manualBlocks.includes(roomId)) {
    appState.manualBlocks.push(roomId);
    await syncBlocks();
    toast(`Classroom ${roomId} marked unavailable`, 'warning');
  }
  document.getElementById('sb-block-room').value = '';
}

async function handleCorridorBlock(corrId) {
  if (!corrId) return;
  if (!appState.manualBlocks.includes(corrId)) {
    appState.manualBlocks.push(corrId);
    await syncBlocks();
    toast(`Corridor ${corrId} blocked`, 'warning');
  }
  document.getElementById('sb-block-corridor').value = '';
}

async function handleStairBlock(stairId) {
  if (!stairId) return;
  if (!appState.manualBlocks.includes(stairId)) {
    appState.manualBlocks.push(stairId);
    await syncBlocks();
    toast(`Stairwell ${stairId} closed for drill`, 'warning');
  }
  document.getElementById('sb-block-stair').value = '';
}

async function clearAllBlocks() {
  if (!appState.manualBlocks.length) return;
  appState.manualBlocks = [];
  await syncBlocks();
  toast('All hazard closures reopened', 'success');
}

async function removeBlock(nodeId) {
  appState.manualBlocks = appState.manualBlocks.filter(n => n !== nodeId);
  await syncBlocks();
  toast(`Reopened: ${nodeId}`, 'success');
}

async function syncBlocks() {
  const res = await apiFetch('/api/blocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manual_blocks: appState.manualBlocks }),
  });
  if (res?.ok) {
    renderActiveClosures();
    await refresh();
  }
}

function renderActiveClosures() {
  const container = document.getElementById('active-closures-container');
  if (!container) return;
  if (!appState.manualBlocks.length) {
    container.innerHTML = '<span style="font-size:10px; color:var(--c-sidebar-muted);">No manual blocks active.</span>';
    return;
  }
  container.innerHTML = appState.manualBlocks.map(b => `
    <span style="background:rgba(220,38,38,0.25); border:1px solid var(--c-red); color:#fca5a5; font-size:10px; font-weight:700; padding:2px 7px; border-radius:10px; display:inline-flex; align-items:center; gap:4px; font-family:'JetBrains Mono',monospace;">
      ${b}
      <span style="cursor:pointer; color:#ffffff; font-weight:bold;" onclick="removeBlock('${b}')">&times;</span>
    </span>
  `).join('');
}

// ── Main Refresh Loop ──────────────────────────────────────
async function refresh() {
  const [snap, status, detData] = await Promise.all([
    apiFetch('/api/snapshot'),
    apiFetch('/api/status'),
    apiFetch('/api/detections'),
  ]);

  if (snap)    appState.snapshot = snap;
  if (detData) appState.detections = detData.detections || [];

  if (status) {
    appState.gatesBlocked = status.unavailable_gates || [];
    appState.manualBlocks = status.manual_blocks || [];
    renderActiveClosures();
    handleStatusChange(status);
    updateTopBar(status);
    updateSidebar(status);
    updateGateControls(status);
  }

  if (snap) {
    updateMetrics(snap);
    updateRoomsTable(snap);
    updateEventLog(snap);
    updateBuildingBadges(snap);
    renderOutdoorPaths(snap);
    updateEgressCard(document.getElementById('sb-room-select').value);
  }

  if (appState.tab === 'cctv') {
    renderCamGrid();
  }

  if (appState.tab === 'map' && appState.mapView !== 'campus') {
    renderBuildingFloors(appState.selectedBuilding, snap);
  }
}

// ── Multi-Modal Status Transition & Alarms ─────────────────
function handleStatusChange(status) {
  const curr = status.status;
  const banner = document.getElementById('alert-banner');
  const bannerText = document.getElementById('alert-banner-text');

  if (curr !== appState.lastStatus) {
    if (curr === 'WARNING') {
      playWarningTone();
      toast('Security Notice: Elevated threat index detected.', 'warning');
      banner.style.display = 'flex';
      banner.className = '';
      bannerText.textContent = 'Caution: Elevated activity under review. Classrooms maintain standard protocol.';
    } else if (curr === 'CRITICAL') {
      playEmergencySiren();
      toast('EMERGENCY: Active hazard confirmed on campus.', 'error');
      banner.style.display = 'flex';
      banner.className = 'critical';
      bannerText.textContent = 'EMERGENCY: Immediate evacuation order in effect. Avoid compromised zones.';
    } else {
      banner.style.display = 'none';
      if (appState.lastStatus !== 'NORMAL') {
        toast('Campus perimeter restored to Normal All-Clear.', 'success');
      }
    }
    appState.lastStatus = curr;
  }
}

// ── Top Bar Updates ────────────────────────────────────────
function updateTopBar(status) {
  const beacon = document.getElementById('topbar-beacon');
  const txt = document.getElementById('topbar-status-text');
  const lvl = status.status.toLowerCase();

  beacon.className = `status-beacon ${lvl}`;
  txt.textContent = status.status === 'NORMAL' ? 'ALL CLEAR' : status.status === 'WARNING' ? 'ELEVATED CAUTION' : 'EMERGENCY ALERT';
  txt.style.color = lvl === 'critical' ? 'var(--c-red)' : lvl === 'warning' ? 'var(--c-amber)' : 'var(--c-green)';
}

// ── Sidebar Updates ────────────────────────────────────────
function updateSidebar(status) {
  const badge  = document.getElementById('sb-status-badge');
  const beacon = document.getElementById('sb-beacon');
  const label  = document.getElementById('sb-status-label');
  const sub    = document.getElementById('sb-status-sub');
  const lvl = status.status.toLowerCase();

  badge.className = `sb-status-badge ${lvl}`;
  beacon.className = `status-beacon ${lvl}`;
  label.textContent = status.status_label;
  sub.textContent = `${status.known_incidents} active incident${status.known_incidents !== 1 ? 's' : ''}`;
}

function updateGateControls(status) {
  const blocked = status.unavailable_gates || [];
  ['GATE-W', 'GATE-NE'].forEach(g => {
    const short = g === 'GATE-W' ? 'w' : 'ne';
    const btn  = document.getElementById(`gate-${short}-btn`);
    const stat = document.getElementById(`gate-${short}-status`);
    const isBlocked = blocked.includes(g);
    btn.className  = `gate-btn ${isBlocked ? 'blocked' : 'open'}`;
    stat.textContent = isBlocked ? 'BLOCKED' : 'OPEN';
  });

  const dW  = document.getElementById('d-gate-w');
  const dNE = document.getElementById('d-gate-ne');
  if (dW) {
    dW.className = blocked.includes('GATE-W') ? 'badge blocked' : 'badge safe';
    dW.innerHTML = `<span class="status-beacon ${blocked.includes('GATE-W') ? 'critical' : 'normal'}" style="width:6px; height:6px;"></span> ${blocked.includes('GATE-W') ? 'BLOCKED' : 'OPEN'}`;
  }
  if (dNE) {
    dNE.className = blocked.includes('GATE-NE') ? 'badge blocked' : 'badge safe';
    dNE.innerHTML = `<span class="status-beacon ${blocked.includes('GATE-NE') ? 'critical' : 'normal'}" style="width:6px; height:6px;"></span> ${blocked.includes('GATE-NE') ? 'BLOCKED' : 'OPEN'}`;
  }
}

// ── Classroom Evacuation Card ──────────────────────────────
async function updateEgressCard(roomId) {
  if (!roomId || !appState.snapshot) return;
  const r = appState.snapshot.routes?.[roomId];
  if (!r) return;

  const card   = document.getElementById('sb-egress-card');
  const doorEl = document.getElementById('egress-door');
  const pathEl = document.getElementById('egress-path');
  const gateEl = document.getElementById('egress-gate');

  if (r.status === 'MODELED_ROUTE_AVAILABLE') {
    card.className = 'egress-card safe';
    doorEl.textContent = `Exit via: ${r.door_label || r.door || 'Designated Door'}`;
    pathEl.textContent = 'Follow corridor to stairwell and descend';
    gateEl.textContent = `Assemble at: ${r.gate === 'GATE-W' ? 'West Gate (GATE-W)' : 'Northeast Gate (GATE-NE)'}`;
  } else if (r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE') {
    card.className = 'egress-card warning';
    doorEl.textContent = 'SHELTER IN PLACE — Hold';
    pathEl.textContent = 'Corridor egress path has an active hazard';
    gateEl.textContent = 'Await authorized security instruction';
  } else {
    card.className = 'egress-card critical';
    doorEl.textContent = 'NO CONFIRMED ROUTE AVAILABLE';
    pathEl.textContent = 'All exit stairwells or gates are compromised';
    gateEl.textContent = 'Follow instructions from on-site emergency team';
  }
}

// ── Gate Toggle Handler ────────────────────────────────────
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
    toast(`${gateName} ${blocked.includes(gateName) ? 'marked Blocked' : 'reopened'}`, blocked.includes(gateName) ? 'warning' : 'success');
    await refresh();
  }
}

// ── Reset to All-Clear Baseline ───────────────────────────
async function resetAll() {
  const res = await apiFetch('/api/reset', { method: 'POST' });
  if (res?.ok) {
    document.getElementById('sb-scenario-select').value = 'all_clear';
    appState.manualBlocks = [];
    renderActiveClosures();
    toast('System baseline restored to All Clear.', 'success');
    await refresh();
  }
}

// ── MQTT Broadcast to ESP32 / Wokwi ────────────────────────
async function broadcastMQTT() {
  toast('Broadcasting signal to ESP32 alarm node via MQTT…', 'info');
  const res = await apiFetch('/api/mqtt/broadcast');
  if (res?.ok) toast('ESP32 telemetry dispatched successfully.', 'success');
  else toast('MQTT broadcast failed to connect.', 'error');
}

// ── Pill Tab Switcher ──────────────────────────────────────
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

    // Auto-sync sidebar room selector to the currently viewed building
    const prefix = `B${bNum}`;
    const sel = document.getElementById('sb-room-select');
    if (sel && appState.rooms?.length) {
      const matchRoom = appState.rooms.find(r => r.startsWith(prefix));
      if (matchRoom && !sel.value.startsWith(prefix)) {
        sel.value = matchRoom;
        updateEgressCard(matchRoom);
      }
    }

    renderBuildingFloors(bNum, appState.snapshot);
  }
}

// ── Outdoor Walkway Path Renderer (Obstacle Avoidance) ─────
function renderOutdoorPaths(snapshot) {
  const container = document.getElementById('outdoor-paths-container');
  if (!container) return;

  const wBlocked  = appState.gatesBlocked.includes('GATE-W');
  const neBlocked = appState.gatesBlocked.includes('GATE-NE');

  const wCircle = document.getElementById('gate-w-circle');
  const wFill   = document.getElementById('gate-w-fill');
  const wText   = document.getElementById('gate-w-text');
  const neCircle = document.getElementById('gate-ne-circle');
  const neFill   = document.getElementById('gate-ne-fill');
  const neText   = document.getElementById('gate-ne-text');

  if (wCircle && wText) {
    wCircle.setAttribute('stroke', wBlocked ? 'var(--c-red)' : 'var(--c-green)');
    if (wFill) wFill.setAttribute('fill', wBlocked ? 'rgba(220, 38, 38, 0.25)' : 'rgba(5, 150, 105, 0.2)');
    wText.textContent = wBlocked ? 'GATE-W (BLOCKED)' : 'GATE-W';
  }
  if (neCircle && neText) {
    neCircle.setAttribute('stroke', neBlocked ? 'var(--c-red)' : 'var(--c-green)');
    if (neFill) neFill.setAttribute('fill', neBlocked ? 'rgba(220, 38, 38, 0.25)' : 'rgba(5, 150, 105, 0.2)');
    neText.textContent = neBlocked ? 'GATE-NE (BLOCKED)' : 'GATE-NE';
  }

  if (wBlocked && neBlocked) {
    container.innerHTML = `
      <g>
        <circle cx="512" cy="382" r="28" fill="rgba(220, 38, 38, 0.2)" stroke="var(--c-red)" stroke-width="2"/>
        <text x="512" y="386" text-anchor="middle" fill="var(--c-red)" font-size="12" font-weight="700" font-family="'Plus Jakarta Sans', sans-serif">ALL GATES BLOCKED</text>
      </g>
    `;
    return;
  }

  // Check if campus is currently in an active emergency or drill
  const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING' || appState.gatesBlocked.length > 0 || appState.manualBlocks.length > 0;

  // During ALL CLEAR (Normal Baseline), do not clutter map with emergency evacuation arrows
  if (!isEmergency) {
    container.innerHTML = `
      <g>
        <rect x="362" y="22" width="300" height="26" rx="13" fill="#0f172a" opacity="0.9" stroke="var(--c-green)" stroke-width="1.5"/>
        <circle cx="380" cy="35" r="4.5" fill="var(--c-green)"/>
        <text x="512" y="39" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans', sans-serif">ALL CLEAR — GATES &amp; WALKWAYS SECURE</text>
      </g>
    `;
    return;
  }

  // Check whether each building actually has any room that CAN safely evacuate
  const b1CanEvacuate = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B1-') && r.status === 'MODELED_ROUTE_AVAILABLE'
  );
  const b2CanEvacuate = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B2-') && r.status === 'MODELED_ROUTE_AVAILABLE'
  );
  const b3CanEvacuate = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B3-') && r.status === 'MODELED_ROUTE_AVAILABLE'
  );

  const b1HasThreat = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B1-') && r.status === 'NO_CONFIRMED_ROUTE'
  );
  const b2HasThreat = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B2-') && r.status === 'NO_CONFIRMED_ROUTE'
  );
  const b3HasThreat = Object.entries(snapshot?.routes || {}).some(
    ([rm, r]) => rm.startsWith('B3-') && r.status === 'NO_CONFIRMED_ROUTE'
  );

  let pathsHtml = '';

  // Calibrated Obstacle-Free Walkway Waypoints along open concrete driveways (Zero Building/Tree/Fence clipping):
  // West Gate Portal: (195, 405) with clear paved driveway along y=405
  // NE Gate Portal: (778, 146) with clear northeast driveway through (750, 160) -> (690, 210)
  // Central Courtyard Open Quad: (460, 450) and (600, 450)

  // 1. Building 1 Left Stair Egress: only draw if Building 1 CAN evacuate
  if (b1CanEvacuate) {
    if (!wBlocked) {
      pathsHtml += `
        <path d="M 240 395 L 235 405 L 195 405" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.9s" repeatCount="indefinite"/>
        </path>`;
    } else {
      // Reroute across open quad driveway avoiding trees and fences
      pathsHtml += `
        <path d="M 240 395 L 330 405 L 460 450 L 600 450 L 660 350 L 690 210 L 750 160 L 778 146" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="1.3s" repeatCount="indefinite"/>
        </path>`;
    }
  }

  // 2. Building 1 Right Stair Egress: only draw if Building 1 CAN evacuate
  if (b1CanEvacuate) {
    if (!neBlocked) {
      pathsHtml += `
        <path d="M 630 310 L 690 210 L 750 160 L 778 146" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.8s" repeatCount="indefinite"/>
        </path>`;
    } else {
      // Reroute through clear quad driveway into West Gate along y=405
      pathsHtml += `
        <path d="M 630 310 L 660 350 L 600 450 L 460 450 L 330 405 L 195 405" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="1.3s" repeatCount="indefinite"/>
        </path>`;
    }
  }

  // 3. Building 2 Egress: ONLY draw if Building 2 CAN safely evacuate
  if (b2CanEvacuate) {
    if (!neBlocked) {
      pathsHtml += `
        <path d="M 640 450 L 630 350 L 660 240 L 750 160 L 778 146" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="1.1s" repeatCount="indefinite"/>
        </path>`;
    } else {
      pathsHtml += `
        <path d="M 640 480 L 580 480 L 460 450 L 330 405 L 195 405" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="1.2s" repeatCount="indefinite"/>
        </path>`;
    }
  }

  // 4. Building 3 Egress: ONLY draw if Building 3 CAN safely evacuate
  if (b3CanEvacuate) {
    if (!wBlocked) {
      pathsHtml += `
        <path d="M 420 500 L 330 405 L 195 405" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.9s" repeatCount="indefinite"/>
        </path>`;
    } else {
      pathsHtml += `
        <path d="M 420 500 L 460 460 L 600 450 L 660 350 L 690 210 L 750 160 L 778 146" fill="none" stroke="var(--c-green)" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-g)">
          <animate attributeName="stroke-dashoffset" from="32" to="0" dur="1.3s" repeatCount="indefinite"/>
        </path>`;
    }
  }

  // 6 Ground-Floor Perimeter Camera Devices (Ground Level Only)
  const outdoorCams = [
    { id: 'B1-OUT-L', x: 200, y: 425 },
    { id: 'B1-OUT-R', x: 720, y: 225 },
    { id: 'B2-OUT-L', x: 670, y: 495 },
    { id: 'B2-OUT-R', x: 750, y: 360 },
    { id: 'B3-OUT-L', x: 300, y: 535 },
    { id: 'B3-OUT-R', x: 440, y: 560 },
  ];

  let outdoorCamBadges = '';
  outdoorCams.forEach(c => {
    const hasThreat = appState.detections.find(d => d.device_id === c.id);
    const lvl = hasThreat?.classification?.level || 'NORMAL';
    const isBlocked = snapshot?.blocked?.includes(c.id);
    const isCaution = snapshot?.caution?.includes(c.id);
    const dotCol = (lvl === 'CRITICAL' || isBlocked) ? 'var(--c-red)' : (lvl === 'WARNING' || isCaution) ? 'var(--c-amber)' : 'var(--c-green)';
    outdoorCamBadges += `
      <g>
        <rect x="${c.x}" y="${c.y}" width="98" height="24" rx="4" fill="#0f172a" stroke="#334155" stroke-width="1.5" opacity="0.95"/>
        <circle cx="${c.x + 12}" cy="${c.y + 12}" r="4.5" fill="${dotCol}"/>
        <text x="${c.x + 24}" y="${c.y + 16}" fill="#ffffff" font-size="10" font-weight="700" font-family="'JetBrains Mono', monospace">${c.id}</text>
      </g>
    `;
  });

  // Dynamic Ground Stair Beacons matching the real evacuation state of each building:
  const getBeaconHtml = (cx, cy, canEvac, hasThr) => {
    const col = canEvac ? 'var(--c-green)' : hasThr ? 'var(--c-red)' : 'var(--c-amber)';
    return `
      <circle cx="${cx}" cy="${cy}" r="7" fill="${col}"/>
      <circle cx="${cx}" cy="${cy}" r="13" fill="none" stroke="${col}" stroke-width="2" opacity="0.6">
        <animate attributeName="r" values="7;16;7" dur="2s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.8;0.1;0.8" dur="2s" repeatCount="indefinite"/>
      </circle>
    `;
  };

  const beacons = `
    <!-- Building 1 Left Stair Base -->
    ${getBeaconHtml(240, 395, b1CanEvacuate, b1HasThreat)}

    <!-- Building 1 Right Stair Base -->
    ${getBeaconHtml(630, 310, b1CanEvacuate, b1HasThreat)}

    <!-- Building 2 Stair Base -->
    ${getBeaconHtml(640, 480, b2CanEvacuate, b2HasThreat)}

    <!-- Building 3 Stair Base -->
    ${getBeaconHtml(420, 500, b3CanEvacuate, b3HasThreat)}

    <!-- 6 Ground-Floor Perimeter Devices -->
    ${outdoorCamBadges}
  `;

  container.innerHTML = pathsHtml + beacons;
}

// ── Building Floor Plan Renderer (Architectural Blueprint) ─
function renderBuildingFloors(bNum, snapshot) {
  if (!bNum) return;
  const buildings = { 1: [4, 5], 2: [4, 3], 3: [2, 2] };
  const images    = { 1: '/static/b1_floor_plan.jpg', 2: '/static/b2_floor_plan.jpg', 3: '/static/b3_floor_plan.jpg' };
  const [floors, roomsPerFloor] = buildings[bNum];

  // Exact classroom geometry mapped directly onto architectural blueprints
  const roomBoxes = {
    1: {
      1: { x: 148, y: 58, w: 148, h: 242, doorX: 232, doorY: 298, corrY: 360, stairLX: 110, stairRX: 895 },
      2: { x: 298, y: 58, w: 138, h: 242, doorX: 370, doorY: 298, corrY: 360, stairLX: 110, stairRX: 895 },
      3: { x: 438, y: 58, w: 138, h: 242, doorX: 495, doorY: 298, corrY: 360, stairLX: 110, stairRX: 895 },
      4: { x: 578, y: 58, w: 132, h: 242, doorX: 618, doorY: 298, corrY: 360, stairLX: 110, stairRX: 895 },
      5: { x: 712, y: 58, w: 146, h: 242, doorX: 762, doorY: 298, corrY: 360, stairLX: 110, stairRX: 895 },
    },
    2: {
      1: { x: 150, y: 58, w: 242, h: 242, doorX: 280, doorY: 298, corrY: 365, stairLX: 110, stairRX: 895 },
      2: { x: 394, y: 58, w: 224, h: 242, doorX: 495, doorY: 298, corrY: 365, stairLX: 110, stairRX: 895 },
      3: { x: 620, y: 58, w: 240, h: 242, doorX: 720, doorY: 298, corrY: 365, stairLX: 110, stairRX: 895 },
    },
    3: {
      1: { x: 165, y: 48, w: 350, h: 212, doorX: 340, doorY: 258, corrY: 315, stairLX: 120, stairRX: 900 },
      2: { x: 518, y: 48, w: 342, h: 212, doorX: 665, doorY: 258, corrY: 315, stairLX: 120, stairRX: 900 },
    }
  };

  document.getElementById('bld-view-title').textContent = `Building ${bNum}`;
  document.getElementById('bld-view-sub').textContent =
    `${floors} Floors &middot; ${floors * roomsPerFloor} Classrooms`;

  const grid = document.getElementById('floor-grid');
  grid.style.gridTemplateColumns = floors > 1 ? '1fr 1fr' : '1fr';

  let anyBlocked = false;
  let anyCritical = false;

  const selectedRoomId = document.getElementById('sb-room-select')?.value || '';

  grid.innerHTML = '';
  for (let f = 1; f <= floors; f++) {
    const pCode = `B${bNum}-F${f}`;
    const imgW = 1024;
    const imgH = bNum === 1 ? 502 : bNum === 2 ? 523 : 436;

    // EXACT BOTTOM CORNERS for Devices (Large, Distinct, Zero Blue)
    const badgeW = 140;
    const badgeH = 36;
    const camLeftX  = 12;
    const camLeftY  = imgH - badgeH - 10;
    const camRightX = imgW - badgeW - 12;
    const camRightY = imgH - badgeH - 10;

    const didLeft  = `${pCode}-CAM-L`;
    const didRight = `${pCode}-CAM-R`;

    // Dynamic device status
    const detLeft  = appState.detections.find(d => d.device_id === didLeft);
    const detRight = appState.detections.find(d => d.device_id === didRight);
    const colLeft  = detLeft?.classification?.level === 'CRITICAL' ? 'var(--c-red)' : detLeft?.classification?.level === 'WARNING' ? 'var(--c-amber)' : 'var(--c-green)';
    const colRight = detRight?.classification?.level === 'CRITICAL' ? 'var(--c-red)' : detRight?.classification?.level === 'WARNING' ? 'var(--c-amber)' : 'var(--c-green)';

    let roomOverlays = '';
    let arrows = '';
    let floorSafe = true;
    let floorCritical = false;

    const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';

    // Render each classroom on this floor
    for (let r = 1; r <= roomsPerFloor; r++) {
      const rmId = `${pCode}-R${r}`;
      const rm = snapshot?.routes?.[rmId];
      const box = roomBoxes[bNum]?.[r];
      if (!box) continue;

      const rmStatus = rm?.status || 'MODELED_ROUTE_AVAILABLE';

      // Translucent Room Overlays ONLY show during threats/emergencies:
      // Red: Directly Threatened Room/Floor
      // Yellow: Isolated/On Hold Room
      // Green: Safe Evacuation Room (only during emergency)
      // When ALL CLEAR (No threat): Clean architectural blueprint with subtle classroom boundary
      if (isEmergency) {
        let fillCol, strokeCol, tagText, tagCol;
        if (rmStatus === 'MODELED_ROUTE_AVAILABLE') {
          fillCol = 'rgba(5, 150, 105, 0.22)';
          strokeCol = 'rgba(5, 150, 105, 0.75)';
          tagText = `R${r} · SAFE`;
          tagCol = '#86efac';
        } else if (rmStatus === 'HOLD_FOR_AUTHORIZED_GUIDANCE') {
          floorSafe = false;
          fillCol = 'rgba(217, 119, 6, 0.32)';
          strokeCol = 'rgba(217, 119, 6, 0.88)';
          tagText = `R${r} · ON HOLD`;
          tagCol = '#fde68a';
        } else {
          floorSafe = false;
          floorCritical = true;
          fillCol = 'rgba(220, 38, 38, 0.38)';
          strokeCol = 'rgba(220, 38, 38, 0.95)';
          tagText = `R${r} · THREAT`;
          tagCol = '#fca5a5';
        }

        roomOverlays += `
          <g id="box-${rmId}">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="4"
              fill="${fillCol}" stroke="${strokeCol}" stroke-width="2"/>
            <!-- Room Status Tag -->
            <rect x="${box.x + 8}" y="${box.y + 8}" width="68" height="20" rx="4" fill="#0f172a" opacity="0.92"/>
            <text x="${box.x + 42}" y="${box.y + 22}" text-anchor="middle" fill="${tagCol}" font-size="10" font-weight="700" font-family="'JetBrains Mono', monospace">${tagText}</text>
          </g>
        `;

        // Draw evacuation arrows for all safe rooms strictly during an active emergency
        if (rmStatus === 'MODELED_ROUTE_AVAILABLE') {
          const useLeft = rm?.route?.some(n => n.includes('STAIR-L')) || r <= roomsPerFloor / 2;
          const targetX = useLeft ? Math.max(box.stairLX, 125) : Math.min(box.stairRX, 880);
          const startX = box.x + (box.w / 2);
          const startY = box.y + (box.h * 0.45);

          arrows += `
            <path d="M ${startX} ${startY} L ${box.doorX} ${box.doorY} L ${box.doorX} ${box.corrY} L ${targetX} ${box.corrY}"
              fill="none" stroke="var(--c-green)" stroke-width="4.5"
              stroke-dasharray="10,6" filter="url(#glow-g)" marker-end="url(#arr-f-${bNum}-${f})">
              <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.85s" repeatCount="indefinite"/>
            </path>`;
        }
      } else {
        // Normal baseline (All Clear): clean subtle room borders, zero green fills, zero arrows
        roomOverlays += `
          <g id="box-${rmId}">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="4"
              fill="rgba(255, 255, 255, 0.03)" stroke="rgba(148, 163, 184, 0.25)" stroke-width="1"/>
            <rect x="${box.x + 8}" y="${box.y + 8}" width="54" height="18" rx="3" fill="#0f172a" opacity="0.75"/>
            <text x="${box.x + 35}" y="${box.y + 21}" text-anchor="middle" fill="#94a3b8" font-size="10" font-weight="600" font-family="'JetBrains Mono', monospace">R${r}</text>
          </g>
        `;
      }
    }

    if (floorCritical) anyCritical = true;
    if (!floorSafe) anyBlocked = true;

    const badgeClass = floorCritical ? 'critical' : !floorSafe ? 'warning' : 'safe';
    const badgeText  = !isEmergency ? 'Normal Baseline' : floorCritical ? 'Threat Area' : !floorSafe ? 'Caution / Hold' : 'Evacuate';
    const beaconType = floorCritical ? 'critical' : !floorSafe ? 'warning' : 'normal';

    const card = document.createElement('div');
    card.className = 'floor-card';
    card.innerHTML = `
      <div class="floor-card-header">
        <div>
          <span class="floor-card-title">Floor ${f}</span>
          <span class="floor-card-code"> &middot; ${pCode}</span>
        </div>
        <span class="badge ${badgeClass}">
          <span class="status-beacon ${beaconType}" style="width:6px; height:6px;"></span>
          ${badgeText}
        </span>
      </div>
      <div class="floor-card-img-wrap" style="position:relative;">
        <img src="${images[bNum]}" alt="Floor ${f} Blueprint" style="width:100%; display:block;" />
        <svg viewBox="0 0 ${imgW} ${imgH}" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker id="arr-f-${bNum}-${f}" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
              <polygon points="0 0, 9 4.5, 0 9" fill="var(--c-green)"/>
            </marker>
          </defs>

          <!-- Translucent Room Overlays (Green=Safe, Yellow=Hold, Red=Threat) -->
          ${roomOverlays}

          <!-- Evacuation Directional Arrow Lines (Thick, All Rooms) -->
          ${arrows}

          <!-- LARGE Devices at EXACT Bottom Corners (Zero Blue, Neutral Dark Slate - Intact) -->
          <!-- Bottom Left Camera Device -->
          <g>
            <rect x="${camLeftX}" y="${camLeftY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="2"/>
            <circle cx="${camLeftX + 16}" cy="${camLeftY + (badgeH / 2)}" r="5.5" fill="${colLeft}"/>
            <text x="${camLeftX + 28}" y="${camLeftY + (badgeH / 2) + 4}" fill="#ffffff" font-size="11" font-weight="700" font-family="'JetBrains Mono', monospace">${didLeft}</text>
          </g>

          <!-- Bottom Right Camera Device -->
          <g>
            <rect x="${camRightX}" y="${camRightY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="2"/>
            <circle cx="${camRightX + 16}" cy="${camRightY + (badgeH / 2)}" r="5.5" fill="${colRight}"/>
            <text x="${camRightX + 28}" y="${camRightY + (badgeH / 2) + 4}" fill="#ffffff" font-size="11" font-weight="700" font-family="'JetBrains Mono', monospace">${didRight}</text>
          </g>
        </svg>
      </div>`;
    grid.appendChild(card);
  }

  const bldBadge = document.getElementById('bld-view-badge');
  const bType = anyCritical ? 'critical' : anyBlocked ? 'warning' : 'safe';
  bldBadge.className = `badge ${bType}`;
  const isCampusEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';
  bldBadge.innerHTML = `<span class="status-beacon ${bType}" style="width:7px; height:7px;"></span> ${!isCampusEmergency ? 'Normal Baseline' : anyCritical ? 'Threat Area' : anyBlocked ? 'Caution / On Hold' : 'Safe Evacuation'}`;
}

// ── Building Status Dots in Map Subnav ──────────────────────
function updateBuildingBadges(snapshot) {
  const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';
  [1, 2, 3].forEach(b => {
    const dot = document.getElementById(`dot-b${b}`);
    const badgeEl = document.getElementById(`b${b}-badge`);
    if (!dot) return;

    const hasCritical = Object.entries(snapshot?.routes || {}).some(
      ([rm, r]) => rm.startsWith(`B${b}-`) && r.status === 'NO_CONFIRMED_ROUTE'
    );
    const hasWarning = Object.entries(snapshot?.routes || {}).some(
      ([rm, r]) => rm.startsWith(`B${b}-`) && r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE'
    );

    let stat, label;
    if (!isEmergency) {
      stat = 'safe';
      label = 'Normal Baseline';
    } else if (hasCritical) {
      stat = 'critical';
      label = 'Threat Area';
    } else if (hasWarning) {
      stat = 'warning';
      label = 'Shelter in Place';
    } else {
      stat = 'safe';
      label = 'Evacuation Active';
    }

    dot.className = `status-beacon ${stat === 'safe' ? 'normal' : stat}`;

    if (badgeEl) {
      badgeEl.innerHTML = `<span class="badge ${stat}"><span class="status-beacon ${stat === 'safe' ? 'normal' : stat}" style="width:6px; height:6px;"></span> ${label}</span>`;
    }
  });
}

// ── Executive Metrics (Clean 4-Card Grid) ──────────────────
function updateMetrics(snap) {
  const counts = snap.counts || {};
  setText('m-safe',      counts['MODELED_ROUTE_AVAILABLE'] ?? '36');
  setText('m-hold',      counts['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? '0');
  setText('m-blocked',   counts['NO_CONFIRMED_ROUTE'] ?? '0');
}

// ── Classroom Master Table (Green=Safe, Yellow=Hold, Red=Threat) ──
function updateRoomsTable(snap) {
  const tbody = document.getElementById('rooms-table-body');
  if (!tbody) return;

  const routes = snap.routes || {};
  const rows = Object.entries(routes).map(([rm, r]) => {
    const isSafe = r.status === 'MODELED_ROUTE_AVAILABLE';
    const isHold = r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE';
    const rowClass = isSafe ? 'row-safe' : isHold ? 'row-hold' : 'row-threat';
    const statusClass = isSafe ? 'safe' : isHold ? 'warning' : 'critical';
    const statusLabel = isSafe ? 'Safe Evacuation'
      : isHold ? 'On Hold (Threat Below/Hazard)'
      : 'Threat Area / Blocked';
    const beaconType = isSafe ? 'normal' : isHold ? 'warning' : 'critical';

    return `<tr class="${rowClass}">
      <td><span class="room-code">${rm}</span></td>
      <td><span class="badge ${statusClass}"><span class="status-beacon ${beaconType}" style="width:6px; height:6px;"></span> ${statusLabel}</span></td>
      <td><span class="gate-code">${r.gate || '—'}</span></td>
      <td>${r.door_label || '—'}</td>
      <td>${r.route?.length ? r.route.length + ' steps' : 'No Exit'}</td>
    </tr>`;
  });

  tbody.innerHTML = rows.join('') || '<tr><td colspan="5" style="text-align:center; color:var(--c-muted); padding:20px;">No active data.</td></tr>';

  const badge = document.getElementById('table-status-badge');
  const lvl = snap.global_status?.toLowerCase() || 'normal';
  badge.className = `badge ${lvl === 'normal' ? 'safe' : lvl === 'warning' ? 'warning' : 'critical'}`;
  badge.innerHTML = `<span class="status-beacon ${lvl === 'normal' ? 'normal' : lvl}" style="width:6px; height:6px;"></span> ${lvl.toUpperCase()}`;
}

// ── Incident Event Log ─────────────────────────────────────
function updateEventLog(snap) {
  const el = document.getElementById('event-log');
  if (!el) return;
  const events = snap.events || [];
  if (!events.length) {
    el.innerHTML = '<div class="empty-state"><p>No active incidents recorded. Perimeter secure.</p></div>';
    return;
  }
  el.innerHTML = `<div class="event-list">${events.map(ev => {
    const lvl = ev.level.toLowerCase();
    return `
    <div class="event-item ${lvl}">
      <span class="status-beacon ${lvl === 'normal' ? 'normal' : lvl}" style="width:8px; height:8px; margin-top:4px;"></span>
      <div class="event-text">
        <b>${ev.device_id}</b> &middot; <span style="font-weight:700;">${ev.level}</span><br>
        <span style="color:var(--c-muted);">Event ID: <code>${ev.event_id}</code></span>
        ${ev.location ? `<br><span style="color:var(--c-muted);">Reported Area: ${ev.location}</span>` : ''}
      </div>
    </div>`;
  }).join('')}</div>`;
}

// ── CCTV Grid with Realistic Simulated CRT Standby Screen ──
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

  // Descriptive location mapping for ground-floor outdoor devices
  const outdoorDescriptions = {
    'B1-OUT-L': 'Ground Exterior — Building 1 West Approach',
    'B1-OUT-R': 'Ground Exterior — Building 1 East Approach',
    'B2-OUT-L': 'Ground Exterior — Building 2 North Courtyard',
    'B2-OUT-R': 'Ground Exterior — Building 2 South Alley',
    'B3-OUT-L': 'Ground Exterior — Building 3 West Gate Approach',
    'B3-OUT-R': 'Ground Exterior — Building 3 Courtyard Approach',
  };

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
    grid.innerHTML = '<div class="empty-state"><p>No devices mapped to this group.</p></div>';
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
    const beaconType = lvl === 'CRITICAL' ? 'critical' : lvl === 'WARNING' ? 'warning' : 'normal';

    const coverage = outdoorDescriptions[d.device_id]
      || (d.covered_rooms?.length ? `Classrooms: ${d.covered_rooms.join(', ')}` : (d.covered_node || 'Ground Approach'));

    // Video Section: IF video uploaded, show video + scores; ELSE show realistic CCTV standby monitor!
    const videoSection = hasAlert ? `
      <div class="cam-video-row">
        <div>
          <video src="${latest.video_url || '/videos-project/test_video.mp4'}" controls autoplay muted playsinline loop
            style="width:100%; border-radius:6px; border:1px solid var(--c-border); display:block;"
            onloadedmetadata="this.currentTime=0;">
          </video>
        </div>
        <div class="cam-scores">
          <div style="font-size:11px; font-weight:700; color:var(--c-navy); margin-bottom:8px;">Live AI Scoreboard</div>
          <div class="cam-score-row"><span>Threat Index</span><span class="cam-score-val threat">${clf.index?.toFixed(1) ?? '—'} / 100</span></div>
          <div class="cam-score-row"><span>Object (YOLO)</span><span class="cam-score-val">${scores.object ?? clf.object ?? '—'}</span></div>
          <div class="cam-score-row"><span>Pose Keypoints</span><span class="cam-score-val">${scores.pose ?? clf.pose ?? '—'}</span></div>
          <div class="cam-score-row"><span>Acoustic RMS</span><span class="cam-score-val">${scores.acoustic ?? clf.acoustic ?? '—'}</span></div>
          <div class="cam-score-row"><span>Safety Status</span><span class="cam-score-val ${clf.verified ? 'threat' : ''}">${clf.verified ? 'CONFIRMED' : 'Under Review'}</span></div>
        </div>
      </div>` : `
      <div class="cctv-screen">
        <div class="cctv-osd-top">
          <span>${d.device_id}</span>
          <div class="cctv-osd-rec">
            <span class="cctv-rec-dot"></span>
            <span>STANDBY</span>
          </div>
        </div>
        <div class="cctv-center-notice">
          <svg class="icon icon-md" viewBox="0 0 24 24" style="color:#64748b; margin-bottom:4px;">
            <path d="M15 10l4.553-2.07A1 1 0 0121 8.86v6.28a1 1 0 01-1.447.93L15 14M4 8h11a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z"/>
          </svg>
          <div class="cctv-center-status">SIMULATION FEED · NO SIGNAL</div>
          <div class="cctv-center-sub">Standby mode &middot; Ready for upload or simulation</div>
        </div>
        <div class="cctv-osd-bottom">
          <span>FPS: 30</span>
          <span>AUTO-INGEST READY</span>
        </div>
      </div>`;

    return `
    <div class="cam-card ${hasAlert ? 'alert' : ''}">
      <div class="cam-card-header">
        <span class="cam-id">${d.device_id}</span>
        <span class="badge ${badgeClass}">
          <span class="status-beacon ${beaconType}" style="width:6px; height:6px;"></span>
          ${lvl}
        </span>
      </div>
      <div class="cam-body">
        <div class="cam-coverage">Zone: <b>${coverage}</b></div>
        ${videoSection}
      </div>
    </div>`;
  }).join('');
}

// ── Video Threat Simulation & Upload Handlers ──────────────
function openSimModal() {
  const modal = document.getElementById('sim-modal');
  const sel = document.getElementById('sim-target-cam');
  if (modal && sel) {
    const devs = Object.keys(appState.devices).sort();
    sel.innerHTML = devs.map(d => `<option value="${d}">${d}</option>`).join('');
    modal.style.display = 'flex';
  }
}

function closeSimModal() {
  const modal = document.getElementById('sim-modal');
  if (modal) modal.style.display = 'none';
}

async function submitSimThreat() {
  const targetCam = document.getElementById('sim-target-cam')?.value;
  const level = document.getElementById('sim-threat-level')?.value || 'CRITICAL';
  if (!targetCam) return;

  const scores = level === 'CRITICAL' ? { acoustic: 88, pose: 80, object: 92 }
    : level === 'WARNING' ? { acoustic: 55, pose: 45, object: 40 }
    : { acoustic: 12, pose: 10, object: 5 };

  toast(`Simulating video feed on ${targetCam}…`, 'info');
  const res = await apiFetch('/api/simulate-threat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_ids: [targetCam],
      level: level,
      acoustic: scores.acoustic,
      pose: scores.pose,
      object: scores.object,
    }),
  });

  if (res?.ok) {
    closeSimModal();
    toast(`Injected simulated threat feed on ${targetCam}`, 'success');
    await refresh();
  } else {
    toast('Simulation failed to trigger', 'error');
  }
}

async function handleVideoUpload(file) {
  if (!file) return;
  toast(`Uploading ${file.name} for AI analysis…`, 'info');

  const formData = new FormData();
  formData.append('file', file);
  const target = appState.camFilter === 'b2' ? 'B2-F1-CAM-L' : appState.camFilter === 'b3' ? 'B3-F1-CAM-L' : 'B1-F1-CAM-L';
  formData.append('device_ids', target);

  try {
    const res = await fetch(API + '/api/upload-video', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (res.ok) {
      toast(`Video ingested on ${target}! YOLOv8 threat registered.`, 'success');
      await refresh();
    } else {
      toast(`Upload error: ${data.detail || 'Failed to process'}`, 'error');
    }
  } catch (e) {
    toast(`Video upload failed: ${e.message}`, 'error');
  }
}

async function clearDetections() {
  toast('Clearing active detection records…', 'info');
  const res = await apiFetch('/api/detections/clear', { method: 'POST' });
  if (res?.ok) {
    toast('All cameras returned to Standby No-Signal', 'success');
    await refresh();
  }
}

// ── Utility Helpers ────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function formatRoomLabel(id) {
  const m = id.match(/^B(\d+)-F(\d+)-R(\d+)$/);
  if (!m) return id;
  return `Building ${m[1]} &middot; Floor ${m[2]} &middot; Room ${m[3]}`;
}
