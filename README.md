# MASTER PROJECT HANDOVER PROMPT — COMPLETE CONTEXT AND SOURCE CODE

You are taking over an ongoing undergraduate capstone project. Treat this document as the working specification and audit the attached source; do not claim unverified implementation is complete. The user wants simple, readable, ready-to-run code, fast progress, minimal unnecessary explanations, and a functional dashboard targeted for Friday, 16 October 2026 (target, not guarantee). Keep the approved research scope unchanged. Work from the existing Google Colab notebook once uploaded, and preserve it as a backup.

## 1. Official identity and purpose
Official title: **Microcontroller-Based Acoustic-Visual Threat Detection and Evacuation Simulation for Sto. Niño Senior High School, Tacloban City**. Do not use the former project nickname in UI, code labels, documentation, or responses. The supplied school drawing is a **DEMO campus representation**, not a certified survey, emergency plan, or deployed safety system. Goal: process prerecorded video/audio from assigned simulated camera devices; compute object, pose, acoustic indicators; combine into prototype threat assessment; map observations to uncertain campus zones; handle concurrent incidents; recompute modeled routes from every classroom through either of its two doors to either of two gates; show incidents, routes and limitations on a Streamlit dashboard; optionally demonstrate virtual ESP32, LEDs, buzzer and servo in Wokwi. Authorized human oversight and school-approved procedures take precedence; do not automatically command real occupants to evacuate, descend or shelter based solely on simulated AI.

## 2. Source-of-truth and progress, as of 13 October 2026
- Previous Google Colab notebook exists but its full current contents have NOT been retrieved or reviewed. Colab URL: https://colab.research.google.com/drive/1GhT_RjlxQF3XczeuynvZETF7a_OLrOUq?usp=sharing . Google Drive folder link: https://drive.google.com/drive/folders/1G6uNOAuhaovr8RKyhbQMAbCLTwh_6fdU?usp=drive_link . Do not assume those links are accessible; request direct .ipynb upload if necessary.
- Historical Colab progress: Sections 1–5 included initial graph setup, 66 modeled locations, NetworkX pathfinding and basic threat simulation. Section 6 dynamic route recalculation was being refined. Historical graph had 3 disconnected components of sizes 32, 24 and 10. Some tests returned (None,None) after corridor/stair blocks, which must be represented as no available modeled route rather than fabricated paths. The exact notebook cell numbers/content are NOT verified.
- Historical functions: find_route_on_graph(graph,start,destination) -> (route,distance) or (None,None); simulate_threat(threat_location) -> (test_graph,affected_locations); get_evacuation_result(start,destination,threat_location) -> dict; calculate_threat_index(acoustic,pose,object_detection); run_campus_sentinel(...) was the old internal function name, which should be renamed when integrating to avoid using the former nickname. These are LEGACY contracts, not necessarily in latest file.
- A first new demo_school_routing.py and dashboard.py exist. A more advanced dynamic_evacuation.py exists and is the CURRENT routing candidate. Its initial built-in assertions reportedly pass; it has NOT yet been fully integrated with the old Colab notebook, detector models, or Streamlit dashboard. The existing dashboard imports demo_school_routing.py, NOT dynamic_evacuation.py, so it is a starter and needs refactoring. Do not maintain two competing graph implementations.
- Actual YOLOv8 object/pose, Librosa acoustic processing, video ingest, live event lifecycle, full UI, Wokwi linkage, evaluation and final report are PLANNED / not verified as completed. Detection may be simulated to get a working dashboard first. No real-world detection accuracy or safety claim.

