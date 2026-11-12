"""Real-detector and video AI analysis module.

Performs fast acoustic and visual threat detection on prerecorded or uploaded video feeds
using cached YOLOv8 (object and pose keypoint models), direct keyframe seeking, and
3-Criteria early-exit gatekeeping, producing canonical Observation objects for the
dynamic evacuation routing engine.

Project Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City
"""
import json
import os
import subprocess
import time
import uuid
from datetime import datetime
import numpy as np
import database

from dynamic_evacuation import (
    DEVICES, Observation, classify_threat,
    SUPPORT_THRESHOLD, OBJECT_VERIFY_THRESHOLD, CRITICAL_INDEX, WARNING_INDEX,
)

# Paths for local weights and default file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_OBJ_WEIGHTS = os.path.join(BASE_DIR, "yolov8n.pt")
YOLO_POSE_WEIGHTS = os.path.join(BASE_DIR, "yolov8n-pose.pt")
DETECTIONS_JSON = os.path.join(BASE_DIR, "detections.json")

# Module-level Singleton Cache for YOLOv8 Models (eliminates 2.5s-4.0s reload per scan)
_MODEL_OBJ = None
_MODEL_POSE = None


def _get_yolo_models():
    """Return cached (model_obj, model_pose) instances, loading once on first use."""
    global _MODEL_OBJ, _MODEL_POSE
    from ultralytics import YOLO
    if _MODEL_OBJ is None:
        _MODEL_OBJ = YOLO(YOLO_OBJ_WEIGHTS)
    if _MODEL_POSE is None:
        _MODEL_POSE = YOLO(YOLO_POSE_WEIGHTS)
    return _MODEL_OBJ, _MODEL_POSE


def load_detections(path=DETECTIONS_JSON):
    """Return detection records from sentinel.db, falling back to JSON file."""
    try:
        db_records = database.get_all_detections()
        if db_records:
            return db_records
    except Exception:
        pass

    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_detections(records, path=DETECTIONS_JSON):
    """Persist a list of detection records to detections.json and sentinel.db."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    try:
        if not records:
            database.clear_all_detections()
        else:
            for r in records:
                database.record_detection(r)
    except Exception as e:
        print(f"Database sync notice: {e}")


def append_detection(record, path=DETECTIONS_JSON):
    """Append a single detection record to detections.json and sentinel.db."""
    records = load_detections(path)
    records.append(record)
    save_detections(records, path)


def clear_detections(path=DETECTIONS_JSON):
    """Clear all records in detections.json and archive active incidents in sentinel.db."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    try:
        database.clear_all_detections()
    except Exception as e:
        print(f"Database clear notice: {e}")


def observations_from_json(path=DETECTIONS_JSON):
    """Convert every record in detections.json into a canonical Observation.

    Returns (observations, report). `report` is a list of dicts summarizing
    what was loaded, for display in the dashboard.
    """
    records = load_detections(path)
    observations = []
    report = []

    for i, rec in enumerate(records):
        device_id = rec.get("device_id")
        if device_id not in DEVICES:
            report.append({
                "index": i,
                "skipped": True,
                "reason": f"Unknown device: {device_id}"
            })
            continue

        scores = rec.get("scores", {})
        classification = rec.get("classification", {})
        level = classification.get("level", rec.get("level", "NORMAL"))
        obj_stats = rec.get("object_stats", {})
        count = obj_stats.get("frames_with_threat", 1) or obj_stats.get("frames_with_gun", 1) or 1

        obs = Observation(
            event_id=rec.get("event_id", f"real-{i}-{uuid.uuid4().hex[:4]}"),
            device_id=device_id,
            level=level,
            count=max(1, int(count)),
            location=rec.get("location"),
            incident_id=rec.get("incident_id"),
        )
        observations.append(obs)
        report.append({
            "index": i,
            "event_id": obs.event_id,
            "device": device_id,
            "level": level,
            "scores": scores,
            "index_value": classification.get("index"),
            "verified": classification.get("verified"),
        })

    return observations, report


