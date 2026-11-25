"""Database management module for SENTINEL Campus Threat Evacuation System.

Implements a relational SQLite database (sentinel.db) adhering to:
- Third Normal Form (3NF) relational architecture
- Write-Ahead Logging (WAL) for high concurrency
- Explicit foreign key constraints and validation checks
- Comprehensive indexing on foreign keys, timestamps, and query paths
- Versioned schema migrations for seamless future updates
- Audit logging for administrative traceability
"""

import hashlib
import hmac
import os
import json
import secrets
import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Database Configuration & File Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "sentinel.db")
SCHEMA_VERSION = 3


@contextmanager
def get_db_connection(db_path=DB_FILE):
    """Context manager providing a configured SQLite database connection.
    
    Enforces DBA best practices:
    - Foreign key constraints enabled
    - Row factory enabled for dictionary-like column access
    - WAL journal mode for concurrent read/write throughput
    - Automatic commit on exit, rollback on exception
    """
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema Migrations & Initialization
# ---------------------------------------------------------------------------
def init_db(db_path=DB_FILE):
    """Initialize database tables, indexes, and apply versioned migrations."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 0. Migrations Tracking Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Check latest applied migration
        cursor.execute("SELECT MAX(version) FROM schema_migrations;")
        current_version = cursor.fetchone()[0] or 0

        if current_version < 1:
            _apply_migration_v1(cursor)
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?);",
                (1, "Baseline 3NF normalized schema for SENTINEL campus safety system.")
            )

        if current_version < 2:
            _apply_migration_v2(cursor)
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?);",
                (2, "Add facility_overrides table and FACILITY_UNAVAILABLE directive support.")
            )

        if current_version < 3:
            _apply_migration_v3(cursor)
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?);",
                (3, "Add RBAC users and persistent user_sessions tables for Personnel and IT Technician auth.")
            )

        if current_version < 4:
            _apply_migration_v4(cursor)
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?);",
                (4, "Add is_main_it flag to users for Main IT Technician account deletion protection.")
            )

    # Seed static campus topology and default staff accounts if tables are empty
    seed_static_data(db_path)


def _apply_migration_v4(cursor):
    """Migration V4: Mark the primary IT Technician account as protected Main IT."""
    cursor.execute("PRAGMA table_info(users);")
    cols = {row[1] for row in cursor.fetchall()}
    if "is_main_it" not in cols:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN is_main_it INTEGER NOT NULL DEFAULT 0 CHECK (is_main_it IN (0, 1));"
        )
    # Flag the seeded 'it.tech' account as Main IT Technician (or earliest IT_TECHNICIAN if renamed)
    cursor.execute("UPDATE users SET is_main_it = 1 WHERE username = 'it.tech' AND role = 'IT_TECHNICIAN';")
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_main_it = 1;")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """UPDATE users SET is_main_it = 1
               WHERE user_id = (
                   SELECT user_id FROM users WHERE role = 'IT_TECHNICIAN' ORDER BY user_id ASC LIMIT 1
               );"""
        )


def _apply_migration_v3(cursor):
    """Migration V3: Create users and user_sessions tables for role-based access control."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('PERSONNEL', 'IT_TECHNICIAN')),
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE CASCADE
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);")


