/* ============================================================
   SENTINEL — Campus Safety Command
   Frontend Controller (Gemini UI + 1:1 SVG Maps + Fast 3-Criteria Scanner)
   ============================================================ */

const API = '';

let appState = {
  status: null,
  snapshot: null,
  rooms: [],
  devices: {},
  detections: [],
  scenarios: [],
  hardware: null,
  incidents: [],
  user: null,
  token: localStorage.getItem('sentinel_token') || null,
  locBldg: '',
  locFloor: '',
  locRoom: '',
  unavailableGates: [],
  manualBlocks: [],
  unavailableNodes: [],
  activeTab: 'map',
  mapView: 'campus',
  camFilter: 'outside',
  prevGlobalStatus: null,
  resolvedBannerUntil: 0,
  resolvedBannerTimer: null,
};

const CANONICAL_DEVICES = [
  { id: 'TPB-CAM-OUT-L', grp: 'Campus Perimeter & Gates', label: 'TPB-CAM-OUT-L — West Gate Approach (GATE-W)' },
  { id: 'TPB-CAM-OUT-R', grp: 'Campus Perimeter & Gates', label: 'TPB-CAM-OUT-R — Northeast Gate Approach (GATE-NE)' },
  { id: 'AB-CAM-OUT-L',  grp: 'Campus Perimeter & Gates', label: 'AB-CAM-OUT-L — Academic North Courtyard' },
  { id: 'AB-CAM-OUT-R',  grp: 'Campus Perimeter & Gates', label: 'AB-CAM-OUT-R — Academic East Alley' },
  { id: 'LB-CAM-OUT-L',  grp: 'Campus Perimeter & Gates', label: 'LB-CAM-OUT-L — Laboratory West Path' },
  { id: 'LB-CAM-OUT-R',  grp: 'Campus Perimeter & Gates', label: 'LB-CAM-OUT-R — Laboratory Courtyard' },
  { id: 'TPB-F1-CAM-L', grp: 'Tech Pro Building (TPB)', label: 'TPB-F1-CAM-L (Floor 1 Left — R1, R2, R3)' },
  { id: 'TPB-F1-CAM-R', grp: 'Tech Pro Building (TPB)', label: 'TPB-F1-CAM-R (Floor 1 Right — R3, R4, R5)' },
  { id: 'TPB-F2-CAM-L', grp: 'Tech Pro Building (TPB)', label: 'TPB-F2-CAM-L (Floor 2 Left — R1, R2, R3)' },
  { id: 'TPB-F2-CAM-R', grp: 'Tech Pro Building (TPB)', label: 'TPB-F2-CAM-R (Floor 2 Right — R3, R4, R5)' },
  { id: 'TPB-F3-CAM-L', grp: 'Tech Pro Building (TPB)', label: 'TPB-F3-CAM-L (Floor 3 Left — R1, R2, R3)' },
  { id: 'TPB-F3-CAM-R', grp: 'Tech Pro Building (TPB)', label: 'TPB-F3-CAM-R (Floor 3 Right — R3, R4, R5)' },
  { id: 'TPB-F4-CAM-L', grp: 'Tech Pro Building (TPB)', label: 'TPB-F4-CAM-L (Floor 4 Left — R1, R2, R3)' },
  { id: 'TPB-F4-CAM-R', grp: 'Tech Pro Building (TPB)', label: 'TPB-F4-CAM-R (Floor 4 Right — R3, R4, R5)' },
  { id: 'AB-F1-CAM-L', grp: 'Academic Building (AB)', label: 'AB-F1-CAM-L (Floor 1 Left — R1, R2)' },
  { id: 'AB-F1-CAM-R', grp: 'Academic Building (AB)', label: 'AB-F1-CAM-R (Floor 1 Right — R2, R3)' },
  { id: 'AB-F2-CAM-L', grp: 'Academic Building (AB)', label: 'AB-F2-CAM-L (Floor 2 Left — R1, R2)' },
  { id: 'AB-F2-CAM-R', grp: 'Academic Building (AB)', label: 'AB-F2-CAM-R (Floor 2 Right — R2, R3)' },
  { id: 'AB-F3-CAM-L', grp: 'Academic Building (AB)', label: 'AB-F3-CAM-L (Floor 3 Left — R1, R2)' },
  { id: 'AB-F3-CAM-R', grp: 'Academic Building (AB)', label: 'AB-F3-CAM-R (Floor 3 Right — R2, R3)' },
  { id: 'AB-F4-CAM-L', grp: 'Academic Building (AB)', label: 'AB-F4-CAM-L (Floor 4 Left — R1, R2)' },
  { id: 'AB-F4-CAM-R', grp: 'Academic Building (AB)', label: 'AB-F4-CAM-R (Floor 4 Right — R2, R3)' },
  { id: 'LB-F1-CAM-L', grp: 'Laboratory Building (LB)', label: 'LB-F1-CAM-L (Floor 1 Left — R1)' },
  { id: 'LB-F1-CAM-R', grp: 'Laboratory Building (LB)', label: 'LB-F1-CAM-R (Floor 1 Right — R2)' },
  { id: 'LB-F2-CAM-L', grp: 'Laboratory Building (LB)', label: 'LB-F2-CAM-L (Floor 2 Left — R1)' },
  { id: 'LB-F2-CAM-R', grp: 'Laboratory Building (LB)', label: 'LB-F2-CAM-R (Floor 2 Right — R2)' },
];

// ── Bootstrapping ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuthSession();
  await loadInitialMeta();
  applyUrlFloorPin();
  await refresh();
  setInterval(refresh, 4000);
});

function applyUrlFloorPin() {
  const params = new URLSearchParams(window.location.search);
  const fParam = (params.get('floor') || '').trim().toUpperCase();
  const m = fParam.match(/^(TPB|AB|LB)-F(\d+)$/);
  if (!m) return;
  const bldg = m[1];
  const fl = m[2];
  const bSel = document.getElementById('loc-bldg');
  if (bSel) {
    bSel.value = bldg;
    onLocatorBuildingChange();
    const fSel = document.getElementById('loc-floor');
    if (fSel) {
      fSel.value = fl;
      onLocatorFloorChange();
    }
  }
}

function toggleSidebar() {
  if (!appState.user) return;
  const sb = document.getElementById('app-sidebar');
  if (sb) sb.classList.toggle('collapsed');
}

// ── API Fetch Helper (with Bearer Auth) ────────────────────
function authHeaders(extra = {}) {
  const hdrs = { ...extra };
  if (appState.token) hdrs['Authorization'] = `Bearer ${appState.token}`;
  return hdrs;
}

