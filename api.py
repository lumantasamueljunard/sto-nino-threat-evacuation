"""
SENTINEL FastAPI Backend
Official Title: Microcontroller-Based Acoustic-Visual Threat Detection and
Evacuation Simulation for Sto. Niño Senior High School, Tacloban City

Run with:  python -m uvicorn api:app --reload --port 8000
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from dynamic_evacuation import (
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS, BUILDING_NAMES,
    Observation, assess, route, all_routes, route_summary_counts,
    classify_threat, calculate_threat_index,
    SUPPORT_THRESHOLD, OBJECT_VERIFY_THRESHOLD, CRITICAL_INDEX,
)
from demo_detector import prebaked_scenarios
import database
from real_detector import (
    load_detections, observations_from_json, clear_detections,
    save_detections, analyze_video_feed,
)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
database.init_db()

app = FastAPI(
    title="SENTINEL — Campus Safety Command API",
    version="2.1.0",
    description="Acoustic-Visual Threat Detection and Evacuation Simulation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML/CSS/JS/Images)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

VIDEOS_DIR = Path(__file__).parent / "videos-project"
if VIDEOS_DIR.exists():
    app.mount("/videos-project", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")


# ---------------------------------------------------------------------------
# In-Memory Campus State
# ---------------------------------------------------------------------------
_state = {
    "scenario": "all_clear",
    "manual_blocks": [],
    "closed_edges": [],
    "unavailable_gates": [],
}


def _get_snapshot():
    """Build current campus assessment snapshot from active state."""
    obs = []

    if _state["scenario"] != "all_clear":
        scenarios = {s["name"]: s["observations"] for s in prebaked_scenarios()}
        label = _state["scenario"]
        if label in scenarios:
            obs = list(scenarios[label])
    else:
        live_records = load_detections()
        if live_records:
            obs_list, _ = observations_from_json()
            obs = obs_list

    snap = assess(
        obs,
        manual_blocks=_state["manual_blocks"],
        closed_edges=_state["closed_edges"],
        unavailable_gates=_state["unavailable_gates"],
    )
    return snap, obs


def _global_status(observations, snap=None):
    """Determine global campus status accounting for AI observations, gate closures, and manual blocks."""
    blocked_nodes = set(snap["blocked"]) if snap else set(_state["unavailable_gates"]) | set(_state["manual_blocks"])
    if any(o.level == "CRITICAL" for o in observations) or set(GATES).issubset(blocked_nodes):
        return "CRITICAL"
    if (
        any(o.level == "WARNING" for o in observations)
        or _state["unavailable_gates"]
        or _state["manual_blocks"]
        or _state["closed_edges"]
    ):
        return "WARNING"
    return "NORMAL"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    scenario: str  # "all_clear" | named prebaked key


class GateRequest(BaseModel):
    unavailable_gates: list[str]


class BlockRequest(BaseModel):
    manual_blocks: list[str]


class ThreatSimRequest(BaseModel):
    device_ids: list[str]
    level: str = "CRITICAL"
    acoustic: float = 85.0
    pose: float = 80.0
    object: float = 92.0
    incident_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes: Static Files
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Routes: Campus Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    """Global campus health: threat level, gate states, active scenario."""
    snap, obs = _get_snapshot()
    status = _global_status(obs, snap)
    blocked_set = set(snap["blocked"])

    gate_states = {}
    for g in GATES:
        gate_states[g] = "BLOCKED" if (g in _state["unavailable_gates"] or g in blocked_set) else "OPEN"

    try:
        database.update_gate_statuses(gate_states)
    except Exception:
        pass

    return {
        "status": status,
        "status_label": {
            "NORMAL": "ALL CLEAR — Campus Secure",
            "WARNING": "ELEVATED RISK — Caution Active",
            "CRITICAL": "EMERGENCY — Evacuate Now",
        }[status],
        "active_scenario": _state["scenario"],
        "gates": gate_states,
        "known_incidents": snap["known_incident_count"],
        "observation_count": snap["observation_count"],
        "blocked_nodes": list(snap["blocked"]),
        "caution_nodes": list(snap["caution"]),
        "unavailable_gates": _state["unavailable_gates"],
        "manual_blocks": _state["manual_blocks"],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/snapshot")
async def get_snapshot():
    """Full routing snapshot for all 36 rooms."""
    snap, obs = _get_snapshot()
    status = _global_status(obs, snap)
    counts = route_summary_counts(snap)

    routes_out = {}
    for rm in ROOMS:
        r = route(rm, snap)
        door_val = str(r.get("door") or "")
        routes_out[rm] = {
            "status": r["status"],
            "gate": r.get("gate"),
            "door": r.get("door"),
            "door_label": "Left Door" if door_val.endswith("-DL") else "Right Door" if door_val else None,
            "route": r.get("route", []),
            "cost": r.get("cost"),
            "reason": r.get("reason", ""),
        }

    events_out = []
    for ev in snap.get("events", []):
        if isinstance(ev, dict):
            events_out.append({
                "event_id": ev.get("event_id"),
                "device_id": ev.get("device") or ev.get("device_id"),
                "level": ev.get("level"),
                "count": ev.get("count_in_video") or ev.get("count", 1),
                "location": ev.get("possible_locations") or ev.get("location"),
                "incident_id": ev.get("incident_id"),
            })
        else:
            events_out.append({
                "event_id": getattr(ev, "event_id", ""),
                "device_id": getattr(ev, "device_id", ""),
                "level": getattr(ev, "level", "NORMAL"),
                "count": getattr(ev, "count", 1),
                "location": getattr(ev, "location", None),
                "incident_id": getattr(ev, "incident_id", None),
            })

    try:
        database.save_evacuation_states(routes_out)
    except Exception as e:
        print(f"Notice: evacuation_states db save: {e}")

    return {
        "global_status": status,
        "counts": counts,
        "routes": routes_out,
        "events": events_out,
        "blocked": list(snap["blocked"]),
        "caution": list(snap["caution"]),
        "known_incident_count": snap["known_incident_count"],
        "unique_threat_count": snap["unique_threat_count"],
        "possible_threat_locations": list(snap["possible_threat_locations"]),
        "note": snap["note"],
    }


@app.get("/api/route/{room_id}")
async def get_room_route(room_id: str):
    """Egress route for a single classroom."""
    if room_id not in ROOMS:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    snap, _ = _get_snapshot()
    r = route(room_id, snap)
    door_val = str(r.get("door") or "")
    return {
        "room": room_id,
        "status": r["status"],
        "gate": r.get("gate"),
        "door": r.get("door"),
        "door_label": "Left Door" if door_val.endswith("-DL") else "Right Door" if door_val else None,
        "route": r.get("route", []),
        "cost": r.get("cost"),
        "reason": r.get("reason", ""),
    }


@app.get("/api/rooms")
async def get_rooms():
    """List of all 36 room IDs."""
    return {"rooms": ROOMS}


@app.get("/api/devices")
async def get_devices():
    """All 26 camera devices with coverage metadata."""
    out = {}
    for dev_id, meta in DEVICES.items():
        zone = meta.get("zone", "indoor")
        cov = sorted(list(COVERAGE.get(dev_id, [])))
        rooms = [r for r in cov if r in ROOMS]
        node = cov[0] if cov and cov[0] not in ROOMS else None
        out[dev_id] = {
            "device_id": dev_id,
            "building": meta.get("building"),
            "floor": meta.get("floor"),
            "side": meta.get("side"),
            "zone": zone,
            "kind": zone,
            "covered_rooms": rooms,
            "covered_node": node,
        }
    return {"devices": out}


@app.get("/api/detections")
async def get_detections():
    """Raw detection records from detections.json."""
    records = load_detections()
    return {"detections": records, "count": len(records)}


@app.get("/api/scenarios")
async def get_scenarios():
    """Available prebaked drill scenarios."""
    scenarios = prebaked_scenarios()
    return {"scenarios": ["all_clear"] + [s["name"] for s in scenarios]}


@app.get("/api/buildings")
async def get_buildings():
    """Building metadata."""
    out = {}
    for b_code, (floors, rooms_per_floor) in BUILDINGS.items():
        out[b_code] = {
            "building_code": b_code,
            "name": BUILDING_NAMES.get(b_code, b_code),
            "floors": floors,
            "rooms_per_floor": rooms_per_floor,
            "total_rooms": floors * rooms_per_floor,
            "rooms": [f"{b_code}-F{f}-R{r}" for f in range(1, floors + 1) for r in range(1, rooms_per_floor + 1)],
        }
    return {"buildings": out}


# ---------------------------------------------------------------------------
# Routes: Control Endpoints (POST)
# ---------------------------------------------------------------------------
@app.post("/api/scenario")
async def set_scenario(req: ScenarioRequest):
    """Load a drill scenario by name."""
    valid = ["all_clear"] + [s["name"] for s in prebaked_scenarios()]
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown scenario. Valid: {valid}")
    _state["scenario"] = req.scenario
    try:
        database.log_audit("SET_SCENARIO", "OPERATOR", {"scenario": req.scenario})
    except Exception:
        pass
    return {"ok": True, "active_scenario": req.scenario}


@app.post("/api/gates")
async def set_gates(req: GateRequest):
    """Block/unblock emergency gates."""
    invalid = [g for g in req.unavailable_gates if g not in GATES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown gates: {invalid}")
    _state["unavailable_gates"] = req.unavailable_gates
    try:
        database.log_audit("SET_GATES", "OPERATOR", {"unavailable_gates": req.unavailable_gates})
    except Exception:
        pass
    return {"ok": True, "unavailable_gates": _state["unavailable_gates"]}


@app.post("/api/blocks")
async def set_blocks(req: BlockRequest):
    """Manually block nodes (stairwells, corridors, classrooms)."""
    _state["manual_blocks"] = req.manual_blocks
    try:
        database.log_audit("SET_BLOCKS", "OPERATOR", {"manual_blocks": req.manual_blocks})
    except Exception:
        pass
    return {"ok": True, "manual_blocks": _state["manual_blocks"]}


@app.post("/api/reset")
async def reset_state():
    """Reset campus state to all-clear, clear detections."""
    _state["scenario"] = "all_clear"
    _state["manual_blocks"] = []
    _state["closed_edges"] = []
    _state["unavailable_gates"] = []
    clear_detections()
    try:
        database.update_gate_statuses({g: "OPEN" for g in GATES})
        database.log_audit("RESET_STATE", "OPERATOR", {"status": "ALL_CLEAR"})
    except Exception:
        pass
    return {"ok": True, "message": "Campus state reset to normal."}


@app.post("/api/simulate-threat")
async def simulate_threat(req: ThreatSimRequest):
    """Simulate a threat detection on specified camera device(s)."""
    current_records = load_detections()
    incident_id = req.incident_id or f"inc-{uuid.uuid4().hex[:6]}"
    clf = classify_threat(req.acoustic, req.pose, req.object)

    for did in req.device_ids:
        if did not in DEVICES:
            continue
        rec = {
            "source": "manual_mock_simulator",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "device_id": did,
            "event_id": f"sim-{uuid.uuid4().hex[:6]}",
            "incident_id": incident_id,
            "scores": {"acoustic": req.acoustic, "pose": req.pose, "object": req.object},
            "object_stats": {"frames_analyzed": 1, "frames_with_threat": int(req.object > 50)},
            "pose_stats": {"pose_score": req.pose},
            "acoustic_stats": {"score": req.acoustic},
            "classification": clf,
        }
        current_records.append(rec)

    save_detections(current_records)
    _state["scenario"] = "all_clear"
    try:
        database.log_audit("SIMULATE_THREAT", "OPERATOR", {"devices": req.device_ids, "classification": clf})
    except Exception:
        pass
    return {"ok": True, "count": len(req.device_ids), "classification": clf}


@app.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    device_ids: str = Form("TPB-F1-CAM-L"),
):
    """Upload a video file, run fast 3-Criteria YOLOv8 & acoustic threat analysis, update detections.json."""
    dev_list = [d.strip() for d in device_ids.split(",") if d.strip() in DEVICES]
    if not dev_list:
        raise HTTPException(status_code=400, detail="No valid device_ids provided.")

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "upload.mp4")
    VIDEOS_DIR.mkdir(exist_ok=True)
    save_path = VIDEOS_DIR / f"upload_{uuid.uuid4().hex[:6]}_{safe_name}"
    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    incident_id = f"inc-{uuid.uuid4().hex[:6]}"
    current_records = load_detections()

    try:
        base_rec = analyze_video_feed(
            str(save_path),
            device_id=dev_list[0],
            incident_id=incident_id,
            sample_frames=8,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

    for did in dev_list:
        c_rec = dict(base_rec)
        c_rec["device_id"] = did
        c_rec["event_id"] = f"ai-{uuid.uuid4().hex[:6]}"
        c_rec["video_url"] = f"/videos-project/{save_path.name}"
        current_records.append(c_rec)

    save_detections(current_records)
    _state["scenario"] = "all_clear"

    clf = base_rec.get("classification", {})
    level = clf.get("level", "NORMAL")
    passed = level in ("CRITICAL", "WARNING")
    breakdown = base_rec.get("criteria_breakdown", {})
    scan_ms = breakdown.get("scan_ms", 0.0)

    try:
        database.log_audit("UPLOAD_VIDEO", "OPERATOR", {
            "devices": dev_list,
            "file": safe_name,
            "level": level,
            "threat_index": clf.get("index", 0.0),
            "scan_ms": scan_ms,
        })
    except Exception:
        pass

    return {
        "ok": True,
        "devices": dev_list,
        "device_id": dev_list[0],
        "records_added": len(dev_list),
        "level": level,
        "threat_index": clf.get("index", 0.0),
        "object_score": base_rec.get("scores", {}).get("object", 0.0),
        "pose_score": base_rec.get("scores", {}).get("pose", 0.0),
        "acoustic_score": base_rec.get("scores", {}).get("acoustic", 0.0),
        "supporting_signals": clf.get("supporting_signals", 0),
        "verified": clf.get("verified", False),
        "criteria_passed": passed,
        "criteria_breakdown": breakdown,
        "scan_ms": scan_ms,
        "frames_analyzed": base_rec.get("object_stats", {}).get("frames_analyzed", 0),
        "early_exit": base_rec.get("object_stats", {}).get("early_exit", False),
        "video_url": f"/videos-project/{save_path.name}",
        "message": (
            f"THREAT VERIFIED: {level} (Index {clf.get('index', 0):.1f}/100 · {scan_ms:.0f}ms). Evacuation simulation active!"
            if passed
            else f"Criteria Not Met: {level} (Index {clf.get('index', 0):.1f}/100 · {scan_ms:.0f}ms). Campus remains ALL CLEAR."
        )
    }


@app.post("/api/detections/clear")
async def clear_detections_endpoint():
    """Clear all records from detections.json."""
    clear_detections()
    return {"ok": True, "message": "All detection records cleared."}


# ---------------------------------------------------------------------------
# MQTT Telemetry (non-blocking)
# ---------------------------------------------------------------------------
def _mqtt_broadcast():
    try:
        import paho.mqtt.client as mqtt
        _, obs = _get_snapshot()
        status = _global_status(obs)
        gates_open = ",".join(g for g in GATES if g not in _state["unavailable_gates"]) or "NONE"
        client = mqtt.Client(client_id=f"sentinel_{uuid.uuid4().hex[:6]}")
        client.connect("broker.hivemq.com", 1883, 2)
        client.publish("stonino/campus/alert", json.dumps({
            "status": status,
            "gates": gates_open,
            "time": datetime.now().strftime("%H:%M:%S"),
        }))
        client.disconnect()
    except Exception:
        pass


@app.get("/api/mqtt/broadcast")
async def mqtt_broadcast():
    """Trigger MQTT broadcast to Wokwi ESP32 (non-blocking)."""
    threading.Thread(target=_mqtt_broadcast, daemon=True).start()
    return {"ok": True, "message": "MQTT broadcast dispatched."}


# ---------------------------------------------------------------------------
# Database Management Endpoints (DBA & Audit)
# ---------------------------------------------------------------------------
@app.get("/api/db/stats")
async def get_db_stats():
    """Return database metrics, table record counts, and storage metrics."""
    try:
        stats = database.get_database_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/incidents")
async def get_db_incidents():
    """List threat incidents recorded in sentinel.db."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_incidents ORDER BY started_at DESC LIMIT 50;")
            rows = [dict(r) for r in cursor.fetchall()]
            return {"ok": True, "incidents": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/audit-logs")
async def get_db_audit_logs():
    """List administrative audit trail records."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_audit_logs ORDER BY created_at DESC LIMIT 50;")
            rows = [dict(r) for r in cursor.fetchall()]
            return {"ok": True, "audit_logs": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