## 3. Floor plan and modeled geometry
A supplied image of the entire demo school is the primary visual reference; include/inspect the attached floor-plan JPG. Current interpretation: B1 has 4 floors x 5 rooms = 20; B2 has 4 floors x 3 rooms = 12; B3 has 2 floors x 2 rooms = 4; TOTAL 36 rooms across 10 floor levels. Every classroom has TWO doors at opposite ends, modeled as -DL and -DR. Each floor has a corridor/veranda and left/right stair access. Two potential destination gates: GATE-W (western) and GATE-NE (northeastern). Outdoors links among buildings, courtyard and gates are illustrative/hypothetical; actual connectivity, path lengths, exits, assembly points, visibility and camera placement must be verified with an approved layout/survey. Do not call abstract edge weights meters or travel times. Model nodes for rooms, doors, corridor segments, stair nodes, building outdoor approaches, courtyard/path nodes, gates. A shortest path may choose either door and either available gate; the physically nearest gate is not necessarily safest when hazards block paths. No path -> NO_CONFIRMED_ROUTE / HOLD_FOR_AUTHORIZED_GUIDANCE, not a fabricated route.

Current graph identifiers: B1-F4-R3, B2-F2-R1, B3-F2-R2; room doors B1-F4-R3-DL / -DR; corridor B1-F4-C0..C5; stairs B1-F4-STAIR-L/-R; outdoor B1-OUT-L/-R; WEST-PATH, NORTH-PATH, EAST-PATH, COURTYARD, GATE-W, GATE-NE. This differs from the legacy B1-F4-CORRIDOR naming; update callers/tests when migrating.

## 4. Camera/device simulation and threat location uncertainty
Current candidate: two corner cameras per floor (10 floors x 2 = 20) plus two outdoor approach cameras per building (3 x 2 = 6), total 26 simulated devices. Indoor devices at opposite ends cover up to three nearby rooms; overlaps are intentional. Each classroom is assigned to at least one camera, and coverage counts are asserted. Outdoor cameras currently cover their corresponding outdoor approach NODE only. This DOES NOT prove optical coverage of every physical school area or inside each classroom: need line-of-sight, walls, doors, corridors, blind spots, lighting, outdoor perimeters and realistic camera field-of-view survey. User proposes to feed prerecorded video associated with a device ID; if video qualifies as a threat, assume it lies somewhere in that device's modeled coverage. If a location is specifically verified and within device coverage, use that; otherwise conservatively consider the full coverage area uncertain. Do not pretend video itself provides reliable geolocation. Keep device_id, event_id, timestamp/frame, input source, scores, threat level, optional confirmed location and incident_id.

Simultaneous observations from different devices may be independent or overlapping. Report count_in_video and raw_detection_count; only report a campus-wide unique threat count if tracking/deduplication evidence supports it. An incident_id may group observations but does not automatically prove unique persons. Two cameras observing one incident must not silently double-count unique threats. Video detections should have an event lifecycle: first seen, updated, last seen, active, expired/resolved, with confidence/confirmation and configurable temporal persistence to avoid flicker or permanently blocked routes. Treat fresh snapshot evaluation atomically and distinguish WARNING, CRITICAL and NORMAL.

## 5. Threat index and verification — prototype, not validated science
Legacy design inputs acoustic A, pose P, object O in [0,100]. Index = 0.25*A + 0.30*P + 0.45*O. Initial verification gate: O >= 60 and at least TWO of A/P/O >= 50. CRITICAL when index >= 70 AND gate verified. WARNING when index >= 30 or high index but not verified. Else NORMAL. Clarify edge cases and test exact boundaries; thresholds/weights are project assumptions and should be documented as adjustable, not presented as measured real-world probabilities. YOLOv8 object model can only detect classes it was trained to recognize; generic pretrained models may not include firearms. Pose does not prove intent; audio alone does not prove a threat. Separate detection/assessment from routing. Route only on verified modeled incidents or manual authorized hazard blocks according to documented policy; WARNING should trigger review/caution, not unverified automatic life-safety action.

