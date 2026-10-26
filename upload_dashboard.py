"""Upload Dashboard — Edge Camera Simulator with Live YOLOv8 & Acoustic Analysis.

Allows simulated camera nodes to process uploaded or preloaded video streams,
run YOLOv8 object & pose inference, calculate acoustic features,
and persist threat observations to detections.json for the evacuation engine.

Project Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City
"""
import os
import tempfile
import time
import uuid
from datetime import datetime
import streamlit as st
import pandas as pd

from dynamic_evacuation import DEVICES, classify_threat
from real_detector import (
    analyze_video_feed, load_detections, save_detections,
    clear_detections, BASE_DIR
)

st.set_page_config(
    page_title="Edge Camera Simulator — Sto. Niño SHS",
    page_icon="📹",
    layout="wide",
)

st.title("📹 Edge Camera Simulator & Live AI Ingest")
st.caption(
    "Simulate edge camera devices by feeding prerecorded or uploaded video. "
    "Runs local YOLOv8 (object + pose) and audio analysis, then updates campus routing."
)

with st.expander("ℹ️ Simulation Context & Methodology", expanded=False):
    st.markdown(
        "- **Object Indicator ($O$)**: YOLOv8n detections for persons, weapons, or suspicious items.\n"
        "- **Pose Indicator ($P$)**: YOLOv8n-pose keypoint tracking (raised arms / aggressive stances).\n"
        "- **Acoustic Indicator ($A$)**: Extracted audio stream RMS amplitude and peak intensity.\n"
        "- **Threat Index**: $0.25A + 0.30P + 0.45O$.\n"
        "- **Verification Gate**: $O \\ge 60$ and $\\ge 2$ signals $\\ge 50$. Requires human verification for life safety."
    )

# --- Layout: 2 Columns (Controls vs Current Active Detections) ---
col_left, col_right = st.columns([1.1, 0.9])

with col_left:
    st.subheader("1. Select Camera Device(s)")
    all_devs = sorted(DEVICES.keys())
    
    # Pre-select B1-F1-CAM-L as default
    default_dev = ["B1-F1-CAM-L"] if "B1-F1-CAM-L" in all_devs else [all_devs[0]]
    selected_devices = st.multiselect(
        "Camera Device(s) observing this stream:",
        options=all_devs,
        default=default_dev,
        help="Select multiple cameras to simulate overlapping fields of view.",
    )

    st.subheader("2. Video Feed Source")
    sample_video_path = os.path.join(BASE_DIR, "videos-project", "test_video.mp4")
    has_sample = os.path.exists(sample_video_path)

    feed_source = st.radio(
        "Choose video feed source:",
        options=[
            "Preloaded Project Video (test_video.mp4)" if has_sample else "No preloaded video",
            "Upload Custom Video File (.mp4, .avi, .mov)",
            "Mock Simulation (Manual instant scores)",
        ],
        index=0 if has_sample else 1,
    )

    uploaded_file = None
    target_video_path = None

    if feed_source == "Upload Custom Video File (.mp4, .avi, .mov)":
        uploaded_file = st.file_uploader("Upload video clip", type=["mp4", "avi", "mov", "mkv"])
    elif feed_source.startswith("Preloaded"):
        target_video_path = sample_video_path
        st.success(f"Loaded: `{os.path.basename(sample_video_path)}` ({os.path.getsize(sample_video_path) / 1024 / 1024:.1f} MB)")

    # Video preview
    if target_video_path and os.path.exists(target_video_path):
        st.video(target_video_path)
    elif uploaded_file is not None:
        st.video(uploaded_file)

    st.subheader("3. Processing Mode & Parameters")
    if feed_source == "Mock Simulation (Manual instant scores)":
        mock_profile = st.selectbox("Mock Profile", ["Critical Threat", "Warning Hazard", "Normal Ambient", "Custom"])
        if mock_profile == "Critical Threat":
            m_a, m_p, m_o = 85.0, 80.0, 92.0
        elif mock_profile == "Warning Hazard":
            m_a, m_p, m_o = 55.0, 45.0, 40.0
        elif mock_profile == "Normal Ambient":
            m_a, m_p, m_o = 15.0, 10.0, 5.0
        else:
            col_m1, col_m2, col_m3 = st.columns(3)
            m_a = col_m1.slider("Acoustic (A)", 0.0, 100.0, 50.0)
            m_p = col_m2.slider("Pose (P)", 0.0, 100.0, 50.0)
            m_o = col_m3.slider("Object (O)", 0.0, 100.0, 50.0)
    else:
        sample_frames = st.slider("Number of sample frames to evaluate:", 10, 60, 30, step=5,
                                  help="Higher values increase analysis precision, lower values run faster.")

    # Shared Incident ID toggle
    use_shared_incident = st.checkbox(
        "Group selected cameras under single Incident ID (deduplication test)",
        value=True,
    )

    # Action button
    process_btn = st.button("🚀 Process Video Feed & Update Campus", type="primary", use_container_width=True)