def _apply_migration_v2(cursor):
    """Migration V2: Support persisted non-threat personnel facility unavailability."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facility_overrides (
            node_id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL DEFAULT 'room' CHECK (node_type IN ('room', 'corridor', 'corridor_floor', 'stair')),
            condition TEXT NOT NULL DEFAULT 'UNAVAILABLE',
            assigned_by TEXT NOT NULL DEFAULT 'PERSONNEL',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Rebuild evacuation_states so directive CHECK allows FACILITY_UNAVAILABLE cleanly
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evacuation_states_v2 (
            room_id TEXT PRIMARY KEY,
            chosen_gate TEXT,
            chosen_door TEXT,
            path_sequence TEXT,
            path_cost REAL NOT NULL DEFAULT 0.0,
            directive TEXT NOT NULL CHECK (directive IN ('MODELED_ROUTE_AVAILABLE', 'HOLD_FOR_AUTHORIZED_GUIDANCE', 'NO_CONFIRMED_ROUTE', 'FACILITY_UNAVAILABLE')),
            reason TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (chosen_gate) REFERENCES campus_gates(gate_id) ON UPDATE CASCADE ON DELETE SET NULL,
            FOREIGN KEY (chosen_door) REFERENCES room_doors(door_id) ON UPDATE CASCADE ON DELETE SET NULL
        );
    """)
    cursor.execute("INSERT OR IGNORE INTO evacuation_states_v2 SELECT * FROM evacuation_states;")
    cursor.execute("DROP TABLE evacuation_states;")
    cursor.execute("ALTER TABLE evacuation_states_v2 RENAME TO evacuation_states;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evac_dir ON evacuation_states(directive);")


def _apply_migration_v1(cursor):
    """Migration V1: Create all 8 normalized 3NF tables and audit logging."""

    # 1. Buildings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            building_code TEXT PRIMARY KEY,
            building_name TEXT NOT NULL,
            total_floors INTEGER NOT NULL CHECK (total_floors > 0),
            rooms_per_floor INTEGER NOT NULL CHECK (rooms_per_floor > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Rooms Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            building_code TEXT NOT NULL,
            floor_no INTEGER NOT NULL CHECK (floor_no > 0),
            room_no INTEGER NOT NULL CHECK (room_no > 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (building_code) REFERENCES buildings(building_code) ON UPDATE CASCADE ON DELETE RESTRICT
        );
    """)

    # 3. Room Doors Table (Enforcing dual-door modeling per classroom)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_doors (
            door_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            door_label TEXT NOT NULL,
            corridor_node TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON UPDATE CASCADE ON DELETE CASCADE
        );
    """)

    # 4. Campus Gates Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campus_gates (
            gate_id TEXT PRIMARY KEY,
            gate_name TEXT NOT NULL,
            coordinates_x REAL NOT NULL,
            coordinates_y REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'BLOCKED', 'COMPROMISED')),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 5. Devices Table (26 IoT Cameras and Acoustic Nodes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            building_code TEXT,
            device_type TEXT NOT NULL CHECK (device_type IN ('indoor_cam', 'outdoor_cam', 'acoustic_sensor')),
            floor_no INTEGER NOT NULL DEFAULT 0,
            zone_type TEXT NOT NULL CHECK (zone_type IN ('indoor', 'outdoor')),
            covered_rooms TEXT, -- JSON array of covered room IDs or node string
            status TEXT NOT NULL DEFAULT 'ONLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'ALERT', 'STANDBY')),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (building_code) REFERENCES buildings(building_code) ON UPDATE CASCADE ON DELETE SET NULL
        );
    """)

    # 6. Threat Incidents Table (Emergency Event Sessions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS threat_incidents (
            incident_id TEXT PRIMARY KEY,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            severity_level TEXT NOT NULL DEFAULT 'NORMAL' CHECK (severity_level IN ('NORMAL', 'WARNING', 'CRITICAL')),
            root_location TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RESOLVED', 'DRILL')),
            notes TEXT
        );
    """)

    # 7. Threat Detections Table (AI Scoring & Sensory Readings)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS threat_detections (
            detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            incident_id TEXT,
            device_id TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'live_video_analysis',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acoustic_score REAL NOT NULL DEFAULT 0.0 CHECK (acoustic_score BETWEEN 0.0 AND 100.0),
            pose_score REAL NOT NULL DEFAULT 0.0 CHECK (pose_score BETWEEN 0.0 AND 100.0),
            object_score REAL NOT NULL DEFAULT 0.0 CHECK (object_score BETWEEN 0.0 AND 100.0),
            threat_index REAL NOT NULL DEFAULT 0.0 CHECK (threat_index BETWEEN 0.0 AND 100.0),
            threat_level TEXT NOT NULL CHECK (threat_level IN ('NORMAL', 'WARNING', 'CRITICAL')),
            verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
            video_url TEXT,
            metadata TEXT, -- JSON blob for frame counts, keypoints, and extra stats
            FOREIGN KEY (incident_id) REFERENCES threat_incidents(incident_id) ON UPDATE CASCADE ON DELETE SET NULL,
            FOREIGN KEY (device_id) REFERENCES devices(device_id) ON UPDATE CASCADE ON DELETE CASCADE
        );
    """)

    # 8. Evacuation States Table (Real-Time Egress Directives)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evacuation_states (
            room_id TEXT PRIMARY KEY,
            chosen_gate TEXT,
            chosen_door TEXT,
            path_sequence TEXT, -- JSON array of route node IDs
            path_cost REAL NOT NULL DEFAULT 0.0,
            directive TEXT NOT NULL CHECK (directive IN ('MODELED_ROUTE_AVAILABLE', 'HOLD_FOR_AUTHORIZED_GUIDANCE', 'NO_CONFIRMED_ROUTE')),
            reason TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (chosen_gate) REFERENCES campus_gates(gate_id) ON UPDATE CASCADE ON DELETE SET NULL,
            FOREIGN KEY (chosen_door) REFERENCES room_doors(door_id) ON UPDATE CASCADE ON DELETE SET NULL
        );
    """)

    # 9. System Audit Logs Table (Administrative Traceability)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'SYSTEM',
            details TEXT, -- JSON serialized details
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # --- Database Performance Indexes ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_bldg ON rooms(building_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doors_room ON room_doors(room_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_devs_bldg ON devices(building_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_det_dev ON threat_detections(device_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_det_inc ON threat_detections(incident_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_det_time ON threat_detections(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_det_level ON threat_detections(threat_level);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inc_status ON threat_incidents(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evac_dir ON evacuation_states(directive);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON system_audit_logs(created_at);")