## 6. Current candidate dynamic routing behavior and gaps to audit
NetworkX weighted undirected graph; all buildings connected through hypothetical outdoors; shortest route from each of 36 rooms to both gates, considering either door. Critical indoor camera with unconfirmed location currently blocks all covered rooms AND all corridor segments and both stair nodes on its floor. Thus upper floors cannot descend through that affected floor. This is deliberately conservative, but may suppress viable safe routes; avoid describing it as physically proven safety. For lower-floor threats, consider both vertical shafts and alternative routes; do NOT send people through an affected floor or assume upper floors should automatically evacuate. If origin lies in blocked/uncertain area -> HOLD_FOR_AUTHORIZED_GUIDANCE. Critical outdoor camera blocks covered outdoor approach. Manual blocks, closed edges and unavailable gates supported. Current WARNING nodes are removed from routing graph too (caution=set then graph removes blocked|caution): this is conservative but potentially inconsistent with intended 'warning review only' semantics; decide and document a policy. Snapshot resets previous hazards when new observation list is supplied; add lifecycle/time-based persistence before dashboard integration. `route(room,snapshot,current=None)` allows a current node but requires a valid classroom ID; confirm actual position and path continuity before rerouting an in-progress evacuation. Current shortest-path algorithm optimizes illustrative cost only, not exposure, congestion, accessibility, capacity, travel time or dynamically moving crowds. Do not claim globally safest or seamless real-world evacuation. Consider route churn/hysteresis, gate capacity, occupancy and stairs only as explicitly labeled later enhancements or demo parameters.

## 7. Required code architecture / contracts
- One canonical graph builder and node schema; no parallel old/new graphs.
- `Observation(event_id,device_id,level,count=1,location=None,incident_id=None)` is current dataclass. Add optional timestamp/source/scores only with backwards-compatible changes and tests.
- `assess(observations,manual_blocks=(),closed_edges=(),unavailable_gates=())` returns snapshot with `graph`, `blocked`, `caution`, `events`, `observation_count`, `raw_detection_count`, `known_incident_count`, `unique_threat_count=None`, `possible_threat_locations`, `note`.
- `route(room,snapshot,current=None)` returns `room,status,gate,door,route`, plus `cost` or `reason` as appropriate.
- `all_routes(snapshot)` returns route dict for 36 classrooms.
- `evaluate(observations=(),**kwargs)` returns serializable assessment + routes (without NetworkX graph).
- Add pure `calculate_threat_index` and `classify_threat` functions with explicit validation and deterministic boundary tests. Connect detector output to Observation; avoid circular imports.
- Dashboard must import the canonical module and present device selection, prerecorded clip/mock scores, concurrent events, floor/building view, affected zones, route for any classroom, all-room statuses, gate chosen, detection count caveat, manual closures, and no-route/hold message. Do not expose the old project nickname.
- Wokwi virtual ESP32 LED/buzzer/servo represents a demonstration of status signals, not automatic real-life access control. A real integration transport must be explicitly implemented/tested rather than claimed.

## 8. Detailed Colab migration plan — audit actual .ipynb first
Backup old notebook. Inventory every cell and output; do not assert these are exact existing numbered cells until inspected. Reorganize into: (1) imports/install, (2) canonical demo campus graph and layout metadata, (3) camera coverage and verification assertions, (4) pure threat-index/verification/classification, (5) event/observation input and deduplication, (6) multi-threat dynamic graph snapshot and all-room routing, (7) integration tests including video mock inputs, (8) visualization/export/API-friendly results. Retain valid old audio/visual experiments, not legacy conflicting graph functions. Change old node names to canonical schema and adjust callers. Keep tests from historical B1-F4-R3 and B3-F2-R2 examples but reinterpret according to new graph. The current .py module may be uploaded to Colab and imported after `!pip install networkx`; ensure module is reloaded when edited (`import importlib; importlib.reload(dynamic_evacuation)`). Export code into .py files for Streamlit rather than copying notebook cell state blindly.

## 9. Mandatory test matrix before calling routing complete
Baseline all 36 rooms reach one of two gates; every room has exactly two door nodes and coverage >=1; every camera <=3 indoor rooms; verify graph connected and both gates present; one confirmed threat and one uncertain camera-area threat; two simultaneous threats in same/different buildings/floors; overlapping camera observations and unique-count caveat; 3+ threats; ground-floor threat with occupants above; top-floor threat with occupants below; threats on one/both stairs; corridor threats; outdoor paths and gate blockage; both gates blocked; origin threatened; manual closed edge; warning-only policy; unknown device/location and duplicate event ID errors; event expiry/reset; route updates after current location changes; no false route across disconnected/removed nodes; route cost agrees with path edge weights; consistent deterministic tie breaking; performance for all rooms. Test edge thresholds 29.99/30/49.99/50/59.99/60/69.99/70/100. Include validation of actual camera coverage assumptions separately from graph coverage.

