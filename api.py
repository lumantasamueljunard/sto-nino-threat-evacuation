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

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from dynamic_evacuation import (
    ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS, BUILDING_NAMES,
    Observation, assess, route, all_routes, route_summary_counts,
    classify_threat, calculate_threat_index, _expand_unavailable_nodes,
    SUPPORT_THRESHOLD, OBJECT_VERIFY_THRESHOLD, CRITICAL_INDEX,
)
from demo_detector import prebaked_scenarios
import database
from mqtt_bridge import bridge
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
def _load_persisted_facilities():
    try:
        return [r["node_id"] for r in database.get_facility_overrides()]
    except Exception:
        return []


_state = {
    "scenario": "all_clear",
    "manual_blocks": [],
    "closed_edges": [],
    "unavailable_gates": [],
    "unavailable_nodes": _load_persisted_facilities(),
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
        unavailable_nodes=_state["unavailable_nodes"],
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
def _compute_hardware_context():
    """Build current status, gate states, counts, and routes map for MQTT/Twin sync."""
    snap, obs = _get_snapshot()
    status = _global_status(obs, snap)
    blocked_set = set(snap["blocked"])
    gate_states = {
        g: "BLOCKED" if (g in _state["unavailable_gates"] or g in blocked_set) else "OPEN"
        for g in GATES
    }
    counts = route_summary_counts(snap)
    routes_out = {rm: route(rm, snap) for rm in ROOMS}
    return status, routes_out, gate_states, counts


def _sync_hardware():
    """Push latest campus state to persistent MQTT bridge (non-blocking)."""
    try:
        status, routes_out, gate_states, counts = _compute_hardware_context()
        return bridge.publish_state(
            status, routes_out, gate_states, counts, _state["unavailable_gates"]
        )
    except Exception:
        return None


def _handle_hardware_trigger(payload: dict):
    """Ingest inbound trigger or reset packet sent from Wokwi ESP32 over MQTT."""
    action = str(payload.get("action", "TRIGGER")).upper()
    if action == "RESET":
        _state["scenario"] = "all_clear"
        _state["manual_blocks"] = []
        _state["closed_edges"] = []
        _state["unavailable_gates"] = []
        clear_detections()
        database.update_gate_statuses({g: "OPEN" for g in GATES})
        database.log_audit("HARDWARE_RESET", payload.get("device_id", "ESP32-CAMPUS-GW01"), payload)
        _sync_hardware()
        return

    target_node = str(payload.get("target_device", "TPB-F1-CAM-L"))
    if target_node not in DEVICES:
        target_node = "TPB-F1-CAM-L"

    acoustic = float(payload.get("acoustic", 88.0))
    pose = float(payload.get("pose", 76.0))
    obj = float(payload.get("object", 85.0))
    clf = classify_threat(acoustic, pose, obj)

    current_records = load_detections()
    current_records.append({
        "source": payload.get("source", "wokwi_esp32_hardware"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "device_id": target_node,
        "event_id": f"hw-{uuid.uuid4().hex[:6]}",
        "incident_id": f"inc-{uuid.uuid4().hex[:6]}",
        "scores": {"acoustic": acoustic, "pose": pose, "object": obj},
        "object_stats": {"frames_analyzed": 1, "frames_with_threat": int(obj >= 60)},
        "pose_stats": {"pose_score": pose},
        "acoustic_stats": {"score": acoustic},
        "classification": clf,
    })
    save_detections(current_records)
    _state["scenario"] = "all_clear"
    database.log_audit("HARDWARE_TRIGGER", payload.get("device_id", "ESP32-CAMPUS-GW01"), payload)
    _sync_hardware()


bridge.set_trigger_handler(_handle_hardware_trigger)
bridge.start()


class ScenarioRequest(BaseModel):
    scenario: str  # "all_clear" | named prebaked key


class GateRequest(BaseModel):
    unavailable_gates: list[str]


class BlockRequest(BaseModel):
    manual_blocks: list[str]


class FacilityOverrideRequest(BaseModel):
    unavailable_nodes: list[str]
    assigned_by: str = "PERSONNEL"


class ResolveIncidentRequest(BaseModel):
    notes: str = "Threat apprehended and campus perimeter secured."
    resolved_by: str = "DRRM_OFFICER"


# ---------------------------------------------------------------------------
# Role-Based Authentication & Authorization (PERSONNEL & IT_TECHNICIAN)
# ---------------------------------------------------------------------------
REG_CODES = {
    "PERSONNEL": os.environ.get("SENTINEL_CODE_PERSONNEL", "SNSHS-PERSONNEL-2026"),
    "IT_TECHNICIAN": os.environ.get("SENTINEL_CODE_IT", "SNSHS-IT-2026"),
}


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def require_staff(authorization: Optional[str] = Header(default=None)) -> dict:
    """Require an authenticated PERSONNEL or IT_TECHNICIAN session."""
    user = database.get_session_user(_extract_bearer(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required (Personnel or IT Technician).")
    return user


def require_it(authorization: Optional[str] = Header(default=None)) -> dict:
    """Require an authenticated IT_TECHNICIAN session."""
    user = database.get_session_user(_extract_bearer(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="IT Technician authentication required.")
    if user["role"] != "IT_TECHNICIAN":
        raise HTTPException(status_code=403, detail="Access restricted to IT Technician role.")
    return user


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    full_name: str
    role: str
    password: str
    auth_code: str


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Authenticate Personnel or IT Technician account."""
    sess = database.authenticate_user(req.username, req.password)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"ok": True, **sess}


@app.post("/api/auth/register")
async def auth_register(req: RegisterRequest):
    """Register a new Personnel or IT Technician account using an authorized staff code."""
    role = req.role.strip().upper()
    if role not in ("PERSONNEL", "IT_TECHNICIAN"):
        raise HTTPException(status_code=400, detail="Role must be PERSONNEL or IT_TECHNICIAN.")
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(req.full_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Full name is required.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    expected_code = REG_CODES[role]
    if req.auth_code.strip() != expected_code:
        raise HTTPException(status_code=403, detail=f"Invalid authorization code for {role}.")

    try:
        user = database.create_user(req.username, req.full_name, role, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    sess = database.authenticate_user(req.username, req.password)
    return {"ok": True, **sess}


@app.post("/api/auth/logout")
async def auth_logout(authorization: Optional[str] = Header(default=None)):
    """Revoke active session token."""
    database.revoke_session(_extract_bearer(authorization))
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(authorization: Optional[str] = Header(default=None)):
    """Return current authenticated user or {authenticated: false}."""
    user = database.get_session_user(_extract_bearer(authorization))
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteUserRequest(BaseModel):
    password: str


@app.get("/api/auth/users")
async def auth_users(user: dict = Depends(require_it)):
    """IT Technician-only: list registered personnel and IT accounts."""
    return {"ok": True, "users": database.list_users()}


@app.post("/api/auth/change-password")
async def auth_change_password(req: ChangePasswordRequest, user: dict = Depends(require_staff)):
    """Authenticated Personnel or IT Technician: change own password and log the update."""
    try:
        res = database.change_user_password(user["user_id"], req.current_password, req.new_password)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "message": "Password updated successfully.", **res}


@app.post("/api/auth/users/{target_user_id}/delete")
async def auth_delete_user(target_user_id: int, req: DeleteUserRequest, user: dict = Depends(require_it)):
    """IT Technician-only: password-confirmed account deletion respecting Main IT hierarchy."""
    if not req.password:
        raise HTTPException(status_code=400, detail="Your IT Technician password is required to confirm deletion.")
    try:
        res = database.delete_user_account(user["user_id"], req.password, target_user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "message": f"Account '{res['deleted_username']}' has been deleted.", **res}


@app.get("/api/auth/activity-logs")
async def auth_activity_logs(
    scope: str = "all",
    category: str = "all",
    limit: int = 120,
    user: dict = Depends(require_staff),
):
    """Role-scoped account activity logs.

    - Personnel strictly receive only their own login, logout, and password-change logs.
    - IT Technicians receive all Personnel & IT Technician account logs (or scope='mine').
    """
    logs = database.get_account_activity_logs(user, scope=scope, category=category, limit=limit)
    return {"ok": True, "role": user["role"], "is_main_it": bool(user.get("is_main_it")), "logs": logs}


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
        "unavailable_nodes": _state["unavailable_nodes"],
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
        "unavailable": list(snap.get("unavailable", [])),
        "unavailable_raw": list(snap.get("unavailable_raw", [])),
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
async def get_detections(user: dict = Depends(require_staff)):
    """Raw detection records from detections.json (Personnel/IT only)."""
    records = load_detections()
    return {"detections": records, "count": len(records)}


@app.get("/api/scenarios")
async def get_scenarios(user: dict = Depends(require_staff)):
    """Available prebaked drill scenarios (Personnel/IT only)."""
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
async def set_scenario(req: ScenarioRequest, user: dict = Depends(require_staff)):
    """Load a drill scenario by name."""
    valid = ["all_clear"] + [s["name"] for s in prebaked_scenarios()]
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown scenario. Valid: {valid}")
    _state["scenario"] = req.scenario
    if req.scenario == "all_clear":
        clear_detections()
    try:
        database.log_audit("SET_SCENARIO", f"{user['username']} ({user['role']})", {"scenario": req.scenario})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "active_scenario": req.scenario}


@app.post("/api/gates")
async def set_gates(req: GateRequest, user: dict = Depends(require_staff)):
    """Block/unblock emergency gates."""
    invalid = [g for g in req.unavailable_gates if g not in GATES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown gates: {invalid}")
    _state["unavailable_gates"] = req.unavailable_gates
    try:
        database.log_audit("SET_GATES", f"{user['username']} ({user['role']})", {"unavailable_gates": req.unavailable_gates})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "unavailable_gates": _state["unavailable_gates"]}


@app.post("/api/blocks")
async def set_blocks(req: BlockRequest, user: dict = Depends(require_staff)):
    """Manually block nodes (threat-level overrides)."""
    _state["manual_blocks"] = req.manual_blocks
    try:
        database.log_audit("SET_BLOCKS", f"{user['username']} ({user['role']})", {"manual_blocks": req.manual_blocks})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "manual_blocks": _state["manual_blocks"]}


@app.post("/api/facility-overrides")
async def set_facility_overrides(req: FacilityOverrideRequest, user: dict = Depends(require_staff)):
    """Personnel assignment of non-threat unavailable rooms, corridors, or staircases."""
    try:
        _expand_unavailable_nodes(req.unavailable_nodes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    deduped = list(dict.fromkeys(req.unavailable_nodes))
    _state["unavailable_nodes"] = deduped
    actor = f"{user['username']} ({user['role']})"
    try:
        database.replace_facility_overrides(deduped, assigned_by=actor)
        database.log_audit("SET_FACILITY_OVERRIDES", actor, {"unavailable_nodes": deduped})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "unavailable_nodes": _state["unavailable_nodes"]}


@app.post("/api/reset")
async def reset_state(user: dict = Depends(require_staff)):
    """Reset campus state to all-clear, clear detections."""
    _state["scenario"] = "all_clear"
    _state["manual_blocks"] = []
    _state["closed_edges"] = []
    _state["unavailable_gates"] = []
    clear_detections()
    try:
        database.update_gate_statuses({g: "OPEN" for g in GATES})
        database.log_audit("RESET_STATE", f"{user['username']} ({user['role']})", {"status": "ALL_CLEAR"})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "message": "Campus state reset to normal."}


@app.post("/api/incidents/resolve")
async def resolve_incidents(req: ResolveIncidentRequest, user: dict = Depends(require_staff)):
    """Stand-down campus emergency once threat is apprehended or evacuation is secured."""
    _state["scenario"] = "all_clear"
    _state["manual_blocks"] = []
    _state["closed_edges"] = []
    _state["unavailable_gates"] = []

    clear_detections()

    resolved_count = 0
    actor = f"{user['username']} ({user['role']})"
    try:
        resolved_count = database.resolve_active_incidents(
            resolution_notes=req.notes,
            resolved_by=actor,
        )
        database.update_gate_statuses({g: "OPEN" for g in GATES})
    except Exception:
        pass

    _sync_hardware()
    return {
        "ok": True,
        "resolved_incidents": resolved_count,
        "status": "NORMAL",
        "message": f"Stand-down complete: {req.notes}",
    }


@app.post("/api/simulate-threat")
async def simulate_threat(req: ThreatSimRequest, user: dict = Depends(require_staff)):
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
        database.log_audit("SIMULATE_THREAT", f"{user['username']} ({user['role']})", {"devices": req.device_ids, "classification": clf})
    except Exception:
        pass
    _sync_hardware()
    return {"ok": True, "count": len(req.device_ids), "classification": clf}


@app.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    device_ids: str = Form("TPB-F1-CAM-L"),
    user: dict = Depends(require_staff),
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
            sample_frames=12,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

    clf = base_rec.get("classification", {})
    level = clf.get("level", "NORMAL")
    verified_critical = bool(clf.get("verified") and level == "CRITICAL")
    has_alert = level in ("CRITICAL", "WARNING")
    breakdown = base_rec.get("criteria_breakdown", {})
    scan_ms = breakdown.get("scan_ms", 0.0)

    if has_alert:
        for did in dev_list:
            c_rec = dict(base_rec)
            c_rec["device_id"] = did
            c_rec["event_id"] = f"ai-{uuid.uuid4().hex[:6]}"
            c_rec["video_url"] = f"/videos-project/{save_path.name}"
            current_records.append(c_rec)

        save_detections(current_records)
        _state["scenario"] = "all_clear"
        _sync_hardware()

    actor = f"{user['username']} ({user['role']})"
    try:
        audit_evt = "UPLOAD_VIDEO_CRITICAL" if verified_critical else "UPLOAD_VIDEO_WARNING" if has_alert else "UPLOAD_VIDEO_STANDBY"
        database.log_audit(audit_evt, actor, {
            "devices": dev_list,
            "file": safe_name,
            "level": level,
            "threat_index": clf.get("index", 0.0),
            "scan_ms": scan_ms,
            "evacuation_activated": verified_critical,
        })
    except Exception:
        pass

    if verified_critical:
        msg = f"THREAT VERIFIED: CRITICAL (Index {clf.get('index', 0):.1f}/100 · {scan_ms:.0f}ms). Evacuation simulation active!"
    elif level == "WARNING":
        msg = f"CAUTION ALERT (WARNING · Index {clf.get('index', 0):.1f}/100 · {scan_ms:.0f}ms). Monitor zone — CRITICAL threshold not met."
    else:
        msg = f"Criteria Not Met: NORMAL (Index {clf.get('index', 0):.1f}/100 · {scan_ms:.0f}ms). Campus remains ALL CLEAR."

    return {
        "ok": True,
        "devices": dev_list,
        "device_id": dev_list[0],
        "records_added": len(dev_list) if has_alert else 0,
        "level": level,
        "threat_index": clf.get("index", 0.0),
        "object_score": base_rec.get("scores", {}).get("object", 0.0),
        "pose_score": base_rec.get("scores", {}).get("pose", 0.0),
        "acoustic_score": base_rec.get("scores", {}).get("acoustic", 0.0),
        "supporting_signals": clf.get("supporting_signals", 0),
        "verified": clf.get("verified", False),
        "criteria_passed": verified_critical,
        "criteria_breakdown": breakdown,
        "scan_ms": scan_ms,
        "frames_analyzed": base_rec.get("object_stats", {}).get("frames_analyzed", 0),
        "early_exit": base_rec.get("object_stats", {}).get("early_exit", False),
        "video_url": f"/videos-project/{save_path.name}",
        "message": msg,
    }


@app.post("/api/detections/clear")
async def clear_detections_endpoint(user: dict = Depends(require_staff)):
    """Clear all records from detections.json."""
    clear_detections()
    _sync_hardware()
    return {"ok": True, "message": "All detection records cleared."}


# ---------------------------------------------------------------------------
# Hardware Digital Twin & Persistent MQTT Telemetry
# ---------------------------------------------------------------------------
class EdgeTriggerRequest(BaseModel):
    action: str = "TRIGGER"
    target_device: str = "TPB-F1-CAM-L"
    acoustic: float = 88.0
    pose: float = 76.0
    object: float = 85.0


@app.get("/api/mqtt/broadcast")
async def mqtt_broadcast(user: dict = Depends(require_it)):
    """Trigger immediate MQTT state sync to Wokwi ESP32 (IT Technician only)."""
    threading.Thread(target=_sync_hardware, daemon=True).start()
    return {"ok": True, "message": "MQTT state broadcast dispatched."}


@app.get("/api/hardware/status")
async def get_hardware_status(user: dict = Depends(require_it)):
    """Return live Hardware Digital Twin status, 12 LEDs, and MQTT packet stream (IT Technician only)."""
    status, routes_out, gate_states, counts = _compute_hardware_context()
    return bridge.get_twin_status(
        status, routes_out, gate_states, counts, _state["unavailable_gates"]
    )


@app.post("/api/hardware/sync")
async def sync_hardware_now(user: dict = Depends(require_it)):
    """Force immediate state packet transmission to ESP32 zone controller (IT Technician only)."""
    payload = _sync_hardware()
    return {"ok": True, "telemetry": payload}


@app.post("/api/hardware/simulate-edge")
async def simulate_edge_trigger(req: EdgeTriggerRequest, user: dict = Depends(require_it)):
    """Simulate an ESP32 hardware Break-Glass / acoustic trigger flowing back to the dashboard."""
    packet = {
        "device_id": "ESP32-CAMPUS-GW01",
        "action": req.action.upper(),
        "target_device": req.target_device,
        "acoustic": req.acoustic,
        "pose": req.pose,
        "object": req.object,
        "source": "esp32_edge_hardware",
    }
    bridge._record_packet("RX", "stonino/campus/device/trigger", packet)
    _handle_hardware_trigger(packet)
    return {"ok": True, "packet": packet}


# ---------------------------------------------------------------------------
# Database Management Endpoints (DBA & Audit)
# ---------------------------------------------------------------------------
@app.get("/api/db/stats")
async def get_db_stats(user: dict = Depends(require_it)):
    """Return database metrics, table record counts, and storage metrics (IT Technician only)."""
    try:
        stats = database.get_database_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/incidents")
async def get_db_incidents(user: dict = Depends(require_staff)):
    """List threat incidents recorded in sentinel.db (Personnel/IT only)."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_incidents ORDER BY started_at DESC LIMIT 50;")
            rows = [dict(r) for r in cursor.fetchall()]
            return {"ok": True, "incidents": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/audit-logs")
async def get_db_audit_logs(user: dict = Depends(require_it)):
    """List administrative audit trail records (IT Technician only)."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_audit_logs ORDER BY created_at DESC LIMIT 50;")
            rows = [dict(r) for r in cursor.fetchall()]
            return {"ok": True, "audit_logs": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