# ---------------------------------------------------------------------------
# Idempotent Seeding of Campus Infrastructure
# ---------------------------------------------------------------------------
def seed_static_data(db_path=DB_FILE):
    """Seed static campus topology if the database is unpopulated."""
    from dynamic_evacuation import BUILDINGS, BUILDING_NAMES, DEVICES, COVERAGE

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Seed Buildings
        cursor.execute("SELECT COUNT(*) FROM buildings;")
        if cursor.fetchone()[0] == 0:
            for b_code, (floors, rpf) in BUILDINGS.items():
                name = BUILDING_NAMES.get(b_code, b_code)
                cursor.execute(
                    "INSERT INTO buildings (building_code, building_name, total_floors, rooms_per_floor) VALUES (?, ?, ?, ?);",
                    (b_code, name, floors, rpf)
                )

        # 2. Seed Classrooms & Doors
        cursor.execute("SELECT COUNT(*) FROM rooms;")
        if cursor.fetchone()[0] == 0:
            for b_code, (floors, rpf) in BUILDINGS.items():
                for f in range(1, floors + 1):
                    for r in range(1, rpf + 1):
                        room_id = f"{b_code}-F{f}-R{r}"
                        cursor.execute(
                            "INSERT INTO rooms (room_id, building_code, floor_no, room_no) VALUES (?, ?, ?, ?);",
                            (room_id, b_code, f, r)
                        )
                        # Dual door modeling
                        c_left = f"{b_code}-F{f}-C{r - 1}"
                        c_right = f"{b_code}-F{f}-C{r}"
                        cursor.execute(
                            "INSERT INTO room_doors (door_id, room_id, door_label, corridor_node) VALUES (?, ?, ?, ?);",
                            (f"{room_id}-DL", room_id, "Left Door", c_left)
                        )
                        cursor.execute(
                            "INSERT INTO room_doors (door_id, room_id, door_label, corridor_node) VALUES (?, ?, ?, ?);",
                            (f"{room_id}-DR", room_id, "Right Door", c_right)
                        )

        # 3. Seed Campus Gates
        cursor.execute("SELECT COUNT(*) FROM campus_gates;")
        if cursor.fetchone()[0] == 0:
            gates = [
                ("GATE-W", "West Gate (Barangay 91 Access)", 195.0, 405.0, "OPEN"),
                ("GATE-NE", "Northeast Gate (Main Highway Access)", 778.0, 146.0, "OPEN")
            ]
            cursor.executemany(
                "INSERT INTO campus_gates (gate_id, gate_name, coordinates_x, coordinates_y, status) VALUES (?, ?, ?, ?, ?);",
                gates
            )

        # 4. Seed Devices
        cursor.execute("SELECT COUNT(*) FROM devices;")
        if cursor.fetchone()[0] == 0:
            for did, meta in DEVICES.items():
                bldg = meta.get("building")
                floor = meta.get("floor", 0)
                zone = meta.get("zone", "indoor")
                dev_type = "outdoor_cam" if zone == "outdoor" else "indoor_cam"
                covered = list(COVERAGE.get(did, []))
                cursor.execute(
                    """INSERT INTO devices (device_id, building_code, device_type, floor_no, zone_type, covered_rooms, status)
                       VALUES (?, ?, ?, ?, ?, ?, 'ONLINE');""",
                    (did, bldg, dev_type, floor, zone, json.dumps(covered))
                )

        # 5. Seed Default Personnel & IT Technician Accounts if empty
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("safety.officer", "School DRRM Officer", "PERSONNEL", "Sentinel@2026"),
                ("it.tech", "Campus IT Technician", "IT_TECHNICIAN", "TechAdmin@2026"),
            ]
            for uname, fname, role, pw in defaults:
                pw_hash, salt_hex = hash_password(pw)
                is_main = 1 if (uname == "it.tech" and role == "IT_TECHNICIAN") else 0
                cursor.execute(
                    "INSERT INTO users (username, full_name, role, password_hash, salt, is_main_it) VALUES (?, ?, ?, ?, ?, ?);",
                    (uname, fname, role, pw_hash, salt_hex, is_main)
                )