## 10. End-to-end workflow and priority
A. Preserve and inspect .ipynb and attached .py files; run current assertions; document any failures.
B. Freeze campus node IDs, graph schema and assumed path weights; review floor plan against source image.
C. Resolve warning policy, uncertainty propagation, stairs/vertical isolation, event lifecycle, deduplication and rerouting stability. Implement tests, not just prose.
D. Build minimal deterministic fake video/audio score adapter; connect classification -> incident records -> route engine; demonstrate multiple concurrent threats and both gates.
E. Streamlit dashboard: use current canonical module, display event feed, coverage map, per-floor routes, two-gate decisions, all 36 statuses and simulation disclaimer. Focus on a working demo by Friday 16 Oct 2026, then improve visuals.
F. Integrate real prerecorded-video YOLO object/pose and Librosa audio modules only after confirming classes, sample files, model dependencies and runtime. Document false positives/negatives and limited dataset. No claims of full AI implementation before tested.
G. Wokwi virtual alert demonstration and integration; repeat reproducible scenario tests; capture evidence, screenshots and report results.
H. SRS, Chapter III technical background, implementation/methodology, test cases, limitations, final presentation. Chapter III sections: 3.1 Current System; 3.2 Proposed System; 3.2.1 Software; 3.2.2 Hardware; 3.2.3 People-ware. Use official title and credible citations for established technologies; distinguish own prototype choices.

## 11. Immediate instructions to receiving assistant
Read the source code BELOW before changing it. Inspect uploaded latest .ipynb when available, and explicitly report cells to keep/replace; do not invent notebook cell numbers. Verify code via executable tests. Prefer one complete ready-to-run updated Colab notebook and modular .py files. Clearly label confirmed functionality vs assumptions vs unfinished features. Keep replies concise and provide full code/file artifacts when asked. Do not promise a certified evacuation system. The floor-plan image should be provided alongside this document; if unavailable, ask for it rather than claiming you can see it.

## 12. Full source files as of handover
The following code is reproduced verbatim from the available working-directory files. `dynamic_evacuation.py` is the most recent routing candidate; `demo_school_routing.py` and `dashboard.py` are earlier starter versions, supplied for migration comparison, NOT simultaneous deployment.