async function apiFetch(path, opts = {}) {
  try {
    const mergedOpts = {
      ...opts,
      headers: authHeaders(opts.headers || {}),
    };
    const res = await fetch(API + path, mergedOpts);
    if (res.status === 401 && appState.token) {
      // Session expired
      appState.token = null;
      appState.user = null;
      localStorage.removeItem('sentinel_token');
      applyAuthUI();
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error('API Error:', path, e);
    return null;
  }
}

function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="status-beacon ${type === 'critical' || type === 'error' ? 'critical' : type === 'warning' ? 'warning' : ''}" style="width:7px;height:7px;"></span><span>${msg}</span>`;
  c.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 220);
  }, 3400);
}

// ── Initial Metadata Load (Role-Aware) ─────────────────────
async function loadInitialMeta() {
  const isStaff = !!appState.user;
  const calls = [
    apiFetch('/api/rooms'),
    apiFetch('/api/devices'),
  ];
  if (isStaff) calls.push(apiFetch('/api/scenarios'));

  const [roomsData, devData, scenData] = await Promise.all(calls);

  if (roomsData?.rooms) {
    appState.rooms = roomsData.rooms;
    populateRoomDropdowns(roomsData.rooms);
  }
  if (devData?.devices) {
    appState.devices = devData.devices;
  }
  if (scenData?.scenarios) {
    appState.scenarios = scenData.scenarios;
    populateScenarioDropdown(scenData.scenarios);
  }
  populateHazardDropdowns();
}

async function refresh() {
  const isStaff = !!appState.user;
  const isIT = appState.user?.role === 'IT_TECHNICIAN';

  const calls = [
    apiFetch('/api/status'),
    apiFetch('/api/snapshot'),
  ];
  if (isStaff) {
    calls.push(apiFetch('/api/detections'));
    calls.push(apiFetch('/api/db/incidents'));
  }
  if (isIT) {
    calls.push(apiFetch('/api/hardware/status'));
  }

  const results = await Promise.all(calls);
  const status = results[0];
  const snapshot = results[1];
  const detData = isStaff ? results[2] : null;
  const incData = isStaff ? results[3] : null;
  const hwData = isIT ? results[isStaff ? 4 : 2] : null;

  if (status) {
    appState.status = status;
    appState.unavailableGates = status.unavailable_gates || [];
    appState.manualBlocks = status.manual_blocks || [];
    appState.unavailableNodes = status.unavailable_nodes || [];
  }
  if (snapshot) appState.snapshot = snapshot;
  if (detData) appState.detections = detData.detections || [];
  if (incData?.incidents) appState.incidents = incData.incidents;
  if (hwData) appState.hardware = hwData;

  renderAll();
}

// ── Populate Sidebar Dropdowns ─────────────────────────────
function populateScenarioDropdown(scenarios) {
  const sel = document.getElementById('sb-scenario-select');
  if (!sel) return;
  const labels = {
    'all_clear': 'Normal (all clear)',
    'Gate-W Threat (Reroute to Gate-NE)': 'Drill: West gate threat (use NE)',
    'Gate-NE Threat (Reroute to Gate-W)': 'Drill: Northeast gate threat (use W)',
    'TPB Floor 1 Indoor Threat': 'Drill: Tech Pro Floor 1 threat',
    'AB Floor 2 Indoor Threat': 'Drill: Academic Floor 2 threat',
    'Corridor C2 Caution Zone': 'Drill: Corridor caution zone',
  };
  sel.innerHTML = scenarios.map(s => `<option value="${s}">${labels[s] || s}</option>`).join('');
}

function populateRoomDropdowns(rooms) {
  const sel = document.getElementById('sb-room-select');
  const blockSel = document.getElementById('sb-room-block-select');
  if (!sel) return;

  const groups = {
    'Tech Pro Building (TPB)': rooms.filter(r => r.startsWith('TPB-')),
    'Academic Building (AB)':  rooms.filter(r => r.startsWith('AB-')),
    'Laboratory Building (LB)':rooms.filter(r => r.startsWith('LB-')),
  };

  let html = '<option value="">Choose a classroom</option>';
  let blockHtml = '<option value="">Close a classroom</option>';

  for (const [grp, list] of Object.entries(groups)) {
    html += `<optgroup label="${grp}">${list.map(r => `<option value="${r}">${r}</option>`).join('')}</optgroup>`;
    blockHtml += `<optgroup label="${grp}">${list.map(r => `<option value="${r}">${r}</option>`).join('')}</optgroup>`;
  }
  sel.innerHTML = html;
  if (blockSel) blockSel.innerHTML = blockHtml;
}

function populateHazardDropdowns() {
  const corrSel = document.getElementById('sb-corridor-select');
  const stairSel = document.getElementById('sb-stair-select');
  const bldgs = [
    { code: 'TPB', name: 'Tech Pro (TPB)', floors: 4, rpf: 5 },
    { code: 'AB',  name: 'Academic (AB)',  floors: 4, rpf: 3 },
    { code: 'LB',  name: 'Laboratory (LB)',floors: 2, rpf: 2 },
  ];

  if (corrSel) {
    let html = '<option value="">Close a corridor</option>';
    bldgs.forEach(b => {
      let opts = '';
      for (let f = 1; f <= b.floors; f++) {
        opts += `<option value="${b.code}-F${f}-CORRIDOR">${b.code}-F${f}-CORRIDOR (whole Floor ${f})</option>`;
        for (let c = 0; c <= b.rpf; c++) {
          const id = `${b.code}-F${f}-C${c}`;
          opts += `<option value="${id}">${id} (Floor ${f}, section ${c})</option>`;
        }
      }
      html += `<optgroup label="${b.name}">${opts}</optgroup>`;
    });
    corrSel.innerHTML = html;
  }

  if (stairSel) {
    let html = '<option value="">Close a stairwell</option>';
    bldgs.forEach(b => {
      let opts = '';
      for (let f = 1; f <= b.floors; f++) {
        opts += `<option value="${b.code}-F${f}-STAIR-L">${b.code}-F${f}-STAIR-L (Floor ${f} Left)</option>`;
        opts += `<option value="${b.code}-F${f}-STAIR-R">${b.code}-F${f}-STAIR-R (Floor ${f} Right)</option>`;
      }
      html += `<optgroup label="${b.name}">${opts}</optgroup>`;
    });
    stairSel.innerHTML = html;
  }
}

// ── Master Render ──────────────────────────────────────────
function renderAll() {
  const { status, snapshot } = appState;
  if (!status || !snapshot) return;

  updateTopbarStatus(status, snapshot);
  updateSidebarControls(status);
  updateMetrics(snapshot);
  updateBuildingBadges(snapshot);

  const selectedRoom = document.getElementById('sb-room-select')?.value;
  if (selectedRoom) {
    updateRoomInspectorCard(selectedRoom);
  } else {
    const ins = document.getElementById('inspector-result');
    if (ins) ins.style.display = 'none';
  }
  updatePublicThreatBar(snapshot);
  updateOccupantGuidance();

  if (appState.mapView === 'campus') {
    renderCampusMap(snapshot, status);
  } else {
    renderBuildingFloors(appState.mapView, snapshot);
  }

  updateRoomsTable(snapshot);
  updateEventLog(snapshot);
  renderCamGrid();
  renderHardwareTwin();
}

// ── Topbar & Emergency Banner ──────────────────────────────
function updateTopbarStatus(status, snapshot) {
  const pill = document.getElementById('global-status-pill');
  const beacon = document.getElementById('global-beacon');
  const text = document.getElementById('global-status-text');
  const banner = document.getElementById('emergency-banner');
  const ebBeacon = document.getElementById('eb-beacon');
  const ebTitle = document.getElementById('eb-title');
  const ebSub = document.getElementById('eb-sub');

  const lvl = (snapshot.global_status || status.status || 'NORMAL').toUpperCase();

  pill.className = 'global-status-pill';
  beacon.className = 'status-beacon';

  const qrChip = document.getElementById('emergency-qr-chip');

  if (lvl === 'CRITICAL') {
    pill.classList.add('critical');
    beacon.classList.add('critical');
    text.textContent = 'Emergency: evacuate';
    banner.className = 'emergency-banner visible';
    ebBeacon.className = 'status-beacon critical';
    ebTitle.textContent = 'Critical threat active';
    const safeCnt = snapshot.counts?.available ?? snapshot.counts?.['MODELED_ROUTE_AVAILABLE'] ?? 0;
    const holdCnt = snapshot.counts?.hold ?? snapshot.counts?.['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? 0;
    const blkCnt  = snapshot.counts?.no_route ?? snapshot.counts?.['NO_CONFIRMED_ROUTE'] ?? 0;
    ebSub.textContent = `${safeCnt} rooms evacuating, ${holdCnt} holding in place, ${blkCnt} blocked.`;
    if (qrChip) qrChip.style.display = 'inline-flex';
  } else if (lvl === 'WARNING') {
    pill.classList.add('warning');
    beacon.classList.add('warning');
    text.textContent = 'Caution: rerouting';
    banner.className = 'emergency-banner warning visible';
    ebBeacon.className = 'status-beacon warning';
    ebTitle.textContent = 'Caution active';
    ebSub.textContent = 'Routes adjusted around restricted zones or gates.';
    if (qrChip) qrChip.style.display = 'none';
    closeQr911Modal();
  } else {
    text.textContent = 'All clear';
    banner.className = 'emergency-banner';
    if (qrChip) qrChip.style.display = 'none';
    closeQr911Modal();
  }
}

function openQr911Modal() {
  const m = document.getElementById('qr-911-modal');
  if (m) m.style.display = 'flex';
}

function closeQr911Modal() {
  const m = document.getElementById('qr-911-modal');
  if (m) m.style.display = 'none';
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeQr911Modal();
    closeDeleteAccountModal();
    closeAuthModal();
    closeUploadModal();
    closeSimModal();
  }
});

// ── Sidebar Controls Sync ──────────────────────────────────
function updateSidebarControls(status) {
  const scenSel = document.getElementById('sb-scenario-select');
  if (scenSel && status.active_scenario) {
    scenSel.value = status.active_scenario;
  }

  const gateStates = status.gates || {};
  const wBlocked = gateStates['GATE-W'] === 'BLOCKED' || appState.unavailableGates.includes('GATE-W');
  const neBlocked = gateStates['GATE-NE'] === 'BLOCKED' || appState.unavailableGates.includes('GATE-NE');

  const btnW = document.getElementById('gate-btn-w');
  const stW = document.getElementById('gate-status-w');
  if (btnW && stW) {
    btnW.className = `gate-pill-btn ${wBlocked ? 'blocked' : ''}`;
    stW.textContent = wBlocked ? 'BLOCKED' : 'OPEN';
  }

  const btnNE = document.getElementById('gate-btn-ne');
  const stNE = document.getElementById('gate-status-ne');
  if (btnNE && stNE) {
    btnNE.className = `gate-pill-btn ${neBlocked ? 'blocked' : ''}`;
    stNE.textContent = neBlocked ? 'BLOCKED' : 'OPEN';
  }

  const tagsEl = document.getElementById('facility-tags');
  const clearBtn = document.getElementById('btn-clear-facilities');
  if (tagsEl) {
    tagsEl.innerHTML = (appState.unavailableNodes || []).map(node => `
      <span class="tag-chip unavail">
        [X] ${node}
        <button onclick="removeUnavailableFacility('${node}')" title="Re-open Facility">&times;</button>
      </span>
    `).join('');
  }
  if (clearBtn) {
    clearBtn.style.display = appState.unavailableNodes?.length ? 'inline-block' : 'none';
  }
}

// ── Interactive Control Actions ────────────────────────────
function switchTab(tab) {
  appState.activeTab = tab;
  document.querySelectorAll('.nav-pill').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-btn-${tab}`)?.classList.add('active');
  document.getElementById('sb-btn-accounts')?.classList.toggle('active', tab === 'accounts');

  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`tab-${tab}`)?.classList.add('active');

  if (tab === 'accounts' && appState.user) {
    loadAccountsTabData();
  }
}

function switchMapView(view) {
  appState.mapView = view;
  document.querySelectorAll('#tab-map .filter-pill').forEach(b => b.classList.remove('active'));
  document.getElementById(`mv-${view}`)?.classList.add('active');

  const campusView = document.getElementById('map-view-campus');
  const bldView = document.getElementById('map-view-building');

  if (view === 'campus') {
    campusView.style.display = 'flex';
    bldView.style.display = 'none';
    if (appState.snapshot && appState.status) {
      renderCampusMap(appState.snapshot, appState.status);
    }
  } else {
    campusView.style.display = 'none';
    bldView.style.display = 'flex';
    if (appState.snapshot) {
      renderBuildingFloors(view, appState.snapshot);
    }
  }
}

async function onScenarioChange(scenario) {
  await apiFetch('/api/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  });
  toast(`Scenario loaded: ${scenario === 'all_clear' ? 'All Clear' : scenario}`, 'info');
  await refresh();
}

function onRoomInspect(roomId) {
  const card = document.getElementById('inspector-result');
  if (!roomId) {
    if (card) card.style.display = 'none';
    return;
  }
  updateRoomInspectorCard(roomId);
  const bCode = roomId.split('-')[0].toLowerCase();
  if (['tpb', 'ab', 'lb'].includes(bCode)) {
    switchMapView(bCode);
  }
}

function updateRoomInspectorCard(roomId) {
  const card = document.getElementById('inspector-result');
  const r = appState.snapshot?.routes?.[roomId];
  if (!card || !r) return;

  card.style.display = 'block';
  const isSafe = r.status === 'MODELED_ROUTE_AVAILABLE';
  const isHold = r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE';
  const isUnavail = r.status === 'FACILITY_UNAVAILABLE';

  card.className = `inspector-card ${isSafe ? '' : isUnavail ? 'unavail' : isHold ? 'warning' : 'critical'}`;
  setText(
    'ins-status-label',
    isSafe ? 'Safe route available'
      : isUnavail ? 'Closed for maintenance'
      : isHold ? 'Hold in place'
      : 'Threat area, blocked'
  );
  setText('ins-gate', r.gate || 'None');
  setText('ins-door', r.door_label || 'None');
  setText('ins-steps', r.route?.length ? `${r.route.length} steps (cost ${r.cost})` : (r.reason || 'No route available'));
}

async function toggleGate(gateId) {
  if (!appState.user) {
    toast('Sign in as School Personnel or IT Technician to toggle perimeter gates.', 'warning');
    return;
  }
  const list = [...appState.unavailableGates];
  const idx = list.indexOf(gateId);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(gateId);

  await apiFetch('/api/gates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unavailable_gates: list }),
  });
  toast(`${gateId} ${idx >= 0 ? 're-opened' : 'manually blocked'}`, idx >= 0 ? 'success' : 'warning');
  await refresh();
}

async function addUnavailableFacility(selectEl) {
  const node = selectEl.value;
  selectEl.value = '';
  if (!node || appState.unavailableNodes.includes(node)) return;

  const next = [...appState.unavailableNodes, node];
  const res = await apiFetch('/api/facility-overrides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unavailable_nodes: next, assigned_by: 'PERSONNEL' }),
  });
  if (res?.ok) {
    toast(`Marked ${node} unavailable (Gray X · Non-Threat)`, 'info');
    await refresh();
  }
}

async function removeUnavailableFacility(node) {
  const next = appState.unavailableNodes.filter(n => n !== node);
  await apiFetch('/api/facility-overrides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unavailable_nodes: next, assigned_by: 'PERSONNEL' }),
  });
  toast(`Re-opened ${node}`, 'success');
  await refresh();
}

async function clearFacilities() {
  await apiFetch('/api/facility-overrides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unavailable_nodes: [], assigned_by: 'PERSONNEL' }),
  });
  toast('All facilities re-opened', 'success');
  await refresh();
}

async function resetAll() {
  await apiFetch('/api/reset', { method: 'POST' });
  const rmSel = document.getElementById('sb-room-select');
  if (rmSel) rmSel.value = '';
  const insCard = document.getElementById('inspector-result');
  if (insCard) insCard.style.display = 'none';
  toast('Campus reset to Normal All-Clear state', 'success');
  await refresh();
}

async function resolveEmergency() {
  const res = await apiFetch('/api/incidents/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      notes: 'Threat apprehended and evacuation secured by authorized personnel.',
      resolved_by: 'DRRM_OFFICER',
    }),
  });
  if (res?.ok) {
    showResolvedThreatBanner(6000);
    toast('Campus secured. Threat logged as resolved and ESP32 stood down.', 'success');
    await refresh();
  }
}