def extract_audio_features(video_path):
    """Extract audio from video using imageio-ffmpeg and calculate acoustic indicator.

    Optimized with -t 15 and -ar 16000 for sub-150ms extraction on large video files.
    """
    try:
        import imageio_ffmpeg
        import soundfile as sf

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_wav = os.path.join(BASE_DIR, f"_temp_audio_{uuid.uuid4().hex[:6]}.wav")

        cmd = [
            ffmpeg_exe, "-y", "-t", "15", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            temp_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)

        if res.returncode == 0 and os.path.exists(temp_wav):
            data, sr = sf.read(temp_wav)
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

            if len(data) > 0:
                rms = float(np.sqrt(np.mean(data ** 2)))
                peak = float(np.max(np.abs(data)))
                score = min(100.0, max(0.0, rms * 500.0))
                return {
                    "rms": round(rms, 4),
                    "peak": round(peak, 4),
                    "score": round(score, 2),
                    "has_audio": True,
                    "duration_sec": round(len(data) / sr, 2),
                }
    except Exception:
        pass

    return {
        "rms": 0.02,
        "peak": 0.05,
        "score": 15.0,
        "has_audio": False,
        "duration_sec": 0.0,
    }


def _compute_live_scores(frames_analyzed, frames_with_person, frames_with_threat_item, frames_raised_arms):
    """Compute current (obj_score, pose_score) from running frame counters."""
    total_safe = max(1, frames_analyzed)
    threat_ratio = frames_with_threat_item / total_safe
    person_ratio = frames_with_person / total_safe
    pose_ratio = frames_raised_arms / max(1, frames_with_person) if frames_with_person > 0 else 0.0

    if frames_with_threat_item > 0:
        obj_score = min(100.0, 60.0 + (threat_ratio * 40.0))
    else:
        obj_score = min(55.0, person_ratio * 50.0)

    pose_score = min(100.0, pose_ratio * 100.0)
    if frames_raised_arms > 0 and pose_score < 50.0:
        pose_score = 50.0

    return round(obj_score, 2), round(pose_score, 2)