### dynamic_evacuation.py
```python
"""Demo-only routing. Costs are illustrative, never a certified life-safety system."""
from dataclasses import dataclass
from collections import defaultdict
import networkx as nx

BUILDINGS = {1:(4,5), 2:(4,3), 3:(2,2)}
GATES = ('GATE-W','GATE-NE')
G = nx.Graph()
ROOMS, DEVICES, COVERAGE = [], {}, {}

def edge(a,b,w=1):
    G.add_edge(a,b,weight=float(w))

def build():
    for b,(floors,count) in BUILDINGS.items():
        for f in range(1,floors+1):
            p=f'B{b}-F{f}'
            for i in range(count+1):
                c=f'{p}-C{i}'
                G.add_node(c,kind='corridor',building=b,floor=f)
                if i: edge(f'{p}-C{i-1}',c,2)
            for r in range(1,count+1):
                room=f'{p}-R{r}'; ROOMS.append(room)
                G.add_node(room,kind='room',building=b,floor=f)
                for side,seg in (('L',r-1),('R',r)):
                    door=f'{room}-D{side}'
                    G.add_node(door,kind='door',building=b,floor=f)
                    edge(room,door,.5); edge(door,f'{p}-C{seg}',.5)
            for side,seg in (('L',0),('R',count)):
                stair=f'{p}-STAIR-{side}'
                G.add_node(stair,kind='stair',building=b,floor=f)
                edge(stair,f'{p}-C{seg}',1)
                if f>1: edge(stair,f'B{b}-F{f-1}-STAIR-{side}',4)
            # Two end devices cover at most three rooms each; overlapping coverage is intentional.
            for side,covered in (('L',range(1,min(count,3)+1)),('R',range(max(1,count-2),count+1))):
                did=f'{p}-CAM-{side}'
                DEVICES[did]={'building':b,'floor':f,'zone':'indoor','side':side}
                COVERAGE[did]=frozenset(f'{p}-R{r}' for r in covered)
        for side in 'LR':
            out=f'B{b}-OUT-{side}'
            G.add_node(out,kind='outdoor',building=b,floor=0)
            edge(f'B{b}-F1-STAIR-{side}',out,1)
            did=f'B{b}-CAM-OUT-{side}'
            DEVICES[did]={'building':b,'floor':0,'zone':'outdoor','side':side}
            COVERAGE[did]=frozenset((out,))
    # Hypothetical site paths; revise against an approved, measured site survey.
    for a,b,w in [('B1-OUT-L','WEST-PATH',2),('B3-OUT-L','WEST-PATH',3),
                  ('WEST-PATH','GATE-W',2),('B1-OUT-R','NORTH-PATH',2),
                  ('NORTH-PATH','GATE-NE',2),('B2-OUT-R','EAST-PATH',3),
                  ('EAST-PATH','NORTH-PATH',3),('B2-OUT-L','COURTYARD',2),
                  ('B3-OUT-R','COURTYARD',2),('COURTYARD','WEST-PATH',4),
                  ('COURTYARD','EAST-PATH',4),('B1-OUT-L','COURTYARD',3),
                  ('B1-OUT-R','COURTYARD',4)]: edge(a,b,w)
    for gate in GATES: G.nodes[gate]['kind']='gate'
    for n in G: G.nodes[n].setdefault('kind','outdoor')
    assert len(ROOMS)==36 and nx.is_connected(G)
    assert all(any(r in COVERAGE[d] for d in DEVICES) for r in ROOMS)
    return G
build()

@dataclass(frozen=True)
class Observation:
    event_id: str
    device_id: str
    level: str  # NORMAL, WARNING, CRITICAL; determined upstream, not here
    count: int = 1  # independent detections in this one video; NOT unique people campus-wide
    location: str | None = None  # optional confirmed location inside device coverage
    incident_id: str | None = None  # common ID permits deduplication of overlapping cameras

def _validate(observations):
    ids=set()
    for o in observations:
        if o.event_id in ids: raise ValueError('Duplicate event_id')
        ids.add(o.event_id)
        if o.device_id not in DEVICES: raise ValueError(f'Unknown device: {o.device_id}')
        if o.level not in ('NORMAL','WARNING','CRITICAL'): raise ValueError('Invalid level')
        if type(o.count) is not int or o.count<0: raise ValueError('Invalid count')
        if o.location is not None and o.location not in COVERAGE[o.device_id]:
            raise ValueError('Location is outside device coverage')

def assess(observations, manual_blocks=(), closed_edges=(), unavailable_gates=()):
    """A fresh, atomic snapshot. Unknown location => conservatively protect whole camera coverage.
    Affected floor's stairs may carry risk to upper floors; no automatic descend through it.
    """
    observations=list(observations); _validate(observations)
    unknown=(set(manual_blocks)|set(unavailable_gates))-set(G)
    if unknown: raise ValueError(f'Unknown blocked nodes: {sorted(unknown)}')
    if set(unavailable_gates)-set(GATES): raise ValueError('Invalid gate')
    for a,b in closed_edges:
        if not G.has_edge(a,b): raise ValueError(f'Unknown edge: {a}, {b}')
    blocked=set(manual_blocks)|set(unavailable_gates)
    caution=set(); affected=[]; events=[]; seen_incidents=set(); unique_known=0; raw=0
    critical_origins=[]
    for o in observations:
        if o.level=='NORMAL': continue
        area={o.location} if o.location else set(COVERAGE[o.device_id])
        events.append({'event_id':o.event_id,'device':o.device_id,'level':o.level,
                       'count_in_video':o.count,'possible_locations':sorted(area),
                       'location_confirmed':o.location is not None})
        raw+=o.count
        if o.incident_id is not None and o.incident_id not in seen_incidents:
            unique_known+=o.count; seen_incidents.add(o.incident_id)
        if o.level=='CRITICAL':
            blocked.update(area); critical_origins.append((o,area))
        else: caution.update(area)
        affected.extend(area)
    # Room threats: both doors are unsafe; corridor/stair nodes are not automatically
    # cleared. A threat somewhere in a camera's coverage is uncertain, so block all covered rooms.
    for o,area in critical_origins:
        info=DEVICES[o.device_id]
        if info['zone']=='indoor':
            b,f=info['building'],info['floor']; p=f'B{b}-F{f}'
            # A camera cannot establish that the shared veranda is clear.
            blocked.update(f'{p}-C{i}' for i in range(BUILDINGS[b][1]+1))
            # If a threat is on a lower floor, upper floors cannot rely on stairs through it.
            # Block both stair nodes on the affected floor; graph disconnects vertical transit.
            blocked.update((f'{p}-STAIR-L',f'{p}-STAIR-R'))
            # No route is issued from an affected floor until location/paths are verified.
        else:
            # Outdoor camera's view is limited; block its observed outdoor approach.
            blocked.update(area)
    # Manual stair/corridor threats are represented by blocked nodes and hence break vertical paths.
    graph=G.copy(); graph.remove_nodes_from(blocked | caution)
    for a,b in closed_edges:
        if graph.has_edge(a,b): graph.remove_edge(a,b)
    return {'graph':graph,'blocked':sorted(blocked),'caution':sorted(caution-blocked),
            'events':events,'observation_count':len(events),'raw_detection_count':raw,
            'known_incident_count':len(seen_incidents),
            'known_incident_detection_sum':unique_known,
            'unique_threat_count':None, # cannot infer unique people from overlapping videos
            'possible_threat_locations':sorted(set(affected)),
            'note':'Counts are detections per video, not confirmed distinct threats.'}

def route(room,snapshot, current=None):
    if room not in ROOMS: raise ValueError('Unknown classroom')
    graph=snapshot['graph']
    start=current or room
    if start not in G: raise ValueError('Unknown current node')
    if start not in graph:
        return {'room':room,'status':'HOLD_FOR_AUTHORIZED_GUIDANCE','gate':None,'door':None,
                'route':None,'reason':'Origin is within blocked or uncertain threat area.'}
    choices=[]
    for gate in GATES:
        if gate not in graph: continue
        try:
            path=nx.shortest_path(graph,start,gate,weight='weight')
            choices.append((nx.path_weight(graph,path,weight='weight'),gate,path))
        except nx.NetworkXNoPath: pass
    if not choices:
        return {'room':room,'status':'NO_CONFIRMED_ROUTE','gate':None,'door':None,
                'route':None,'reason':'No verified modeled path. Follow authorized emergency guidance.'}
    cost,gate,path=min(choices,key=lambda x:(x[0],x[1]))
    door=next((n for n in path if n.startswith(room+'-D')),None)
    return {'room':room,'status':'MODELED_ROUTE_AVAILABLE','gate':gate,'door':door,
            'route':path,'cost':cost,'reason':'Shortest available modeled route; not a safety certification.'}

def all_routes(snapshot):
    return {r:route(r,snapshot) for r in ROOMS}

def evaluate(observations=(),**kwargs):
    snapshot=assess(observations,**kwargs)
    routes=all_routes(snapshot)
    return {k:v for k,v in snapshot.items() if k!='graph'}|{'routes':routes}

if __name__=='__main__':
    base=assess([])
    assert len(DEVICES)==26 and len(ROOMS)==36
    assert all(route(r,base)['gate'] in GATES for r in ROOMS)
    assert all(route(r,assess([],unavailable_gates=GATES))['gate'] is None for r in ROOMS)
    a=Observation('1','B1-F1-CAM-L','CRITICAL',2)
    b=Observation('2','B1-F1-CAM-R','CRITICAL',1)
    s=assess([a,b]); assert s['raw_detection_count']==3
    assert route('B1-F4-R3',s)['gate'] is None # upper floor cannot descend through threat floor
    assert route('B2-F4-R2',s)['gate'] in GATES
    assert route('B1-F1-R1',s)['gate'] is None
    assert route('B1-F2-R1',assess([]))['gate'] in GATES # fresh snapshot clears stale threats
    assert all(len(COVERAGE[d])<=3 for d in DEVICES)
    assert all(any(r in COVERAGE[d] for d in DEVICES) for r in ROOMS)
    print('PASS: coverage, baseline, simultaneous threats, floor isolation, alternate gates, reset')

```