// ── Shorten Final Segment of SVG Path so Arrowhead Never Overlaps Gate Circle ──
function shortenPathEnd(points, trimPx = 28) {
  if (points.length < 2) return '';
  const pts = points.map(p => [...p]);
  const last = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  const dx = last[0] - prev[0];
  const dy = last[1] - prev[1];
  const len = Math.hypot(dx, dy);
  if (len > trimPx + 6) {
    last[0] = Math.round(last[0] - (dx / len) * trimPx);
    last[1] = Math.round(last[1] - (dy / len) * trimPx);
  }
  return pts.map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${pt[0]} ${pt[1]}`).join(' ');
}

// ── Render Campus Site Plan SVG Overlay (Zero Clipping) ────
function renderCampusMap(snapshot, status) {
  const svg = document.getElementById('campus-overlay');
  if (!svg) return;

  const isEmergency = snapshot.global_status === 'CRITICAL' || snapshot.global_status === 'WARNING';
  const blockedSet = new Set(snapshot.blocked || []);

  const gateCoords = {
    'GATE-W':  { x: 202, y: 398, label: 'GATE-W · West Exit' },
    'GATE-NE': { x: 776, y: 150, label: 'GATE-NE · Northeast Exit' },
  };

  // Paved-walkway outdoor routes traced strictly along concrete sidewalks & gate aprons
  // (avoids cutting across buildings, hedges, central grass lawn, or perimeter trees)
  const bldConfigs = [
    {
      code: 'TPB', title: 'TECH PRO (TPB)',
      cx: 455, cy: 232, w: 176, h: 62,
      paths: {
        'GATE-W':  [[442, 354], [334, 394], [258, 386], [202, 398]],
        'GATE-NE': [[552, 304], [686, 244], [722, 212], [750, 174], [776, 150]],
      }
    },
    {
      code: 'AB', title: 'ACADEMIC (AB)',
      cx: 734, cy: 388, w: 176, h: 62,
      paths: {
        'GATE-W':  [[638, 355], [602, 286], [492, 336], [355, 390], [258, 390], [202, 398]],
        'GATE-NE': [[660, 292], [714, 224], [750, 174], [776, 150]],
      }
    },
    {
      code: 'LB', title: 'LABORATORY (LB)',
      cx: 384, cy: 492, w: 176, h: 62,
      paths: {
        'GATE-W':  [[428, 440], [396, 394], [320, 398], [258, 392], [202, 398]],
        'GATE-NE': [[428, 440], [396, 382], [498, 340], [608, 290], [716, 216], [750, 174], [776, 150]],
      }
    }
  ];

  let pathsSvg = '';
  let bldBoxesSvg = '';

  bldConfigs.forEach(b => {
    const bRoutes = Object.entries(snapshot.routes || {}).filter(([rm]) => rm.startsWith(`${b.code}-`));
    const safeRoutes = bRoutes.filter(([_, r]) => r.status === 'MODELED_ROUTE_AVAILABLE');
    const unavailRoutes = bRoutes.filter(([_, r]) => r.status === 'FACILITY_UNAVAILABLE');
    const holdRoutes = bRoutes.filter(([_, r]) => r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE');
    const critRoutes = bRoutes.filter(([_, r]) => r.status === 'NO_CONFIRMED_ROUTE');

    let bCol = '#059669';
    let bStatusText = unavailRoutes.length
      ? `${safeRoutes.length} CLEAR · ${unavailRoutes.length} CLOSED`
      : `${bRoutes.length}/${bRoutes.length} CLEAR`;
    if (isEmergency) {
      if (critRoutes.length > 0) {
        bCol = '#dc2626';
        bStatusText = `${critRoutes.length} THREAT · ${safeRoutes.length} EVAC`;
      } else if (holdRoutes.length > 0) {
        bCol = '#d97706';
        bStatusText = `${holdRoutes.length} HOLD · ${safeRoutes.length} EVAC`;
      } else {
        bCol = '#059669';
        bStatusText = `ALL ${safeRoutes.length} EVACUATING`;
      }
    } else if (unavailRoutes.length === bRoutes.length && bRoutes.length > 0) {
      bCol = '#64748b';
    }

    // Draw Evacuation Flow Arrow(s) when Emergency/Warning or Gate Override is active
    if ((isEmergency || appState.unavailableGates.length > 0) && safeRoutes.length > 0) {
      const activeGates = [...new Set(safeRoutes.map(([_, r]) => r.gate).filter(Boolean))];
      activeGates.forEach(targetGate => {
        if (b.paths[targetGate]) {
          const dStr = shortenPathEnd(b.paths[targetGate], 28);
          pathsSvg += `
            <path d="${dStr}" fill="none" stroke="#047857" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity="0.28"/>
            <path d="${dStr}" fill="none" stroke="#10b981" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"
              stroke-dasharray="12,8" marker-end="url(#campus-arr-safe)">
              <animate attributeName="stroke-dashoffset" from="40" to="0" dur="0.9s" repeatCount="indefinite"/>
            </path>
          `;
        }
      });
    }

    const bx = b.cx - b.w / 2;
    const by = b.cy - b.h / 2;
    bldBoxesSvg += `
      <g style="cursor:pointer; pointer-events:all;" onclick="switchMapView('${b.code.toLowerCase()}')">
        <rect x="${bx}" y="${by}" width="${b.w}" height="${b.h}" rx="12"
          fill="rgba(15, 23, 42, 0.92)" stroke="${bCol}" stroke-width="3"/>
        <text x="${b.cx}" y="${by + 25}" text-anchor="middle" fill="#ffffff"
          font-size="12.5" font-weight="800" font-family="'Atkinson Hyperlegible Next', sans-serif">${b.title}</text>
        <rect x="${b.cx - 66}" y="${by + 33}" width="132" height="21" rx="10" fill="${bCol}"/>
        <text x="${b.cx}" y="${by + 47}" text-anchor="middle" fill="#ffffff"
          font-size="10.5" font-weight="800" font-family="'Atkinson Hyperlegible Mono', monospace">${bStatusText}</text>
      </g>
    `;
  });

  // Render Gate Markers
  let gatesSvg = '';
  for (const [gId, g] of Object.entries(gateCoords)) {
    const isBlocked = appState.unavailableGates.includes(gId) || blockedSet.has(gId);
    const gCol = isBlocked ? '#dc2626' : '#059669';
    const gTag = isBlocked ? `${gId} · BLOCKED` : `${gId} · OPEN`;

    gatesSvg += `
      <g style="cursor:pointer; pointer-events:all;" onclick="toggleGate('${gId}')">
        <circle cx="${g.x}" cy="${g.y}" r="28" fill="${gCol}" opacity="0.22"/>
        <circle cx="${g.x}" cy="${g.y}" r="21" fill="#0f172a" stroke="${gCol}" stroke-width="3.5"/>
        <text x="${g.x}" y="${g.y + 4}" text-anchor="middle" fill="#ffffff"
          font-size="10.5" font-weight="800" font-family="'Atkinson Hyperlegible Mono', monospace">${gId === 'GATE-W' ? 'W' : 'NE'}</text>
        <rect x="${g.x - 66}" y="${g.y + 27}" width="132" height="22" rx="11"
          fill="#0f172a" stroke="${gCol}" stroke-width="2"/>
        <text x="${g.x}" y="${g.y + 42}" text-anchor="middle" fill="#ffffff"
          font-size="10.5" font-weight="800" font-family="'Atkinson Hyperlegible Mono', monospace">${gTag}</text>
      </g>
    `;
  }

  svg.innerHTML = `
    <defs>
      <marker id="campus-arr-safe" viewBox="0 0 12 12" markerWidth="7" markerHeight="7" refX="8" refY="6" orient="auto" overflow="visible">
        <path d="M 0 1 L 10 6 L 0 11 z" fill="#10b981" stroke="#064e3b" stroke-width="0.8"/>
      </marker>
    </defs>
    ${pathsSvg}
    ${bldBoxesSvg}
    ${gatesSvg}
  `;
}

// ── Render Building Floor Blueprints (Door-Aligned Non-Cut Arrows) ──
function renderBuildingFloors(bKey, snapshot) {
  // Exact native pixel dimensions match b1_floor.png (1024x502), b2_floor.png (1024x523), b3_floor.png (1024x436)
  const bMap = {
    tpb: {
      code: 'TPB', num: 1, name: 'Tech Pro Building', floors: 4, rpf: 5,
      img: '/static/img/b1_floor.png', imgH: 502,
      stairLBox: { x: 70, y: 58, w: 72, h: 246 },
      stairRBox: { x: 875, y: 58, w: 73, h: 246 },
    },
    ab: {
      code: 'AB', num: 2, name: 'Academic Building', floors: 4, rpf: 3,
      img: '/static/img/b2_floor.png', imgH: 523,
      stairLBox: { x: 72, y: 60, w: 73, h: 248 },
      stairRBox: { x: 875, y: 60, w: 73, h: 248 },
    },
    lb: {
      code: 'LB', num: 3, name: 'Laboratory Building', floors: 2, rpf: 2,
      img: '/static/img/b3_floor.png', imgH: 436,
      stairLBox: { x: 74, y: 50, w: 90, h: 250 },
      stairRBox: { x: 882, y: 50, w: 86, h: 250 },
    },
  };
  const cfg = bMap[bKey] || bMap.tpb;
  const { code: bCode, num: bNum, name: bName, floors, rpf: roomsPerFloor, img: bImg, imgH, stairLBox, stairRBox } = cfg;

  // Measured exact doorway openings (dlX / drX both pass cleanly inside the drawn open doorway)
  const roomBoxes = {
    TPB: {
      1: { x: 148, y: 58, w: 146, h: 246, dlX: 233, drX: 241, doorY: 306, corrY: 368, stairLX: 106, stairRX: 911, stairEntryY: 270 },
      2: { x: 298, y: 58, w: 136, h: 246, dlX: 375, drX: 383, doorY: 306, corrY: 368, stairLX: 106, stairRX: 911, stairEntryY: 270 },
      3: { x: 438, y: 58, w: 132, h: 246, dlX: 499, drX: 507, doorY: 306, corrY: 368, stairLX: 106, stairRX: 911, stairEntryY: 270 },
      4: { x: 574, y: 58, w: 134, h: 246, dlX: 627, drX: 635, doorY: 306, corrY: 368, stairLX: 106, stairRX: 911, stairEntryY: 270 },
      5: { x: 712, y: 58, w: 158, h: 246, dlX: 777, drX: 785, doorY: 306, corrY: 368, stairLX: 106, stairRX: 911, stairEntryY: 270 },
    },
    AB: {
      1: { x: 150, y: 60, w: 244, h: 248, dlX: 282, drX: 290, doorY: 310, corrY: 374, stairLX: 108, stairRX: 911, stairEntryY: 274 },
      2: { x: 400, y: 60, w: 220, h: 248, dlX: 504, drX: 512, doorY: 310, corrY: 374, stairLX: 108, stairRX: 911, stairEntryY: 274 },
      3: { x: 626, y: 60, w: 244, h: 248, dlX: 734, drX: 742, doorY: 310, corrY: 374, stairLX: 108, stairRX: 911, stairEntryY: 274 },
    },
    LB: {
      1: { x: 172, y: 50, w: 348, h: 250, dlX: 344, drX: 352, doorY: 302, corrY: 355, stairLX: 119, stairRX: 925, stairEntryY: 265 },
      2: { x: 528, y: 50, w: 346, h: 250, dlX: 682, drX: 690, doorY: 302, corrY: 355, stairLX: 119, stairRX: 925, stairEntryY: 265 },
    }
  };

  setText('bld-view-title', `${bName} (${bCode})`);
  setText('bld-view-sub', `${floors} Floors · ${floors * roomsPerFloor} Classrooms`);

  const grid = document.getElementById('floor-grid');
  if (!grid) return;

  let anyBlocked = false;
  let anyCritical = false;
  const selectedRoomId = appState.locRoom || document.getElementById('sb-room-select')?.value || '';
  const focusedFloorKey = (appState.locBldg && appState.locFloor) ? `${appState.locBldg}-F${appState.locFloor}` : '';
  const isSingleFloorDisplay = focusedFloorKey.startsWith(`${bCode}-`);
  grid.className = `floor-grid ${isSingleFloorDisplay ? 'single-floor-focus' : ''}`;
  const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';
  const unavailSet = new Set(snapshot?.unavailable || []);
  const unavailRawSet = new Set(snapshot?.unavailable_raw || []);

  // Helper: Draw Gray Overlay with Crisp Bold SVG 'X' and Label Pill
  function renderGrayX(x, y, w, h, tagText, pillW = 88) {
    const pad = Math.min(18, Math.max(8, Math.min(w, h) * 0.16));
    const cx = x + w / 2;
    const cy = y + h / 2;
    return `
      <g>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="5"
          fill="rgba(71, 85, 105, 0.58)" stroke="#94a3b8" stroke-width="2"/>
        <line x1="${x + pad}" y1="${y + pad}" x2="${x + w - pad}" y2="${y + h - pad}"
          stroke="#0f172a" stroke-width="8" stroke-linecap="round" opacity="0.6"/>
        <line x1="${x + w - pad}" y1="${y + pad}" x2="${x + pad}" y2="${y + h - pad}"
          stroke="#0f172a" stroke-width="8" stroke-linecap="round" opacity="0.6"/>
        <line x1="${x + pad}" y1="${y + pad}" x2="${x + w - pad}" y2="${y + h - pad}"
          stroke="#e2e8f0" stroke-width="4.5" stroke-linecap="round"/>
        <line x1="${x + w - pad}" y1="${y + pad}" x2="${x + pad}" y2="${y + h - pad}"
          stroke="#e2e8f0" stroke-width="4.5" stroke-linecap="round"/>
        <rect x="${cx - pillW / 2}" y="${cy - 10}" width="${pillW}" height="20" rx="4" fill="#0f172a" opacity="0.95"/>
        <text x="${cx}" y="${cy + 3.5}" text-anchor="middle" fill="#cbd5e1"
          font-size="9.5" font-weight="800" font-family="'Atkinson Hyperlegible Mono', monospace">${tagText}</text>
      </g>
    `;
  }

  grid.innerHTML = '';
  for (let f = 1; f <= floors; f++) {
    const pCode = `${bCode}-F${f}`;
    if (isSingleFloorDisplay && pCode !== focusedFloorKey) continue;
    const imgW = 1024;

    const badgeW = 136;
    const badgeH = 32;
    const camLeftX = 148;
    const camLeftY = imgH - badgeH - 10;
    const camRightX = 1024 - 148 - badgeW;
    const camRightY = imgH - badgeH - 10;

    const didLeft  = `${pCode}-CAM-L`;
    const didRight = `${pCode}-CAM-R`;

    const detLeft  = appState.detections.find(d => d.device_id === didLeft);
    const detRight = appState.detections.find(d => d.device_id === didRight);

    const colLeft = detLeft?.classification?.level === 'CRITICAL' ? '#dc2626' : detLeft?.classification?.level === 'WARNING' ? '#d97706' : '#10b981';
    const colRight = detRight?.classification?.level === 'CRITICAL' ? '#dc2626' : detRight?.classification?.level === 'WARNING' ? '#d97706' : '#10b981';

    let roomOverlays = '';
    let facilityOverlays = '';
    let arrows = '';
    let floorSafe = true;
    let floorCritical = false;

    const firstBox = roomBoxes[bCode]?.[1];
    const lastBox = roomBoxes[bCode]?.[roomsPerFloor];
    const corrY = firstBox?.corrY || 356;

    // 1. Check Unavailable Stairwells & Corridors (Always visible as Gray X)
    if (unavailSet.has(`${pCode}-STAIR-L`)) {
      facilityOverlays += renderGrayX(stairLBox.x, stairLBox.y, stairLBox.w, stairLBox.h, 'STAIR L · X', 80);
    }
    if (unavailSet.has(`${pCode}-STAIR-R`)) {
      facilityOverlays += renderGrayX(stairRBox.x, stairRBox.y, stairRBox.w, stairRBox.h, 'STAIR R · X', 80);
    }

    const wholeCorrUnavail = unavailRawSet.has(`${pCode}-CORRIDOR`);
    if (wholeCorrUnavail) {
      facilityOverlays += renderGrayX(firstBox.x, corrY - 16, (lastBox.x + lastBox.w) - firstBox.x, 32, `${pCode} CORRIDOR UNAVAIL`, 170);
    } else {
      for (let c = 0; c <= roomsPerFloor; c++) {
        if (unavailSet.has(`${pCode}-C${c}`)) {
          const sx = c === 0
            ? 140
            : c === roomsPerFloor
              ? (lastBox.x + lastBox.w - 30)
              : (roomBoxes[bCode][c].x + roomBoxes[bCode][c].w - 42);
          const sw = (c === 0 || c === roomsPerFloor) ? 74 : 84;
          facilityOverlays += renderGrayX(sx, corrY - 15, sw, 30, `C${c} · X`, 64);
        }
      }
    }

    // 2. Render Each Classroom Box & Diverting Arrows
    const showDetourArrows = isEmergency || unavailSet.size > 0;
    for (let r = 1; r <= roomsPerFloor; r++) {
      const rmId = `${pCode}-R${r}`;
      const rm = snapshot?.routes?.[rmId];
      const box = roomBoxes[bCode]?.[r];
      if (!box) continue;

      const rmStatus = rm?.status || 'MODELED_ROUTE_AVAILABLE';
      const isSelected = rmId === selectedRoomId;

      if (rmStatus === 'FACILITY_UNAVAILABLE') {
        roomOverlays += renderGrayX(box.x, box.y, box.w, box.h, `R${r} · UNAVAIL`, 92);
        continue;
      }

      if (showDetourArrows || isSelected) {
        let fillCol, strokeCol, tagText, tagCol;
        if (rmStatus === 'MODELED_ROUTE_AVAILABLE') {
          fillCol = isSelected ? 'rgba(5, 150, 105, 0.34)' : 'rgba(5, 150, 105, 0.20)';
          strokeCol = '#10b981';
          tagText = `R${r} · SAFE`;
          tagCol = '#86efac';
        } else if (rmStatus === 'HOLD_FOR_AUTHORIZED_GUIDANCE') {
          floorSafe = false;
          fillCol = 'rgba(217, 119, 6, 0.30)';
          strokeCol = '#f59e0b';
          tagText = `R${r} · HOLD`;
          tagCol = '#fde68a';
        } else {
          floorSafe = false;
          floorCritical = true;
          fillCol = 'rgba(220, 38, 38, 0.36)';
          strokeCol = '#ef4444';
          tagText = `R${r} · THREAT`;
          tagCol = '#fca5a5';
        }

        roomOverlays += `
          <g id="box-${rmId}" style="cursor:pointer; pointer-events:all;" onclick="inspectRoomFromBlueprint('${rmId}')">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="5"
              fill="${fillCol}" stroke="${strokeCol}" stroke-width="${isSelected ? 3.5 : 2}"/>
            <rect x="${box.x + 8}" y="${box.y + 8}" width="72" height="20" rx="4" fill="#0f172a" opacity="0.92"/>
            <text x="${box.x + 44}" y="${box.y + 22}" text-anchor="middle" fill="${tagCol}"
              font-size="10" font-weight="800" font-family="'Atkinson Hyperlegible Mono', monospace">${tagText}</text>
          </g>
        `;

        if (rmStatus === 'MODELED_ROUTE_AVAILABLE') {
          const useLeft = rm?.route?.some(n => n.includes('STAIR-L'))
            ? true
            : rm?.route?.some(n => n.includes('STAIR-R'))
              ? false
              : (r <= roomsPerFloor / 2);

          const targetX = useLeft ? box.stairLX : box.stairRX;
          const doorX = rm?.door?.endsWith('-DL') ? box.dlX : rm?.door?.endsWith('-DR') ? box.drX : (useLeft ? box.dlX : box.drX);
          const startX = Math.round(box.x + (box.w / 2));
          const startY = Math.round(box.y + (box.h * 0.48));
          const preDoorY = box.doorY - 38;
          const laneOffset = Math.round((r - (roomsPerFloor + 1) / 2) * 7);
          const laneY = box.corrY + laneOffset;
          const pathD = `M ${startX} ${startY} L ${doorX} ${preDoorY} L ${doorX} ${box.doorY} L ${doorX} ${laneY} L ${targetX} ${laneY} L ${targetX} ${box.stairEntryY}`;

          arrows += `
            <path d="${pathD}"
              fill="none" stroke="#064e3b" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.45"/>
            <path d="${pathD}"
              fill="none" stroke="#10b981" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"
              stroke-dasharray="10,6" marker-end="url(#arr-f-${bCode}-${f})">
              <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.85s" repeatCount="indefinite"/>
            </path>
          `;
        }
      } else {
        roomOverlays += `
          <g id="box-${rmId}" style="cursor:pointer; pointer-events:all;" onclick="inspectRoomFromBlueprint('${rmId}')">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="4"
              fill="${isSelected ? 'rgba(11, 92, 171, 0.18)' : 'rgba(255, 255, 255, 0.03)'}"
              stroke="${isSelected ? '#0b5cab' : 'rgba(148, 163, 184, 0.25)'}" stroke-width="${isSelected ? 3 : 1}"/>
            <rect x="${box.x + 8}" y="${box.y + 8}" width="46" height="18" rx="4" fill="#0f172a" opacity="0.8"/>
            <text x="${box.x + 31}" y="${box.y + 21}" text-anchor="middle" fill="#cbd5e1"
              font-size="10" font-weight="700" font-family="'Atkinson Hyperlegible Mono', monospace">R${r}</text>
          </g>
        `;
      }
    }

    if (floorCritical) anyCritical = true;
    if (!floorSafe) anyBlocked = true;

    const badgeClass = floorCritical ? 'critical' : !floorSafe ? 'warning' : 'safe';
    const badgeText  = !isEmergency ? (unavailSet.size ? 'Detour Active' : 'Clear') : floorCritical ? 'Threat' : !floorSafe ? 'Hold' : 'Evacuating';

    const isFocusedFloor = pCode === focusedFloorKey;
    const card = document.createElement('div');
    card.id = `floor-card-${pCode}`;
    card.className = `floor-card ${isFocusedFloor ? 'focused-floor' : ''}`;
    card.innerHTML = `
      <div class="floor-card-header">
        <div>
          <span class="floor-card-title">Floor ${f}</span>
          <span class="floor-card-code"> &middot; ${pCode}</span>
          ${isFocusedFloor ? '<span class="brand-tag" style="margin-left:6px;">YOUR LOCATION</span>' : ''}
        </div>
        <span class="badge ${badgeClass}">
          <span class="status-beacon ${badgeClass === 'safe' ? '' : badgeClass}" style="width:6px; height:6px;"></span>
          ${badgeText}
        </span>
      </div>
      <div class="floor-card-img-wrap">
        <img src="${bImg}" alt="Floor ${f} Blueprint" />
        <svg viewBox="0 0 ${imgW} ${imgH}" overflow="visible" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker id="arr-f-${bCode}-${f}" viewBox="0 0 12 12" markerWidth="6.5" markerHeight="6.5" refX="8" refY="6" orient="auto" overflow="visible">
              <path d="M 0 1 L 10 6 L 0 11 z" fill="#10b981" stroke="#064e3b" stroke-width="0.8"/>
            </marker>
          </defs>
          ${roomOverlays}
          ${facilityOverlays}
          ${arrows}
          <g>
            <rect x="${camLeftX}" y="${camLeftY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <circle cx="${camLeftX + 14}" cy="${camLeftY + badgeH / 2}" r="5" fill="${colLeft}"/>
            <text x="${camLeftX + 25}" y="${camLeftY + badgeH / 2 + 4}" fill="#ffffff" font-size="10.5" font-weight="700" font-family="'Atkinson Hyperlegible Mono', monospace">${didLeft}</text>
          </g>
          <g>
            <rect x="${camRightX}" y="${camRightY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <circle cx="${camRightX + 14}" cy="${camRightY + badgeH / 2}" r="5" fill="${colRight}"/>
            <text x="${camRightX + 25}" y="${camRightY + badgeH / 2 + 4}" fill="#ffffff" font-size="10.5" font-weight="700" font-family="'Atkinson Hyperlegible Mono', monospace">${didRight}</text>
          </g>
        </svg>
      </div>
    `;
    grid.appendChild(card);
  }

  const bldBadge = document.getElementById('bld-view-badge');
  const bType = anyCritical ? 'critical' : anyBlocked ? 'warning' : 'safe';
  if (bldBadge) {
    bldBadge.className = `badge ${bType}`;
    bldBadge.innerHTML = `<span class="status-beacon ${bType === 'safe' ? '' : bType}" style="width:6px; height:6px;"></span> ${!isEmergency ? 'Normal' : anyCritical ? 'Threat Area' : anyBlocked ? 'Hold / Caution' : 'Evacuating'}`;
  }
}

// ── Building Status Badges in Pills & Summary Cards ────────
function updateBuildingBadges(snapshot) {
  const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';
  const bMap = [
    { code: 'TPB', dotId: 'dot-tpb', badgeId: 'tpb-badge' },
    { code: 'AB',  dotId: 'dot-ab',  badgeId: 'ab-badge' },
    { code: 'LB',  dotId: 'dot-lb',  badgeId: 'lb-badge' },
  ];

  bMap.forEach(({ code, dotId, badgeId }) => {
    const dot = document.getElementById(dotId);
    const badgeEl = document.getElementById(badgeId);

    const hasCritical = Object.entries(snapshot?.routes || {}).some(
      ([rm, r]) => rm.startsWith(`${code}-`) && r.status === 'NO_CONFIRMED_ROUTE'
    );
    const hasWarning = Object.entries(snapshot?.routes || {}).some(
      ([rm, r]) => rm.startsWith(`${code}-`) && r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE'
    );

    let stat = 'safe';
    let label = 'All Clear';
    if (isEmergency) {
      if (hasCritical) { stat = 'critical'; label = 'Threat Area'; }
      else if (hasWarning) { stat = 'warning'; label = 'Hold in Place'; }
      else { stat = 'safe'; label = 'Evacuating'; }
    }

    if (dot) dot.className = `status-beacon ${stat === 'safe' ? '' : stat}`;
    if (badgeEl) {
      badgeEl.innerHTML = `<span class="badge ${stat}"><span class="status-beacon ${stat === 'safe' ? '' : stat}" style="width:6px;height:6px;"></span>${label}</span>`;
    }
  });
}

// ── KPI Metrics ────────────────────────────────────────────
function updateMetrics(snap) {
  const counts = snap.counts || {};
  setText('m-safe',    counts.available ?? counts['MODELED_ROUTE_AVAILABLE'] ?? '36');
  setText('m-unavail', counts.unavailable ?? 0);
  setText('m-hold',    counts.hold ?? counts['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? '0');
  setText('m-blocked', counts.no_route ?? counts['NO_CONFIRMED_ROUTE'] ?? '0');
}

// ── Classroom Table & Event Log ────────────────────────────
function updateRoomsTable(snap) {
  const tbody = document.getElementById('rooms-table-body');
  if (!tbody) return;

  const routes = snap.routes || {};
  tbody.innerHTML = Object.entries(routes).map(([rm, r]) => {
    const isSafe = r.status === 'MODELED_ROUTE_AVAILABLE';
    const isUnavail = r.status === 'FACILITY_UNAVAILABLE';
    const isHold = r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE';
    const rowClass = isSafe ? 'row-safe' : isUnavail ? 'row-unavail' : isHold ? 'row-hold' : 'row-threat';
    const statusClass = isSafe ? 'safe' : isUnavail ? 'unavail' : isHold ? 'warning' : 'critical';
    const statusLabel = isSafe ? 'Safe Egress' : isUnavail ? 'Unavailable (X)' : isHold ? 'Hold in Place' : 'Threat / Blocked';

    return `<tr class="${rowClass}">
      <td><span class="room-code">${rm}</span></td>
      <td><span class="badge ${statusClass}"><span class="status-beacon ${statusClass === 'safe' || statusClass === 'unavail' ? '' : statusClass}" style="width:6px;height:6px;"></span>${statusLabel}</span></td>
      <td><span class="gate-code">${r.gate || '—'}</span></td>
      <td>${r.door_label || '—'}</td>
      <td>${r.route?.length ? r.route.length + ' nodes' : (isUnavail ? 'Closed' : 'Blocked')}</td>
    </tr>`;
  }).join('');

  const badge = document.getElementById('table-status-badge');
  const lvl = (snap.global_status || 'NORMAL').toLowerCase();
  if (badge) {
    badge.className = `badge ${lvl === 'normal' ? 'safe' : lvl}`;
    badge.textContent = lvl.toUpperCase();
  }
}

function updateEventLog(snap) {
  const el = document.getElementById('event-log');
  if (el) {
    const events = snap.events || [];
    if (!events.length) {
      el.innerHTML = '<div class="empty-state">No active incidents recorded. Campus secure.</div>';
    } else {
      el.innerHTML = `<div class="event-list">${events.map(ev => {
        const lvl = (ev.level || 'NORMAL').toLowerCase();
        const loc = Array.isArray(ev.location) ? ev.location.join(', ') : (ev.location || '');
        return `
          <div class="event-item ${lvl}">
            <span class="status-beacon ${lvl === 'normal' ? '' : lvl}" style="margin-top:4px;"></span>
            <div>
              <div style="font-weight:800; color:var(--c-navy);">${ev.device_id} &middot; ${ev.level}</div>
              <div style="color:var(--c-muted); font-size:11px;">Event <code>${ev.event_id}</code> ${loc ? `&middot; Zone: ${loc}` : ''}</div>
            </div>
          </div>
        `;
      }).join('')}</div>`;
    }
  }

  const resEl = document.getElementById('resolved-incidents-log');
  if (resEl) {
    const hist = (appState.incidents || []).slice(0, 6);
    if (!hist.length) {
      resEl.innerHTML = '<div class="archive-note">No archived incidents yet.</div>';
    } else {
      resEl.innerHTML = hist.map(inc => {
        const isRes = inc.status === 'RESOLVED';
        return `
          <div class="archive-row">
            <div>
              <b>${inc.incident_id}</b> · ${inc.root_location || 'Campus'}
              ${inc.notes ? `<div class="archive-note">${inc.notes}</div>` : ''}
            </div>
            <span class="badge ${isRes ? 'safe' : 'critical'}">${inc.status}</span>
          </div>
        `;
      }).join('');
    }
  }
}

// ── CCTV Matrix Grid ───────────────────────────────────────
function filterCams(group) {
  appState.camFilter = group;
  document.querySelectorAll('#tab-cctv .filter-pill').forEach(b => b.classList.remove('active'));
  document.getElementById(`camf-${group}`)?.classList.add('active');
  renderCamGrid();
}

function renderCamGrid() {
  const grid = document.getElementById('cam-grid');
  if (!grid) return;

  const filter = appState.camFilter;
  const allDevices = appState.devices || {};
  const detections = appState.detections || [];

  const outdoorDescriptions = {
    'TPB-CAM-OUT-L': 'Perimeter — Tech Pro West Approach (GATE-W)',
    'TPB-CAM-OUT-R': 'Perimeter — Tech Pro East Approach (GATE-NE)',
    'AB-CAM-OUT-L':  'Perimeter — Academic North Courtyard',
    'AB-CAM-OUT-R':  'Perimeter — Academic East Alley',
    'LB-CAM-OUT-L':  'Perimeter — Laboratory West Gate Path',
    'LB-CAM-OUT-R':  'Perimeter — Laboratory Courtyard Path',
  };

  const filtered = Object.values(allDevices).filter(d => {
    const isOutdoor = d.kind === 'outdoor' || d.device_id.includes('OUT');
    if (filter === 'outside') return isOutdoor;
    if (filter === 'tpb') return d.device_id.startsWith('TPB-') && !isOutdoor;
    if (filter === 'ab')  return d.device_id.startsWith('AB-')  && !isOutdoor;
    if (filter === 'lb')  return d.device_id.startsWith('LB-')  && !isOutdoor;
    return false;
  });

  if (!filtered.length) {
    grid.innerHTML = '<div class="empty-state">No cameras in this group.</div>';
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

    const coverage = outdoorDescriptions[d.device_id]
      || (d.covered_rooms?.length ? `Rooms: ${d.covered_rooms.join(', ')}` : (d.covered_node || 'Campus Approach'));

    const bodyHtml = hasAlert ? `
      <div class="cam-video-row">
        <video src="${latest.video_url || '/videos-project/test_video.mp4'}" controls autoplay muted playsinline loop
          style="width:100%; height:156px; object-fit:cover; border-radius:8px; background:#000; display:block;">
        </video>
        <div class="cam-scores">
          <div class="cam-scores-title">Detection scores</div>
          <div class="cam-score-row"><span>Threat score</span><span class="cam-score-val threat">${clf.index?.toFixed(1) ?? '—'} / 100</span></div>
          <div class="cam-score-row"><span>Object (&ge;60%)</span><span class="cam-score-val">${scores.object ?? clf.object ?? '—'}%</span></div>
          <div class="cam-score-row"><span>Pose</span><span class="cam-score-val">${scores.pose ?? clf.pose ?? '—'}%</span></div>
          <div class="cam-score-row"><span>Sound</span><span class="cam-score-val">${scores.acoustic ?? clf.acoustic ?? '—'}%</span></div>
          <div class="cam-score-row"><span>Verified</span><span class="cam-score-val ${clf.verified ? 'threat' : ''}">${clf.verified ? 'Yes' : 'No'}</span></div>
        </div>
      </div>
    ` : `
      <div class="cctv-screen">
        <div class="cctv-osd-top">
          <span>${d.device_id}</span>
          <span class="cctv-osd-rec"><span class="cctv-rec-dot"></span>STANDBY</span>
        </div>
        <div class="cctv-center-notice">
          <div class="cctv-center-status">ONLINE &middot; NO ACTIVE THREAT</div>
          <div class="cctv-center-sub">Ready for 3-Criteria Video Scan</div>
        </div>
        <div class="cctv-osd-bottom">
          <span>YOLOv8n + Pose + RMS</span>
          <span>30 FPS</span>
        </div>
      </div>
    `;

    return `
      <div class="cam-card ${hasAlert ? 'alert' : ''}">
        <div class="cam-card-header">
          <span class="cam-id">${d.device_id}</span>
          <span class="badge ${badgeClass}">
            <span class="status-beacon ${badgeClass === 'safe' ? '' : badgeClass}" style="width:6px;height:6px;"></span>
            ${lvl}
          </span>
        </div>
        <div class="cam-body">
          <div class="cam-coverage">${coverage}</div>
          ${bodyHtml}
        </div>
      </div>
    `;
  }).join('');
}

// ── Fast 3-Criteria Video Scanner Modal ────────────────────
function resetCriteriaCards() {
  const defs = [
    { idx: 1, rule: 'YOLO >= 60%' },
    { idx: 2, rule: '>=2 Sigs >= 50%' },
    { idx: 3, rule: 'Index >= 70.0' },
  ];
  defs.forEach(({ idx, rule }) => {
    const card = document.getElementById(`crit-card-${idx}`);
    const badge = document.getElementById(`crit-badge-${idx}`);
    const val = document.getElementById(`crit-val-${idx}`);
    if (card) card.className = 'crit-pill-card';
    if (badge) badge.textContent = 'REQ';
    if (val) val.textContent = rule;
  });
  const resBox = document.getElementById('modal-scan-result');
  if (resBox) {
    resBox.style.display = 'none';
    resBox.className = 'scan-result-box';
  }
}

function openUploadModal() {
  const modal = document.getElementById('upload-modal');
  const sel = document.getElementById('modal-upload-device');
  const fileInput = document.getElementById('modal-video-file');
  const progress = document.getElementById('modal-upload-progress');
  const submitBtn = document.getElementById('modal-upload-submit');

  if (fileInput) fileInput.value = '';
  if (progress) progress.style.display = 'none';
  if (submitBtn) submitBtn.disabled = false;
  resetCriteriaCards();

  if (modal && sel) {
    populateDeviceDropdown(sel);
    modal.style.display = 'flex';
  }
}

function closeUploadModal() {
  const modal = document.getElementById('upload-modal');
  if (modal) modal.style.display = 'none';
}

function populateDeviceDropdown(selectEl) {
  const groups = {};
  CANONICAL_DEVICES.forEach(d => {
    if (!groups[d.grp]) groups[d.grp] = [];
    groups[d.grp].push(d);
  });
  selectEl.innerHTML = Object.entries(groups)
    .map(([grp, list]) => `<optgroup label="${grp}">${list.map(item => `<option value="${item.id}">${item.label}</option>`).join('')}</optgroup>`)
    .join('');
}

async function submitModalVideoUpload() {
  const fileInput = document.getElementById('modal-video-file');
  const devSelect = document.getElementById('modal-upload-device');
  const progress = document.getElementById('modal-upload-progress');
  const statusTxt = document.getElementById('modal-upload-status');
  const submitBtn = document.getElementById('modal-upload-submit');
  const cancelBtn = document.getElementById('modal-upload-cancel');
  const closeBtn = document.getElementById('modal-upload-close');
  const resBox = document.getElementById('modal-scan-result');

  if (!fileInput || !fileInput.files.length) {
    toast('Select a video file first', 'warning');
    return;
  }
  const file = fileInput.files[0];
  const targetDev = devSelect ? devSelect.value : 'TPB-CAM-OUT-L';

  resetCriteriaCards();
  if (progress) progress.style.display = 'block';
  if (statusTxt) statusTxt.textContent = `Scanning ${file.name} on ${targetDev} (YOLOv8 + Multi-Pose + Audio)…`;

  // Lock scan button & modal controls while inference runs
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add('btn-scanning');
    submitBtn.innerHTML = '<span class="spinner"></span> Scanning Video…';
  }
  if (cancelBtn) cancelBtn.disabled = true;
  if (closeBtn) closeBtn.disabled = true;
  if (fileInput) fileInput.disabled = true;
  if (devSelect) devSelect.disabled = true;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('device_ids', targetDev);

  try {
    const res = await fetch(API + '/api/upload-video', {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    const data = await res.json();

    if (res.ok) {
      const c1Pass = (data.object_score ?? 0) >= 60;
      const c2Pass = (data.supporting_signals ?? 0) >= 2;
      const c3Pass = (data.threat_index ?? 0) >= 70;

      // Update Criterion 1 Card
      const c1Card = document.getElementById('crit-card-1');
      if (c1Card) c1Card.className = `crit-pill-card ${c1Pass ? 'pass' : 'fail'}`;
      setText('crit-badge-1', c1Pass ? 'PASS' : 'FAIL');
      setText('crit-val-1', `Object: ${Number(data.object_score || 0).toFixed(1)}%`);

      // Update Criterion 2 Card
      const c2Card = document.getElementById('crit-card-2');
      if (c2Card) c2Card.className = `crit-pill-card ${c2Pass ? 'pass' : 'fail'}`;
      setText('crit-badge-2', c2Pass ? 'PASS' : 'FAIL');
      setText('crit-val-2', `${data.supporting_signals ?? 0}/3 Signals >= 50%`);

      // Update Criterion 3 Card
      const c3Card = document.getElementById('crit-card-3');
      if (c3Card) c3Card.className = `crit-pill-card ${c3Pass ? 'pass' : 'fail'}`;
      setText('crit-badge-3', c3Pass ? 'PASS' : 'FAIL');
      setText('crit-val-3', `Index: ${Number(data.threat_index || 0).toFixed(1)} / 100`);

      if (resBox) {
        const boxCls = data.criteria_passed ? 'critical' : data.level === 'WARNING' ? 'warning' : 'safe';
        const headline = data.criteria_passed
          ? `Threat verified (${data.level}) — evacuation activated`
          : data.level === 'WARNING'
            ? 'Caution alert (WARNING) — monitor zone'
            : `Standby — no threat detected (${data.level})`;
        resBox.style.display = 'block';
        resBox.className = `scan-result-box ${boxCls}`;
        resBox.innerHTML = `
          <div style="font-weight:700; margin-bottom:2px;">
            ${headline}
            &middot; <span style="font-family:'Atkinson Hyperlegible Mono',monospace;">${Number(data.scan_ms || 0).toFixed(0)}ms</span>
            ${data.early_exit ? ' &middot; Early-Exit' : ''}
          </div>
          <div style="font-size:12px;">
            Object ${Number(data.object_score || 0).toFixed(0)}% &middot; Pose ${Number(data.pose_score || 0).toFixed(0)}% &middot; Acoustic ${Number(data.acoustic_score || 0).toFixed(0)}%
            (${data.frames_analyzed || 0} keyframes)
          </div>
        `;
      }

      await refresh();
      const toastMsg = data.criteria_passed
        ? `Threat verified on ${targetDev} in ${Number(data.scan_ms || 0).toFixed(0)}ms. Evacuation activated.`
        : data.level === 'WARNING'
          ? `Caution alert (WARNING) on ${targetDev} (${Number(data.scan_ms || 0).toFixed(0)}ms). Monitor zone.`
          : `No threat detected on ${targetDev} (${Number(data.scan_ms || 0).toFixed(0)}ms). Campus remains clear.`;
      const toastKind = data.criteria_passed ? 'critical' : data.level === 'WARNING' ? 'warning' : 'success';
      toast(toastMsg, toastKind);
    } else {
      toast(`Scan error: ${data.detail || 'Inference failed'}`, 'error');
    }
  } catch (err) {
    toast(`Upload failed: ${err.message}`, 'error');
  } finally {
    if (progress) progress.style.display = 'none';
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove('btn-scanning');
      submitBtn.textContent = 'Scan Video Now';
    }
    if (cancelBtn) cancelBtn.disabled = false;
    if (closeBtn) closeBtn.disabled = false;
    if (fileInput) fileInput.disabled = false;
    if (devSelect) devSelect.disabled = false;
  }
}

// ── Quick Simulator Modal ──────────────────────────────────
function openSimModal() {
  const modal = document.getElementById('sim-modal');
  const sel = document.getElementById('sim-target-cam');
  if (modal && sel) {
    populateDeviceDropdown(sel);
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

  const scores = level === 'CRITICAL'
    ? { acoustic: 88, pose: 80, object: 92 }
    : { acoustic: 55, pose: 45, object: 40 };

  const res = await apiFetch('/api/simulate-threat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_ids: [targetCam],
      level,
      acoustic: scores.acoustic,
      pose: scores.pose,
      object: scores.object,
    }),
  });

  if (res?.ok) {
    closeSimModal();
    toast(`Simulated ${level} feed on ${targetCam}`, 'critical');
    await refresh();
  }
}

async function clearDetections() {
  const res = await apiFetch('/api/detections/clear', { method: 'POST' });
  if (res?.ok) {
    toast('All camera detections cleared', 'success');
    await refresh();
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Hardware Digital Twin & MQTT Telemetry Renderer ────────
function renderHardwareTwin() {
  const hw = appState.hardware;
  if (!hw) return;

  const dev = hw.device || {};
  const tel = hw.telemetry || {};
  const brokerOk = !!hw.broker_connected;
  const espOnline = !!dev.online;

  // Topbar ESP32 status dot inside the ESP32 device nav pill
  const topBeacon = document.getElementById('topbar-esp-beacon');
  const hwTabBtn = document.getElementById('tab-btn-hardware');
  if (topBeacon) topBeacon.className = `status-beacon ${espOnline ? '' : 'warning'}`;
  if (hwTabBtn) hwTabBtn.title = espOnline ? 'ESP32 online' : 'ESP32 standby';

  // Broker & Node badges
  const brokerBadge = document.getElementById('hw-broker-badge');
  const brokerDot = document.getElementById('hw-broker-dot');
  if (brokerBadge) brokerBadge.className = `badge ${brokerOk ? 'safe' : 'warning'}`;
  if (brokerDot) brokerDot.className = `status-beacon ${brokerOk ? '' : 'warning'}`;
  setText('hw-broker-text', brokerOk ? `MQTT: ${hw.broker}:${hw.port}` : 'MQTT: reconnecting');

  const nodeBadge = document.getElementById('hw-node-badge');
  const nodeDot = document.getElementById('hw-node-dot');
  if (nodeBadge) nodeBadge.className = `badge ${espOnline ? 'safe' : 'warning'}`;
  if (nodeDot) nodeDot.className = `status-beacon ${espOnline ? '' : 'warning'}`;
  setText('hw-node-text', espOnline ? `${dev.device_id}: online` : `${dev.device_id}: waiting`);
  setText('hw-last-hb', dev.last_heartbeat ? `Last heartbeat: ${dev.last_heartbeat}` : 'Start Wokwi sketch to connect');

  // Virtual SSD1306 OLED & Buzzer
  setText('oled-link', espOnline ? '[LIVE]' : '[TWIN]');
  setText('oled-status', tel.status || 'NORMAL');
  setText('oled-gate', tel.evac_gate || 'BOTH');
  const c = tel.counts || {};
  setText('oled-counts', `S:${c.safe ?? 36}  H:${c.hold ?? 0}  T:${c.blocked ?? 0}  #${tel.seq ?? 0}`);

  const buzBadge = document.getElementById('hw-buzzer-badge');
  const buzMode = tel.buzzer || 'OFF';
  if (buzBadge) {
    buzBadge.className = `badge ${buzMode === 'ALARM' ? 'critical' : buzMode === 'CHIRP' ? 'warning' : 'safe'}`;
    buzBadge.textContent = `BUZZER: ${buzMode}`;
  }

  // ESP32 Edge Acoustic Sensor & Link Telemetry (GPIO 34 / Wi-Fi RSSI)
  const acVal = Number(dev.acoustic_sim ?? 18.0);
  const pct = Math.min(100, Math.max(0, acVal));
  setText('hw-fw-badge', dev.firmware || 'SENTINEL-GW-v2.1');
  setText('hw-acoustic-val', `${acVal.toFixed(1)} dB-idx`);
  setText('hw-rssi-val', dev.rssi != null ? `${dev.rssi} dBm` : '— dBm');
  const acBar = document.getElementById('hw-acoustic-bar');
  if (acBar) {
    acBar.style.width = `${pct}%`;
    acBar.className = `acoustic-bar-fill ${acVal >= 85 ? 'crit' : acVal >= 50 ? 'warn' : ''}`;
  }

  // 12-Channel Addressable NeoPixel Zone Strip
  const ledStrip = document.getElementById('hw-led-strip');
  if (ledStrip && Array.isArray(hw.leds)) {
    ledStrip.innerHTML = hw.leds.map((led, idx) => {
      const code = led.code || 'S';
      const label = code === 'T' ? 'Threat / blocked' : code === 'H' ? 'Hold / caution' : 'Safe / open';
      return `
        <div class="hw-led-node">
          <div class="hw-led-top">
            <span class="hw-led-id">#${idx} · ${led.id}</span>
            <span class="hw-led-bulb ${code}"></span>
          </div>
          <span class="hw-led-sub">${label}</span>
        </div>
      `;
    }).join('');
  }

  // Live MQTT Packet Stream
  const pktLog = document.getElementById('hw-packet-log');
  if (pktLog) {
    const pkts = hw.packets || [];
    if (!pkts.length) {
      pktLog.innerHTML = '<div class="empty-state">No MQTT packets logged yet. Click Sync ESP32 Now.</div>';
    } else {
      pktLog.innerHTML = pkts.map(p => `
        <div class="mqtt-pkt-row">
          <span style="color:var(--c-muted);">${p.time}</span>
          <span class="mqtt-dir ${p.dir}">${p.dir}</span>
          <span style="font-weight:700; color:var(--c-navy);">${p.topic}</span>
          <span class="mqtt-pkt-payload">${JSON.stringify(p.payload)}</span>
        </div>
      `).join('');
    }
  }
}

