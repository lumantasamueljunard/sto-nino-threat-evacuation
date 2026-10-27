"""Canonical campus graph, threat assessment, and dynamic evacuation routing.
DEMO ONLY. Costs are illustrative, never a certified life-safety system.

This module is the single source of truth for:
  - the Sto. Niño SHS campus graph (36 rooms, 10 floors, 26 devices):
      * Tech Pro Building (TPB): 4 floors, 5 rooms/floor (20 rooms)
      * Academic Building (AB): 4 floors, 3 rooms/floor (12 rooms)
      * Laboratory Building (LB): 2 floors, 2 rooms/floor (4 rooms)
  - pure threat-index math and classification,
  - Observation input and per-snapshot assessment,
  - per-classroom dynamic routing.
"""
from dataclasses import dataclass
import networkx as nx

# ---------------------------------------------------------------------------
# Configuration & Building Metadata
# ---------------------------------------------------------------------------
BUILDINGS = {
    'TPB': (4, 5),   # Tech Pro Building: 4 floors, 5 rooms/floor (20 rooms)
    'AB':  (4, 3),   # Academic Building: 4 floors, 3 rooms/floor (12 rooms)
    'LB':  (2, 2),   # Laboratory Building: 2 floors, 2 rooms/floor (4 rooms)
}
BUILDING_NAMES = {
    'TPB': 'Tech Pro Building',
    'AB':  'Academic Building',
    'LB':  'Laboratory Building',
}
GATES = ('GATE-W', 'GATE-NE')
TOTAL_ROOMS = sum(f * r for f, r in BUILDINGS.values())   # 36

# Prototype threat-index parameters — adjustable, not measured science.
W_ACOUSTIC, W_POSE, W_OBJECT = 0.25, 0.30, 0.45
SUPPORT_THRESHOLD = 50         # a signal counts as "supporting" at >= this
OBJECT_VERIFY_THRESHOLD = 60   # object score needed to verify a CRITICAL
CRITICAL_INDEX = 70
WARNING_INDEX = 30

# ---------------------------------------------------------------------------
# Graph, rooms, devices
# ---------------------------------------------------------------------------
G = nx.Graph()
ROOMS = []       # list of room ids
DEVICES = {}     # device_id -> dict(building, floor, zone, side)
COVERAGE = {}    # device_id -> frozenset of covered node ids


def _edge(a, b, w=1.0):
    G.add_edge(a, b, weight=float(w))


