"""SENTINEL — Campus Threat Detection and Evacuation Command Center.

Official Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City

Features:
    - Interactive Campus Site Plan with dynamic animated evacuation routes.
    - Architectural Floor-by-Floor Blueprint view with classroom doors and stairs.
    - Non-IT Friendly Dashboard: Plain-language instructions, simple status badges.
    - School Intelligence & Real-time Metrics.
    - Multi-device CCTV Monitoring Grid with live video & AI Threat Scoreboard.
    - MQTT Telemetry sync for Wokwi ESP32 alarm hardware.
"""
import base64
from datetime import datetime
import json
import os
import uuid
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from dynamic_evacuation import (
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS, G,
    Observation, assess, route, format_route, route_summary_counts,
    classify_threat,
)
from demo_detector import fake_scores, observation_from_scores, prebaked_scenarios
from real_detector import load_detections, observations_from_json, clear_detections, BASE_DIR

import threading

# Optional MQTT Publisher for Wokwi ESP32
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


def _mqtt_async_worker(threat_level, gates_open, active_device):
    """Worker running in a background thread to prevent UI freezing."""
    try:
        client = mqtt.Client(client_id=f"stonino_pub_{uuid.uuid4().hex[:6]}", callback_api_version=mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, "CallbackAPIVersion") else None)
        client.connect("broker.hivemq.com", 1883, 2)
        payload = json.dumps({
            "status": threat_level,
            "gates": gates_open,
            "device": active_device,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        client.publish("stonino/campus/alert", payload)
        client.disconnect()
    except Exception:
        pass


def publish_esp32_mqtt(threat_level, gates_open="GATE-W,GATE-NE", active_device="ALL"):
    """Non-blocking asynchronous MQTT broadcast with deduplication."""
    if not MQTT_AVAILABLE:
        return
    # Only dispatch if state changed to avoid repeated network hits
    last_sent = st.session_state.get("_last_mqtt_state")
    current_state = (threat_level, gates_open, active_device)
    if last_sent == current_state:
        return
    st.session_state["_last_mqtt_state"] = current_state

    # Run in background thread so Streamlit UI stays instantaneous
    threading.Thread(target=_mqtt_async_worker, args=current_state, daemon=True).start()


# ---------------------------------------------------------------------------
# Page Setup & Tactical EOC Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SENTINEL — Sto. Niño SHS Safety Command",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Contrast, Clean Design System
st.markdown("""
<style>
    /* Global Typography & Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Hide Streamlit Chrome for Enterprise Feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1400px;
    }

    /* Top Navigation Pills */
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        justify-content: center;
        gap: 12px;
        background: #f0f1f5;
        padding: 6px;
        border-radius: 30px;
        border: 1px solid #e2e4ec;
        margin-bottom: 20px;
    }
    div[data-testid="stRadio"] label {
        background: transparent;
        padding: 8px 24px;
        border-radius: 24px;
        font-weight: 600;
        font-size: 14px;
        color: #4b5563;
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: #ffffff !important;
        color: #1d4ed8 !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    div[data-testid="stRadio"] input {
        display: none;
    }

    /* Clean Card Containers */
    .eoc-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 15px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6b7280;
    }

    /* Status Badges */
    .badge-normal {
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-warning {
        background: #fffbeb;
        color: #d97706;
        border: 1px solid #fde68a;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-critical {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Base64 Asset Helpers
# ---------------------------------------------------------------------------
@st.cache_data
def load_b64_image(filename):
    """Load and base64-encode an image for inline SVG/HTML rendering."""
    target_path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(target_path):
        return ""
    with open(target_path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{base64.b64encode(data).decode('utf-8')}"


B1_IMG_B64 = load_b64_image("b1_floor_plan.jpg")
B2_IMG_B64 = load_b64_image("b2_floor_plan.jpg")
B3_IMG_B64 = load_b64_image("b3_floor_plan.jpg")
SITE_IMG_B64 = load_b64_image("site_plan.jpg")


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if 'nav_tab' not in st.session_state:
    st.session_state.nav_tab = "🗺️ Campus Floor Plan & Evacuation"
if 'map_view' not in st.session_state:
    st.session_state.map_view = "SCHOOL MAP"
if 'manual_blocks' not in st.session_state:
    st.session_state.manual_blocks = []
if 'closed_edges' not in st.session_state:
    st.session_state.closed_edges = []
if 'unavailable_gates' not in st.session_state:
    st.session_state.unavailable_gates = []
if 'inspected_room' not in st.session_state:
    st.session_state.inspected_room = "B1-F1-R1"
if 'scenario' not in st.session_state:
    st.session_state.scenario = "All Clear (Normal Campus Day)"


# ---------------------------------------------------------------------------
# Determine Active Observations & Threat Assessment
# ---------------------------------------------------------------------------
# Load live edge detections if available
live_records = load_detections()
active_observations = []
active_device_id = "ALL"

if st.session_state.scenario != "All Clear (Normal Campus Day)":
    # Prebaked drill scenarios
    scenarios = dict(prebaked_scenarios())
    if st.session_state.scenario in scenarios:
        active_observations = list(scenarios[st.session_state.scenario])
elif live_records:
    # Live detections from edge cameras
    obs_list, _ = observations_from_json()
    active_observations = obs_list
    if live_records:
        active_device_id = live_records[-1].get("device_id", "ALL")

# Evaluate campus network snapshot
snapshot = assess(
    active_observations,
    manual_blocks=st.session_state.manual_blocks,
    closed_edges=st.session_state.closed_edges,
    unavailable_gates=st.session_state.unavailable_gates,
)

# Global status determination
if any(obs.level == "CRITICAL" for obs in active_observations):
    global_status = "CRITICAL"
    status_color = "#dc2626"
    status_label = "🔴 EMERGENCY LOCKDOWN / EVACUATE"
elif any(obs.level == "WARNING" for obs in active_observations) or len(st.session_state.unavailable_gates) > 0:
    global_status = "WARNING"
    status_color = "#d97706"
    status_label = "🟡 ELEVATED RISK / CAUTION"
else:
    global_status = "NORMAL"
    status_color = "#059669"
    status_label = "🟢 ALL CLEAR / NORMAL"

# Broadcast MQTT to Wokwi ESP32
available_gates_str = ",".join([g for g in GATES if g not in st.session_state.unavailable_gates]) or "NONE"
publish_esp32_mqtt(global_status, available_gates_str, active_device_id)


# ---------------------------------------------------------------------------
# SIDEBAR: Non-IT Emergency Controls & Egress Assistant
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
        <span style="font-size:24px;">🛡️</span>
        <div>
            <div style="font-size:18px; font-weight:800; color:#1e293b; letter-spacing:0.04em;">SENTINEL</div>
            <div style="font-size:11px; font-weight:600; color:#64748b;">CAMPUS SAFETY COMMAND</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Campus Health Badge
    st.markdown(f"""
    <div style="background:{status_color}15; border:1px solid {status_color}40; border-radius:10px; padding:12px; margin-bottom:18px; text-align:center;">
        <div style="font-size:11px; font-weight:700; color:{status_color}; text-transform:uppercase;">Overall Campus Status</div>
        <div style="font-size:15px; font-weight:700; color:{status_color}; margin-top:3px;">{status_label}</div>
    </div>
    """, unsafe_allow_html=True)

    # --- Section: Classroom Evacuation Finder ---
    st.markdown("### 📍 Evacuation Guide")
    st.caption("Select your current room to view plain egress instructions:")
    
    room_options = sorted(ROOMS)
    selected_room = st.selectbox(
        "Current Location:",
        room_options,
        index=room_options.index(st.session_state.inspected_room) if st.session_state.inspected_room in room_options else 0,
        label_visibility="collapsed",
    )
    st.session_state.inspected_room = selected_room

    r_info = route(selected_room, snapshot)
    
    if r_info["status"] == "MODELED_ROUTE_AVAILABLE":
        gate_name = "West Gate (GATE-W)" if r_info["gate"] == "GATE-W" else "Northeast Gate (GATE-NE)"
        door_side = "Left Door" if str(r_info.get("door") or "").endswith("-DL") else "Right Door"
        
        st.markdown(f"""
        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:12px; margin-bottom:15px;">
            <div style="font-size:11px; font-weight:700; color:#15803d; text-transform:uppercase;">Safe Egress Action:</div>
            <div style="font-size:13px; font-weight:600; color:#166534; margin-top:4px;">
                🚪 Exit via: <b>{door_side}</b><br>
                🚶 Pathway: <b>Follow corridor to stairs</b><br>
                🏁 Assembly Point: <b>{gate_name}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
    elif r_info["status"] == "HOLD_FOR_AUTHORIZED_GUIDANCE":
        st.markdown("""
        <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:12px; margin-bottom:15px;">
            <div style="font-size:11px; font-weight:700; color:#b91c1c; text-transform:uppercase;">Action Required:</div>
            <div style="font-size:13px; font-weight:600; color:#991b1b; margin-top:4px;">
                ⚠️ <b>SHELTER IN PLACE / HOLD</b><br>
                Direct corridor is compromised. Await authorized campus security guidance.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:12px; margin-bottom:15px;">
            <div style="font-size:11px; font-weight:700; color:#b45309; text-transform:uppercase;">Route Alert:</div>
            <div style="font-size:13px; font-weight:600; color:#92400e; margin-top:4px;">
                🚫 <b>NO CONFIRMED ROUTE</b><br>
                Egress corridors or both gates are currently blocked.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- Section: Quick Emergency Drill Scenarios ---
    st.divider()
    st.markdown("### 🚨 Emergency Drills & Scenarios")
    scenario_choices = [
        "All Clear (Normal Campus Day)",
        "West Gate Blocked Drill",
        "Building 1 Ground Floor Incident",
        "Two Simultaneous Threats (B1 & B2)",
        "Stairway Hazard Drill",
    ]
    curr_scen = st.selectbox(
        "Load Quick Scenario:",
        scenario_choices,
        index=0 if st.session_state.scenario not in scenario_choices else scenario_choices.index(st.session_state.scenario),
    )
    if curr_scen != st.session_state.scenario:
        st.session_state.scenario = curr_scen
        st.rerun()

    # --- Section: Hazard & Closure Overrides ---
    st.divider()
    st.markdown("### ⛔ Manual Gate & Area Closures")
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        w_blocked = st.checkbox("Block West Gate", value="GATE-W" in st.session_state.unavailable_gates)
    with col_g2:
        ne_blocked = st.checkbox("Block NE Gate", value="GATE-NE" in st.session_state.unavailable_gates)

    new_gates = []
    if w_blocked: new_gates.append("GATE-W")
    if ne_blocked: new_gates.append("GATE-NE")
    if set(new_gates) != set(st.session_state.unavailable_gates):
        st.session_state.unavailable_gates = new_gates
        st.rerun()

    # Manual stair closure
    manual_block_options = [
        "B1-F1-STAIR-L", "B1-F1-STAIR-R",
        "B2-F1-STAIR-L", "B2-F1-STAIR-R",
        "B3-F1-STAIR-L", "B3-F1-STAIR-R"
    ]
    stair_sel = st.multiselect(
        "Close Stairwells (Maintenance/Fire):",
        manual_block_options,
        default=st.session_state.manual_blocks,
        help="Simulates closing an entire stair column for drills.",
    )
    if set(stair_sel) != set(st.session_state.manual_blocks):
        st.session_state.manual_blocks = stair_sel
        st.rerun()

    # Reset button
    if st.button("↺ Reset All Overrides to Normal", use_container_width=True):
        st.session_state.manual_blocks = []
        st.session_state.closed_edges = []
        st.session_state.unavailable_gates = []
        st.session_state.scenario = "All Clear (Normal Campus Day)"
        clear_detections()
        st.rerun()


# ---------------------------------------------------------------------------
# TOP BAR NAVIGATION PILLS (Wireframe Match)
# ---------------------------------------------------------------------------
tab_choice = st.radio(
    "Navigation Pills",
    ["🗺️ Campus Floor Plan & Evacuation", "📊 School Data & Intelligence", "📹 CCTV & Device Feeds"],
    label_visibility="collapsed",
    horizontal=True,
)


# ===========================================================================
# PILL 1: CAMPUS FLOOR PLAN & EVACUATION
# ===========================================================================
if tab_choice == "🗺️ Campus Floor Plan & Evacuation":
    # Top-Left Sub-Navigation (Buildings & School Map)
    col_nav, col_legend = st.columns([1.2, 0.8])
    with col_nav:
        b1_stat = "🔴" if any("B1" in obs.device_id and obs.level == "CRITICAL" for obs in active_observations) else "🟢"
        b2_stat = "🔴" if any("B2" in obs.device_id and obs.level == "CRITICAL" for obs in active_observations) else "🟢"
        b3_stat = "🔴" if any("B3" in obs.device_id and obs.level == "CRITICAL" for obs in active_observations) else "🟢"

        btn_cols = st.columns(4)
        if btn_cols[0].button(f"Building 1 {b1_stat}", use_container_width=True, type="primary" if st.session_state.map_view == "BUILDING 1" else "secondary"):
            st.session_state.map_view = "BUILDING 1"
            st.rerun()
        if btn_cols[1].button(f"Building 2 {b2_stat}", use_container_width=True, type="primary" if st.session_state.map_view == "BUILDING 2" else "secondary"):
            st.session_state.map_view = "BUILDING 2"
            st.rerun()
        if btn_cols[2].button(f"Building 3 {b3_stat}", use_container_width=True, type="primary" if st.session_state.map_view == "BUILDING 3" else "secondary"):
            st.session_state.map_view = "BUILDING 3"
            st.rerun()
        if btn_cols[3].button("School Map", use_container_width=True, type="primary" if st.session_state.map_view == "SCHOOL MAP" else "secondary"):
            st.session_state.map_view = "SCHOOL MAP"
            st.rerun()

    with col_legend:
        st.markdown("""
        <div style="display:flex; justify-content:flex-end; gap:16px; font-size:12px; font-weight:600; color:#475569; padding-top:6px;">
            <span>🟢 Normal Route</span>
            <span>🟣 Emergency Gate</span>
            <span>🔴 Blocked / Hazard</span>
            <span>📡 ESP32 Alarm Station</span>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # VIEW A: OUTSIDE CAMPUS SITE PLAN (Overview)
    # -----------------------------------------------------------------------
    if st.session_state.map_view == "SCHOOL MAP":
        # Determine gate visual states
        w_gate_blocked = "GATE-W" in st.session_state.unavailable_gates
        ne_gate_blocked = "GATE-NE" in st.session_state.unavailable_gates

        w_col = "#ef4444" if w_gate_blocked else "#8b5cf6"
        ne_col = "#ef4444" if ne_gate_blocked else "#8b5cf6"
        w_label = "GATE-W (BLOCKED)" if w_gate_blocked else "GATE-W (SAFE EXIT)"
        ne_label = "GATE-NE (BLOCKED)" if ne_gate_blocked else "GATE-NE (SAFE EXIT)"

        # Animated arrow SVG definitions
        outside_svg = f"""
        <div style="position:relative; width:100%; max-width:1150px; margin:0 auto; background:#ffffff; border-radius:14px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 12px rgba(0,0,0,0.06);">
            <svg viewBox="0 0 1312 1199" width="100%" height="auto" style="display:block;">
                <defs>
                    <marker id="arrow-green" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                        <polygon points="0 0, 6 3, 0 6" fill="#10b981" />
                    </marker>
                    <marker id="arrow-blue" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                        <polygon points="0 0, 6 3, 0 6" fill="#3b82f6" />
                    </marker>
                    <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#10b981" flood-opacity="0.6"/>
                    </filter>
                    <filter id="glow-purple" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#a855f7" flood-opacity="0.8"/>
                    </filter>
                </defs>

                <!-- Base Architectural Campus Drawing -->
                <image href="{SITE_IMG_B64}" width="1312" height="1199" preserveAspectRatio="none" />

                <!-- Purple Encircled Gates (Matching Miro Wireframe) -->
                <!-- West Gate (Left) -->
                <g style="cursor:pointer;" onclick="window.parent.postMessage('select_gate_w', '*');">
                    <circle cx="430" cy="680" r="42" fill="none" stroke="{w_col}" stroke-width="5" stroke-dasharray="8,4" filter="url(#glow-purple)" />
                    <rect x="330" y="735" width="200" height="30" rx="6" fill="#1e1b4b" opacity="0.9" />
                    <text x="430" y="755" fill="#ffffff" font-size="13" font-weight="bold" font-family="sans-serif" text-anchor="middle">{w_label}</text>
                </g>

                <!-- Northeast Gate (Top-Right) -->
                <g style="cursor:pointer;" onclick="window.parent.postMessage('select_gate_ne', '*');">
                    <circle cx="985" cy="335" r="42" fill="none" stroke="{ne_col}" stroke-width="5" stroke-dasharray="8,4" filter="url(#glow-purple)" />
                    <rect x="885" y="270" width="200" height="30" rx="6" fill="#1e1b4b" opacity="0.9" />
                    <text x="985" y="290" fill="#ffffff" font-size="13" font-weight="bold" font-family="sans-serif" text-anchor="middle">{ne_label}</text>
                </g>

                <!-- Pulsing Beacons on Buildings -->
                <!-- Building 1 Left Stair Exit -->
                <circle cx="485" cy="565" r="14" fill="#10b981" opacity="0.8">
                    <animate attributeName="r" values="8;18;8" dur="2s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.9;0.2;0.9" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="485" cy="565" r="7" fill="#ffffff" />

                <!-- Building 1 Right Stair Exit -->
                <circle cx="900" cy="355" r="14" fill="#10b981" opacity="0.8">
                    <animate attributeName="r" values="8;18;8" dur="2s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.9;0.2;0.9" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="900" cy="355" r="7" fill="#ffffff" />

                <!-- Building 2 Exit -->
                <circle cx="915" cy="695" r="14" fill="#10b981" opacity="0.8">
                    <animate attributeName="r" values="8;18;8" dur="2s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.9;0.2;0.9" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="915" cy="695" r="7" fill="#ffffff" />

                <!-- Building 3 Exit -->
                <circle cx="660" cy="770" r="14" fill="#10b981" opacity="0.8">
                    <animate attributeName="r" values="8;18;8" dur="2s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.9;0.2;0.9" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="660" cy="770" r="7" fill="#ffffff" />

                <!-- Dynamic Animated Evacuation Arrows (Matching Miro Wireframe) -->
                <!-- Path from Building 1 Left to West Gate -->
                <path d="M 485 575 C 470 610, 455 640, 440 665" fill="none" stroke="#10b981" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-green)" marker-end="url(#arrow-green)">
                    <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.8s" repeatCount="indefinite" />
                </path>

                <!-- Path from Building 1 Right to Northeast Gate -->
                <path d="M 905 355 C 930 350, 955 345, 975 340" fill="none" stroke="#10b981" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-green)" marker-end="url(#arrow-green)">
                    <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.8s" repeatCount="indefinite" />
                </path>

                <!-- Path from Building 2 around courtyard to Northeast Gate -->
                <path d="M 915 695 C 890 680, 880 520, 895 430 C 905 380, 940 350, 970 340" fill="none" stroke="#10b981" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-green)" marker-end="url(#arrow-green)">
                    <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.8s" repeatCount="indefinite" />
                </path>

                <!-- Path from Building 3 to West Gate -->
                <path d="M 660 770 C 600 780, 500 750, 445 695" fill="none" stroke="#10b981" stroke-width="6" stroke-dasharray="10,6" filter="url(#glow-green)" marker-end="url(#arrow-green)">
                    <animate attributeName="stroke-dashoffset" from="32" to="0" dur="0.8s" repeatCount="indefinite" />
                </path>
            </svg>
        </div>
        """
        components.html(outside_svg, height=660)

    # -----------------------------------------------------------------------
    # VIEW B: DETAILED BUILDING FLOOR PLAN VIEW (Miro Image 5)
    # -----------------------------------------------------------------------
    else:
        b_num = 1 if st.session_state.map_view == "BUILDING 1" else 2 if st.session_state.map_view == "BUILDING 2" else 3
        floors_count, rooms_per_floor = BUILDINGS[b_num]
        blueprint_b64 = B1_IMG_B64 if b_num == 1 else B2_IMG_B64 if b_num == 2 else B3_IMG_B64
        svg_h = 502 if b_num == 1 else 523 if b_num == 2 else 437

        st.markdown(f"#### 🏢 Building {b_num} — Multi-Floor Egress Layout")
        st.caption(f"{floors_count} Floors • {rooms_per_floor} Classrooms per floor • Microcontroller Alert Nodes stationed at stairwells")

        # Render unified responsive floor grid (Matching Miro Image 5)
        floor_cards_html = []

        for f_idx in range(1, floors_count + 1):
            p_code = f"B{b_num}-F{f_idx}"
            floor_critical = any(obs.level == "CRITICAL" and p_code in obs.device_id for obs in active_observations)
            floor_warning = any(obs.level == "WARNING" and p_code in obs.device_id for obs in active_observations)

            floor_badge = "🔴 BLOCKED" if floor_critical else "🟡 CAUTION" if floor_warning else "🟢 SAFE"
            badge_style = "background:#fef2f2; color:#dc2626; border:1px solid #fecaca;" if floor_critical else "background:#fffbeb; color:#d97706; border:1px solid #fde68a;" if floor_warning else "background:#ecfdf5; color:#059669; border:1px solid #a7f3d0;"

            arrow_elements = []
            room_badges = []

            for r_num in range(1, rooms_per_floor + 1):
                rm_id = f"{p_code}-R{r_num}"
                rm_eval = route(rm_id, snapshot)

                if b_num == 1:
                    rm_x = 145 + (r_num - 1) * 145 + 72
                    stair_left_x, stair_right_x = 110, 895
                elif b_num == 2:
                    rm_x = 180 + (r_num - 1) * 230 + 115
                    stair_left_x, stair_right_x = 135, 895
                else:  # B3
                    rm_x = 190 + (r_num - 1) * 335 + 167
                    stair_left_x, stair_right_x = 140, 900

                door_x = rm_x
                door_y = 310
                corridor_y = 350

                if rm_eval["status"] == "MODELED_ROUTE_AVAILABLE":
                    target_stair_x = stair_left_x if "STAIR-L" in " ".join(rm_eval.get("route", [])) or r_num <= rooms_per_floor / 2 else stair_right_x
                    arrow_elements.append(f"""
                    <path d="M {door_x} {door_y} L {door_x} {corridor_y} L {target_stair_x} {corridor_y}" fill="none" stroke="#10b981" stroke-width="4" stroke-dasharray="6,4" marker-end="url(#arrow-grid-g)">
                        <animate attributeName="stroke-dashoffset" from="20" to="0" dur="0.6s" repeatCount="indefinite" />
                    </path>
                    """)
                elif rm_eval["status"] == "HOLD_FOR_AUTHORIZED_GUIDANCE":
                    room_badges.append(f"""
                    <rect x="{rm_x - 30}" y="120" width="60" height="24" rx="4" fill="#dc2626" />
                    <text x="{rm_x}" y="136" fill="#ffffff" font-size="11" font-weight="bold" text-anchor="middle">HOLD</text>
                    """)

            floor_cards_html.append(f"""
            <div style="background:#ffffff; border-radius:10px; overflow:hidden; border:1px solid #cbd5e1; box-shadow:0 2px 6px rgba(0,0,0,0.04);">
                <div style="padding:6px 12px; background:#f8fafc; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:13px; color:#1e293b;">Floor {f_idx} <span style="font-size:11px; color:#64748b; font-weight:normal;">({p_code})</span></b>
                    <span style="{badge_style} padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">{floor_badge}</span>
                </div>
                <svg viewBox="0 0 1024 {svg_h}" width="100%" height="auto" style="display:block;">
                    <image href="{blueprint_b64}" width="1024" height="{svg_h}" />
                    <g>
                        <circle cx="{stair_left_x}" cy="{corridor_y}" r="9" fill="#2563eb" />
                        <text x="{stair_left_x}" y="{corridor_y + 3}" fill="#ffffff" font-size="7" font-weight="bold" text-anchor="middle">ESP</text>
                        <circle cx="{stair_right_x}" cy="{corridor_y}" r="9" fill="#2563eb" />
                        <text x="{stair_right_x}" y="{corridor_y + 3}" fill="#ffffff" font-size="7" font-weight="bold" text-anchor="middle">ESP</text>
                    </g>
                    {''.join(arrow_elements)}
                    {''.join(room_badges)}
                </svg>
            </div>
            """)

        total_grid_html = f"""
        <div style="display:grid; grid-template-columns:repeat({2 if floors_count > 1 else 1}, 1fr); gap:14px; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">
            <svg style="position:absolute; width:0; height:0;">
                <defs>
                    <marker id="arrow-grid-g" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                        <polygon points="0 0, 6 3, 0 6" fill="#10b981" />
                    </marker>
                </defs>
            </svg>
            {''.join(floor_cards_html)}
        </div>
        """
        components.html(total_grid_html, height=590 if floors_count > 2 else 310)


# ===========================================================================
# PILL 2: SCHOOL DATA & INTELLIGENCE
# ===========================================================================
elif tab_choice == "📊 School Data & Intelligence":
    st.markdown("### 📊 Campus Intelligence & System Metrics")
    st.caption("Real-time operational summary of all 36 classrooms, access gates, and sensor devices.")

    # High-level EOC Metrics
    total_rooms = len(ROOMS)
    summary = route_summary_counts(snapshot)
    safe_rooms = summary.get("MODELED_ROUTE_AVAILABLE", 0)
    hold_rooms = summary.get("HOLD_FOR_AUTHORIZED_GUIDANCE", 0)
    blocked_rooms = summary.get("NO_CONFIRMED_ROUTE", 0)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="eoc-card">
            <div class="metric-label">Total Classrooms</div>
            <div class="metric-value" style="color:#1e293b;">{total_rooms}</div>
            <div style="font-size:11px; color:#64748b; margin-top:4px;">10 floor levels</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="eoc-card">
            <div class="metric-label">Safe & Accessible</div>
            <div class="metric-value" style="color:#059669;">{safe_rooms}</div>
            <div style="font-size:11px; color:#059669; margin-top:4px;">Direct egress open</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="eoc-card">
            <div class="metric-label">Shelter in Place</div>
            <div class="metric-value" style="color:#dc2626;">{hold_rooms}</div>
            <div style="font-size:11px; color:#dc2626; margin-top:4px;">Corridor hazard</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="eoc-card">
            <div class="metric-label">No Route / Blocked</div>
            <div class="metric-value" style="color:#d97706;">{blocked_rooms}</div>
            <div style="font-size:11px; color:#d97706; margin-top:4px;">Gates/stairs cut off</div>
        </div>
        """, unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="eoc-card">
            <div class="metric-label">Active Incidents</div>
            <div class="metric-value" style="color:#7c3aed;">{snapshot['known_incident_count']}</div>
            <div style="font-size:11px; color:#7c3aed; margin-top:4px;">Deduplicated events</div>
        </div>
        """, unsafe_allow_html=True)

    # Building Health Overview Cards
    st.markdown("#### Campus Infrastructure Status")
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)

    with b_col1:
        st.markdown("""
        <div class="eoc-card">
            <b>Building 1 (4 Floors)</b><br>
            <span class="badge-normal">20 Classrooms Safe</span>
            <div style="font-size:12px; color:#64748b; margin-top:6px;">Dual stair columns operational</div>
        </div>
        """, unsafe_allow_html=True)
    with b_col2:
        st.markdown("""
        <div class="eoc-card">
            <b>Building 2 (4 Floors)</b><br>
            <span class="badge-normal">12 Classrooms Safe</span>
            <div style="font-size:12px; color:#64748b; margin-top:6px;">Courtyard egress path open</div>
        </div>
        """, unsafe_allow_html=True)
    with b_col3:
        st.markdown("""
        <div class="eoc-card">
            <b>Building 3 (2 Floors)</b><br>
            <span class="badge-normal">4 Classrooms Safe</span>
            <div style="font-size:12px; color:#64748b; margin-top:6px;">Direct West Path link active</div>
        </div>
        """, unsafe_allow_html=True)
    with b_col4:
        w_st = "🔴 BLOCKED" if "GATE-W" in st.session_state.unavailable_gates else "🟢 OPEN"
        ne_st = "🔴 BLOCKED" if "GATE-NE" in st.session_state.unavailable_gates else "🟢 OPEN"
        st.markdown(f"""
        <div class="eoc-card">
            <b>Emergency Gates</b><br>
            <span style="font-size:12px; color:#334155;">GATE-W: <b>{w_st}</b></span><br>
            <span style="font-size:12px; color:#334155;">GATE-NE: <b>{ne_st}</b></span>
        </div>
        """, unsafe_allow_html=True)

    # Complete Classrooms Egress Table
    st.markdown("#### Classroom-by-Classroom Detailed Status")
    all_rows = []
    for rm in ROOMS:
        res = route(rm, snapshot)
        door_val = str(res.get("door") or "")
        all_rows.append({
            "Classroom": rm,
            "Safety Status": res["status"].replace("_", " "),
            "Assigned Gate": res.get("gate") or "—",
            "Exit Door": "Left Door (-DL)" if door_val.endswith("-DL") else "Right Door (-DR)" if door_val else "—",
            "Path Hops": len(res.get("route", [])) if res.get("route") else "—",
        })
    df_rooms = pd.DataFrame(all_rows)
    st.dataframe(df_rooms, use_container_width=True, hide_index=True)


# ===========================================================================
# PILL 3: CCTV & DEVICE FEEDS
# ===========================================================================
elif tab_choice == "📹 CCTV & Device Feeds":
    st.markdown("### 📹 CCTV & Simulated Edge Device Feeds")
    st.caption("Live video inference and multi-modal acoustic-visual sensor telemetry across all 26 campus devices.")

    # 4 Camera Section Filters (Matching User Plan)
    cam_filter = st.segmented_control(
        "Camera Group:",
        ["Outside Perimeter (6)", "Building 1 Cameras (8)", "Building 2 Cameras (8)", "Building 3 Cameras (4)"],
        default="Building 1 Cameras (8)",
    )

    if "Outside" in cam_filter:
        dev_list = [d for d in DEVICES if "OUT" in d]
    elif "Building 1" in cam_filter:
        dev_list = [d for d in DEVICES if d.startswith("B1") and "OUT" not in d]
    elif "Building 2" in cam_filter:
        dev_list = [d for d in DEVICES if d.startswith("B2") and "OUT" not in d]
    else:
        dev_list = [d for d in DEVICES if d.startswith("B3") and "OUT" not in d]

    # Grid of cameras (2 columns)
    cols = st.columns(2)
    sample_video_path = os.path.join(BASE_DIR, "videos-project", "test_video.mp4")

    for idx, dev_id in enumerate(dev_list):
        with cols[idx % 2]:
            dev_meta = DEVICES[dev_id]
            covered_str = ", ".join(dev_meta.get("covered_rooms", [])) or dev_meta.get("covered_node", "Perimeter")

            # Check if this camera has an active detection in detections.json
            matching_det = [rec for rec in live_records if rec.get("device_id") == dev_id]

            st.markdown(f"""
            <div class="eoc-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:15px; color:#0f172a;">📹 {dev_id}</b>
                    <span class="{'badge-critical' if matching_det else 'badge-normal'}">
                        {'🔴 THREAT DETECTED' if matching_det else '🟢 FEED NORMAL'}
                    </span>
                </div>
                <div style="font-size:12px; color:#64748b; margin-top:4px;">
                    Modeled Coverage: <b>{covered_str}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # If this camera has a video detection, display video & AI Scoreboard!
            if matching_det:
                rec = matching_det[-1]
                clf = rec.get("classification", {})
                scores = rec.get("scores", {})

                v_col, s_col = st.columns([1.2, 1.0])
                with v_col:
                    if os.path.exists(sample_video_path):
                        st.video(sample_video_path)
                    else:
                        st.info("Video stream archived.")
                with s_col:
                    st.markdown(f"""
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; font-size:12px;">
                        <b>AI Threat Scoreboard:</b><br>
                        • Threat Index: <b style="color:#dc2626;">{clf.get('index', 0):.1f} / 100</b><br>
                        • Object Score ($O$): <b>{scores.get('object', 0)}</b><br>
                        • Pose Score ($P$): <b>{scores.get('pose', 0)}</b><br>
                        • Acoustic Score ($A$): <b>{scores.get('acoustic', 0)}</b><br>
                        • Verified Threat: <b>{'YES' if clf.get('verified') else 'Awaiting Review'}</b>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No suspicious indicators. Camera operating within baseline parameters.")


# ---------------------------------------------------------------------------
# FOOTER & LEGAL DISCLAIMER
# ---------------------------------------------------------------------------
st.divider()
st.markdown("""
<div style="font-size:11px; color:#94a3b8; text-align:center;">
    <b>Official Title:</b> Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation for Sto. Niño Senior High School, Tacloban City.<br>
    Campus floor drawings and edge weights are simulated demonstration models. Authorized school personnel and emergency services take absolute precedence.
</div>
""", unsafe_allow_html=True)