async function syncHardwareNow() {
  const res = await apiFetch('/api/hardware/sync', { method: 'POST' });
  if (res?.ok) {
    toast('Synced live campus state to ESP32 MQTT topic', 'success');
    await refresh();
  }
}

async function simulateHardwareEdgeTrigger(action) {
  const res = await apiFetch('/api/hardware/simulate-edge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action,
      target_device: 'TPB-F1-CAM-L',
      acoustic: 88.0,
      pose: 76.0,
      object: 85.0,
    }),
  });
  if (res?.ok) {
    toast(
      action === 'RESET'
        ? 'Hardware Reset button simulated — Campus All Clear'
        : 'ESP32 Break-Glass trigger simulated on TPB-F1-CAM-L!',
      action === 'RESET' ? 'success' : 'critical'
    );
    await refresh();
  }
}

// ── Public Occupant Floor & Location Selector ──────────────
function onLocatorBuildingChange() {
  const bldg = document.getElementById('loc-bldg')?.value || '';
  appState.locBldg = bldg;
  appState.locFloor = '';
  appState.locRoom = '';

  const flSel = document.getElementById('loc-floor');
  const rmSel = document.getElementById('loc-room');
  if (rmSel) rmSel.innerHTML = '<option value="">All rooms</option>';

  if (!bldg) {
    if (flSel) flSel.innerHTML = '<option value="">Floor</option>';
    switchMapView('campus');
    updateOccupantGuidance();
    return;
  }

  const maxFloors = bldg === 'LB' ? 2 : 4;
  if (flSel) {
    let html = '<option value="">All floors</option>';
    for (let f = 1; f <= maxFloors; f++) {
      html += `<option value="${f}">Floor ${f}</option>`;
    }
    flSel.innerHTML = html;
  }
  switchMapView(bldg.toLowerCase());
  updateOccupantGuidance();
}