def build():
    """Build the canonical campus graph. Node IDs are frozen; do not rename."""
    for b, (floors, count) in BUILDINGS.items():
        for f in range(1, floors + 1):
            prefix = f'{b}-F{f}'

            # Corridor segments C0..C<count> run along the veranda.
            for i in range(count + 1):
                c = f'{prefix}-C{i}'
                G.add_node(c, kind='corridor', building=b, floor=f)
                if i:
                    _edge(f'{prefix}-C{i-1}', c, 2)

            # Rooms — each has TWO doors (L and R), matching the site plan.
            for r in range(1, count + 1):
                room = f'{prefix}-R{r}'
                ROOMS.append(room)
                G.add_node(room, kind='room', building=b, floor=f)
                for side, seg in (('L', r - 1), ('R', r)):
                    door = f'{room}-D{side}'
                    G.add_node(door, kind='door', building=b, floor=f)
                    _edge(room, door, 0.5)
                    _edge(door, f'{prefix}-C{seg}', 0.5)

            # Two stairwells per floor, one at each end of the veranda.
            for side, seg in (('L', 0), ('R', count)):
                stair = f'{prefix}-STAIR-{side}'
                G.add_node(stair, kind='stair', building=b, floor=f)
                _edge(stair, f'{prefix}-C{seg}', 1)
                if f > 1:
                    _edge(stair, f'{b}-F{f-1}-STAIR-{side}', 4)

            # Two indoor cameras per floor. L covers the leftmost <=3 rooms,
            # R covers the rightmost <=3. Overlap in the middle is intentional.
            for side, covered in (('L', range(1, min(count, 3) + 1)),
                                  ('R', range(max(1, count - 2), count + 1))):
                did = f'{prefix}-CAM-{side}'
                DEVICES[did] = {'building': b, 'floor': f,
                                'zone': 'indoor', 'side': side}
                COVERAGE[did] = frozenset(f'{prefix}-R{r}' for r in covered)

        # Outdoor approaches and outdoor cameras (one per building side).
        for side in 'LR':
            out = f'{b}-OUT-{side}'
            G.add_node(out, kind='outdoor', building=b, floor=0)
            _edge(f'{b}-F1-STAIR-{side}', out, 1)
            did = f'{b}-CAM-OUT-{side}'
            DEVICES[did] = {'building': b, 'floor': 0,
                            'zone': 'outdoor', 'side': side}
            COVERAGE[did] = frozenset((out,))

    # Paved outdoor path network connecting buildings and perimeter gates.
    for a, b_node, w in [
        ('TPB-OUT-L', 'WEST-PATH', 2), ('LB-OUT-L', 'WEST-PATH', 3),
        ('WEST-PATH', 'GATE-W', 2),
        ('TPB-OUT-R', 'NORTH-PATH', 2), ('NORTH-PATH', 'GATE-NE', 2),
        ('AB-OUT-R', 'EAST-PATH', 3), ('EAST-PATH', 'NORTH-PATH', 3),
        ('AB-OUT-L', 'COURTYARD', 2), ('LB-OUT-R', 'COURTYARD', 2),
        ('COURTYARD', 'WEST-PATH', 4), ('COURTYARD', 'EAST-PATH', 4),
        ('TPB-OUT-L', 'COURTYARD', 3), ('TPB-OUT-R', 'COURTYARD', 4),
    ]:
        _edge(a, b_node, w)

    for gate in GATES:
        G.add_node(gate, kind='gate')
    for n in G:
        G.nodes[n].setdefault('kind', 'outdoor')

    # Sanity checks — fail loudly, not silently during the demo.
    assert len(ROOMS) == TOTAL_ROOMS == 36, f'Room count mismatch: {len(ROOMS)} vs {TOTAL_ROOMS}'
    assert nx.is_connected(G), 'Campus graph must be connected'
    assert all(any(r in COVERAGE[d] for d in DEVICES) for r in ROOMS), \
        'Every classroom must be covered by at least one device'


build()

# ---------------------------------------------------------------------------
# Pure threat index & classifier (deterministic; no side effects)
# ---------------------------------------------------------------------------
def _check_score(name, value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f'{name} must be a number in [0, 100]')
    if not (0 <= value <= 100):
        raise ValueError(f'{name} must be in [0, 100], got {value}')


def calculate_threat_index(acoustic, pose, object_detection):
    """Pure weighted index: 0.25A + 0.30P + 0.45O, rounded to 2 dp."""
    _check_score('acoustic', acoustic)
    _check_score('pose', pose)
    _check_score('object_detection', object_detection)
    return round(W_ACOUSTIC * acoustic +
                 W_POSE * pose +
                 W_OBJECT * object_detection, 2)


def classify_threat(acoustic, pose, object_detection):
    """Return a dict describing one classification.

    Keys: acoustic, pose, object, index, supporting_signals, verified, level.
    level is one of NORMAL, WARNING, CRITICAL.
    verified requires object_detection >= 60 AND >=2 signals >= 50.
    """
    index = calculate_threat_index(acoustic, pose, object_detection)
    scores = (acoustic, pose, object_detection)
    supporting = sum(1 for s in scores if s >= SUPPORT_THRESHOLD)
    verified = (object_detection >= OBJECT_VERIFY_THRESHOLD) and (supporting >= 2)

    if index >= CRITICAL_INDEX and verified:
        level = 'CRITICAL'
    elif index >= WARNING_INDEX or (index >= CRITICAL_INDEX and not verified):
        level = 'WARNING'
    else:
        level = 'NORMAL'

    return {
        'acoustic': acoustic,
        'pose': pose,
        'object': object_detection,
        'index': index,
        'supporting_signals': supporting,
        'verified': verified,
        'level': level,
    }

# ---------------------------------------------------------------------------
# Observations and per-snapshot assessment
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Observation:
    """One detection event from one device. Not proof of a unique person."""
    event_id: str
    device_id: str
    level: str                      # NORMAL | WARNING | CRITICAL
    count: int = 1                  # detections in THIS video
    location: str | None = None     # optional confirmed node inside coverage
    incident_id: str | None = None  # shared id -> dedupe overlapping cameras


