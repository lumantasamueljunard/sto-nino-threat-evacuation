"""
SENTINEL FastAPI Backend
Official Title: Microcontroller-Based Acoustic-Visual Threat Detection and
Evacuation Simulation for Sto. Niño Senior High School, Tacloban City

Run with:  uvicorn api:app --reload --port 8000
"""
import json
import os
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
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS,
    Observation, assess, route, all_routes, route_summary_counts,
    classify_threat, calculate_threat_index,
)
from demo_detector import prebaked_scenarios
from real_detector import (
    load_detections, observations_from_json, clear_detections,
    save_detections, analyze_video_feed,
)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SENTINEL — Campus Safety Command API",
    version="2.0.0",
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
        scenarios = dict(prebaked_scenarios())
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


def _global_status(observations):
    if any(o.level == "CRITICAL" for o in observations):
        return "CRITICAL"
    if any(o.level == "WARNING" for o in observations) or _state["unavailable_gates"]:
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
    status = _global_status(obs)

    gate_states = {}
    for g in GATES:
        gate_states[g] = "BLOCKED" if g in _state["unavailable_gates"] else "OPEN"

    return {
        "status": status,
        "status_label": {
            "NORMAL": "ALL CLEAR — Campus Secure",
            "WARNING": "ELEVATED RISK — Caution",
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
    status = _global_status(obs)
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
    s = dict(prebaked_scenarios())
    return {"scenarios": ["all_clear"] + list(s.keys())}


@app.get("/api/buildings")
async def get_buildings():
    """Building metadata."""
    out = {}
    for b_num, (floors, rooms_per_floor) in BUILDINGS.items():
        out[f"B{b_num}"] = {
            "building_num": b_num,
            "floors": floors,
            "rooms_per_floor": rooms_per_floor,
            "total_rooms": floors * rooms_per_floor,
            "rooms": [f"B{b_num}-F{f}-R{r}" for f in range(1, floors + 1) for r in range(1, rooms_per_floor + 1)],
        }
    return {"buildings": out}


# ---------------------------------------------------------------------------
# Routes: Control Endpoints (POST)
# ---------------------------------------------------------------------------
@app.post("/api/scenario")
async def set_scenario(req: ScenarioRequest):
    """Load a drill scenario by name."""
    valid = ["all_clear"] + list(dict(prebaked_scenarios()).keys())
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown scenario. Valid: {valid}")
    _state["scenario"] = req.scenario
    return {"ok": True, "active_scenario": req.scenario}


@app.post("/api/gates")
async def set_gates(req: GateRequest):
    """Block/unblock emergency gates."""
    invalid = [g for g in req.unavailable_gates if g not in GATES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown gates: {invalid}")
    _state["unavailable_gates"] = req.unavailable_gates
    return {"ok": True, "unavailable_gates": _state["unavailable_gates"]}


@app.post("/api/blocks")
async def set_blocks(req: BlockRequest):
    """Manually block nodes (stairwells, corridors)."""
    _state["manual_blocks"] = req.manual_blocks
    return {"ok": True, "manual_blocks": _state["manual_blocks"]}


@app.post("/api/reset")
async def reset_state():
    """Reset campus state to all-clear, clear detections."""
    _state["scenario"] = "all_clear"
    _state["manual_blocks"] = []
    _state["closed_edges"] = []
    _state["unavailable_gates"] = []
    clear_detections()
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
    return {"ok": True, "count": len(req.device_ids), "classification": clf}


@app.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    device_ids: str = Form("B1-F1-CAM-L"),
):
    """Upload a video file, run YOLOv8 & acoustic threat analysis, update detections.json."""
    dev_list = [d.strip() for d in device_ids.split(",") if d.strip() in DEVICES]
    if not dev_list:
        raise HTTPException(status_code=400, detail="No valid device_ids provided.")
    
    VIDEOS_DIR.mkdir(exist_ok=True)
    save_path = VIDEOS_DIR / f"upload_{uuid.uuid4().hex[:6]}_{file.filename}"
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
            sample_frames=20,
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
    return {"ok": True, "devices": dev_list, "records_added": len(dev_list)}


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