# ---------------------------------------------------------------------------
# Data Access Repository Functions (CRUD & Analytics)
# ---------------------------------------------------------------------------
def record_detection(record, db_path=DB_FILE):
    """Insert a new threat detection record and ensure its incident exists."""
    incident_id = record.get("incident_id") or f"inc-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    event_id = record.get("event_id")
    device_id = record.get("device_id")
    timestamp = record.get("timestamp") or datetime.now().isoformat()
    source = record.get("source", "live_video_analysis")

    scores = record.get("scores", {})
    acoustic = float(scores.get("acoustic", 0.0))
    pose = float(scores.get("pose", 0.0))
    obj = float(scores.get("object", 0.0))

    clf = record.get("classification", {})
    threat_index = float(clf.get("index", record.get("threat_index", 0.0)))
    threat_level = clf.get("level", record.get("level", "NORMAL"))
    verified = 1 if clf.get("verified", False) else 0
    video_url = record.get("video_url")

    meta = {
        "object_stats": record.get("object_stats", {}),
        "pose_stats": record.get("pose_stats", {}),
        "acoustic_stats": record.get("acoustic_stats", {}),
    }

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Ensure parent incident exists
        cursor.execute("SELECT incident_id, severity_level FROM threat_incidents WHERE incident_id = ?;", (incident_id,))
        inc_row = cursor.fetchone()
        if not inc_row:
            cursor.execute(
                """INSERT INTO threat_incidents (incident_id, started_at, severity_level, root_location, status)
                   VALUES (?, ?, ?, ?, 'ACTIVE');""",
                (incident_id, timestamp, threat_level, device_id)
            )
        else:
            # Upgrade incident severity if higher
            if threat_level == "CRITICAL" and inc_row["severity_level"] != "CRITICAL":
                cursor.execute(
                    "UPDATE threat_incidents SET severity_level = 'CRITICAL' WHERE incident_id = ?;",
                    (incident_id,)
                )

        # Insert detection record
        cursor.execute(
            """INSERT OR REPLACE INTO threat_detections
               (event_id, incident_id, device_id, source, timestamp, acoustic_score, pose_score, object_score,
                threat_index, threat_level, verified, video_url, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (event_id, incident_id, device_id, source, timestamp, acoustic, pose, obj,
             threat_index, threat_level, verified, video_url, json.dumps(meta))
        )

        # Update device status
        dev_status = "ALERT" if threat_level in ("CRITICAL", "WARNING") else "ONLINE"
        cursor.execute("UPDATE devices SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE device_id = ?;", (dev_status, device_id))


def get_all_detections(db_path=DB_FILE):
    """Return all stored detection records formatted as standard dicts."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, i.severity_level as incident_level
            FROM threat_detections d
            LEFT JOIN threat_incidents i ON d.incident_id = i.incident_id
            ORDER BY d.detection_id ASC;
        """)
        rows = cursor.fetchall()
        
        records = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            records.append({
                "detection_id": r["detection_id"],
                "event_id": r["event_id"],
                "incident_id": r["incident_id"],
                "device_id": r["device_id"],
                "source": r["source"],
                "timestamp": r["timestamp"],
                "scores": {
                    "acoustic": r["acoustic_score"],
                    "pose": r["pose_score"],
                    "object": r["object_score"],
                },
                "classification": {
                    "acoustic": r["acoustic_score"],
                    "pose": r["pose_score"],
                    "object": r["object_score"],
                    "index": r["threat_index"],
                    "verified": bool(r["verified"]),
                    "level": r["threat_level"],
                },
                "level": r["threat_level"],
                "video_url": r["video_url"],
                "object_stats": meta.get("object_stats", {}),
                "pose_stats": meta.get("pose_stats", {}),
                "acoustic_stats": meta.get("acoustic_stats", {}),
            })
        return records


def resolve_active_incidents(resolution_notes="Threat apprehended & evacuation secured", resolved_by="DRRM_OFFICER", db_path=DB_FILE):
    """Formally resolve active incidents with stand-down notes and clear live threat alerts."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE threat_incidents
               SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP, notes = ?
               WHERE status = 'ACTIVE';""",
            (resolution_notes,)
        )
        resolved_count = cursor.rowcount
        cursor.execute("DELETE FROM threat_detections;")
        cursor.execute("UPDATE devices SET status = 'ONLINE', updated_at = CURRENT_TIMESTAMP;")
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES (?, ?, ?);",
            (
                "INCIDENT_RESOLVED",
                resolved_by,
                json.dumps({"resolved_count": resolved_count, "notes": resolution_notes}),
            ),
        )
        return resolved_count


def clear_all_detections(db_path=DB_FILE):
    """Safely archive active incidents and clear detections table."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE threat_incidents SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP WHERE status = 'ACTIVE';")
        cursor.execute("DELETE FROM threat_detections;")
        cursor.execute("UPDATE devices SET status = 'ONLINE', updated_at = CURRENT_TIMESTAMP;")
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES ('CLEAR_DETECTIONS', 'ADMIN', '{\"status\":\"All detections cleared and archived\"}');"
        )