function onLocatorFloorChange() {
  const bldg = appState.locBldg;
  const fl = document.getElementById('loc-floor')?.value || '';
  appState.locFloor = fl;
  appState.locRoom = '';

  const rmSel = document.getElementById('loc-room');
  if (rmSel) {
    let html = '<option value="">All rooms</option>';
    if (bldg && fl) {
      const rpf = bldg === 'TPB' ? 5 : bldg === 'AB' ? 3 : 2;
      for (let r = 1; r <= rpf; r++) {
        const rid = `${bldg}-F${fl}-R${r}`;
        html += `<option value="${rid}">Room ${r} (${rid})</option>`;
      }
    }
    rmSel.innerHTML = html;
  }

  if (bldg) {
    switchMapView(bldg.toLowerCase());
    if (fl) {
      const card = document.getElementById(`floor-card-${bldg}-F${fl}`);
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
  updateOccupantGuidance();
}

function onLocatorRoomChange() {
  appState.locRoom = document.getElementById('loc-room')?.value || '';
  if (appState.locBldg) switchMapView(appState.locBldg.toLowerCase());
  updateOccupantGuidance();
}

function inspectRoomFromBlueprint(roomId) {
  const parts = roomId.split('-');
  if (parts.length !== 3) return;
  const bldg = parts[0];
  const fl = parts[1].replace('F', '');
  appState.locBldg = bldg;
  appState.locFloor = fl;
  appState.locRoom = roomId;

  const bSel = document.getElementById('loc-bldg');
  if (bSel && bSel.value !== bldg) {
    bSel.value = bldg;
    onLocatorBuildingChange();
  }
  const fSel = document.getElementById('loc-floor');
  if (fSel && fSel.value !== fl) {
    fSel.value = fl;
    onLocatorFloorChange();
  }
  const rSel = document.getElementById('loc-room');
  if (rSel) rSel.value = roomId;
  appState.locRoom = roomId;

  if (appState.user) {
    const sbSel = document.getElementById('sb-room-select');
    if (sbSel) {
      sbSel.value = roomId;
      updateRoomInspectorCard(roomId);
    }
  }
  switchMapView(bldg.toLowerCase());
  updateOccupantGuidance();
}

function showResolvedThreatBanner(durationMs = 6000) {
  appState.resolvedBannerUntil = Date.now() + durationMs;
  if (appState.resolvedBannerTimer) {
    clearTimeout(appState.resolvedBannerTimer);
  }
  appState.resolvedBannerTimer = setTimeout(() => {
    appState.resolvedBannerTimer = null;
    appState.resolvedBannerUntil = 0;
    if (appState.snapshot) {
      updatePublicThreatBar(appState.snapshot);
    } else {
      const bar = document.getElementById('public-threat-bar');
      if (bar) bar.className = 'threat-loc-bar';
    }
  }, durationMs + 50);
}

function updatePublicThreatBar(snapshot) {
  const bar = document.getElementById('public-threat-bar');
  const beacon = document.getElementById('ptb-beacon');
  const labelEl = document.getElementById('ptb-label');
  const zonesEl = document.getElementById('ptb-zones');
  const actEl = document.getElementById('ptb-action');
  if (!bar || !snapshot) return;

  const lvl = (snapshot.global_status || 'NORMAL').toUpperCase();
  const prev = appState.prevGlobalStatus;
  const locs = snapshot.possible_threat_locations || [];
  const blocked = snapshot.blocked || [];
  const gatesBlocked = ['GATE-W', 'GATE-NE'].filter(g => blocked.includes(g));

  bar.className = 'threat-loc-bar';
  beacon.className = 'status-beacon';

  if (lvl === 'CRITICAL' || lvl === 'WARNING') {
    appState.prevGlobalStatus = lvl;
    appState.resolvedBannerUntil = 0;
    if (appState.resolvedBannerTimer) {
      clearTimeout(appState.resolvedBannerTimer);
      appState.resolvedBannerTimer = null;
    }

    bar.classList.add('visible', lvl === 'CRITICAL' ? 'critical' : 'warning');
    beacon.classList.add(lvl === 'CRITICAL' ? 'critical' : 'warning');
    if (labelEl) labelEl.textContent = 'Threat location';

    const displayLocs = [...new Set([...locs, ...gatesBlocked])];
    zonesEl.textContent = displayLocs.length
      ? `${displayLocs.join(', ')} — avoid area`
      : 'Caution or gate override active';
    actEl.textContent = lvl === 'CRITICAL'
      ? 'Follow green arrows away from the threat'
      : 'Use alternate open corridors and gates';
    return;
  }

  // Detect transition from active threat/warning back to normal on any screen
  if (prev === 'CRITICAL' || prev === 'WARNING') {
    if (Date.now() >= appState.resolvedBannerUntil) {
      showResolvedThreatBanner(6000);
    }
  }
  appState.prevGlobalStatus = 'NORMAL';

  // Show apprehended / secured notice briefly, then hide bar completely
  if (Date.now() < appState.resolvedBannerUntil) {
    bar.classList.add('visible', 'resolved');
    if (labelEl) labelEl.textContent = 'Threat apprehended';
    zonesEl.textContent = 'Campus secured — all zones clear';
    actEl.textContent = 'Returning to normal view';
  }
}

function clearFloorLocation() {
  appState.locBldg = '';
  appState.locFloor = '';
  appState.locRoom = '';
  const bSel = document.getElementById('loc-bldg');
  const fSel = document.getElementById('loc-floor');
  const rSel = document.getElementById('loc-room');
  if (bSel) bSel.value = '';
  if (fSel) fSel.innerHTML = '<option value="">Floor</option>';
  if (rSel) rSel.innerHTML = '<option value="">All rooms</option>';
  switchMapView('campus');
  updateOccupantGuidance();
}

function updateOccupantGuidance() {
  const box = document.getElementById('occupant-guidance-card');
  if (!box) return;
  const { locBldg, locFloor, locRoom, snapshot } = appState;
  if (!locBldg || !snapshot?.routes) {
    box.style.display = 'none';
    return;
  }

  let targets = Object.entries(snapshot.routes).filter(([rm]) => {
    if (locRoom) return rm === locRoom;
    if (locFloor) return rm.startsWith(`${locBldg}-F${locFloor}-`);
    return rm.startsWith(`${locBldg}-`);
  });
  if (!targets.length) {
    box.style.display = 'none';
    return;
  }

  const safe = targets.filter(([_, r]) => r.status === 'MODELED_ROUTE_AVAILABLE');
  const hold = targets.filter(([_, r]) => r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE');
  const crit = targets.filter(([_, r]) => r.status === 'NO_CONFIRMED_ROUTE');
  const unavail = targets.filter(([_, r]) => r.status === 'FACILITY_UNAVAILABLE');
  const labelLoc = locRoom || (locFloor ? `${locBldg} Floor ${locFloor}` : `${locBldg} Building`);

  let cls = '';
  let title = '';
  let detail = '';

  if (crit.length > 0) {
    cls = 'critical';
    title = `${labelLoc}: danger, do not enter`;
    detail = `${crit.length} room(s) affected. Stay sheltered or follow responder instructions.`;
  } else if (hold.length > 0 && safe.length === 0) {
    cls = 'warning';
    title = `${labelLoc}: hold in place`;
    detail = hold[0][1].reason || 'Stairway or corridor blocked. Wait for staff guidance.';
  } else if (unavail.length === targets.length) {
    cls = 'unavail';
    title = `${labelLoc}: closed for maintenance`;
    detail = 'Marked out of service by school personnel.';
  } else {
    cls = '';
    const gates = [...new Set(safe.map(([_, r]) => r.gate).filter(Boolean))].join(' or ');
    const doors = locRoom && safe[0] ? ` via ${safe[0][1].door_label}` : '';
    const stairSet = new Set();
    safe.forEach(([_, r]) => (r.route || []).forEach(n => {
      if (n.includes('STAIR-L')) stairSet.add('Left Stair');
      if (n.includes('STAIR-R')) stairSet.add('Right Stair');
    }));
    const stairsTxt = stairSet.size ? ` (${[...stairSet].join(' / ')})` : '';
    title = `${labelLoc}: safe exit available`;
    detail = `Follow green arrows${doors}${stairsTxt} toward ${gates || 'nearest open exit gate'}.${unavail.length ? ` (${unavail.length} closed room(s) marked Gray X)` : ''}`;
  }

  box.style.display = 'flex';
  box.className = `occupant-guidance-card ${cls}`;
  box.innerHTML = `
    <div>
      <div class="og-title">${title}</div>
      <div class="og-detail">${detail}</div>
    </div>
    <span class="badge ${cls === '' ? 'safe' : cls}">${safe.length}/${targets.length} safe</span>
  `;
}

// ── Authentication & RBAC Session Controllers ──────────────
async function checkAuthSession() {
  if (!appState.token) {
    appState.user = null;
    applyAuthUI();
    return;
  }
  try {
    const res = await fetch(API + '/api/auth/me', { headers: authHeaders() });
    const data = await res.json();
    if (data?.authenticated && data.user) {
      appState.user = data.user;
    } else {
      appState.user = null;
      appState.token = null;
      localStorage.removeItem('sentinel_token');
    }
  } catch {
    appState.user = null;
  }
  applyAuthUI();
}

function applyAuthUI() {
  const role = appState.user?.role || 'public';
  const isMainIt = Boolean(appState.user?.is_main_it);
  document.body.setAttribute('data-auth', role);
  setText(
    'brand-mode-tag',
    appState.user ? (role === 'IT_TECHNICIAN' ? (isMainIt ? 'Main IT admin' : 'IT admin') : 'Personnel') : 'Evacuation map'
  );

  if (appState.user) {
    setText('user-role-badge', role === 'IT_TECHNICIAN' ? (isMainIt ? 'Main IT' : 'IT tech') : 'Personnel');
    setText('user-display-name', appState.user.full_name || appState.user.username);
    appState.locBldg = '';
    appState.locFloor = '';
    appState.locRoom = '';
    if (role !== 'IT_TECHNICIAN' && appState.activeTab === 'hardware') {
      switchTab('map');
    }
  } else {
    // Public view always remains strictly on Map & Blueprints
    if (appState.activeTab !== 'map') {
      switchTab('map');
    }
  }
}

function openAuthModal(tab = 'login') {
  const m = document.getElementById('auth-modal');
  if (!m) return;
  switchAuthTab(tab);
  const le = document.getElementById('auth-login-error');
  const re = document.getElementById('auth-reg-error');
  if (le) le.style.display = 'none';
  if (re) re.style.display = 'none';
  m.style.display = 'flex';
}

function closeAuthModal() {
  const m = document.getElementById('auth-modal');
  if (m) m.style.display = 'none';
}

function switchAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('auth-tab-login')?.classList.toggle('active', isLogin);
  document.getElementById('auth-tab-register')?.classList.toggle('active', !isLogin);
  const pl = document.getElementById('auth-panel-login');
  const pr = document.getElementById('auth-panel-register');
  if (pl) pl.style.display = isLogin ? 'flex' : 'none';
  if (pr) pr.style.display = isLogin ? 'none' : 'flex';
}

function fillDemoCreds(u, p) {
  const uEl = document.getElementById('login-username');
  const pEl = document.getElementById('login-password');
  if (uEl) uEl.value = u;
  if (pEl) pEl.value = p;
}

async function submitLogin() {
  const username = document.getElementById('login-username')?.value.trim() || '';
  const password = document.getElementById('login-password')?.value || '';
  const errEl = document.getElementById('auth-login-error');
  if (errEl) errEl.style.display = 'none';

  try {
    const res = await fetch(API + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) {
        errEl.textContent = data.detail || 'Invalid username or password.';
        errEl.style.display = 'block';
      }
      return;
    }
    appState.token = data.token;
    appState.user = data.user;
    localStorage.setItem('sentinel_token', data.token);
    applyAuthUI();
    closeAuthModal();
    toast(`Signed in as ${data.user.full_name} (${data.user.role})`, 'success');
    await loadInitialMeta();
    await refresh();
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.style.display = 'block';
    }
  }
}

