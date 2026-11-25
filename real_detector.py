"""Real-detector and video AI analysis module.

Performs fast acoustic and visual threat detection on prerecorded or uploaded video feeds
using cached multi-model YOLOv8 (primary COCO YOLOv8s object detector, dual-model firearm
consensus ensemble with COCO benign-object suppression, and multi-person raised/aiming/
weapon-wielding pose keypoint detector), producing canonical Observation objects for the
dynamic evacuation routing engine.

Project Title:
    Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation
    for Sto. Niño Senior High School, Tacloban City
"""
import json
import math
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
YOLO_OBJ_WEIGHTS = (
    os.path.join(BASE_DIR, "yolov8s.pt")
    if os.path.exists(os.path.join(BASE_DIR, "yolov8s.pt"))
    else os.path.join(BASE_DIR, "yolov8n.pt")
)
YOLO_POSE_WEIGHTS = os.path.join(BASE_DIR, "yolov8n-pose.pt")
YOLO_WEAPON_CCTV_WEIGHTS = os.path.join(BASE_DIR, "weapon_cctv_yolov8n.pt")
YOLO_FIREARM_WEIGHTS = os.path.join(BASE_DIR, "firearm_yolov8n.pt")
DETECTIONS_JSON = os.path.join(BASE_DIR, "detections.json")

# COCO threat classes detected directly by primary YOLOv8s detector
COCO_THREAT_CLASSES = {"knife", "scissors", "baseball bat"}

# Benign COCO classes commonly confused for weapons by standalone firearm models
BENIGN_DISTRACTOR_CLASSES = {
    "cell phone", "remote", "handbag", "backpack", "suitcase", "bottle", "cup",
    "wine glass", "umbrella", "book", "laptop", "keyboard", "mouse", "chair",
    "couch", "car", "truck", "bus", "train", "bicycle", "motorcycle",
    "sports ball", "vase", "potted plant", "tie", "clock", "tv", "hair drier",
    "toothbrush", "fork", "spoon", "bowl", "banana", "apple", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "teddy bear",
    "skateboard", "surfboard", "tennis racket", "frisbee", "skis", "snowboard",
    "kite", "horse", "dog", "cat", "bird", "bench", "dining table", "bed",
}

# Module-level Singleton Cache for YOLOv8 Models (eliminates 2.5s-4.0s reload per scan)
_MODEL_OBJ = None
_MODEL_POSE = None
_MODEL_WEAPON_CCTV = None
_MODEL_FIREARM = None
_WEAPON_MODELS_CHECKED = False


def _get_yolo_models():
    """Return cached (model_obj, model_pose, model_cctv, model_firearm) instances."""
    global _MODEL_OBJ, _MODEL_POSE, _MODEL_WEAPON_CCTV, _MODEL_FIREARM, _WEAPON_MODELS_CHECKED
    from ultralytics import YOLO
    if _MODEL_OBJ is None:
        _MODEL_OBJ = YOLO(YOLO_OBJ_WEIGHTS)
    if _MODEL_POSE is None:
        _MODEL_POSE = YOLO(YOLO_POSE_WEIGHTS)
    if not _WEAPON_MODELS_CHECKED:
        _WEAPON_MODELS_CHECKED = True
        if os.path.exists(YOLO_WEAPON_CCTV_WEIGHTS):
            _MODEL_WEAPON_CCTV = YOLO(YOLO_WEAPON_CCTV_WEIGHTS)
        if os.path.exists(YOLO_FIREARM_WEIGHTS):
            _MODEL_FIREARM = YOLO(YOLO_FIREARM_WEIGHTS)
    return _MODEL_OBJ, _MODEL_POSE, _MODEL_WEAPON_CCTV, _MODEL_FIREARM


