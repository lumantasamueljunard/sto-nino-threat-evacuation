"""Streamlit dashboard for the Sto. Niño SHS acoustic-visual threat
detection and evacuation simulation.

Run locally with:
    streamlit run dashboard.py

Reads ONLY from dynamic_evacuation.py and demo_detector.py.
This is a demonstration prototype, not a certified life-safety system.
"""
import os
import uuid
import streamlit as st
import pandas as pd

from dynamic_evacuation import (
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS, G,
    Observation, assess, route, format_route, route_summary_counts,
    classify_threat,
)
from demo_detector import fake_scores, observation_from_scores, prebaked_scenarios

st.set_page_config(
    page_title='Sto. Niño SHS — Threat & Evacuation Demo',
    layout='wide',
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if 'observations' not in st.session_state:
    st.session_state.observations = []
if 'manual_blocks' not in st.session_state:
    st.session_state.manual_blocks = []
if 'closed_edges' not in st.session_state:
    st.session_state.closed_edges = []
if 'unavailable_gates' not in st.session_state:
    st.session_state.unavailable_gates = []

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title('Microcontroller-Based Acoustic-Visual Threat Detection '
         'and Evacuation Simulation')
st.caption('Sto. Niño Senior High School, Tacloban City — '
           'Demonstration prototype. Not a certified emergency system.')

with st.expander('⚠️ Simulation disclaimer & limitations', expanded=False):
    st.markdown(
        '- The site layout is a **demo representation**, not a certified survey.\n'
        '- Edge costs are **illustrative**, not metres or travel times.\n'
        '- Detections are **simulated mock scores** until the real YOLO/Librosa '
        'models are integrated.\n'
        '- `unique_threat_count` is intentionally `None`; overlapping cameras '
        'cannot prove distinct people.\n'
        '- Authorized human oversight and school-approved procedures always '
        'take precedence over this simulation.'
    )

# ---------------------------------------------------------------------------
# Sidebar — controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header('Simulation Controls')

    st.subheader('Prebaked scenarios')
    scenarios = prebaked_scenarios()
    scenario_names = ['— none —'] + [s['name'] for s in scenarios]
    chosen = st.selectbox('Load a scenario', scenario_names, index=0)
    col_a, col_b = st.columns(2)
    if col_a.button('Load', use_container_width=True) and chosen != '— none —':
        s = next(x for x in scenarios if x['name'] == chosen)
        st.session_state.observations = list(s['observations'])
        st.rerun()
    if col_b.button('Clear events', use_container_width=True):
        st.session_state.observations = []
        st.rerun()

    st.divider()
    st.subheader('Add a manual mock observation')
    device_ids = sorted(DEVICES.keys())
    dev = st.selectbox('Device', device_ids)
    profile = st.selectbox('Mock profile', ['normal', 'warning', 'critical', 'random'])
    if st.button('Add observation', use_container_width=True):
        event_id = f'manual-{uuid.uuid4().hex[:8]}'
        scores = fake_scores(dev, profile=profile)
        obs, c = observation_from_scores(event_id, dev, scores)
        st.session_state.observations.append(obs)
        st.success(f'Added {c["level"]} from {dev} '
                   f'(index {c["index"]}, verified={c["verified"]})')
        st.rerun()

    st.divider()
    st.subheader('Manual closures')
    manual_blocks = st.multiselect(
        'Blocked nodes (rooms, corridors, stairs, gates)',
        options=sorted(G.nodes), default=st.session_state.manual_blocks)
    unavailable_gates = st.multiselect(
        'Unavailable gates', options=list(GATES),
        default=st.session_state.unavailable_gates)
    all_edges = [(a, b) for a, b in G.edges if a < b]
    edge_labels = [f'{a} ↔ {b}' for a, b in all_edges]
    closed_labels = st.multiselect('Closed edges', options=edge_labels, default=[])
    closed_edges = [all_edges[edge_labels.index(lbl)] for lbl in closed_labels]

    # Persist for the next rerun
    st.session_state.manual_blocks = manual_blocks
    st.session_state.unavailable_gates = unavailable_gates

# ---------------------------------------------------------------------------
# Build the snapshot
# ---------------------------------------------------------------------------
snapshot = assess(
    st.session_state.observations,
    manual_blocks=manual_blocks,
    closed_edges=closed_edges,
    unavailable_gates=unavailable_gates,
)
counts = route_summary_counts(snapshot)

# ---------------------------------------------------------------------------
# Top KPI row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric('Rooms', len(ROOMS))
k2.metric('Devices', len(DEVICES))
k3.metric('Events (this snapshot)', snapshot['observation_count'])
k4.metric('Detections in video', snapshot['raw_detection_count'])
k5.metric('Unique threat count', 'not determinable')

k6, k7, k8 = st.columns(3)
k6.metric('Rooms with a modeled route', counts['available'])
k7.metric('Rooms on HOLD', counts['hold'])
k8.metric('Rooms with no route', counts['no_route'])

st.caption(f'Note: {snapshot["note"]}')

# ---------------------------------------------------------------------------
# Event feed
# ---------------------------------------------------------------------------
st.subheader('Concurrent event feed')
if not snapshot['events']:
    st.info('No active WARNING or CRITICAL events in this snapshot.')
else:
    df = pd.DataFrame([{
        'Event ID': e['event_id'],
        'Device': e['device'],
        'Level': e['level'],
        'Count in video': e['count_in_video'],
        'Location confirmed': e['location_confirmed'],
        'Possible locations': ', '.join(e['possible_locations']),
    } for e in snapshot['events']])
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button('Remove all events'):
        st.session_state.observations = []
        st.rerun()

# ---------------------------------------------------------------------------
# Coverage explorer
# ---------------------------------------------------------------------------
with st.expander('Device coverage (26 simulated cameras)'):
    cov_rows = []
    for did, info in sorted(DEVICES.items()):
        cov_rows.append({
            'Device': did,
            'Building': info['building'],
            'Floor': info['floor'],
            'Zone': info['zone'],
            'Side': info['side'],
            'Covered nodes': ', '.join(sorted(COVERAGE[did])),
        })
    st.dataframe(pd.DataFrame(cov_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Single-classroom route
# ---------------------------------------------------------------------------
st.subheader('Route for a selected classroom')
col1, col2 = st.columns([1, 2])
with col1:
    room = st.selectbox('Classroom', ROOMS, index=ROOMS.index('B1-F4-R3'))
    current = st.text_input('Current node (optional; leave blank to use the room)', '')
    current_node = current.strip() or None
with col2:
    r = route(room, snapshot, current=current_node)
    if r['status'] == 'MODELED_ROUTE_AVAILABLE':
        st.success(f"Destination: {r['gate']}  |  Door: {r['door']}  |  "
                   f"Cost: {r['cost']:.2f}")
        st.write(' → '.join(r['route']))
        st.caption(r['reason'])
    elif r['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE':
        st.warning(f"HOLD FOR AUTHORIZED GUIDANCE — {r['reason']}")
    else:
        st.error(f"NO CONFIRMED ROUTE — {r['reason']}")

# ---------------------------------------------------------------------------
# All-36 status table
# ---------------------------------------------------------------------------
st.subheader('All 36 classrooms')
rows = []
for rm in ROOMS:
    rr = route(rm, snapshot)
    rows.append({
        'Classroom': rm,
        'Status': rr['status'],
        'Gate': rr['gate'],
        'Door': rr['door'],
        'Cost': rr['cost'],
        'Reason': rr['reason'],
    })
status_df = pd.DataFrame(rows)

def _color(status):
    if status == 'MODELED_ROUTE_AVAILABLE':
        return 'background-color: #d1f0d1'
    if status == 'HOLD_FOR_AUTHORIZED_GUIDANCE':
        return 'background-color: #fff2cc'
    return 'background-color: #f4c7c3'

st.dataframe(
    status_df.style.applymap(_color, subset=['Status']),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Site plan image (optional)
# ---------------------------------------------------------------------------
site_path = os.path.join('assets', 'site_plan.jpg')
if os.path.exists(site_path):
    with st.expander('Site plan'):
        st.image(site_path, caption='Demo campus layout (not a certified survey).')

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    'Prototype only. Modeled routes are illustrative. '
    'Authorized human oversight and school-approved procedures take precedence. '
    'Do not issue real evacuation instructions based on this simulation.'
)