### demo_school_routing.py
```python
import networkx as nx

# DEMO distances are relative movement costs, not surveyed metres.
G = nx.Graph()
ROOMS = []
GATES = ['GATE-W', 'GATE-NE']

def connect(a, b, cost=1):
    G.add_edge(a, b, weight=cost)

def build_school():
    for building, floors, rooms in [(1, 4, 5), (2, 4, 3), (3, 2, 2)]:
        for floor in range(1, floors + 1):
            prefix = f'B{building}-F{floor}'
            # Corridor segments give each classroom two separate door connections.
            for segment in range(rooms + 1):
                G.add_node(f'{prefix}-C{segment}', kind='corridor', building=building, floor=floor)
                if segment:
                    connect(f'{prefix}-C{segment-1}', f'{prefix}-C{segment}', 2)
            for room_number in range(1, rooms + 1):
                room = f'{prefix}-R{room_number}'
                ROOMS.append(room)
                G.add_node(room, kind='room', building=building, floor=floor)
                for side, segment in [('L', room_number - 1), ('R', room_number)]:
                    door = f'{room}-D{side}'
                    G.add_node(door, kind='door', building=building, floor=floor)
                    connect(room, door, 0.5)
                    connect(door, f'{prefix}-C{segment}', 0.5)
            for side, segment in [('L', 0), ('R', rooms)]:
                stair = f'{prefix}-STAIR-{side}'
                G.add_node(stair, kind='stair', building=building, floor=floor)
                connect(stair, f'{prefix}-C{segment}', 1)
                if floor > 1:
                    connect(stair, f'B{building}-F{floor-1}-STAIR-{side}', 4)
        for side in ['L', 'R']:
            connect(f'B{building}-F1-STAIR-{side}', f'B{building}-OUT-{side}', 1)
            G.nodes[f'B{building}-OUT-{side}']['kind'] = 'outdoor'

    # Illustrative outdoor paths inferred from site arrangement; verify on site.
    for a, b, cost in [
        ('B1-OUT-L', 'WEST-PATH', 2), ('B3-OUT-L', 'WEST-PATH', 3),
        ('WEST-PATH', 'GATE-W', 2), ('B1-OUT-R', 'NORTH-PATH', 2),
        ('NORTH-PATH', 'GATE-NE', 2), ('B2-OUT-R', 'EAST-PATH', 3),
        ('EAST-PATH', 'NORTH-PATH', 3), ('B2-OUT-L', 'COURTYARD', 2),
        ('B3-OUT-R', 'COURTYARD', 2), ('COURTYARD', 'WEST-PATH', 4),
        ('COURTYARD', 'EAST-PATH', 4), ('B1-OUT-L', 'COURTYARD', 3),
        ('B1-OUT-R', 'COURTYARD', 4)
    ]:
        connect(a, b, cost)
    for gate in GATES:
        G.nodes[gate]['kind'] = 'gate'
    for node in G:
        G.nodes[node].setdefault('kind', 'outdoor')
    return G

build_school()

def affected_graph(blocked=None, blocked_edges=None):
    blocked = set(blocked or [])
    blocked_edges = blocked_edges or []
    unknown = blocked - set(G)
    if unknown:
        raise ValueError(f'Unknown locations: {sorted(unknown)}')
    if any(gate in blocked for gate in GATES):
        pass  # A gate can be unavailable; the other gate remains a candidate.
    graph = G.copy()
    graph.remove_nodes_from(blocked)
    for a, b in blocked_edges:
        if graph.has_edge(a, b):
            graph.remove_edge(a, b)
    return graph

def safest_route(room, blocked=None, blocked_edges=None):
    if room not in ROOMS:
        raise ValueError('Select a valid classroom ID.')
    graph = affected_graph(blocked, blocked_edges)
    if room not in graph:
        return {'status': 'ROOM_BLOCKED', 'room': room, 'route': None, 'gate': None}
    candidates = []
    for gate in GATES:
        if gate in graph:
            try:
                route = nx.shortest_path(graph, room, gate, weight='weight')
                cost = nx.path_weight(graph, route, weight='weight')
                candidates.append((cost, gate, route))
            except nx.NetworkXNoPath:
                continue
    if not candidates:
        return {'status': 'NO_CONFIRMED_ROUTE', 'room': room, 'route': None, 'gate': None,
                'instruction': 'No modeled route available. Follow authorized emergency guidance.'}
    cost, gate, route = min(candidates, key=lambda x: (x[0], x[1]))
    return {'status': 'ROUTE_AVAILABLE', 'room': room, 'gate': gate,
            'door': next((n for n in route if n.endswith(('-DL', '-DR'))), None),
            'cost': cost, 'route': route, 'note': 'Shortest available modeled path, not a certified safe evacuation route.'}

def all_classroom_routes(blocked=None, blocked_edges=None):
    return {room: safest_route(room, blocked, blocked_edges) for room in ROOMS}

if __name__ == '__main__':
    assert len(ROOMS) == 36
    assert nx.is_connected(G)
    assert all(all_classroom_routes()[room]['status'] == 'ROUTE_AVAILABLE' for room in ROOMS)
    assert safest_route('B1-F1-R1', blocked=['GATE-W'])['gate'] == 'GATE-NE'
    assert safest_route('B1-F1-R1', blocked=GATES)['status'] == 'NO_CONFIRMED_ROUTE'
    print('PASS: 36 rooms, connected campus, alternate gate, both gates blocked')
    for room in ['B1-F4-R3', 'B2-F4-R2', 'B3-F2-R2']:
        print(safest_route(room))

```