def save_evacuation_states(routes_map, db_path=DB_FILE):
    """Persist calculated dynamic evacuation routes for all rooms."""
    now = datetime.now().isoformat()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for room_id, r in routes_map.items():
            path_seq = json.dumps(r.get("route", []))
            gate = r.get("gate")
            door = r.get("door")
            cost = float(r.get("cost", 0.0) or 0.0)
            directive = r.get("status", "NO_CONFIRMED_ROUTE")
            reason = r.get("reason", "")

            cursor.execute(
                """INSERT OR REPLACE INTO evacuation_states
                   (room_id, chosen_gate, chosen_door, path_sequence, path_cost, directive, reason, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                (room_id, gate, door, path_seq, cost, directive, reason, now)
            )


def get_evacuation_states(db_path=DB_FILE):
    """Retrieve the latest cached evacuation routes for all rooms."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evacuation_states;")
        rows = cursor.fetchall()
        out = {}
        for r in rows:
            out[r["room_id"]] = {
                "status": r["directive"],
                "gate": r["chosen_gate"],
                "door": r["chosen_door"],
                "route": json.loads(r["path_sequence"]) if r["path_sequence"] else [],
                "cost": r["path_cost"],
                "reason": r["reason"],
                "updated_at": r["updated_at"],
            }
        return out