async function submitRegister() {
  const full_name = document.getElementById('reg-fullname')?.value.trim() || '';
  const username  = document.getElementById('reg-username')?.value.trim() || '';
  const role      = document.getElementById('reg-role')?.value || 'PERSONNEL';
  const auth_code = document.getElementById('reg-authcode')?.value.trim() || '';
  const password  = document.getElementById('reg-password')?.value || '';
  const password2 = document.getElementById('reg-password2')?.value || '';
  const errEl     = document.getElementById('auth-reg-error');
  if (errEl) errEl.style.display = 'none';

  if (password !== password2) {
    if (errEl) {
      errEl.textContent = 'Passwords do not match.';
      errEl.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch(API + '/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name, username, role, auth_code, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) {
        errEl.textContent = data.detail || 'Account registration failed.';
        errEl.style.display = 'block';
      }
      return;
    }
    appState.token = data.token;
    appState.user = data.user;
    localStorage.setItem('sentinel_token', data.token);
    applyAuthUI();
    closeAuthModal();
    toast(`Account created! Signed in as ${data.user.full_name} (${data.user.role})`, 'success');
    await loadInitialMeta();
    await refresh();
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.style.display = 'block';
    }
  }
}

async function logoutUser() {
  await fetch(API + '/api/auth/logout', { method: 'POST', headers: authHeaders() }).catch(() => {});
  appState.token = null;
  appState.user = null;
  localStorage.removeItem('sentinel_token');
  closeAccountModal();
  closeDeleteAccountModal();
  const rmSel = document.getElementById('sb-room-select');
  if (rmSel) rmSel.value = '';
  const ins = document.getElementById('inspector-result');
  if (ins) ins.style.display = 'none';
  applyAuthUI();
  toast('Signed out. Switched to public map view.', 'info');
  await refresh();
}

