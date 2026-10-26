"""Streamlit Dashboard for Sto. Niño SHS Threat Detection and Evacuation Simulation.

Supports both live edge video detections (via detections.json / upload_dashboard.py)
and prebaked / mock evaluation scenarios.

Run with:
    streamlit run dashboard.py

Official Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City
"""
import os
import uuid
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from dynamic_evacuation import (
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS, G,
    Observation, assess, route, format_route, route_summary_counts,
    classify_threat,
)
from demo_detector import fake_scores, observation_from_scores, prebaked_scenarios
from real_detector import load_detections, observations_from_json, clear_detections

st.set_page_config(
    page_title="Sto. Niño SHS — Threat & Evacuation Demo",
    page_icon="🛡️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if 'observations' not in st.session_state:
    st.session_state.observations = []
if 'manual_blocks' not in st.session_state:
    st.session_state.manual_blocks = []
if 'closed_edges' not in st.session_state:
    st.session_state.closed_edges = []
if 'unavailable_gates' not in st.session_state:
    st.session_state.unavailable_gates = []
if 'data_source' not in st.session_state:
    st.session_state.data_source = 'Live Edge Ingest (detections.json)'

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation")
st.caption(
    "Sto. Niño Senior High School, Tacloban City — "
    "Demonstration prototype. Not a certified emergency system."
)

with st.expander("⚠️ Simulation disclaimer & research scope", expanded=False):
    st.markdown(
        "- The school layout is a **DEMO campus representation**, not a certified survey or life-safety blueprint.\n"
        "- Graph edge weights are **illustrative relative path costs**, not measured travel times or distances.\n"
        "- Detections are produced by simulated edge cameras with local YOLOv8 (object/pose) and acoustic analysis.\n"
        "- `unique_threat_count` is intentionally reported as **not determinable** without cross-camera re-identification.\n"
        "- Authorized human oversight and school-approved emergency procedures always take precedence."
    )

# ---------------------------------------------------------------------------
# Sidebar — Data Source & Simulation Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Control Center")

    st.subheader("1. Data Ingest Mode")
    st.session_state.data_source = st.radio(
        "Observation Source:",
        ["Live Edge Ingest (detections.json)", "Prebaked Scenarios & Manual Mocks"],
        index=0 if st.session_state.data_source.startswith("Live") else 1,
    )

    if st.session_state.data_source == "Live Edge Ingest (detections.json)":
        raw_detections = load_detections()
        st.info(f"Loaded **{len(raw_detections)}** detection record(s) from `detections.json`.")
        
        col_r1, col_r2 = st.columns(2)
        if col_r1.button("🔄 Reload File", use_container_width=True):
            st.rerun()
        if col_r2.button("🗑️ Clear Live", use_container_width=True):
            clear_detections()
            st.session_state.observations = []
            st.rerun()
            
        obs_list, report = observations_from_json()
        active_observations = obs_list
    else:
        raw_detections = []
        st.subheader("Prebaked Scenarios")
        scenarios = prebaked_scenarios()
        scenario_names = ["— select a scenario —"] + [s["name"] for s in scenarios]
        chosen = st.selectbox("Load a scenario:", scenario_names, index=0)
        
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("Load Scenario", use_container_width=True) and chosen != "— select a scenario —":
            sc = next(x for x in scenarios if x["name"] == chosen)
            st.session_state.observations = list(sc["observations"])
            st.rerun()
        if col_s2.button("Clear Events", use_container_width=True):
            st.session_state.observations = []
            st.rerun()

        st.divider()
        st.subheader("Manual Mock Event")
        dev_id = st.selectbox("Device ID", sorted(DEVICES.keys()))
        profile = st.selectbox("Mock Profile", ["critical", "warning", "normal", "random"])
        if st.button("Add Mock Event", use_container_width=True):
            eid = f"manual-{uuid.uuid4().hex[:6]}"
            scs = fake_scores(dev_id, profile=profile)
            obs, clf = observation_from_scores(eid, dev_id, scs)
            st.session_state.observations.append(obs)
            st.success(f"Added {clf['level']} on {dev_id} (Index: {clf['index']})")
            st.rerun()

        active_observations = list(st.session_state.observations)

    st.divider()
    st.subheader("Manual Closures & Overrides")
    manual_blocks = st.multiselect(
        "Blocked Nodes (Rooms, Corridors, Stairs):",
        options=sorted(G.nodes),
        default=st.session_state.manual_blocks,
    )
    unavailable_gates = st.multiselect(
        "Unavailable Assembly Gates:",
        options=list(GATES),
        default=st.session_state.unavailable_gates,
    )
    all_edges = [(a, b) for a, b in G.edges if a < b]
    edge_labels = [f"{a} ↔ {b}" for a, b in all_edges]
    closed_labels = st.multiselect("Closed Edges (Debris/Obstruction):", options=edge_labels, default=[])
    closed_edges = [all_edges[edge_labels.index(lbl)] for lbl in closed_labels]

    st.session_state.manual_blocks = manual_blocks
    st.session_state.unavailable_gates = unavailable_gates

# ---------------------------------------------------------------------------
# Assessment & Snapshot Generation
# ---------------------------------------------------------------------------
snapshot = assess(
    active_observations,
    manual_blocks=manual_blocks,
    closed_edges=closed_edges,
    unavailable_gates=unavailable_gates,
)
counts = route_summary_counts(snapshot)

# ---------------------------------------------------------------------------
# Top KPI Row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Classrooms Modeled", len(ROOMS))
k2.metric("Simulated Edge Cameras", len(DEVICES))
k3.metric("Threat Events in Snapshot", snapshot["observation_count"])
k4.metric("Detections in Video", snapshot["raw_detection_count"])
k5.metric("Unique Threat Count", "Not Determinable", help="Per research methodology, overlapping cameras cannot infer unique people.")

m1, m2, m3 = st.columns(3)
m1.metric("✅ Classrooms with Safe Route", counts["available"])
m2.metric("⚠️ Classrooms on HOLD", counts["hold"], help="Occupants inside or adjacent to confirmed/uncertain hazard area.")
m3.metric("🚫 Classrooms with No Route", counts["no_route"], help="Both egress doors or vertical stair descents are compromised.")

if snapshot["note"]:
    st.caption(f"**Engine Note**: {snapshot['note']}")

st.divider()

# ---------------------------------------------------------------------------
# Main Tabs: Map, Camera Feeds, Analytics
# ---------------------------------------------------------------------------
tab_map, tab_cam, tab_analytics = st.tabs([
    "🗺️ Interactive Campus Evacuation Map",
    "📹 Edge Camera Ingest & Live Signals",
    "📊 Threat Analytics & Timeline",
])

# ===========================================================================
# TAB 1: CAMPUS MAP & EVACUATION VISUALIZER
# ===========================================================================
with tab_map:
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        sel_b = st.selectbox("Select Building:", [1, 2, 3], format_func=lambda b: f"Building {b} ({BUILDINGS[b][0]} Floors, {BUILDINGS[b][1]} Rooms/Floor)")
    with col_ctrl2:
        max_f = BUILDINGS[sel_b][0]
        sel_f = st.selectbox("Select Floor Level:", list(range(1, max_f + 1)), format_func=lambda f: f"Floor {f}")

    p = f"B{sel_b}-F{sel_f}"
    rooms_per_floor = BUILDINGS[sel_b][1]

    st.markdown(f"#### Floor Plan Layout — {p}")

    # Build responsive HTML/SVG diagram
    box_w = 90
    box_gap = 10
    stair_w = 46
    pad_left = 60
    total_svg_w = pad_left + (rooms_per_floor * (box_w + box_gap)) + stair_w + 30
    corridor_w = rooms_per_floor * (box_w + box_gap) - box_gap

    svg_elements = []
    div_elements = []

    # Stairs Left and Right
    div_elements.append(
        f'<div style="position:absolute; top:20px; left:0px; width:{stair_w}px; height:120px; '
        f'background:#e5e5ea; border:2px solid #86868b; border-radius:8px; text-align:center; '
        f'display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold; '
        f'color:#1d1d1f; z-index:2;">STAIR<br>L</div>'
    )
    stair_r_x = pad_left + corridor_w + 12
    div_elements.append(
        f'<div style="position:absolute; top:20px; left:{stair_r_x}px; width:{stair_w}px; height:120px; '
        f'background:#e5e5ea; border:2px solid #86868b; border-radius:8px; text-align:center; '
        f'display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold; '
        f'color:#1d1d1f; z-index:2;">STAIR<br>R</div>'
    )

    # Veranda / Corridor label box
    div_elements.append(
        f'<div style="position:absolute; top:108px; left:{pad_left}px; width:{corridor_w}px; height:32px; '
        f'background:#f2f2f7; border:1px dashed #aeaeb2; border-radius:6px; text-align:center; '
        f'line-height:32px; color:#86868b; font-size:11px; font-weight:bold; letter-spacing:1px; z-index:1;">'
        f'VERANDA / CORRIDOR ({p}-C0 … C{rooms_per_floor})</div>'
    )

    # Rooms and egress paths
    for r in range(1, rooms_per_floor + 1):
        room_id = f"{p}-R{r}"
        rr = route(room_id, snapshot)
        r_x = pad_left + (r - 1) * (box_w + box_gap)

        if rr["status"] == "HOLD_FOR_AUTHORIZED_GUIDANCE":
            bg_col, border_col, txt_col, badge = "#ffe5e5", "#ff3b30", "#d70015", "HOLD ⚠️"
        elif rr["status"] == "NO_CONFIRMED_ROUTE":
            bg_col, border_col, txt_col, badge = "#f3e5f5", "#af52de", "#5856d6", "BLOCKED 🚫"
        else:
            bg_col, border_col, txt_col, badge = "#e8f5e9", "#34c759", "#248a3d", "SAFE 🚪"

        div_elements.append(
            f'<div style="position:absolute; top:20px; left:{r_x}px; width:{box_w}px; height:75px; '
            f'background:{bg_col}; border:2px solid {border_col}; border-radius:8px; text-align:center; '
            f'padding-top:14px; font-weight:bold; color:{txt_col}; z-index:2; box-shadow:0 1px 3px rgba(0,0,0,0.06);">'
            f'<div style="font-size:14px;">R{r}</div>'
            f'<div style="font-size:10px; margin-top:4px;">{badge}</div>'
            f'</div>'
        )

        # Dynamic arrow animation towards chosen door/stair
        if rr["status"] == "MODELED_ROUTE_AVAILABLE":
            door_x = r_x + (box_w // 2)
            chosen_door = rr.get("door", "")
            
            # Direct arrow to stair L or R based on route
            if "STAIR-L" in " ".join(rr.get("route", [])) or r <= rooms_per_floor / 2:
                target_x = stair_w + 5
            else:
                target_x = stair_r_x - 5

            path_d = f"M {door_x} 95 L {door_x} 124 L {target_x} 124"
            svg_elements.append(f"""
                <path d="{path_d}" fill="none" stroke="#34c759" stroke-width="3" stroke-dasharray="8, 6" marker-end="url(#arrowhead)">
                    <animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.6s" repeatCount="indefinite" />
                </path>
            """)

    html_container = f"""
    <div style="background:#ffffff; border-radius:12px; padding:20px; overflow-x:auto; border:1px solid #e5e5ea; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">
        <div style="position:relative; width:{total_svg_w}px; height:160px; margin:0 auto;">
            {''.join(div_elements)}
            <svg width="{total_svg_w}px" height="160px" style="position:absolute; top:0; left:0; z-index:3; pointer-events:none;">
                <defs>
                    <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                        <polygon points="0 0, 6 3, 0 6" fill="#34c759" />
                    </marker>
                </defs>
                {''.join(svg_elements)}
            </svg>
        </div>
    </div>
    """
    components.html(html_container, height=200)

    # Classroom Route Inspector
    st.divider()
    st.subheader("Single Classroom Route Inspector")
    col_insp1, col_insp2 = st.columns([1, 2])
    with col_insp1:
        sel_room = st.selectbox("Inspect Classroom:", ROOMS, index=ROOMS.index("B1-F4-R3") if "B1-F4-R3" in ROOMS else 0)
        curr_input = st.text_input("Current Position (leave blank to start from room):", "").strip() or None
    with col_insp2:
        r_eval = route(sel_room, snapshot, current=curr_input)
        st_label = r_eval["status"]
        if st_label == "MODELED_ROUTE_AVAILABLE":
            st.success(f"**Destination Gate**: `{r_eval['gate']}` | **Exit Door**: `{r_eval['door']}` | **Path Cost**: `{r_eval['cost']:.1f}`")
            st.markdown(f"**Hops**: `{' → '.join(r_eval['route'])}`")
            st.caption(f"Reasoning: {r_eval['reason']}")
        elif st_label == "HOLD_FOR_AUTHORIZED_GUIDANCE":
            st.warning(f"**HOLD FOR AUTHORIZED GUIDANCE**\n\n{r_eval['reason']}")
        else:
            st.error(f"**NO CONFIRMED ROUTE AVAILABLE**\n\n{r_eval['reason']}")

    # All-36 Classrooms Summary
    st.divider()
    with st.expander("📋 View All 36 Classrooms Evacuation Status", expanded=False):
        all_rows = []
        for rm in ROOMS:
            res = route(rm, snapshot)
            all_rows.append({
                "Classroom": rm,
                "Status": res["status"],
                "Assigned Gate": res.get("gate") or "—",
                "Exit Door": res.get("door") or "—",
                "Relative Cost": res.get("cost") or "—",
                "Route Note": res.get("reason", ""),
            })
        df_all = pd.DataFrame(all_rows)

        def style_status(val):
            if val == "MODELED_ROUTE_AVAILABLE":
                return "background-color: #d1f0d1; color: #155724; font-weight: bold;"
            elif val == "HOLD_FOR_AUTHORIZED_GUIDANCE":
                return "background-color: #fff3cd; color: #856404; font-weight: bold;"
            return "background-color: #f8d7da; color: #721c24; font-weight: bold;"

        st.dataframe(df_all.style.map(style_status, subset=["Status"]), use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 2: ACTIVE CAMERA FEEDS & SIGNALS
# ===========================================================================
with tab_cam:
    st.markdown("### Edge Camera Feeds & Indicator Breakdown")
    st.caption("26 modeled cameras (20 indoor corner cameras + 6 outdoor approach cameras).")

    threat_rank = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    sorted_devs = sorted(
        DEVICES.keys(),
        key=lambda d: next((threat_rank[o.level] for o in active_observations if o.device_id == d), 0),
        reverse=True,
    )

    # Render cameras in 2-column grid
    cam_cols = st.columns(2)
    for idx, did in enumerate(sorted_devs[:8]):
        obs = next((o for o in active_observations if o.device_id == did), None)
        status = obs.level if obs else "NORMAL"
        badge_color = "#34c759" if status == "NORMAL" else "#ff9500" if status == "WARNING" else "#ff3b30"
        
        # Get raw score record if available
        raw_rec = next((r for r in raw_detections if r.get("device_id") == did), None)
        scores = raw_rec.get("scores", {}) if raw_rec else {}
        sc_obj = scores.get("object", 10.0 if status == "NORMAL" else 50.0 if status == "WARNING" else 85.0)
        sc_pose = scores.get("pose", 10.0 if status == "NORMAL" else 45.0 if status == "WARNING" else 80.0)
        sc_ac = scores.get("acoustic", 15.0 if status == "NORMAL" else 50.0 if status == "WARNING" else 75.0)

        with cam_cols[idx % 2]:
            st.markdown(f"""
            <div style="background:#ffffff; border-radius:12px; padding:15px; border:1px solid #e5e5ea; border-top: 5px solid {badge_color}; margin-bottom:15px; box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <h4 style="margin:0; color:#1d1d1f;">📹 {did}</h4>
                    <span style="background:{badge_color}; color:white; padding:3px 10px; border-radius:12px; font-weight:bold; font-size:12px;">{status}</span>
                </div>
                <div style="font-size:12px; color:#86868b; margin-bottom:10px;">
                    Covered: {', '.join(sorted(COVERAGE[did]))}
                </div>
                <div style="background:#1d1d1f; height:150px; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#86868b;">
                    <span style="font-size:24px;">▶</span>
                    <span style="font-size:12px; margin-top:5px;">Edge Video Stream ({did})</span>
                </div>
                <div style="display:flex; justify-content:space-around; margin-top:12px; padding-top:8px; border-top:1px solid #f2f2f7; font-size:13px; color:#1d1d1f;">
                    <span>🔫 Object (O): <b>{sc_obj:.1f}</b></span>
                    <span>🧍 Pose (P): <b>{sc_pose:.1f}</b></span>
                    <span>🎤 Acoustic (A): <b>{sc_ac:.1f}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ===========================================================================
# TAB 3: ANALYTICS & TIMELINE
# ===========================================================================
with tab_analytics:
    st.markdown("### Threat Index & System Metrics")
    
    # Synthetic time-series chart
    time_points = pd.date_range(end=datetime.now(), periods=15, freq="2min")
    if raw_detections:
        latest_idx = raw_detections[-1].get("classification", {}).get("index", 25.0)
    else:
        latest_idx = 20.0
    
    sample_curve = [15.0, 18.2, 16.5, 22.0, 24.5, 20.1, 28.3, 31.0, 25.4, 22.1, 29.8, 35.0, 42.1, 55.4, latest_idx]
    df_chart = pd.DataFrame({"Threat Index": sample_curve}, index=time_points)
    st.line_chart(df_chart, color="#ff3b30")

    st.markdown("### Incident Event Log")
    if raw_detections:
        for rec in reversed(raw_detections):
            lvl = rec.get("classification", {}).get("level", rec.get("level", "NORMAL"))
            col = "#34c759" if lvl == "NORMAL" else "#ff9500" if lvl == "WARNING" else "#ff3b30"
            clf = rec.get("classification", {})
            sc = rec.get("scores", {})
            st.markdown(f"""
            <div style="border-left: 4px solid {col}; padding: 10px 15px; margin-bottom: 10px; background: white; border-radius: 0 8px 8px 0; border:1px solid #e5e5ea; border-left: 5px solid {col};">
                <div style="display:flex; justify-content:space-between;">
                    <b style="font-size:14px; color:#1d1d1f;">{rec.get('device_id')} — <span style="color:{col};">{lvl}</span></b>
                    <span style="font-size:12px; color:#86868b;">{rec.get('timestamp', 'Recent')}</span>
                </div>
                <div style="font-size:12px; color:#515154; margin-top:5px;">
                    Index: <b>{clf.get('index', '—')}</b> | Verified: <b>{'Yes' if clf.get('verified') else 'No'}</b> |
                    Object: {sc.get('object', '—')} | Pose: {sc.get('pose', '—')} | Acoustic: {sc.get('acoustic', '—')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    elif active_observations:
        for obs in reversed(active_observations):
            col = "#34c759" if obs.level == "NORMAL" else "#ff9500" if obs.level == "WARNING" else "#ff3b30"
            st.markdown(f"""
            <div style="border-left: 5px solid {col}; padding: 10px 15px; margin-bottom: 10px; background: white; border-radius: 0 8px 8px 0; border:1px solid #e5e5ea; border-left: 5px solid {col};">
                <b>{obs.device_id}</b> — <span style="color:{col}; font-weight:bold;">{obs.level}</span> (Event: `{obs.event_id}`)
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No incident events recorded. Trigger video analysis in the Edge Camera Simulator or load a scenario.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Capstone Project Prototype — Sto. Niño Senior High School, Tacloban City. "
    "Routes and calculations are illustrative. Authorized human oversight takes precedence."
)