def get_facility_overrides(db_path=DB_FILE):
    """Return list of persisted non-threat unavailable facility node IDs."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT node_id, node_type, condition, assigned_by, created_at FROM facility_overrides ORDER BY created_at ASC;")
        return [dict(r) for r in cursor.fetchall()]


def replace_facility_overrides(node_ids, assigned_by="PERSONNEL", db_path=DB_FILE):
    """Persist the complete active list of unavailable facility nodes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM facility_overrides;")
        for nid in node_ids:
            if nid.endswith("-CORRIDOR"):
                ntype = "corridor_floor"
            elif "-STAIR-" in nid:
                ntype = "stair"
            elif "-C" in nid:
                ntype = "corridor"
            else:
                ntype = "room"
            cursor.execute(
                "INSERT INTO facility_overrides (node_id, node_type, condition, assigned_by) VALUES (?, ?, 'UNAVAILABLE', ?);",
                (nid, ntype, assigned_by)
            )


def update_gate_statuses(gate_states, db_path=DB_FILE):
    """Synchronize real-time gate statuses (OPEN, BLOCKED, COMPROMISED) in campus_gates."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for gate_id, st in gate_states.items():
            valid_st = st if st in ("OPEN", "BLOCKED", "COMPROMISED") else "BLOCKED"
            cursor.execute(
                "UPDATE campus_gates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE gate_id = ?;",
                (valid_st, gate_id)
            )


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Hash password with PBKDF2-HMAC-SHA256 and per-user cryptographic salt."""
    salt_bytes = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 120000)
    return digest.hex(), salt_bytes.hex()


def create_user(username: str, full_name: str, role: str, password: str, db_path=DB_FILE):
    """Create a new PERSONNEL or IT_TECHNICIAN account."""
    uname = username.strip().lower()
    if role not in ("PERSONNEL", "IT_TECHNICIAN"):
        raise ValueError("Invalid role; must be PERSONNEL or IT_TECHNICIAN.")
    pw_hash, salt_hex = hash_password(password)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?;", (uname,))
        if cursor.fetchone():
            raise ValueError(f"Username '{uname}' is already registered.")
        cursor.execute(
            "INSERT INTO users (username, full_name, role, password_hash, salt) VALUES (?, ?, ?, ?, ?);",
            (uname, full_name.strip(), role, pw_hash, salt_hex)
        )
        uid = cursor.lastrowid
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES ('USER_REGISTER', ?, ?);",
            (uname, json.dumps({"role": role, "full_name": full_name.strip()}))
        )
        return {"user_id": uid, "username": uname, "full_name": full_name.strip(), "role": role}


def authenticate_user(username: str, password: str, ttl_hours: int = 12, db_path=DB_FILE):
    """Verify credentials and issue a persisted session token."""
    uname = username.strip().lower()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1;", (uname,))
        row = cursor.fetchone()
        if not row:
            return None
        candidate_hash, _ = hash_password(password, row["salt"])
        if not hmac.compare_digest(candidate_hash, row["password_hash"]):
            return None

        token = secrets.token_urlsafe(32)
        expires_at = time.time() + (ttl_hours * 3600)
        cursor.execute("DELETE FROM user_sessions WHERE expires_at < ?;", (time.time(),))
        cursor.execute(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?);",
            (token, row["user_id"], expires_at)
        )
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES ('USER_LOGIN', ?, ?);",
            (uname, json.dumps({"role": row["role"], "full_name": row["full_name"]}))
        )
        return {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "user_id": row["user_id"],
                "username": row["username"],
                "full_name": row["full_name"],
                "role": row["role"],
                "is_main_it": bool(row["is_main_it"]),
            },
        }