// ── Account Security, Password Change & Activity Logs ──────
let _acctLogCategory = 'all';
let _pendingDeleteTarget = null;

function _escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _formatRoleLabel(role, isMainIt = false) {
  if (role === 'IT_TECHNICIAN') return isMainIt ? 'Main IT Tech' : 'IT Tech';
  return 'Personnel';
}

function _formatActivityBadge(action) {
  switch (action) {
    case 'USER_LOGIN':      return '<span class="badge safe">Sign in</span>';
    case 'USER_LOGOUT':     return '<span class="badge" style="background:var(--c-pill-bg);color:var(--c-slate);border-color:var(--c-border-str);">Sign out</span>';
    case 'PASSWORD_CHANGE': return '<span class="badge warning">Password changed</span>';
    case 'USER_REGISTER':   return '<span class="badge safe">Account created</span>';
    case 'USER_DELETE':     return '<span class="badge critical">Account deleted</span>';
    default:                return `<span class="badge">${_escHtml(action)}</span>`;
  }
}

function _formatActivityDetails(log) {
  const d = log.details_obj || {};
  if (log.action === 'USER_DELETE') {
    const delName = d.deleted_full_name ? `${d.deleted_full_name} (@${d.deleted_username})` : `@${d.deleted_username || 'unknown'}`;
    const delRole = _formatRoleLabel(d.deleted_role, false);
    return `Deleted ${delName} · ${delRole}`;
  }
  if (log.action === 'PASSWORD_CHANGE') {
    return `${_formatRoleLabel(d.role)} updated password`;
  }
  if (log.action === 'USER_LOGIN') {
    return `${_formatRoleLabel(d.role)} signed in`;
  }
  if (log.action === 'USER_LOGOUT') {
    return `${_formatRoleLabel(d.role)} signed out`;
  }
  if (log.action === 'USER_REGISTER') {
    return `Registered as ${_formatRoleLabel(d.role)}`;
  }
  return _escHtml(log.details || '—');
}