with col_right:
    st.subheader("Current Edge Detections Queue")
    current_records = load_detections()
    
    st.metric("Total Active Records", len(current_records))
    
    col_c1, col_c2 = st.columns(2)
    if col_c1.button("🔄 Refresh List", use_container_width=True):
        st.rerun()
    if col_c2.button("🗑️ Clear All Detections", use_container_width=True):
        clear_detections()
        st.success("Cleared all records from detections.json!")
        st.rerun()

    if current_records:
        summary_rows = []
        for r in current_records:
            scores = r.get("scores", {})
            clf = r.get("classification", {})
            summary_rows.append({
                "Timestamp": r.get("timestamp", "").split("T")[-1],
                "Device": r.get("device_id"),
                "Level": clf.get("level", r.get("level", "NORMAL")),
                "Threat Index": clf.get("index", 0),
                "Verified": "✅" if clf.get("verified") else "❌",
                "Incident ID": r.get("incident_id", "-"),
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    else:
        st.info("detections.json is currently empty. Run processing to add events.")

# --- Processing Execution ---
if process_btn:
    if not selected_devices:
        st.error("Please select at least one camera device.")
    else:
        incident_id = f"inc-{uuid.uuid4().hex[:6]}" if use_shared_incident else None
        
        if feed_source == "Mock Simulation (Manual instant scores)":
            with st.spinner("Recording simulated mock observations..."):
                time.sleep(0.5)
                clf = classify_threat(m_a, m_p, m_o)
                for dev_id in selected_devices:
                    rec = {
                        "source": "manual_mock_simulator",
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "device_id": dev_id,
                        "event_id": f"mock-{uuid.uuid4().hex[:6]}",
                        "incident_id": incident_id or f"inc-{uuid.uuid4().hex[:6]}",
                        "scores": {"acoustic": m_a, "pose": m_p, "object": m_o},
                        "object_stats": {"frames_analyzed": 1, "frames_with_threat": int(m_o > 50)},
                        "pose_stats": {"pose_score": m_p},
                        "acoustic_stats": {"score": m_a},
                        "classification": clf,
                    }
                    current_records.append(rec)
                save_detections(current_records)
                st.success(f"Added {len(selected_devices)} record(s)! Level: **{clf['level']}** (Index: {clf['index']})")
                st.rerun()
        else:
            # Live AI Mode
            tmp_to_clean = None
            if uploaded_file is not None:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp.write(uploaded_file.read())
                    target_video_path = tmp.name
                    tmp_to_clean = tmp.name

            if not target_video_path or not os.path.exists(target_video_path):
                st.error("Please provide a valid video file.")
            else:
                progress_bar = st.progress(0, text="Initializing YOLOv8 models & video decode...")
                
                def update_prog(cur, total):
                    pct = min(1.0, max(0.0, cur / max(1, total)))
                    progress_bar.progress(pct, text=f"Analyzing frame {cur} of {total}...")

                try:
                    # Run live AI analysis on the primary video
                    with st.spinner("Running YOLOv8 Object + Pose and Audio extraction..."):
                        base_rec = analyze_video_feed(
                            target_video_path,
                            device_id=selected_devices[0],
                            incident_id=incident_id,
                            sample_frames=sample_frames,
                            progress_callback=update_prog,
                        )
                    
                    progress_bar.progress(1.0, text="Analysis complete!")

                    # Append record for all selected cameras
                    for did in selected_devices:
                        c_rec = dict(base_rec)
                        c_rec["device_id"] = did
                        c_rec["event_id"] = f"ai-{uuid.uuid4().hex[:6]}"
                        if not incident_id:
                            c_rec["incident_id"] = f"inc-{uuid.uuid4().hex[:6]}"
                        current_records.append(c_rec)

                    save_detections(current_records)

                    # Display Analysis Feedback
                    st.divider()
                    st.subheader("🎯 Video AI Analysis Results")

                    clf = base_rec["classification"]
                    scores = base_rec["scores"]
                    
                    lvl = clf["level"]
                    color = "red" if lvl == "CRITICAL" else "orange" if lvl == "WARNING" else "green"
                    st.markdown(f"### Threat Classification: :{color}[{lvl}] (Threat Index: {clf['index']})")

                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Object Score (O)", f"{scores['object']:.1f} / 100")
                    k2.metric("Pose Score (P)", f"{scores['pose']:.1f} / 100")
                    k3.metric("Acoustic Score (A)", f"{scores['acoustic']:.1f} / 100")
                    k4.metric("Verification Gate", "VERIFIED ✅" if clf["verified"] else "UNVERIFIED ⚠️")

                    obj_stats = base_rec.get("object_stats", {})
                    st.markdown(
                        f"- **Frames Analyzed**: {obj_stats.get('frames_analyzed')}\n"
                        f"- **Classes Detected in Stream**: `{', '.join(obj_stats.get('detected_classes', [])) or 'None'}`\n"
                        f"- **Threat Stance / Raised Arms Frames**: `{base_rec.get('pose_stats', {}).get('frames_raised_arms', 0)}`\n"
                        f"- **Extracted Audio Duration**: `{base_rec.get('acoustic_stats', {}).get('duration_sec', 0)}s` "
                        f"(RMS: `{base_rec.get('acoustic_stats', {}).get('rms', 0)}`)"
                    )
                    st.success(f"Successfully appended {len(selected_devices)} camera event(s) to detections.json! Open Main Dashboard to view route recalculation.")

                finally:
                    if tmp_to_clean and os.path.exists(tmp_to_clean):
                        try:
                            os.remove(tmp_to_clean)
                        except OSError:
                            pass