def _validate(observations):
    seen = set()
    for o in observations:
        if o.event_id in seen:
            raise ValueError(f'Duplicate event_id: {o.event_id}')
        seen.add(o.event_id)
        if o.device_id not in DEVICES:
            raise ValueError(f'Unknown device: {o.device_id}')
        if o.level not in ('NORMAL', 'WARNING', 'CRITICAL'):
            raise ValueError(f'Invalid level: {o.level}')
        if type(o.count) is not int or o.count < 0:
            raise ValueError(f'Invalid count on event {o.event_id}')
        if o.location is not None and o.location not in COVERAGE[o.device_id]:
            raise ValueError(
                f'Location {o.location} is outside coverage of {o.device_id}')


def assess(observations, manual_blocks=(), closed_edges=(), unavailable_gates=()):
    """Atomic snapshot from the current observation list.

    Policy:
      - Unknown location => conservatively protect the whole camera coverage.
      - Indoor CRITICAL blocks covered rooms, the affected floor's corridor,
        and both stairs on that floor. Upper floors can no longer rely on
        descending through the affected floor.
      - Gate-W / West Approach threat: Blocks GATE-W, WEST-PATH, and TPB-F1-STAIR-L.
        Every building can still evacuate towards GATE-NE (TPB uses safe STAIR-R).
      - Gate-NE / North Approach threat: Blocks GATE-NE, NORTH-PATH, and TPB-F1-STAIR-R.
        Every building can still evacuate towards GATE-W (TPB uses safe STAIR-L).
      - Both gates blocked => Campus lockdown; no confirmed route.
      - WARNING events act as caution zones in this snapshot.
    """
    observations = list(observations)
    _validate(observations)

    unknown = (set(manual_blocks) | set(unavailable_gates)) - set(G)
    if unknown:
        raise ValueError(f'Unknown blocked nodes: {sorted(unknown)}')
    if set(unavailable_gates) - set(GATES):
        raise ValueError('unavailable_gates must be a subset of GATES')
    for a, b in closed_edges:
        if not G.has_edge(a, b):
            raise ValueError(f'Unknown edge: {a}, {b}')

    blocked = set(manual_blocks) | set(unavailable_gates)
    caution = set()
    affected = set()
    events = []
    seen_incidents = set()
    unique_known = 0
    raw = 0
    critical_origins = []

    for o in observations:
        if o.level == 'NORMAL':
            continue
        area = {o.location} if o.location else set(COVERAGE[o.device_id])
        events.append({
            'event_id': o.event_id,
            'device': o.device_id,
            'level': o.level,
            'count_in_video': o.count,
            'possible_locations': sorted(area),
            'location_confirmed': o.location is not None,
        })
        raw += o.count
        if o.incident_id is not None and o.incident_id not in seen_incidents:
            unique_known += o.count
            seen_incidents.add(o.incident_id)

        if o.level == 'CRITICAL':
            blocked.update(area)
            critical_origins.append((o, area))
        else:
            caution.update(area)
        affected.update(area)

    # Threat escalation:
    for o, area in critical_origins:
        info = DEVICES[o.device_id]
        if info['zone'] == 'indoor':
            # Indoor CRITICAL: blocks the entire affected floor (corridor + both stairs)
            b, f = info['building'], info['floor']
            p = f'{b}-F{f}'
            blocked.update(f'{p}-C{i}' for i in range(BUILDINGS[b][1] + 1))
            blocked.update((f'{p}-STAIR-L', f'{p}-STAIR-R'))
        else:
            # Outdoor CRITICAL:
            dev_id = o.device_id
            b = info.get('building')
            side = info.get('side')
            if dev_id == 'TPB-CAM-OUT-L' or 'GATE-W' in area or 'TPB-OUT-L' in area:
                # Threat at Gate-W: Compromise Gate-W, West-Path, and the adjacent left stair
                blocked.update(('GATE-W', 'WEST-PATH', 'TPB-OUT-L', 'TPB-F1-STAIR-L'))
            elif dev_id == 'TPB-CAM-OUT-R' or 'GATE-NE' in area or 'TPB-OUT-R' in area:
                # Threat at Gate-NE: Compromise Gate-NE, North-Path, and the adjacent right stair
                blocked.update(('GATE-NE', 'NORTH-PATH', 'TPB-OUT-R', 'TPB-F1-STAIR-R'))
            else:
                blocked.update(area)
                if b and side:
                    blocked.add(f'{b}-F1-STAIR-{side}')

    graph = G.copy()
    graph.remove_nodes_from(blocked | caution)
    for a, b in closed_edges:
        if graph.has_edge(a, b):
            graph.remove_edge(a, b)

    return {
        'graph': graph,
        'blocked': sorted(blocked),
        'caution': sorted(caution - blocked),
        'events': events,
        'observation_count': len(events),
        'raw_detection_count': raw,
        'known_incident_count': len(seen_incidents),
        'known_incident_detection_sum': unique_known,
        'unique_threat_count': None,
        'possible_threat_locations': sorted(affected),
        'note': ('Counts are per-video detections, not confirmed distinct threats. '
                 'WARNING events act as caution zones in this snapshot.'),
    }

# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def _floor_is_threatened(node, danger_nodes):
    """Check whether node's building floor has active threat, blocked corridors or stairs."""
    parts = node.split('-')
    if len(parts) >= 2:
        b_code = parts[0]
        f_str = parts[1]
        if b_code in BUILDINGS and f_str.startswith('F'):
            try:
                rooms = BUILDINGS[b_code][1]
                prefix = f'{b_code}-{f_str}'
                floor_nodes = set()
                floor_nodes.update(f'{prefix}-C{i}' for i in range(rooms + 1))
                floor_nodes.update((f'{prefix}-STAIR-L', f'{prefix}-STAIR-R'))
                floor_nodes.update(f'{prefix}-R{i}' for i in range(1, rooms + 1))
                return bool(floor_nodes & danger_nodes)
            except Exception:
                return False
    return False


def route(room, snapshot, current=None):
    """Return a modeled route for one classroom.

    statuses:
      MODELED_ROUTE_AVAILABLE       -> gate, door, route, cost are set (GREEN)
      HOLD_FOR_AUTHORIZED_GUIDANCE  -> isolated/cut-off from descending (YELLOW)
      NO_CONFIRMED_ROUTE            -> directly threatened room or floor (RED)
    """
    if room not in ROOMS:
        raise ValueError(f'Unknown classroom: {room}')
    graph = snapshot['graph']
    start = current or room
    if start not in G:
        raise ValueError(f'Unknown current node: {start}')

    danger = set(snapshot.get('blocked', [])) | set(snapshot.get('caution', []))
    floor_threatened = _floor_is_threatened(start, danger)

    # If the origin node itself is removed (threat or blocked node)
    if start not in graph:
        return {'room': room, 'status': 'NO_CONFIRMED_ROUTE',
                'gate': None, 'door': None, 'route': None, 'cost': None,
                'reason': 'Room or origin is inside a confirmed or active threat zone.'}

    # If all campus gates are unavailable
    available_gates = [g for g in GATES if g in graph]
    if not available_gates:
        return {'room': room, 'status': 'NO_CONFIRMED_ROUTE',
                'gate': None, 'door': None, 'route': None, 'cost': None,
                'reason': 'All campus egress gates are unavailable or blocked.'}

    choices = []
    for gate in available_gates:
        try:
            path = nx.shortest_path(graph, start, gate, weight='weight')
            cost = nx.path_weight(graph, path, weight='weight')
            choices.append((cost, gate, path))
        except nx.NetworkXNoPath:
            pass

    if not choices:
        if floor_threatened:
            return {'room': room, 'status': 'NO_CONFIRMED_ROUTE',
                    'gate': None, 'door': None, 'route': None, 'cost': None,
                    'reason': 'Floor corridor or stairs blocked by active threat.'}
        else:
            return {'room': room, 'status': 'HOLD_FOR_AUTHORIZED_GUIDANCE',
                    'gate': None, 'door': None, 'route': None, 'cost': None,
                    'reason': 'Descent route blocked by threat on lower level. Hold in place for authorized guidance.'}

    cost, gate, path = min(choices, key=lambda x: (x[0], x[1]))
    door = next((n for n in path if n.startswith(room + '-D')), None)
    return {'room': room, 'status': 'MODELED_ROUTE_AVAILABLE',
            'gate': gate, 'door': door, 'route': path, 'cost': cost,
            'reason': 'Shortest available modeled route; not a safety certification.'}