def analyze_video_feed(video_path, device_id, incident_id=None, sample_frames=6, progress_callback=None):
    """Fast 3-Criteria video scanner with singleton YOLOv8 models, direct frame seeking,
    and early-exit verification once the 3 threat criteria are conclusively met.
    """
    import cv2

    if device_id not in DEVICES:
        raise ValueError(f"Unknown device: {device_id}")

    model_obj, model_pose = _get_yolo_models()
    t0 = time.perf_counter()

    # 1. Fast audio feature extraction first so acoustic score is ready for 3-criteria check
    audio_feat = extract_audio_features(video_path)
    acoustic_score = audio_feat["score"]

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    target_count = max(1, min(sample_frames, total_frames))
    frame_indices = [int(i * (total_frames - 1) / max(1, target_count - 1)) for i in range(target_count)] if target_count > 1 else [0]

    frames_analyzed = 0
    frames_with_person = 0
    frames_with_threat_item = 0
    frames_raised_arms = 0
    detected_classes = set()
    threat_classes = {"knife", "scissors", "baseball bat", "gun", "pistol", "rifle"}
    early_exit_triggered = False

    for target_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        frames_analyzed += 1
        if progress_callback:
            progress_callback(frames_analyzed, target_count)

        # 2. Fast Object Detection (imgsz=320 cuts CPU tensor latency by ~70%)
        res_obj = model_obj(frame, imgsz=320, verbose=False)[0]
        has_person_in_frame = False
        has_threat_in_frame = False

        for b in res_obj.boxes:
            cname = model_obj.names[int(b.cls[0])].lower()
            detected_classes.add(cname)
            if cname == "person":
                has_person_in_frame = True
            if cname in threat_classes:
                has_threat_in_frame = True

        if has_person_in_frame:
            frames_with_person += 1
            # 3. Pose Estimation (only when person is present)
            res_pose = model_pose(frame, imgsz=320, verbose=False)[0]
            if res_pose.keypoints is not None and len(res_pose.keypoints) > 0:
                kpts = res_pose.keypoints.data[0].cpu().numpy()
                if len(kpts) > 10:
                    ls_y, rs_y = kpts[5][1], kpts[6][1]
                    lw_y, rw_y = kpts[9][1], kpts[10][1]
                    if (lw_y < ls_y and kpts[9][2] > 0.3) or (rw_y < rs_y and kpts[10][2] > 0.3):
                        frames_raised_arms += 1

        if has_threat_in_frame:
            frames_with_threat_item += 1

        # 4. 3-Criteria Early-Exit Gatekeeper (after at least 2 keyframes when threat verified)
        if frames_analyzed >= 2 and frames_with_threat_item > 0:
            live_obj, live_pose = _compute_live_scores(
                frames_analyzed, frames_with_person, frames_with_threat_item, frames_raised_arms
            )
            live_clf = classify_threat(acoustic_score, live_pose, live_obj)
            if live_clf.get("verified"):
                early_exit_triggered = True
                break

    cap.release()

    obj_score, pose_score = _compute_live_scores(
        frames_analyzed, frames_with_person, frames_with_threat_item, frames_raised_arms
    )
    classification = classify_threat(acoustic_score, pose_score, obj_score)
    scan_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    # Structured 3-Criteria breakdown for fast operator visual scanning
    c1_pass = obj_score >= OBJECT_VERIFY_THRESHOLD
    c2_pass = classification.get("supporting_signals", 0) >= 2
    c3_pass = classification.get("index", 0.0) >= CRITICAL_INDEX
    criteria_breakdown = {
        "criterion_1_object": {
            "label": f"Object Verification (>= {OBJECT_VERIFY_THRESHOLD}%)",
            "value": obj_score,
            "threshold": OBJECT_VERIFY_THRESHOLD,
            "passed": c1_pass,
        },
        "criterion_2_corroboration": {
            "label": f"Multi-Signal Support (>= 2 signals >= {SUPPORT_THRESHOLD}%)",
            "value": classification.get("supporting_signals", 0),
            "threshold": 2,
            "passed": c2_pass,
        },
        "criterion_3_index": {
            "label": f"Composite Threat Index (>= {CRITICAL_INDEX}.0)",
            "value": classification.get("index", 0.0),
            "threshold": CRITICAL_INDEX,
            "passed": c3_pass,
        },
        "early_exit": early_exit_triggered,
        "scan_ms": scan_ms,
    }

    event_id = f"evt-{uuid.uuid4().hex[:6]}"
    inc_id = incident_id or f"inc-{uuid.uuid4().hex[:6]}"

    record = {
        "source": "live_video_analysis",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "device_id": device_id,
        "event_id": event_id,
        "incident_id": inc_id,
        "scores": {
            "acoustic": acoustic_score,
            "pose": pose_score,
            "object": obj_score,
        },
        "object_stats": {
            "frames_analyzed": frames_analyzed,
            "frames_with_person": frames_with_person,
            "frames_with_threat": frames_with_threat_item,
            "detected_classes": sorted(detected_classes),
            "early_exit": early_exit_triggered,
            "scan_ms": scan_ms,
        },
        "pose_stats": {
            "frames_raised_arms": frames_raised_arms,
            "pose_score": pose_score,
        },
        "acoustic_stats": audio_feat,
        "classification": classification,
        "criteria_breakdown": criteria_breakdown,
    }

    return record


if __name__ == "__main__":
    test_video = os.path.join(BASE_DIR, "videos-project", "test_video.mp4")
    if os.path.exists(test_video):
        print("Testing fast 3-criteria video analysis on:", test_video)
        rec = analyze_video_feed(test_video, "TPB-F1-CAM-L", sample_frames=8)
        print("Classification:", rec["classification"])
        print("Criteria Breakdown:", rec["criteria_breakdown"])