function populateAccountProfileCard() {
  if (!appState.user) return;
  setText('acct-prof-name', appState.user.full_name || appState.user.username);
  setText('acct-prof-username', `@${appState.user.username}`);
  const roleBadge = document.getElementById('acct-prof-role');
  if (roleBadge) {
    roleBadge.textContent = _formatRoleLabel(appState.user.role, appState.user.is_main_it);
    roleBadge.className = appState.user.role === 'IT_TECHNICIAN'
      ? (appState.user.is_main_it ? 'badge critical' : 'badge warning')
      : 'badge safe';
  }
}

function closeAccountModal() {
  // Unified into the Accounts & logs tab; kept as no-op for clean logout compatibility
}

async function submitChangePassword() {
  const current_password = document.getElementById('cp-current')?.value || '';
  const new_password     = document.getElementById('cp-new')?.value || '';
  const confirm_password = document.getElementById('cp-confirm')?.value || '';
  const errEl = document.getElementById('cp-error');
  const okEl  = document.getElementById('cp-success');
  if (errEl) errEl.style.display = 'none';
  if (okEl) okEl.style.display = 'none';

  if (!current_password || !new_password) {
    if (errEl) { errEl.textContent = 'Please fill in your current and new password.'; errEl.style.display = 'block'; }
    return;
  }
  if (new_password.length < 6) {
    if (errEl) { errEl.textContent = 'New password must be at least 6 characters.'; errEl.style.display = 'block'; }
    return;
  }
  if (new_password !== confirm_password) {
    if (errEl) { errEl.textContent = 'New passwords do not match.'; errEl.style.display = 'block'; }
    return;
  }

  try {
    const res = await fetch(API + '/api/auth/change-password', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ current_password, new_password }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) { errEl.textContent = data.detail || 'Could not update password.'; errEl.style.display = 'block'; }
      return;
    }
    ['cp-current', 'cp-new', 'cp-confirm'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    if (okEl) { okEl.textContent = 'Password updated and logged in your activity history.'; okEl.style.display = 'block'; }
    toast('Password updated successfully.', 'success');
    await loadAccountLogsForTab();
  } catch (e) {
    if (errEl) { errEl.textContent = e.message; errEl.style.display = 'block'; }
  }
}

// ── Unified Accounts & Activity Logs Tab ───────────────────
async function filterAccountLogs(category) {
  _acctLogCategory = category;
  document.querySelectorAll('#tab-accounts .filter-pill').forEach(b => b.classList.remove('active'));
  document.getElementById(`acclog-f-${category}`)?.classList.add('active');
  await loadAccountLogsForTab();
}

async function loadAccountsTabData() {
  if (!appState.user) return;
  populateAccountProfileCard();
  const tasks = [loadAccountLogsForTab()];
  if (appState.user.role === 'IT_TECHNICIAN') {
    tasks.push(loadRegisteredUsersForIT());
  }
  await Promise.all(tasks);
}

async function loadRegisteredUsersForIT() {
  const tbody = document.getElementById('accounts-table-body');
  if (!tbody) return;
  try {
    const res = await fetch(API + '/api/auth/users', { headers: authHeaders() });
    const data = await res.json();
    const users = data.users || [];
    setText('accounts-count-badge', `${users.length} account${users.length === 1 ? '' : 's'}`);

    const me = appState.user || {};
    const amMainIt = Boolean(me.is_main_it);

    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No registered accounts found.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => {
      const isMainTarget = Boolean(u.is_main_it);
      const isSelf = u.user_id === me.user_id;
      const isItTarget = u.role === 'IT_TECHNICIAN';

      let actionHtml = '';
      if (isMainTarget) {
        actionHtml = '<span class="acct-protected-tag">Protected</span>';
      } else if (isSelf) {
        actionHtml = '<span class="acct-protected-tag">Current session</span>';
      } else if (isItTarget && !amMainIt) {
        actionHtml = '<span class="acct-protected-tag">Main IT only</span>';
      } else {
        const safeUser = encodeURIComponent(JSON.stringify({
          user_id: u.user_id,
          username: u.username,
          full_name: u.full_name,
          role: u.role,
        }));
        actionHtml = `<button class="btn btn-sm btn-danger" onclick="openDeleteAccountModal('${safeUser}')">Delete</button>`;
      }

      const roleBadge = isMainTarget
        ? '<span class="badge critical">Main IT</span>'
        : isItTarget
          ? '<span class="badge warning">IT Tech</span>'
          : '<span class="badge safe">Personnel</span>';

      return `
        <tr>
          <td style="font-family:'Atkinson Hyperlegible Mono',monospace; font-weight:600;">${_escHtml(u.username)}</td>
          <td>${_escHtml(u.full_name)}</td>
          <td>${roleBadge}</td>
          <td style="font-family:'Atkinson Hyperlegible Mono',monospace; font-size:12px;">${_escHtml(u.created_at || '—')}</td>
          <td style="text-align:right;">${actionHtml}</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Unable to load accounts.</td></tr>';
  }
}

async function loadAccountLogsForTab() {
  const tbody = document.getElementById('accounts-logs-body');
  if (!tbody || !appState.user) return;
  const isIt = appState.user.role === 'IT_TECHNICIAN';
  setText('accounts-log-title', isIt ? 'Personnel & technician activity logs' : 'My activity logs');
  setText(
    'accounts-log-scope',
    isIt
      ? (appState.user.is_main_it ? 'Main IT · All staff & history' : 'IT Tech · All staff')
      : 'Login, logout & password history'
  );
  try {
    const url = isIt
      ? `${API}/api/auth/activity-logs?scope=all&category=${encodeURIComponent(_acctLogCategory)}&limit=120`
      : `${API}/api/auth/activity-logs?scope=mine&limit=60`;
    const res = await fetch(url, { headers: authHeaders() });
    const data = await res.json();
    const logs = data.logs || [];

    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No matching activity logs yet.</td></tr>';
      return;
    }

    tbody.innerHTML = logs.map(l => `
      <tr>
        <td style="font-family:'Atkinson Hyperlegible Mono',monospace; font-size:12px; white-space:nowrap;">${_escHtml(l.created_at)}</td>
        <td style="font-family:'Atkinson Hyperlegible Mono',monospace; font-weight:600;">${_escHtml(l.actor)}</td>
        <td>${_formatActivityBadge(l.action)}</td>
        <td>${_escHtml(_formatActivityDetails(l))}</td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Unable to load activity logs.</td></tr>';
  }
}

// ── Two-Step Password-Confirmed Account Deletion Modal ─────
function openDeleteAccountModal(encodedTarget) {
  try {
    _pendingDeleteTarget = JSON.parse(decodeURIComponent(encodedTarget));
  } catch {
    return;
  }
  setText('del-target-name', _pendingDeleteTarget.full_name || _pendingDeleteTarget.username);
  setText('del-target-username', `@${_pendingDeleteTarget.username}`);
  setText('del-target-username-2', `@${_pendingDeleteTarget.username}`);
  setText('del-target-role', _formatRoleLabel(_pendingDeleteTarget.role, false));

  const s1 = document.getElementById('del-step-1');
  const s2 = document.getElementById('del-step-2');
  const pw = document.getElementById('del-confirm-password');
  const err = document.getElementById('del-error');
  if (s1) s1.style.display = 'flex';
  if (s2) s2.style.display = 'none';
  if (pw) pw.value = '';
  if (err) err.style.display = 'none';

  const m = document.getElementById('delete-account-modal');
  if (m) m.style.display = 'flex';
}

function proceedDeleteStep2() {
  const s1 = document.getElementById('del-step-1');
  const s2 = document.getElementById('del-step-2');
  const err = document.getElementById('del-error');
  if (s1) s1.style.display = 'none';
  if (s2) s2.style.display = 'flex';
  if (err) err.style.display = 'none';
  document.getElementById('del-confirm-password')?.focus();
}

function backToDeleteStep1() {
  const s1 = document.getElementById('del-step-1');
  const s2 = document.getElementById('del-step-2');
  const err = document.getElementById('del-error');
  if (s1) s1.style.display = 'flex';
  if (s2) s2.style.display = 'none';
  if (err) err.style.display = 'none';
}

function closeDeleteAccountModal() {
  _pendingDeleteTarget = null;
  const m = document.getElementById('delete-account-modal');
  if (m) m.style.display = 'none';
}

async function submitDeleteAccount() {
  if (!_pendingDeleteTarget) return;
  const password = document.getElementById('del-confirm-password')?.value || '';
  const errEl = document.getElementById('del-error');
  if (errEl) errEl.style.display = 'none';

  if (!password) {
    if (errEl) { errEl.textContent = 'Please enter your IT Technician password to confirm.'; errEl.style.display = 'block'; }
    return;
  }

  try {
    const res = await fetch(`${API}/api/auth/users/${_pendingDeleteTarget.user_id}/delete`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (errEl) { errEl.textContent = data.detail || 'Account deletion failed.'; errEl.style.display = 'block'; }
      return;
    }
    const deletedName = _pendingDeleteTarget.username;
    closeDeleteAccountModal();
    toast(`Deleted account @${deletedName} and recorded in activity logs.`, 'success');
    await loadAccountsTabData();
  } catch (e) {
    if (errEl) { errEl.textContent = e.message; errEl.style.display = 'block'; }
  }
}