def get_session_user(token: str | None, db_path=DB_FILE):
    """Look up an active non-expired session token and return user info."""
    if not token:
        return None
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT u.user_id, u.username, u.full_name, u.role, u.is_main_it, s.expires_at
               FROM user_sessions s
               JOIN users u ON s.user_id = u.user_id
               WHERE s.token = ? AND u.is_active = 1;""",
            (token,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        if row["expires_at"] < time.time():
            cursor.execute("DELETE FROM user_sessions WHERE token = ?;", (token,))
            return None
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
            "is_main_it": bool(row["is_main_it"]),
        }


def revoke_session(token: str | None, db_path=DB_FILE):
    """Invalidate a session token on logout and record a USER_LOGOUT audit log."""
    if not token:
        return
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT u.username, u.full_name, u.role
               FROM user_sessions s
               JOIN users u ON s.user_id = u.user_id
               WHERE s.token = ?;""",
            (token,)
        )
        row = cursor.fetchone()
        cursor.execute("DELETE FROM user_sessions WHERE token = ?;", (token,))
        if row:
            cursor.execute(
                "INSERT INTO system_audit_logs (action, actor, details) VALUES ('USER_LOGOUT', ?, ?);",
                (row["username"], json.dumps({"role": row["role"], "full_name": row["full_name"]}))
            )


def list_users(db_path=DB_FILE):
    """Return non-sensitive registered accounts for IT Technician management."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT user_id, username, full_name, role, is_main_it, is_active, created_at
               FROM users
               WHERE is_active = 1
               ORDER BY is_main_it DESC, user_id ASC;"""
        )
        out = []
        for r in cursor.fetchall():
            d = dict(r)
            d["is_main_it"] = bool(d["is_main_it"])
            out.append(d)
        return out


def change_user_password(user_id: int, current_password: str, new_password: str, db_path=DB_FILE):
    """Verify current password, rotate salted hash, and log PASSWORD_CHANGE."""
    if len(new_password or "") < 6:
        raise ValueError("New password must be at least 6 characters.")
    if current_password == new_password:
        raise ValueError("New password must be different from your current password.")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1;", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise LookupError("Account not found.")

        cand_hash, _ = hash_password(current_password, row["salt"])
        if not hmac.compare_digest(cand_hash, row["password_hash"]):
            raise PermissionError("Current password is incorrect.")

        new_hash, new_salt = hash_password(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE user_id = ?;",
            (new_hash, new_salt, user_id)
        )
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES ('PASSWORD_CHANGE', ?, ?);",
            (row["username"], json.dumps({"role": row["role"], "full_name": row["full_name"]}))
        )
        return {"username": row["username"], "role": row["role"]}


