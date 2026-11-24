"""Persistent Bidirectional MQTT & Hardware Digital Twin Bridge for SENTINEL.

Maintains a background paho-mqtt client linking the FastAPI evacuation engine
with the Addressable ESP32 Zone Controller (Wokwi or physical hardware).
"""

import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

MQTT_BROKER = os.environ.get("SENTINEL_MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("SENTINEL_MQTT_PORT", "1883"))

TOPIC_STATE = "stonino/campus/state"
TOPIC_ALERT = "stonino/campus/alert"
TOPIC_DEVICE_ACK = "stonino/campus/device/ack"
TOPIC_DEVICE_TRIGGER = "stonino/campus/device/trigger"

FLOOR_ORDER = [
    ("TPB", 1), ("TPB", 2), ("TPB", 3), ("TPB", 4),
    ("AB", 1),  ("AB", 2),  ("AB", 3),  ("AB", 4),
    ("LB", 1),  ("LB", 2),
]


class HardwareBridge:
    """Thread-safe MQTT bridge + local Hardware Digital Twin state tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        self._client = None
        self._started = False
        self._broker_connected = False
        self._seq = 0
        self._trigger_handler = None
        self._packets = deque(maxlen=25)
        self._last_state_payload = None
        self._twin = {
            "device_id": "ESP32-CAMPUS-GW01",
            "mode": "Addressable Zone Concentrator",
            "online": False,
            "last_heartbeat": None,
            "last_heartbeat_epoch": 0.0,
            "rssi": None,
            "acoustic_sim": 18.0,
            "firmware": "SENTINEL-GW-v2.1",
            "active_edge_source": None,
        }

    def set_trigger_handler(self, fn):
        """Register callback(payload_dict) invoked when ESP32 publishes a physical trigger."""
        self._trigger_handler = fn

    def start(self):
        """Start persistent non-blocking MQTT client thread."""
        if self._started or mqtt is None:
            return
        self._started = True

        cid = f"sentinel_srv_{uuid.uuid4().hex[:8]}"
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
        else:
            client = mqtt.Client(client_id=cid)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=2, max_delay=30)

        self._client = client

        def _connect_worker():
            try:
                client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
                client.loop_start()
            except Exception as exc:
                self._record_packet("SYS", "bridge/error", {"error": str(exc)})

        threading.Thread(target=_connect_worker, daemon=True).start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        with self._lock:
            self._broker_connected = True
        client.subscribe(TOPIC_DEVICE_ACK, qos=1)
        client.subscribe(TOPIC_DEVICE_TRIGGER, qos=1)
        self._record_packet("SYS", "broker/connected", {"broker": MQTT_BROKER, "port": MQTT_PORT})

        # Re-publish latest state so a newly connected Wokwi node gets immediate sync
        with self._lock:
            latest = self._last_state_payload
        if latest:
            self._publish_raw(TOPIC_STATE, latest, retain=True)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        with self._lock:
            self._broker_connected = False
        self._record_packet("SYS", "broker/disconnected", {"reason": str(reason_code)})

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="replace"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="replace")}

        self._record_packet("RX", topic, payload)

        if topic == TOPIC_DEVICE_ACK:
            is_online = bool(payload.get("online", True))
            with self._lock:
                self._twin["online"] = is_online
                self._twin["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
                self._twin["last_heartbeat_epoch"] = time.time() if is_online else 0.0
                if "device_id" in payload:
                    self._twin["device_id"] = str(payload["device_id"])
                if "rssi" in payload:
                    self._twin["rssi"] = payload["rssi"]
                if "acoustic" in payload:
                    self._twin["acoustic_sim"] = payload["acoustic"]
                if "firmware" in payload:
                    self._twin["firmware"] = str(payload["firmware"])

        elif topic == TOPIC_DEVICE_TRIGGER:
            with self._lock:
                self._twin["online"] = True
                self._twin["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
                self._twin["last_heartbeat_epoch"] = time.time()
                self._twin["active_edge_source"] = payload.get("action") or payload.get("device_id")
            if self._trigger_handler and isinstance(payload, dict):
                try:
                    self._trigger_handler(payload)
                except Exception as exc:
                    self._record_packet("SYS", "trigger/error", {"error": str(exc)})

    def _record_packet(self, direction, topic, payload):
        entry = {
            "dir": direction,
            "topic": topic,
            "payload": payload,
            "time": datetime.now().strftime("%H:%M:%S"),
        }
        with self._lock:
            self._packets.appendleft(entry)

    def _publish_raw(self, topic, payload_dict, retain=False):
        raw = json.dumps(payload_dict, separators=(",", ":"))
        self._record_packet("TX", topic, payload_dict)
        if self._client is not None and self._broker_connected:
            try:
                self._client.publish(topic, raw, qos=0, retain=retain)
                return True
            except Exception:
                return False
        return False

    def build_hardware_payload(self, global_status, routes_out, gate_states, counts, unavailable_gates):
        """Construct compact deterministic zone bitmask payload for ESP32 NeoPixels & Servos."""
        floor_codes = []
        floor_details = []

        for b_code, fl in FLOOR_ORDER:
            prefix = f"{b_code}-F{fl}-"
            f_routes = [r for rm, r in routes_out.items() if rm.startswith(prefix)]
            if any(r["status"] == "NO_CONFIRMED_ROUTE" for r in f_routes):
                code = "T"   # Threat / Red
            elif any(r["status"] == "HOLD_FOR_AUTHORIZED_GUIDANCE" for r in f_routes):
                code = "H"   # Hold / Amber
            elif f_routes and all(r["status"] == "FACILITY_UNAVAILABLE" for r in f_routes):
                code = "U"   # Closed / Unavailable (Gray)
            else:
                code = "S"   # Safe / Green

            floor_codes.append(code)
            floor_details.append({
                "id": f"{b_code}-F{fl}",
                "building": b_code,
                "floor": fl,
                "code": code,
            })

        w_open = gate_states.get("GATE-W", "OPEN") == "OPEN" and "GATE-W" not in unavailable_gates
        ne_open = gate_states.get("GATE-NE", "OPEN") == "OPEN" and "GATE-NE" not in unavailable_gates

        if w_open and ne_open:
            evac_gate = "BOTH"
        elif w_open:
            evac_gate = "GATE-W"
        elif ne_open:
            evac_gate = "GATE-NE"
        else:
            evac_gate = "LOCKDOWN"

        buzzer = "ALARM" if global_status == "CRITICAL" else "CHIRP" if global_status == "WARNING" else "OFF"

        with self._lock:
            self._seq += 1
            seq_val = self._seq

        payload = {
            "seq": seq_val,
            "status": global_status,
            "evac_gate": evac_gate,
            "gates": {
                "W": "OPEN" if w_open else "BLOCKED",
                "NE": "OPEN" if ne_open else "BLOCKED",
            },
            "servo_w": 90 if w_open else 0,
            "servo_ne": 90 if ne_open else 0,
            "buzzer": buzzer,
            "floors": floor_codes,
            "counts": {
                "safe": int(counts.get("available", counts.get("MODELED_ROUTE_AVAILABLE", 0))),
                "hold": int(counts.get("hold", counts.get("HOLD_FOR_AUTHORIZED_GUIDANCE", 0))),
                "blocked": int(counts.get("no_route", counts.get("NO_CONFIRMED_ROUTE", 0))),
                "unavailable": int(counts.get("unavailable", 0)),
            },
            "time": datetime.now().strftime("%H:%M:%S"),
        }
        return payload, floor_details

    def publish_state(self, global_status, routes_out, gate_states, counts, unavailable_gates):
        """Update cached digital twin payload and push live MQTT messages."""
        payload, _ = self.build_hardware_payload(
            global_status, routes_out, gate_states, counts, unavailable_gates
        )
        with self._lock:
            self._last_state_payload = payload

        self._publish_raw(TOPIC_STATE, payload, retain=True)

        gates_open = ",".join(
            g for g in ("GATE-W", "GATE-NE") if gate_states.get(g, "OPEN") == "OPEN"
        ) or "NONE"
        self._publish_raw(TOPIC_ALERT, {
            "status": global_status,
            "gates": gates_open,
            "time": payload["time"],
        }, retain=False)
        return payload

    def get_twin_status(self, global_status, routes_out, gate_states, counts, unavailable_gates):
        """Return full Hardware Digital Twin representation for the dashboard."""
        payload, floor_details = self.build_hardware_payload(
            global_status, routes_out, gate_states, counts, unavailable_gates
        )
        now_epoch = time.time()

        with self._lock:
            twin = dict(self._twin)
            # Mark offline automatically if no heartbeat within 25s
            if twin["online"] and (now_epoch - twin.get("last_heartbeat_epoch", 0)) > 25.0:
                twin["online"] = False
            packets = list(self._packets)
            broker_ok = self._broker_connected

        return {
            "broker": MQTT_BROKER,
            "port": MQTT_PORT,
            "broker_connected": broker_ok,
            "topics": {
                "state": TOPIC_STATE,
                "ack": TOPIC_DEVICE_ACK,
                "trigger": TOPIC_DEVICE_TRIGGER,
            },
            "device": twin,
            "telemetry": payload,
            "leds": floor_details + [
                {"id": "GATE-W", "building": "GATE", "floor": 0, "code": "S" if payload["gates"]["W"] == "OPEN" else "T"},
                {"id": "GATE-NE", "building": "GATE", "floor": 0, "code": "S" if payload["gates"]["NE"] == "OPEN" else "T"},
            ],
            "packets": packets,
        }


bridge = HardwareBridge()