def all_routes(snapshot):
    """Route every one of the 36 classrooms against the same snapshot."""
    return {r: route(r, snapshot) for r in ROOMS}


def evaluate(observations=(), **kwargs):
    """Serializable summary (NetworkX graph removed) plus routes."""
    snap = assess(observations, **kwargs)
    routes = all_routes(snap)
    serializable = {k: v for k, v in snap.items() if k != 'graph'}
    serializable['routes'] = routes
    return serializable


def format_route(result):
    """One-line human summary for the dashboard / notebook."""
    if result['status'] == 'MODELED_ROUTE_AVAILABLE':
        return (f"{result['room']} -> {result['gate']} via {result['door']} "
                f"(cost {result['cost']:.1f})")
    return f"{result['room']}: {result['status']} - {result['reason']}"


def route_summary_counts(snapshot):
    """Convenience: {'available': n, 'hold': n, 'no_route': n}."""
    counts = {'available': 0, 'hold': 0, 'no_route': 0}
    for r in ROOMS:
        s = route(r, snapshot)['status']
        if s == 'MODELED_ROUTE_AVAILABLE':
            counts['available'] += 1
        elif s == 'HOLD_FOR_AUTHORIZED_GUIDANCE':
            counts['hold'] += 1
        else:
            counts['no_route'] += 1
    return counts

# ---------------------------------------------------------------------------
# Self-check: run `python dynamic_evacuation.py`
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Pure-function boundary tests.
    assert calculate_threat_index(0, 0, 0) == 0.0
    assert calculate_threat_index(100, 100, 100) == 100.0
    assert classify_threat(10, 15, 5)['level'] == 'NORMAL'
    assert classify_threat(60, 40, 30)['level'] == 'WARNING'
    assert classify_threat(85, 80, 95)['level'] == 'CRITICAL'
    assert classify_threat(95, 20, 50)['level'] == 'WARNING'
    assert classify_threat(70, 50, 60)['verified'] is True

    # Coverage & baseline.
    base = assess([])
    assert len(DEVICES) == 26 and len(ROOMS) == 36
    assert all(route(r, base)['status'] == 'MODELED_ROUTE_AVAILABLE' for r in ROOMS)
    assert all(route(r, assess([], unavailable_gates=GATES))['status']
               == 'NO_CONFIRMED_ROUTE' for r in ROOMS)

    # Threat at Gate-W area (TPB-CAM-OUT-L):
    # Every building can evacuate to GATE-NE!
    s_gate_w = assess([Observation('e1', 'TPB-CAM-OUT-L', 'CRITICAL', 1)])
    assert all(route(r, s_gate_w)['status'] == 'MODELED_ROUTE_AVAILABLE' for r in ROOMS)
    assert all(route(r, s_gate_w)['gate'] == 'GATE-NE' for r in ROOMS)
    assert any('STAIR-R' in n for n in (route('TPB-F1-R1', s_gate_w)['route'] or []))

    # Indoor CRITICAL on TPB-F1 -> F1 is Red, upper floors Hold (Yellow), AB/LB Green:
    obs = [Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 2),
           Observation('e2', 'TPB-F1-CAM-R', 'CRITICAL', 1)]
    s = assess(obs)
    assert s['raw_detection_count'] == 3
    assert route('TPB-F4-R3', s)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE'
    assert route('TPB-F1-R1', s)['status'] == 'NO_CONFIRMED_ROUTE'
    assert route('AB-F4-R2', s)['status'] == 'MODELED_ROUTE_AVAILABLE'

    # Fresh snapshot clears stale threats.
    assert route('TPB-F2-R1', assess([]))['status'] == 'MODELED_ROUTE_AVAILABLE'

    # Every camera covers <= 3 rooms; every room is covered.
    assert all(len(COVERAGE[d]) <= 3 for d in DEVICES)
    assert all(any(r in COVERAGE[d] for d in DEVICES) for r in ROOMS)

    print('PASS: dynamic_evacuation self-check')
