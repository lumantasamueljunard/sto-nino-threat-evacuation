"""Real-detector and video AI analysis module.

Performs acoustic and visual threat detection on prerecorded or uploaded video feeds
using local YOLOv8 (object and pose keypoint models) and audio RMS extraction,
producing canonical Observation objects for the dynamic evacuation routing engine.

Project Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City
"""
import json
import os
import subprocess
import uuid
from datetime import datetime
import numpy as np

from dynamic_evacuation import DEVICES, Observation, classify_threat

# Paths for local weights and default file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_OBJ_WEIGHTS = os.path.join(BASE_DIR, "yolov8n.pt")
YOLO_POSE_WEIGHTS = os.path.join(BASE_DIR, "yolov8n-pose.pt")
DETECTIONS_JSON = os.path.join(BASE_DIR, "detections.json")


def load_detections(path=DETECTIONS_JSON):
    """Return the raw list of detection records, or [] if missing/empty."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_detections(records, path=DETECTIONS_JSON):
    """Persist a list of detection records to the JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def append_detection(record, path=DETECTIONS_JSON):
    """Append a single detection record to detections.json."""
    records = load_detections(path)
    records.append(record)
    save_detections(records, path)


def clear_detections(path=DETECTIONS_JSON):
    """Clear all records in detections.json."""
    save_detections([], path)


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

    Returns a dict with:
        rms: root-mean-square amplitude
        peak: peak amplitude
        score: acoustic indicator in [0, 100]
        has_audio: boolean
    """
    try:
        import imageio_ffmpeg
        import soundfile as sf

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_wav = os.path.join(BASE_DIR, f"_temp_audio_{uuid.uuid4().hex[:6]}.wav")

        cmd = [
            ffmpeg_exe, "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
            temp_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
                # Scale RMS to [0, 100] range
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

    # Fallback when video has no audio track or extraction is unsupported
    return {
        "rms": 0.02,
        "peak": 0.05,
        "score": 15.0,
        "has_audio": False,
        "duration_sec": 0.0,
    }


def analyze_video_feed(video_path, device_id, incident_id=None, sample_frames=40, progress_callback=None):
    """Analyze video frames with YOLOv8 object & pose models and audio analysis.

    Returns a standardized detection record dict ready for detections.json.
    """
    import cv2
    from ultralytics import YOLO

    if device_id not in DEVICES:
        raise ValueError(f"Unknown device: {device_id}")

    # Initialize models
    model_obj = YOLO(YOLO_OBJ_WEIGHTS)
    model_pose = YOLO(YOLO_POSE_WEIGHTS)

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    step = max(1, total_frames // max(1, sample_frames))
    frames_analyzed = 0
    frames_with_person = 0
    frames_with_threat_item = 0
    frames_raised_arms = 0
    detected_classes = set()
    threat_classes = {"knife", "scissors", "baseball bat", "gun", "pistol", "rifle"}

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % step == 0:
            frames_analyzed += 1
            if progress_callback:
                progress_callback(frames_analyzed, sample_frames)

            # 1. Object detection
            res_obj = model_obj(frame, verbose=False)[0]
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
                # 2. Pose estimation
                res_pose = model_pose(frame, verbose=False)[0]
                if res_pose.keypoints is not None and len(res_pose.keypoints) > 0:
                    kpts = res_pose.keypoints.data[0].cpu().numpy()
                    # kpts indices: 5=L-shoulder, 6=R-shoulder, 9=L-wrist, 10=R-wrist
                    if len(kpts) > 10:
                        ls_y, rs_y = kpts[5][1], kpts[6][1]
                        lw_y, rw_y = kpts[9][1], kpts[10][1]
                        # Smaller y indicates higher elevation in image space
                        if (lw_y < ls_y and kpts[9][2] > 0.3) or (rw_y < rs_y and kpts[10][2] > 0.3):
                            frames_raised_arms += 1

            if has_threat_in_frame:
                frames_with_threat_item += 1

        frame_idx += 1

    cap.release()

    # 3. Compute indicators in [0, 100]
    total_safe = max(1, frames_analyzed)
    threat_ratio = frames_with_threat_item / total_safe
    person_ratio = frames_with_person / total_safe
    pose_ratio = frames_raised_arms / max(1, frames_with_person) if frames_with_person > 0 else 0.0

    # Object indicator: high if threat item detected, moderate if multiple persons / activity
    if frames_with_threat_item > 0:
        obj_score = min(100.0, 60.0 + (threat_ratio * 40.0))
    else:
        obj_score = min(55.0, person_ratio * 50.0)

    # Pose indicator: raised arms / aggressive posture percentage
    pose_score = min(100.0, pose_ratio * 100.0)
    if frames_raised_arms > 0 and pose_score < 50.0:
        pose_score = 50.0

    # 4. Audio indicator
    audio_feat = extract_audio_features(video_path)
    acoustic_score = audio_feat["score"]

    # 5. Classify threat
    classification = classify_threat(acoustic_score, pose_score, obj_score)

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
        },
        "pose_stats": {
            "frames_raised_arms": frames_raised_arms,
            "pose_score": pose_score,
        },
        "acoustic_stats": audio_feat,
        "classification": classification,
    }

    return record


if __name__ == "__main__":
    test_video = os.path.join(BASE_DIR, "videos-project", "test_video.mp4")
    if os.path.exists(test_video):
        print("Testing video analysis on:", test_video)
        rec = analyze_video_feed(test_video, "B1-F1-CAM-L", sample_frames=15)
        print("Classification:", rec["classification"])
        print("Scores:", rec["scores"])