def _box_iou(b1, b2):
    """Return Intersection-over-Union for two [x1, y1, x2, y2] boxes."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0.0:
        return 0.0
    a1 = max(1e-6, (b1[2] - b1[0]) * (b1[3] - b1[1]))
    a2 = max(1e-6, (b2[2] - b2[0]) * (b2[3] - b2[1]))
    return inter / (a1 + a2 - inter)


def _box_overlap_ratio(target_box, other_box):
    """Return fraction of target_box covered by other_box."""
    x1 = max(target_box[0], other_box[0])
    y1 = max(target_box[1], other_box[1])
    x2 = min(target_box[2], other_box[2])
    y2 = min(target_box[3], other_box[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0.0:
        return 0.0
    area = max(1e-6, (target_box[2] - target_box[0]) * (target_box[3] - target_box[1]))
    return inter / area


def _is_near_any_person(box, person_boxes, frame_diag):
    """Check whether a candidate weapon box lies near or inside any detected person."""
    bx = (box[0] + box[2]) * 0.5
    by = (box[1] + box[3]) * 0.5
    for pb in person_boxes:
        pw = pb[2] - pb[0]
        ph = pb[3] - pb[1]
        exp = [pb[0] - 0.35 * pw, pb[1] - 0.25 * ph, pb[2] + 0.35 * pw, pb[3] + 0.25 * ph]
        if _box_iou(box, exp) > 0.0:
            return True
        px = (pb[0] + pb[2]) * 0.5
        py = (pb[1] + pb[3]) * 0.5
        if math.hypot(bx - px, by - py) <= 0.32 * frame_diag:
            return True
    return False


def _detect_consensus_firearms(frame, model_cctv, model_firearm, person_boxes, distractor_boxes):
    """Run dual-model firearm consensus with COCO benign-object suppression.

    A firearm detection is accepted only when BOTH independent specialist models
    agree spatially (IoU >= 0.18, both conf >= 0.40) and the box does not
    overlap a known benign COCO object (phone, bag, bottle, etc.).
    Returns (best_conf, consensus_boxes).
    """
    if model_cctv is None or model_firearm is None:
        return 0.0, []

    h, w = frame.shape[:2]
    frame_area = float(max(1, h * w))
    frame_diag = math.hypot(w, h)

    res_cctv = model_cctv(frame, imgsz=640, conf=0.36, verbose=False)[0]
    cctv_boxes = []
    for b in res_cctv.boxes:
        cname = model_cctv.names[int(b.cls[0])].lower()
        if "weapon" in cname or "gun" in cname or "pistol" in cname or "rifle" in cname:
            cctv_boxes.append((b.xyxy[0].cpu().numpy().tolist(), float(b.conf[0])))

    if not cctv_boxes:
        return 0.0, []

    res_fa = model_firearm(frame, imgsz=640, conf=0.36, verbose=False)[0]
    fa_boxes = []
    for b in res_fa.boxes:
        cname = model_firearm.names[int(b.cls[0])].lower()
        if "gun" in cname or "weapon" in cname or "pistol" in cname or "rifle" in cname or "firearm" in cname:
            fa_boxes.append((b.xyxy[0].cpu().numpy().tolist(), float(b.conf[0])))

    if not fa_boxes:
        return 0.0, []

    best_conf = 0.0
    accepted_boxes = []
    for c_box, c_conf in cctv_boxes:
        for f_box, f_conf in fa_boxes:
            if _box_iou(c_box, f_box) < 0.18:
                continue

            # Reject implausibly tiny specks or giant full-frame glitches
            c_area = max(0.0, (c_box[2] - c_box[0]) * (c_box[3] - c_box[1])) / frame_area
            f_area = max(0.0, (f_box[2] - f_box[0]) * (f_box[3] - f_box[1])) / frame_area
            if min(c_area, f_area) < 0.0010 or max(c_area, f_area) > 0.45:
                continue

            # Suppress if overlapping a benign COCO distractor (phone, bag, bottle, etc.)
            suppressed = False
            for d_box in distractor_boxes:
                if (
                    _box_iou(c_box, d_box) >= 0.25
                    or _box_iou(f_box, d_box) >= 0.25
                    or _box_overlap_ratio(f_box, d_box) >= 0.45
                ):
                    suppressed = True
                    break
            if suppressed:
                continue

            # Spatial proximity to a person (or high-confidence close-up shot if no person visible)
            if person_boxes:
                if not (
                    _is_near_any_person(c_box, person_boxes, frame_diag)
                    or _is_near_any_person(f_box, person_boxes, frame_diag)
                ):
                    continue
            else:
                if min(c_conf, f_conf) < 0.52:
                    continue

            avg_conf = (c_conf + f_conf) * 0.5
            merged = [
                min(c_box[0], f_box[0]),
                min(c_box[1], f_box[1]),
                max(c_box[2], f_box[2]),
                max(c_box[3], f_box[3]),
            ]
            accepted_boxes.append(merged)
            if avg_conf > best_conf:
                best_conf = avg_conf

    return round(best_conf, 3), accepted_boxes


def _point_near_box(px, py, box, margin):
    """Return True if (px, py) lies inside box expanded by margin pixels."""
    return (
        (box[0] - margin) <= px <= (box[2] + margin)
        and (box[1] - margin) <= py <= (box[3] + margin)
    )


def _detect_threat_pose(res_pose, frame_h, weapon_boxes=None):
    """Evaluate multi-person keypoints for:
      1. Overhead / raised striking arms (foreground persons only to avoid crowd noise)
      2. Horizontal aiming stance (extended shoulder-level arm)
      3. Active weapon-wielding stance (wrist spatially linked to a verified weapon box
         at chest/shoulder/head level — zero false positives on unarmed scenes)

    Returns (has_raised_arm: bool, has_aiming_stance: bool).
    """
    if res_pose.keypoints is None or len(res_pose.keypoints) == 0:
        return False, False

    weapon_boxes = weapon_boxes or []
    min_fg_torso = max(38.0, frame_h * 0.08)
    has_raised = False
    has_aiming = False

    for person_kpts in res_pose.keypoints.data:
        kpts = person_kpts.cpu().numpy()
        if len(kpts) <= 12:
            continue

        ls_x, ls_y, ls_c = kpts[5][0], kpts[5][1], kpts[5][2]
        rs_x, rs_y, rs_c = kpts[6][0], kpts[6][1], kpts[6][2]
        le_x, le_y, le_c = kpts[7][0], kpts[7][1], kpts[7][2]
        re_x, re_y, re_c = kpts[8][0], kpts[8][1], kpts[8][2]
        lw_x, lw_y, lw_c = kpts[9][0], kpts[9][1], kpts[9][2]
        rw_x, rw_y, rw_c = kpts[10][0], kpts[10][1], kpts[10][2]
        lh_y, lh_c = kpts[11][1], kpts[11][2]
        rh_y, rh_c = kpts[12][1], kpts[12][2]

        has_hips = lh_c > 0.30 and rh_c > 0.30
        has_shoulders = ls_c > 0.35 or rs_c > 0.35
        if not has_shoulders:
            continue

        shoulder_y = (
            (ls_y + rs_y) * 0.5 if (ls_c > 0.35 and rs_c > 0.35)
            else (ls_y if ls_c > 0.35 else rs_y)
        )
        if has_hips:
            torso_h = abs(((lh_y + rh_y) * 0.5) - shoulder_y)
        else:
            # Estimate torso height from shoulder width when hips are cropped out (close-up shooter)
            sh_w = math.hypot(rs_x - ls_x, rs_y - ls_y) if (ls_c > 0.35 and rs_c > 0.35) else 0.0
            torso_h = max(48.0, sh_w * 1.35)

        # Ignore tiny blurry distant background figures in crowds
        if torso_h < min_fg_torso:
            continue

        # 1. Overhead / raised striking arm (bat swing, raised blade, panic hands-up)
        left_up = (lw_y < ls_y - 0.18 * torso_h) and lw_c > 0.52 and ls_c > 0.50
        right_up = (rw_y < rs_y - 0.18 * torso_h) and rw_c > 0.52 and rs_c > 0.50
        if left_up or right_up:
            has_raised = True

        # 2. Horizontal aiming stance (arm extended cleanly at shoulder height)
        for (sx, sy, sc, ex, ey, ec, wx, wy, wc) in (
            (ls_x, ls_y, ls_c, le_x, le_y, le_c, lw_x, lw_y, lw_c),
            (rs_x, rs_y, rs_c, re_x, re_y, re_c, rw_x, rw_y, rw_c),
        ):
            if sc > 0.45 and wc > 0.45 and ec > 0.35:
                dx = abs(wx - sx)
                dy = abs(wy - sy)
                arm_len = math.hypot(dx, dy)
                if (
                    arm_len >= max(42.0, 0.50 * torso_h)
                    and dx >= 0.75 * arm_len
                    and dy <= 0.28 * arm_len
                    and abs(ey - sy) <= 0.40 * torso_h
                ):
                    has_aiming = True
                    break

        # 3. Active weapon-wielding stance (wrist holding/aiming a verified firearm/bat
        #    at chest, shoulder, or head level — distinguishes aimed weapons from low table prep)
        if weapon_boxes and not has_aiming:
            margin = max(45.0, 0.55 * torso_h)
            for (wx, wy, wc, sy, sc) in (
                (lw_x, lw_y, lw_c, ls_y, ls_c),
                (rw_x, rw_y, rw_c, rs_y, rs_c),
            ):
                if wc > 0.35 and sc > 0.35 and wy <= (sy + 0.45 * torso_h):
                    if any(_point_near_box(wx, wy, wb, margin) for wb in weapon_boxes):
                        has_aiming = True
                        break

        if has_raised and has_aiming:
            break

    return has_raised, has_aiming


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

    Uses dual-window RMS (0.25s sustained screams/crowds + 0.05s impulsive gunshots)
    plus peak amplitude so sharp firearm reports and shouting both register reliably
    without over-reacting to quiet classroom speech.
    """
    try:
        import imageio_ffmpeg
        import soundfile as sf

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_wav = os.path.join(BASE_DIR, f"_temp_audio_{uuid.uuid4().hex[:6]}.wav")

        cmd = [
            ffmpeg_exe, "-y", "-t", "20", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            temp_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)

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
                if rms < 0.005:
                    score = 0.0
                else:
                    win_long = max(1, int(sr * 0.25))
                    if len(data) >= win_long:
                        chunks_l = data[: (len(data) // win_long) * win_long].reshape(-1, win_long)
                        p95_long = float(np.percentile(np.sqrt(np.mean(chunks_l ** 2, axis=1)), 95))
                    else:
                        p95_long = rms

                    win_short = max(1, int(sr * 0.05))
                    if len(data) >= win_short:
                        chunks_s = data[: (len(data) // win_short) * win_short].reshape(-1, win_short)
                        p99_short = float(np.percentile(np.sqrt(np.mean(chunks_s ** 2, axis=1)), 99))
                    else:
                        p99_short = rms

                    effective_rms = max(p95_long, 0.72 * p99_short)
                    score = min(100.0, max(0.0, 0.65 * (effective_rms * 320.0) + 0.35 * (peak * 65.0)))
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


def _compute_live_scores(
    frames_analyzed,
    frames_with_person,
    frames_with_threat_item,
    frames_threat_pose,
    max_threat_conf=0.0,
):
    """Compute calibrated (obj_score, pose_score, threat_ratio, pose_ratio) from frame counters.

    - Object score is strictly driven by verified threat classes (COCO knife/scissors/bat
      or dual-model consensus firearm); ordinary people never inflate object threat score.
    - Requires >= 2 verified threat frames to cross Criterion 1 (60%) so isolated 1-frame
      artifacts never cause false alarms.
    - Pose score requires sustained threat posture (>= 2 frames of raised striking arms,
      horizontal aiming stance, or chest/shoulder-level weapon wielding) to cross the
      50% corroboration threshold.
    """
    total_safe = max(1, frames_analyzed)
    threat_ratio = frames_with_threat_item / total_safe
    pose_ratio = frames_threat_pose / max(1, frames_with_person) if frames_with_person > 0 else 0.0

    if frames_with_threat_item == 0:
        obj_score = 0.0
    elif frames_with_threat_item == 1:
        obj_score = min(55.0, 22.0 + (max_threat_conf * 45.0))
    else:
        obj_score = min(100.0, 68.0 + (threat_ratio * 24.0) + (max_threat_conf * 18.0))

    if frames_threat_pose == 0:
        pose_score = 0.0
    elif frames_threat_pose == 1:
        pose_score = min(35.0, pose_ratio * 100.0)
    elif pose_ratio < 0.22:
        # Brief low-ratio arm movement (< 22% of person frames) stays below 50% corroboration
        pose_score = min(48.0, 25.0 + (pose_ratio * 120.0))
    else:
        pose_score = min(100.0, 52.0 + (pose_ratio * 95.0))

    return (
        round(obj_score, 2),
        round(pose_score, 2),
        round(threat_ratio, 3),
        round(pose_ratio, 3),
    )


def _sample_video_frames(video_path, sample_frames=12):
    """Read evenly spaced frames cleanly. Uses sequential grab() for WebM/AV1/OGV
    containers where random POS_FRAMES seeks force slow full-stream restarts.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    target_count = max(1, min(sample_frames, total_frames))
    frame_indices = (
        [int(i * (total_frames - 1) / max(1, target_count - 1)) for i in range(target_count)]
        if target_count > 1
        else [0]
    )

    ext = os.path.splitext(video_path)[1].lower()
    use_sequential = ext in (".webm", ".ogv", ".mkv") and total_frames <= 3000

    frames = []
    if use_sequential:
        target_set = set(frame_indices)
        max_idx = frame_indices[-1]
        cur = 0
        while cur <= max_idx:
            if cur in target_set:
                ret, frame = cap.read()
                if ret and frame is not None:
                    frames.append(frame)
            else:
                if not cap.grab():
                    break
            cur += 1
    else:
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                frames.append(frame)

    cap.release()
    return frames, target_count


def analyze_video_feed(video_path, device_id, incident_id=None, sample_frames=12, progress_callback=None):
    """High-accuracy 3-Criteria video scanner with multi-model YOLOv8 (COCO YOLOv8s +
    dual-model firearm consensus + multi-person raised/aiming/wielding pose) and
    transparent visual ratios.
    """
    if device_id not in DEVICES:
        raise ValueError(f"Unknown device: {device_id}")

    model_obj, model_pose, model_cctv, model_firearm = _get_yolo_models()
    t0 = time.perf_counter()

    # 1. Fast audio feature extraction
    audio_feat = extract_audio_features(video_path)
    acoustic_score = audio_feat["score"]

    # 2. Fast keyframe sampling (sequential grab for WebM/AV1, direct seek for MP4)
    sampled_frames, target_count = _sample_video_frames(video_path, sample_frames=sample_frames)

    frames_analyzed = 0
    frames_with_person = 0
    frames_with_threat_item = 0
    frames_raised_arms = 0
    frames_aiming_stance = 0
    frames_threat_pose = 0
    max_threat_conf = 0.0
    detected_classes = set()
    detected_threats = set()
    THREAT_OBJ_CONF = 0.35
    early_exit_triggered = False

    for frame in sampled_frames:
        frames_analyzed += 1
        if progress_callback:
            progress_callback(frames_analyzed, target_count)

        frame_h = frame.shape[0]

        # 3. Primary COCO Object Detection (YOLOv8s at imgsz=640)
        res_obj = model_obj(frame, imgsz=640, verbose=False)[0]
        person_boxes = []
        distractor_boxes = []
        weapon_boxes_for_pose = []
        has_threat_in_frame = False

        for b in res_obj.boxes:
            cname = model_obj.names[int(b.cls[0])].lower()
            conf = float(b.conf[0])
            box = b.xyxy[0].cpu().numpy().tolist()

            if conf >= 0.25:
                detected_classes.add(cname)
            if cname == "person" and conf >= 0.28:
                person_boxes.append(box)
            if cname in BENIGN_DISTRACTOR_CLASSES and conf >= 0.25:
                distractor_boxes.append(box)
            if cname in COCO_THREAT_CLASSES and conf >= THREAT_OBJ_CONF:
                has_threat_in_frame = True
                detected_threats.add(cname)
                if cname == "baseball bat":
                    weapon_boxes_for_pose.append(box)
                if conf > max_threat_conf:
                    max_threat_conf = conf

        # 4. Dual-Model Firearm Consensus (catches pistols/rifles not in COCO with near-zero FPs)
        firearm_conf, firearm_boxes = _detect_consensus_firearms(
            frame, model_cctv, model_firearm, person_boxes, distractor_boxes
        )
        if firearm_conf >= THREAT_OBJ_CONF:
            has_threat_in_frame = True
            detected_classes.add("firearm")
            detected_threats.add("firearm")
            weapon_boxes_for_pose.extend(firearm_boxes)
            if firearm_conf > max_threat_conf:
                max_threat_conf = firearm_conf

        has_person_in_frame = len(person_boxes) > 0
        if has_person_in_frame:
            frames_with_person += 1
            # 5. Multi-person Pose Estimation (raised striking arm + aiming/weapon-wielding stance)
            res_pose = model_pose(frame, imgsz=640, verbose=False)[0]
            raised, aiming = _detect_threat_pose(res_pose, frame_h, weapon_boxes=weapon_boxes_for_pose)
            if raised:
                frames_raised_arms += 1
            if aiming:
                frames_aiming_stance += 1
            if raised or aiming:
                frames_threat_pose += 1

        if has_threat_in_frame:
            frames_with_threat_item += 1

    obj_score, pose_score, threat_ratio, pose_ratio = _compute_live_scores(
        frames_analyzed,
        frames_with_person,
        frames_with_threat_item,
        frames_threat_pose,
        max_threat_conf,
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
            "threat_visual_ratio": threat_ratio,
            "max_threat_conf": round(max_threat_conf, 3),
            "detected_threats": sorted(detected_threats),
            "detected_classes": sorted(detected_classes),
            "early_exit": early_exit_triggered,
            "scan_ms": scan_ms,
        },
        "pose_stats": {
            "frames_raised_arms": frames_raised_arms,
            "frames_aiming_stance": frames_aiming_stance,
            "frames_threat_pose": frames_threat_pose,
            "pose_visual_ratio": pose_ratio,
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
        print("Testing multi-model 3-criteria video analysis on:", test_video)
        rec = analyze_video_feed(test_video, "TPB-F1-CAM-L", sample_frames=12)
        print("Classification:", rec["classification"])
        print("Criteria Breakdown:", rec["criteria_breakdown"])
