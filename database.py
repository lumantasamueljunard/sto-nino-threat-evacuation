"""Database management module for SENTINEL Campus Threat Evacuation System.

Implements a relational SQLite database (sentinel.db) adhering to:
- Third Normal Form (3NF) relational architecture
- Write-Ahead Logging (WAL) for high concurrency
- Explicit foreign key constraints and validation checks
- Comprehensive indexing on foreign keys, timestamps, and query paths
- Versioned schema migrations for seamless future updates
- Audit logging for administrative traceability
"""

import os
import json
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Database Configuration & File Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "sentinel.db")
SCHEMA_VERSION = 1


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

    # Seed static campus topology if tables are empty
    seed_static_data(db_path)


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