def delete_user_account(actor_user_id: int, actor_password: str, target_user_id: int, db_path=DB_FILE):
    """Delete an account after verifying the acting IT Technician's password and RBAC hierarchy."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1;", (actor_user_id,))
        actor = cursor.fetchone()
        if not actor or actor["role"] != "IT_TECHNICIAN":
            raise PermissionError("IT Technician privileges are required to delete accounts.")

        cand_hash, _ = hash_password(actor_password or "", actor["salt"])
        if not hmac.compare_digest(cand_hash, actor["password_hash"]):
            raise PermissionError("Incorrect IT Technician password. Account deletion cancelled.")

        cursor.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1;", (target_user_id,))
        target = cursor.fetchone()
        if not target:
            raise LookupError("Target account not found.")

        if target["is_main_it"]:
            raise PermissionError("The Main IT Technician account is protected and cannot be deleted.")
        if target["user_id"] == actor["user_id"]:
            raise PermissionError("You cannot delete your own active account.")
        if target["role"] == "IT_TECHNICIAN" and not actor["is_main_it"]:
            raise PermissionError("Only the Main IT Technician can delete other IT Technician accounts.")

        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?;", (target_user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = ?;", (target_user_id,))
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details) VALUES ('USER_DELETE', ?, ?);",
            (
                actor["username"],
                json.dumps({
                    "actor_role": actor["role"],
                    "actor_full_name": actor["full_name"],
                    "actor_is_main_it": bool(actor["is_main_it"]),
                    "deleted_user_id": target["user_id"],
                    "deleted_username": target["username"],
                    "deleted_full_name": target["full_name"],
                    "deleted_role": target["role"],
                }),
            ),
        )
        return {
            "deleted_user_id": target["user_id"],
            "deleted_username": target["username"],
            "deleted_full_name": target["full_name"],
            "deleted_role": target["role"],
            "deleted_by": actor["username"],
        }


def get_account_activity_logs(requesting_user: dict, scope: str = "all", category: str = "all", limit: int = 150, db_path=DB_FILE):
    """Return role-scoped account activity logs from system_audit_logs.

    - PERSONNEL: strictly restricted to their own USER_LOGIN, USER_LOGOUT, and PASSWORD_CHANGE logs.
    - IT_TECHNICIAN: can view all Personnel and IT Technician account logs (or scope='mine' for own logs),
      including USER_LOGIN, USER_LOGOUT, PASSWORD_CHANGE, USER_REGISTER, and USER_DELETE.
    """
    role = requesting_user.get("role")
    uname = requesting_user.get("username", "").lower()

    if role != "IT_TECHNICIAN":
        actions = ("USER_LOGIN", "USER_LOGOUT", "PASSWORD_CHANGE")
        where_actor = "AND LOWER(actor) = ?"
        params = [uname]
    else:
        cat_map = {
            "auth": ("USER_LOGIN", "USER_LOGOUT"),
            "password": ("PASSWORD_CHANGE",),
            "delete": ("USER_DELETE",),
            "register": ("USER_REGISTER",),
        }
        actions = cat_map.get(category, ("USER_LOGIN", "USER_LOGOUT", "PASSWORD_CHANGE", "USER_REGISTER", "USER_DELETE"))
        if scope == "mine":
            where_actor = "AND LOWER(actor) = ?"
            params = [uname]
        else:
            where_actor = ""
            params = []

    placeholders = ",".join("?" for _ in actions)
    query = f"""
        SELECT log_id, action, actor, details, created_at
        FROM system_audit_logs
        WHERE action IN ({placeholders}) {where_actor}
        ORDER BY log_id DESC
        LIMIT ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (*actions, *params, int(limit)))
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["details_obj"] = json.loads(d["details"]) if d["details"] else {}
            except Exception:
                d["details_obj"] = {}
            rows.append(d)
        return rows


def log_audit(action, actor="SYSTEM", details=None, ip_address=None, db_path=DB_FILE):
    """Record an administrative or operational event in the audit log."""
    det_str = json.dumps(details) if isinstance(details, (dict, list)) else str(details or "")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_audit_logs (action, actor, details, ip_address) VALUES (?, ?, ?, ?);",
            (action, actor, det_str, ip_address)
        )


def get_database_stats(db_path=DB_FILE):
    """Retrieve database metrics, record counts, and table sizes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        stats = {}
        tables = [
            "buildings", "rooms", "room_doors", "campus_gates",
            "devices", "threat_incidents", "threat_detections",
            "evacuation_states", "system_audit_logs", "schema_migrations"
        ]
        for tbl in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
            stats[tbl] = cursor.fetchone()[0]
        
        cursor.execute("PRAGMA journal_mode;")
        stats["journal_mode"] = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_count;")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size;")
        page_size = cursor.fetchone()[0]
        stats["db_size_bytes"] = page_count * page_size
        return stats


if __name__ == "__main__":
    print(f"Initializing SENTINEL Database at: {DB_FILE}")
    init_db()
    s = get_database_stats()
    print("Database Initialized Successfully!")
    print(f"Journal Mode: {s.get('journal_mode')} | DB Size: {s.get('db_size_bytes')} bytes")
    for k, v in s.items():
        if k not in ("journal_mode", "db_size_bytes"):
            print(f"  - {k}: {v} records")
