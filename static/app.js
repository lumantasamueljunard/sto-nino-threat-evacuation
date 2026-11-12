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
  unavailableGates: [],
  manualBlocks: [],
  activeTab: 'map',
  mapView: 'campus',
  camFilter: 'outside',
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
  await loadInitialMeta();
  await refresh();
  setInterval(refresh, 4000);
});

function toggleSidebar() {
  const sb = document.getElementById('app-sidebar');
  if (sb) sb.classList.toggle('collapsed');
}

// ── API Fetch Helper ───────────────────────────────────────
async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API + path, opts);
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

// ── Initial Metadata Load ──────────────────────────────────
async function loadInitialMeta() {
  const [roomsData, devData, scenData] = await Promise.all([
    apiFetch('/api/rooms'),
    apiFetch('/api/devices'),
    apiFetch('/api/scenarios'),
  ]);

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
  const [status, snapshot, detData] = await Promise.all([
    apiFetch('/api/status'),
    apiFetch('/api/snapshot'),
    apiFetch('/api/detections'),
  ]);

  if (status) {
    appState.status = status;
    appState.unavailableGates = status.unavailable_gates || [];
    appState.manualBlocks = status.manual_blocks || [];
  }
  if (snapshot) appState.snapshot = snapshot;
  if (detData) appState.detections = detData.detections || [];

  renderAll();
}

// ── Populate Sidebar Dropdowns ─────────────────────────────
function populateScenarioDropdown(scenarios) {
  const sel = document.getElementById('sb-scenario-select');
  if (!sel) return;
  const labels = {
    'all_clear': 'Normal — All Clear',
    'Gate-W Threat (Reroute to Gate-NE)': 'Drill: Gate-W Threat -> Reroute NE',
    'Gate-NE Threat (Reroute to Gate-W)': 'Drill: Gate-NE Threat -> Reroute W',
    'TPB Floor 1 Indoor Threat': 'Drill: TPB Floor 1 Indoor Threat',
    'AB Floor 2 Indoor Threat': 'Drill: AB Floor 2 Indoor Threat',
    'Corridor C2 Caution Zone': 'Drill: Corridor Caution Zone',
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

  let html = '<option value="">Select classroom (36 rooms)…</option>';
  let blockHtml = '<option value="">+ Block Classroom…</option>';

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
    let html = '<option value="">+ Block Corridor…</option>';
    bldgs.forEach(b => {
      let opts = '';
      for (let f = 1; f <= b.floors; f++) {
        for (let c = 0; c <= b.rpf; c++) {
          const id = `${b.code}-F${f}-C${c}`;
          opts += `<option value="${id}">${id} (Floor ${f} Seg ${c})</option>`;
        }
      }
      html += `<optgroup label="${b.name}">${opts}</optgroup>`;
    });
    corrSel.innerHTML = html;
  }

  if (stairSel) {
    let html = '<option value="">+ Block Stairwell…</option>';
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
  if (selectedRoom) updateRoomInspectorCard(selectedRoom);

  if (appState.mapView === 'campus') {
    renderCampusMap(snapshot, status);
  } else {
    renderBuildingFloors(appState.mapView, snapshot);
  }

  updateRoomsTable(snapshot);
  updateEventLog(snapshot);
  renderCamGrid();
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

  if (lvl === 'CRITICAL') {
    pill.classList.add('critical');
    beacon.classList.add('critical');
    text.textContent = 'EMERGENCY · EVACUATE';
    banner.className = 'emergency-banner visible';
    ebBeacon.className = 'status-beacon critical';
    ebTitle.textContent = 'CRITICAL THREAT ACTIVE';
    ebSub.textContent = `${snapshot.counts?.['MODELED_ROUTE_AVAILABLE'] ?? 0} rooms evacuating · ${snapshot.counts?.['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? 0} holding · ${snapshot.counts?.['NO_CONFIRMED_ROUTE'] ?? 0} compromised.`;
  } else if (lvl === 'WARNING') {
    pill.classList.add('warning');
    beacon.classList.add('warning');
    text.textContent = 'CAUTION · REROUTING';
    banner.className = 'emergency-banner warning visible';
    ebBeacon.className = 'status-beacon warning';
    ebTitle.textContent = 'ELEVATED CAUTION / OVERRIDE ACTIVE';
    ebSub.textContent = 'Dynamic rerouting engaged around restricted zones or gates.';
  } else {
    text.textContent = 'ALL CLEAR · SECURE';
    banner.className = 'emergency-banner';
  }
}

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

  const tagsEl = document.getElementById('block-tags');
  const clearBtn = document.getElementById('btn-clear-blocks');
  if (tagsEl) {
    tagsEl.innerHTML = appState.manualBlocks.map(node => `
      <span class="tag-chip">
        ${node}
        <button onclick="removeBlock('${node}')" title="Unblock">&times;</button>
      </span>
    `).join('');
  }
  if (clearBtn) {
    clearBtn.style.display = appState.manualBlocks.length ? 'inline-block' : 'none';
  }
}