### dashboard.py
```python
import streamlit as st
from demo_school_routing import G, ROOMS, GATES, safest_route, all_classroom_routes

st.set_page_config(page_title='School Threat and Evacuation Demo', layout='wide')
st.title('Acoustic-Visual Threat Detection and Evacuation Simulation')
st.caption('Demo school layout. Routes use illustrative costs and are not certified emergency instructions.')
room = st.selectbox('Classroom', ROOMS)
blocked = st.multiselect('Simulated inaccessible locations (rooms, doors, corridors, stairs, outdoor paths, gates)', sorted(G.nodes))
result = safest_route(room, blocked)
a, b, c = st.columns(3)
a.metric('Classrooms', len(ROOMS))
b.metric('Available routes', sum(r['status'] == 'ROUTE_AVAILABLE' for r in all_classroom_routes(blocked).values()))
c.metric('Selected route status', result['status'])
st.subheader('Selected classroom result')
if result['status'] == 'ROUTE_AVAILABLE':
    st.success(f"Destination: {result['gate']} | Door: {result['door']} | Relative cost: {result['cost']}")
    st.write(' → '.join(result['route']))
else:
    st.warning('No confirmed modeled route. Follow authorized emergency guidance.')
st.subheader('All classroom routes')
rows = []
for name, value in all_classroom_routes(blocked).items():
    rows.append({'Classroom': name, 'Status': value['status'], 'Gate': value.get('gate'),
                 'Door': value.get('door'), 'Relative cost': value.get('cost')})
st.dataframe(rows, use_container_width=True, hide_index=True)
st.info('Threat classification inputs and floor-map visualization will be connected as separate modules.')

```