// ── Interactive Control Actions ────────────────────────────
function switchTab(tab) {
  appState.activeTab = tab;
  document.querySelectorAll('.nav-pill').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-btn-${tab}`)?.classList.add('active');

  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`tab-${tab}`)?.classList.add('active');
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

  card.className = `inspector-card ${isSafe ? '' : isHold ? 'warning' : 'critical'}`;
  setText('ins-status-label', isSafe ? 'SAFE EVACUATION ROUTE' : isHold ? 'HOLD IN PLACE (ISOLATED)' : 'THREAT AREA / BLOCKED');
  setText('ins-gate', r.gate || 'NONE');
  setText('ins-door', r.door_label || 'NONE');
  setText('ins-steps', r.route?.length ? `${r.route.length} graph nodes (Cost ${r.cost})` : (r.reason || 'No route available'));
}

async function toggleGate(gateId) {
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

async function addBlock(selectEl) {
  const node = selectEl.value;
  selectEl.value = '';
  if (!node || appState.manualBlocks.includes(node)) return;

  const next = [...appState.manualBlocks, node];
  await apiFetch('/api/blocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manual_blocks: next }),
  });
  toast(`Blocked node: ${node}`, 'warning');
  await refresh();
}

async function removeBlock(node) {
  const next = appState.manualBlocks.filter(n => n !== node);
  await apiFetch('/api/blocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manual_blocks: next }),
  });
  await refresh();
}

async function clearBlocks() {
  await apiFetch('/api/blocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manual_blocks: [] }),
  });
  toast('Manual overrides cleared', 'info');
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
    'GATE-W':  { x: 195, y: 405, label: 'GATE-W · West Exit' },
    'GATE-NE': { x: 778, y: 146, label: 'GATE-NE · Northeast Exit' },
  };

  const bldConfigs = [
    {
      code: 'TPB', title: 'TECH PRO (TPB)',
      cx: 485, cy: 235, w: 185, h: 66,
      paths: {
        'GATE-W':  [[390, 250], [285, 315], [195, 405]],
        'GATE-NE': [[580, 225], [685, 185], [778, 146]],
      }
    },
    {
      code: 'AB', title: 'ACADEMIC (AB)',
      cx: 745, cy: 430, w: 185, h: 66,
      paths: {
        'GATE-W':  [[650, 435], [460, 425], [195, 405]],
        'GATE-NE': [[760, 395], [772, 275], [778, 146]],
      }
    },
    {
      code: 'LB', title: 'LABORATORY (LB)',
      cx: 415, cy: 525, w: 185, h: 66,
      paths: {
        'GATE-W':  [[322, 515], [248, 462], [195, 405]],
        'GATE-NE': [[508, 510], [645, 345], [778, 146]],
      }
    }
  ];

  let pathsSvg = '';
  let bldBoxesSvg = '';

  bldConfigs.forEach(b => {
    const bRoutes = Object.entries(snapshot.routes || {}).filter(([rm]) => rm.startsWith(`${b.code}-`));
    const safeRoutes = bRoutes.filter(([_, r]) => r.status === 'MODELED_ROUTE_AVAILABLE');
    const holdRoutes = bRoutes.filter(([_, r]) => r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE');
    const critRoutes = bRoutes.filter(([_, r]) => r.status === 'NO_CONFIRMED_ROUTE');

    let bCol = '#059669';
    let bStatusText = `${bRoutes.length}/${bRoutes.length} CLEAR`;
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
    }

    // Draw Evacuation Flow Arrow when Emergency/Warning or Gate Override is active
    if (isEmergency && safeRoutes.length > 0) {
      const gateCounts = {};
      safeRoutes.forEach(([_, r]) => {
        if (r.gate) gateCounts[r.gate] = (gateCounts[r.gate] || 0) + 1;
      });
      const targetGate = Object.entries(gateCounts).sort((a, b) => b[1] - a[1])[0]?.[0];
      if (targetGate && b.paths[targetGate]) {
        const dStr = shortenPathEnd(b.paths[targetGate], 30);
        pathsSvg += `
          <path d="${dStr}" fill="none" stroke="#047857" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" opacity="0.28"/>
          <path d="${dStr}" fill="none" stroke="#10b981" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"
            stroke-dasharray="12,8" marker-end="url(#campus-arr-safe)">
            <animate attributeName="stroke-dashoffset" from="40" to="0" dur="0.9s" repeatCount="indefinite"/>
          </path>
        `;
      }
    }

    const bx = b.cx - b.w / 2;
    const by = b.cy - b.h / 2;
    bldBoxesSvg += `
      <g style="cursor:pointer; pointer-events:all;" onclick="switchMapView('${b.code.toLowerCase()}')">
        <rect x="${bx}" y="${by}" width="${b.w}" height="${b.h}" rx="12"
          fill="rgba(15, 23, 42, 0.92)" stroke="${bCol}" stroke-width="3"/>
        <text x="${b.cx}" y="${by + 26}" text-anchor="middle" fill="#ffffff"
          font-size="13" font-weight="800" font-family="'Inter', sans-serif">${b.title}</text>
        <rect x="${b.cx - 68}" y="${by + 35}" width="136" height="21" rx="10" fill="${bCol}"/>
        <text x="${b.cx}" y="${by + 49}" text-anchor="middle" fill="#ffffff"
          font-size="10.5" font-weight="800" font-family="'JetBrains Mono', monospace">${bStatusText}</text>
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
          font-size="10.5" font-weight="800" font-family="'JetBrains Mono', monospace">${gId === 'GATE-W' ? 'W' : 'NE'}</text>
        <rect x="${g.x - 66}" y="${g.y + 27}" width="132" height="22" rx="11"
          fill="#0f172a" stroke="${gCol}" stroke-width="2"/>
        <text x="${g.x}" y="${g.y + 42}" text-anchor="middle" fill="#ffffff"
          font-size="10.5" font-weight="800" font-family="'JetBrains Mono', monospace">${gTag}</text>
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

// ── Render Building Floor Blueprints (Sharp Non-Cut Arrows) ──
function renderBuildingFloors(bKey, snapshot) {
  const bMap = {
    tpb: { code: 'TPB', num: 1, name: 'Tech Pro Building', floors: 4, rpf: 5, img: '/static/img/b1_floor.png', imgH: 455 },
    ab:  { code: 'AB',  num: 2, name: 'Academic Building', floors: 4, rpf: 3, img: '/static/img/b2_floor.png', imgH: 455 },
    lb:  { code: 'LB',  num: 3, name: 'Laboratory Building', floors: 2, rpf: 2, img: '/static/img/b3_floor.png', imgH: 400 },
  };
  const cfg = bMap[bKey] || bMap.tpb;
  const { code: bCode, num: bNum, name: bName, floors, rpf: roomsPerFloor, img: bImg, imgH } = cfg;

  const roomBoxes = {
    TPB: {
      1: { x: 148, y: 58, w: 148, h: 242, dlX: 185, drX: 262, doorY: 298, corrY: 356, stairLX: 128, stairRX: 882 },
      2: { x: 298, y: 58, w: 138, h: 242, dlX: 332, drX: 402, doorY: 298, corrY: 356, stairLX: 128, stairRX: 882 },
      3: { x: 438, y: 58, w: 138, h: 242, dlX: 472, drX: 542, doorY: 298, corrY: 356, stairLX: 128, stairRX: 882 },
      4: { x: 578, y: 58, w: 132, h: 242, dlX: 610, drX: 678, doorY: 298, corrY: 356, stairLX: 128, stairRX: 882 },
      5: { x: 712, y: 58, w: 146, h: 242, dlX: 748, drX: 822, doorY: 298, corrY: 356, stairLX: 128, stairRX: 882 },
    },
    AB: {
      1: { x: 150, y: 58, w: 242, h: 242, dlX: 210, drX: 330, doorY: 298, corrY: 360, stairLX: 128, stairRX: 882 },
      2: { x: 394, y: 58, w: 224, h: 242, dlX: 450, drX: 560, doorY: 298, corrY: 360, stairLX: 128, stairRX: 882 },
      3: { x: 620, y: 58, w: 240, h: 242, dlX: 680, drX: 795, doorY: 298, corrY: 360, stairLX: 128, stairRX: 882 },
    },
    LB: {
      1: { x: 165, y: 48, w: 350, h: 212, dlX: 250, drX: 425, doorY: 258, corrY: 312, stairLX: 136, stairRX: 886 },
      2: { x: 518, y: 48, w: 342, h: 212, dlX: 600, drX: 775, doorY: 258, corrY: 312, stairLX: 136, stairRX: 886 },
    }
  };

  setText('bld-view-title', `${bName} (${bCode})`);
  setText('bld-view-sub', `${floors} Floors · ${floors * roomsPerFloor} Classrooms`);

  const grid = document.getElementById('floor-grid');
  if (!grid) return;

  let anyBlocked = false;
  let anyCritical = false;
  const selectedRoomId = document.getElementById('sb-room-select')?.value || '';
  const isEmergency = snapshot?.global_status === 'CRITICAL' || snapshot?.global_status === 'WARNING';

  grid.innerHTML = '';
  for (let f = 1; f <= floors; f++) {
    const pCode = `${bCode}-F${f}`;
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
    let arrows = '';
    let floorSafe = true;
    let floorCritical = false;

    for (let r = 1; r <= roomsPerFloor; r++) {
      const rmId = `${pCode}-R${r}`;
      const rm = snapshot?.routes?.[rmId];
      const box = roomBoxes[bCode]?.[r];
      if (!box) continue;

      const rmStatus = rm?.status || 'MODELED_ROUTE_AVAILABLE';
      const isSelected = rmId === selectedRoomId;

      if (isEmergency || isSelected) {
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
          <g id="box-${rmId}">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="5"
              fill="${fillCol}" stroke="${strokeCol}" stroke-width="${isSelected ? 3.5 : 2}"/>
            <rect x="${box.x + 8}" y="${box.y + 8}" width="72" height="20" rx="4" fill="#0f172a" opacity="0.92"/>
            <text x="${box.x + 44}" y="${box.y + 22}" text-anchor="middle" fill="${tagCol}"
              font-size="10" font-weight="800" font-family="'JetBrains Mono', monospace">${tagText}</text>
          </g>
        `;

        if (rmStatus === 'MODELED_ROUTE_AVAILABLE') {
          // Determine actual stairwell from route nodes (fixes fallback direction bug)
          const useLeft = rm?.route?.some(n => n.includes('STAIR-L'))
            ? true
            : rm?.route?.some(n => n.includes('STAIR-R'))
              ? false
              : (r <= roomsPerFloor / 2);

          const targetX = useLeft ? box.stairLX : box.stairRX;
          const doorX = rm?.door?.endsWith('-DL') ? box.dlX : rm?.door?.endsWith('-DR') ? box.drX : (useLeft ? box.dlX : box.drX);
          const startX = box.x + (box.w / 2);
          const startY = box.y + (box.h * 0.52);
          // Slight corridor lane offset so arrows from adjacent rooms never collide or clip
          const laneOffset = Math.round((r - (roomsPerFloor + 1) / 2) * 3.5);
          const laneY = box.corrY + laneOffset;

          arrows += `
            <path d="M ${startX} ${startY} L ${doorX} ${box.doorY} L ${doorX} ${laneY} L ${targetX} ${laneY}"
              fill="none" stroke="#064e3b" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.45"/>
            <path d="M ${startX} ${startY} L ${doorX} ${box.doorY} L ${doorX} ${laneY} L ${targetX} ${laneY}"
              fill="none" stroke="#10b981" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"
              stroke-dasharray="10,6" marker-end="url(#arr-f-${bCode}-${f})">
              <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.85s" repeatCount="indefinite"/>
            </path>
          `;
        }
      } else {
        roomOverlays += `
          <g id="box-${rmId}">
            <rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" rx="4"
              fill="rgba(255, 255, 255, 0.03)" stroke="rgba(148, 163, 184, 0.25)" stroke-width="1"/>
            <rect x="${box.x + 8}" y="${box.y + 8}" width="46" height="18" rx="4" fill="#0f172a" opacity="0.8"/>
            <text x="${box.x + 31}" y="${box.y + 21}" text-anchor="middle" fill="#cbd5e1"
              font-size="10" font-weight="700" font-family="'JetBrains Mono', monospace">R${r}</text>
          </g>
        `;
      }
    }

    if (floorCritical) anyCritical = true;
    if (!floorSafe) anyBlocked = true;

    const badgeClass = floorCritical ? 'critical' : !floorSafe ? 'warning' : 'safe';
    const badgeText  = !isEmergency ? 'Clear' : floorCritical ? 'Threat' : !floorSafe ? 'Hold' : 'Evacuating';

    const card = document.createElement('div');
    card.className = 'floor-card';
    card.innerHTML = `
      <div class="floor-card-header">
        <div>
          <span class="floor-card-title">Floor ${f}</span>
          <span class="floor-card-code"> &middot; ${pCode}</span>
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
          ${arrows}
          <g>
            <rect x="${camLeftX}" y="${camLeftY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <circle cx="${camLeftX + 14}" cy="${camLeftY + badgeH / 2}" r="5" fill="${colLeft}"/>
            <text x="${camLeftX + 25}" y="${camLeftY + badgeH / 2 + 4}" fill="#ffffff" font-size="10.5" font-weight="700" font-family="'JetBrains Mono', monospace">${didLeft}</text>
          </g>
          <g>
            <rect x="${camRightX}" y="${camRightY}" width="${badgeW}" height="${badgeH}" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
            <circle cx="${camRightX + 14}" cy="${camRightY + badgeH / 2}" r="5" fill="${colRight}"/>
            <text x="${camRightX + 25}" y="${camRightY + badgeH / 2 + 4}" fill="#ffffff" font-size="10.5" font-weight="700" font-family="'JetBrains Mono', monospace">${didRight}</text>
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
  setText('m-safe',    counts['MODELED_ROUTE_AVAILABLE'] ?? '36');
  setText('m-hold',    counts['HOLD_FOR_AUTHORIZED_GUIDANCE'] ?? '0');
  setText('m-blocked', counts['NO_CONFIRMED_ROUTE'] ?? '0');
}

// ── Classroom Table & Event Log ────────────────────────────
function updateRoomsTable(snap) {
  const tbody = document.getElementById('rooms-table-body');
  if (!tbody) return;

  const routes = snap.routes || {};
  tbody.innerHTML = Object.entries(routes).map(([rm, r]) => {
    const isSafe = r.status === 'MODELED_ROUTE_AVAILABLE';
    const isHold = r.status === 'HOLD_FOR_AUTHORIZED_GUIDANCE';
    const rowClass = isSafe ? 'row-safe' : isHold ? 'row-hold' : 'row-threat';
    const statusClass = isSafe ? 'safe' : isHold ? 'warning' : 'critical';
    const statusLabel = isSafe ? 'Safe Egress' : isHold ? 'Hold in Place' : 'Threat / Blocked';

    return `<tr class="${rowClass}">
      <td><span class="room-code">${rm}</span></td>
      <td><span class="badge ${statusClass}"><span class="status-beacon ${statusClass === 'safe' ? '' : statusClass}" style="width:6px;height:6px;"></span>${statusLabel}</span></td>
      <td><span class="gate-code">${r.gate || '—'}</span></td>
      <td>${r.door_label || '—'}</td>
      <td>${r.route?.length ? r.route.length + ' nodes' : 'Blocked'}</td>
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
  if (!el) return;
  const events = snap.events || [];
  if (!events.length) {
    el.innerHTML = '<div class="empty-state">No active incidents recorded. Campus secure.</div>';
    return;
  }
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
          <div style="font-size:10.5px; font-weight:800; color:var(--c-navy); margin-bottom:4px; text-transform:uppercase;">3-Criteria AI Telemetry</div>
          <div class="cam-score-row"><span>Threat Index</span><span class="cam-score-val threat">${clf.index?.toFixed(1) ?? '—'} / 100</span></div>
          <div class="cam-score-row"><span>1. Object (&ge;60%)</span><span class="cam-score-val">${scores.object ?? clf.object ?? '—'}%</span></div>
          <div class="cam-score-row"><span>2. Pose Keypoints</span><span class="cam-score-val">${scores.pose ?? clf.pose ?? '—'}%</span></div>
          <div class="cam-score-row"><span>3. Acoustic RMS</span><span class="cam-score-val">${scores.acoustic ?? clf.acoustic ?? '—'}%</span></div>
          <div class="cam-score-row"><span>Gatekeeper</span><span class="cam-score-val ${clf.verified ? 'threat' : ''}">${clf.verified ? 'VERIFIED' : 'UNVERIFIED'}</span></div>
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
  const resBox = document.getElementById('modal-scan-result');

  if (!fileInput || !fileInput.files.length) {
    toast('Select a video file first', 'warning');
    return;
  }
  const file = fileInput.files[0];
  const targetDev = devSelect ? devSelect.value : 'TPB-CAM-OUT-L';

  resetCriteriaCards();
  if (progress) progress.style.display = 'block';
  if (statusTxt) statusTxt.textContent = `Fast-scanning ${file.name} on ${targetDev} (8-keyframe early-exit)…`;
  if (submitBtn) submitBtn.disabled = true;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('device_ids', targetDev);

  try {
    const res = await fetch(API + '/api/upload-video', {
      method: 'POST',
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
        resBox.style.display = 'block';
        resBox.className = `scan-result-box ${data.criteria_passed ? 'critical' : 'safe'}`;
        resBox.innerHTML = `
          <div style="font-weight:800; margin-bottom:2px;">
            ${data.criteria_passed ? `THREAT VERIFIED (${data.level})` : `ALL CLEAR — CRITERIA NOT MET (${data.level})`}
            &middot; <span style="font-family:'JetBrains Mono',monospace;">${Number(data.scan_ms || 0).toFixed(0)}ms</span>
            ${data.early_exit ? ' &middot; Early-Exit' : ''}
          </div>
          <div style="font-size:11px;">
            Object ${Number(data.object_score || 0).toFixed(0)}% &middot; Pose ${Number(data.pose_score || 0).toFixed(0)}% &middot; Acoustic ${Number(data.acoustic_score || 0).toFixed(0)}%
            (${data.frames_analyzed || 0} keyframes)
          </div>
        `;
      }

      await refresh();
      toast(
        data.criteria_passed
          ? `THREAT VERIFIED on ${targetDev} in ${Number(data.scan_ms || 0).toFixed(0)}ms! Evacuation routes active.`
          : `Scanned ${targetDev} in ${Number(data.scan_ms || 0).toFixed(0)}ms — Criteria not met.`,
        data.criteria_passed ? 'critical' : 'success'
      );
    } else {
      toast(`Scan error: ${data.detail || 'Inference failed'}`, 'error');
    }
  } catch (err) {
    toast(`Upload failed: ${err.message}`, 'error');
  } finally {
    if (progress) progress.style.display = 'none';
    if (submitBtn) submitBtn.disabled = false;
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
