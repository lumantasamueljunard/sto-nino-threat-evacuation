"""Phase 2 — Mandatory test matrix for the Sto. Niño SHS
threat detection and evacuation simulation.

Run with:
    py test_matrix.py

Every test prints PASS or FAIL. At the end, a summary is printed.
"""
import time
import json
import networkx as nx

from dynamic_evacuation import (
    G, ROOMS, DEVICES, COVERAGE, GATES, BUILDINGS,
    Observation, assess, route, all_routes, evaluate,
    calculate_threat_index, classify_threat, route_summary_counts,
)
from demo_detector import prebaked_scenarios


# ---------------------------------------------------------------------------
# Tiny test harness
# ---------------------------------------------------------------------------
_results = []


def check(name, condition, detail=''):
    ok = bool(condition)
    _results.append((name, ok, detail))
    tag = 'PASS' if ok else 'FAIL'
    print(f'[{tag}] {name}' + (f'  -- {detail}' if (detail and not ok) else ''))
    return ok


def expect_raises(name, fn, exc_type):
    try:
        fn()
    except exc_type:
        check(name, True)
        return
    except Exception as e:
        check(name, False, f'Expected {exc_type.__name__}, got {type(e).__name__}: {e}')
        return
    check(name, False, f'Expected {exc_type.__name__}, no exception raised')


# ===========================================================================
# 1. Graph integrity
# ===========================================================================
print('\n== 1. Graph integrity ==')
check('36 rooms defined', len(ROOMS) == 36)
check('26 devices defined', len(DEVICES) == 26)
check('Graph is connected', nx.is_connected(G))
check('Both gates present in graph', all(g in G for g in GATES))

check('Every room has two door nodes (DL and DR)',
      all(f'{r}-D{s}' in G for r in ROOMS for s in ('L', 'R')))

check('Every room covered by >= 1 device',
      all(any(r in COVERAGE[d] for d in DEVICES) for r in ROOMS))

indoor_cams = [d for d, info in DEVICES.items() if info['zone'] == 'indoor']
check('Every indoor camera covers <= 3 rooms',
      all(len(COVERAGE[d]) <= 3 for d in indoor_cams))


# ===========================================================================
# 2. Baseline routing
# ===========================================================================
print('\n== 2. Baseline routing ==')
base = assess([])
base_routes = all_routes(base)

check('All 36 rooms route to a gate',
      all(v['status'] == 'MODELED_ROUTE_AVAILABLE' for v in base_routes.values()))
check('Every chosen gate is GATE-W or GATE-NE',
      all(v['gate'] in GATES for v in base_routes.values()
          if v['status'] == 'MODELED_ROUTE_AVAILABLE'))
check('Every route starts at its own room',
      all(v['route'][0] == v['room'] for v in base_routes.values()
          if v['status'] == 'MODELED_ROUTE_AVAILABLE'))
check('Every route ends at its chosen gate',
      all(v['route'][-1] == v['gate'] for v in base_routes.values()
          if v['status'] == 'MODELED_ROUTE_AVAILABLE'))
check('Every route hits exactly one door of its room',
      all(sum(1 for n in v['route'] if n.startswith(v['room'] + '-D')) == 1
          for v in base_routes.values()
          if v['status'] == 'MODELED_ROUTE_AVAILABLE'))


# ===========================================================================
# 3. Cost consistency
# ===========================================================================
print('\n== 3. Route cost consistency ==')
def cost_matches(v, snapshot):
    if v['status'] != 'MODELED_ROUTE_AVAILABLE':
        return True
    return abs(nx.path_weight(snapshot['graph'], v['route'], weight='weight')
               - v['cost']) < 1e-9

check('Every reported cost equals sum of edge weights',
      all(cost_matches(v, base) for v in base_routes.values()))


# ===========================================================================
# 4. Gate blocking
# ===========================================================================
print('\n== 4. Gate blocking ==')
no_gates = assess([], unavailable_gates=GATES)
check('Both gates blocked -> NO_CONFIRMED_ROUTE for every room',
      all(route(r, no_gates)['status'] == 'NO_CONFIRMED_ROUTE' for r in ROOMS))

only_east = assess([], unavailable_gates=('GATE-W',))
only_east_routes = [route(r, only_east) for r in ROOMS]
check('Only GATE-W blocked -> at least one route remains',
      any(v['status'] == 'MODELED_ROUTE_AVAILABLE' for v in only_east_routes))
check('Only GATE-W blocked -> all available routes use GATE-NE',
      all(v['gate'] == 'GATE-NE' for v in only_east_routes
          if v['status'] == 'MODELED_ROUTE_AVAILABLE'))


# ===========================================================================
# 5. Threat index boundaries
# ===========================================================================
print('\n== 5. Threat index boundary tests ==')
# Note: when a=p=o=v, index equals v exactly (weights sum to 1.00).
check('Index 29.99 -> NORMAL',
      classify_threat(29.99, 29.99, 29.99)['level'] == 'NORMAL')
check('Index 30.00 -> WARNING',
      classify_threat(30, 30, 30)['level'] == 'WARNING')
check('Index 69.99 -> WARNING',
      classify_threat(69.99, 69.99, 69.99)['level'] == 'WARNING')
check('Index 70.00 with verification -> CRITICAL',
      classify_threat(70, 70, 70)['level'] == 'CRITICAL')

c = classify_threat(49.99, 49.99, 49.99)
check('All signals 49.99 -> supporting_signals = 0', c['supporting_signals'] == 0)
check('All signals 49.99 -> not verified', c['verified'] is False)

c = classify_threat(50, 50, 50)
check('All signals 50 -> supporting_signals = 3', c['supporting_signals'] == 3)

check('Object 59.99 -> verified = False',
      classify_threat(60, 60, 59.99)['verified'] is False)
check('Object 60.00 -> verified = True',
      classify_threat(60, 60, 60)['verified'] is True)

c = classify_threat(100, 100, 59.99)
check('High index but unverified -> WARNING', c['level'] == 'WARNING')
check('High index but unverified -> verified = False', c['verified'] is False)


# ===========================================================================
# 6. Single indoor CRITICAL
# ===========================================================================
print('\n== 6. Single indoor CRITICAL ==')
obs1 = [Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 2, incident_id='inc-1')]
s1 = assess(obs1)
check('1 event recorded', s1['observation_count'] == 1)
check('Raw detection count = 2', s1['raw_detection_count'] == 2)
check('Known incident count = 1', s1['known_incident_count'] == 1)
check('unique_threat_count is None (caveat preserved)',
      s1['unique_threat_count'] is None)
check('Covered room TPB-F1-R1 -> NO_CONFIRMED_ROUTE',
      route('TPB-F1-R1', s1)['status'] == 'NO_CONFIRMED_ROUTE')
check('Covered room TPB-F1-R3 -> NO_CONFIRMED_ROUTE',
      route('TPB-F1-R3', s1)['status'] == 'NO_CONFIRMED_ROUTE')
check('Uncovered room on same floor TPB-F1-R5 -> NO_CONFIRMED_ROUTE (corridor blocked)',
      route('TPB-F1-R5', s1)['status'] == 'NO_CONFIRMED_ROUTE')
check('Upper floor TPB-F4-R3 -> HOLD_FOR_AUTHORIZED_GUIDANCE',
      route('TPB-F4-R3', s1)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE')
check('Different building AB-F4-R2 -> route available',
      route('AB-F4-R2', s1)['status'] == 'MODELED_ROUTE_AVAILABLE')


# ===========================================================================
# 7. Uncertain location (device observation without confirmed room)
# ===========================================================================
print('\n== 7. Uncertain location ==')
obs2 = [Observation('e1', 'TPB-F2-CAM-L', 'CRITICAL', 1)]
s2 = assess(obs2)
check('All covered rooms -> NO_CONFIRMED_ROUTE',
      all(route(r, s2)['status'] == 'NO_CONFIRMED_ROUTE'
          for r in ['TPB-F2-R1', 'TPB-F2-R2', 'TPB-F2-R3']))
check('Floor below (TPB-F1-R1) still route-able',
      route('TPB-F1-R1', s2)['status'] == 'MODELED_ROUTE_AVAILABLE')
check('Floor above (TPB-F3-R1) -> HOLD_FOR_AUTHORIZED_GUIDANCE',
      route('TPB-F3-R1', s2)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE')
check('Top floor (TPB-F4-R1) -> HOLD_FOR_AUTHORIZED_GUIDANCE',
      route('TPB-F4-R1', s2)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE')


# ===========================================================================
# 8. Simultaneous threats in different buildings
# ===========================================================================
print('\n== 8. Simultaneous threats ==')
obs3 = [
    Observation('e1', 'TPB-F2-CAM-L', 'CRITICAL', 1, incident_id='inc-A'),
    Observation('e2', 'LB-F1-CAM-R', 'CRITICAL', 1, incident_id='inc-B'),
]
s3 = assess(obs3)
check('2 events recorded', s3['observation_count'] == 2)
check('2 known incidents', s3['known_incident_count'] == 2)
check('AB-F4-R2 unaffected -> route available',
      route('AB-F4-R2', s3)['status'] == 'MODELED_ROUTE_AVAILABLE')
check('TPB-F1-R1 (below TPB-F2) -> route available',
      route('TPB-F1-R1', s3)['status'] == 'MODELED_ROUTE_AVAILABLE')
check('TPB-F4-R3 (above TPB-F2) -> HOLD_FOR_AUTHORIZED_GUIDANCE',
      route('TPB-F4-R3', s3)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE')


# ===========================================================================
# 9. Overlapping cameras on the same incident
# ===========================================================================
print('\n== 9. Overlapping camera observations ==')
obs4 = [
    Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 2, incident_id='inc-1'),
    Observation('e2', 'TPB-F1-CAM-R', 'CRITICAL', 1, incident_id='inc-1'),
]
s4 = assess(obs4)
check('2 events recorded', s4['observation_count'] == 2)
check('1 known incident (deduplicated)', s4['known_incident_count'] == 1)
check('Raw detection count = 3', s4['raw_detection_count'] == 3)
check('unique_threat_count still None', s4['unique_threat_count'] is None)


# ===========================================================================
# 10. Warning-only policy
# ===========================================================================
print('\n== 10. WARNING policy ==')
obs_warn = [Observation('e1', 'TPB-F1-CAM-L', 'WARNING', 1)]
s_warn = assess(obs_warn)
check('WARNING event recorded', s_warn['observation_count'] == 1)
check('Caution list non-empty', len(s_warn['caution']) > 0)
check('Covered room under WARNING -> HOLD or NO_CONFIRMED_ROUTE',
      route('TPB-F1-R1', s_warn)['status'] in
      ('HOLD_FOR_AUTHORIZED_GUIDANCE', 'NO_CONFIRMED_ROUTE'))


# ===========================================================================
# 11. Stair threat with reroute
# ===========================================================================
print('\n== 11. Stair threat ==')
s_stair = assess([], manual_blocks=['TPB-F4-STAIR-L'])
r_stair = route('TPB-F4-R3', s_stair)
check('Blocking one stair still allows a route',
      r_stair['status'] == 'MODELED_ROUTE_AVAILABLE')
check('Route does not use the blocked stair',
      'TPB-F4-STAIR-L' not in (r_stair['route'] or []))


# ===========================================================================
# 12. Origin threatened
# ===========================================================================
print('\n== 12. Origin threatened ==')
s5 = assess([Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 1)])
check('Origin inside covered area -> NO_CONFIRMED_ROUTE',
      route('TPB-F1-R1', s5)['status'] == 'NO_CONFIRMED_ROUTE')


# ===========================================================================
# 13. Manual closed edge (uses the other door)
# ===========================================================================
print('\n== 13. Manual edge closure ==')
r_base = route('TPB-F4-R3', assess([]))
first_edge = (r_base['route'][0], r_base['route'][1])
first_door = first_edge[1]
other_door = 'TPB-F4-R3-DR' if first_door.endswith('-DL') else 'TPB-F4-R3-DL'
s_edge = assess([], closed_edges=[first_edge])
r_new = route('TPB-F4-R3', s_edge)
check('Closing one door edge still allows a route',
      r_new['status'] == 'MODELED_ROUTE_AVAILABLE')
check('Reroute uses the OTHER door',
      other_door in (r_new['route'] or []))


# ===========================================================================
# 14. Input validation errors
# ===========================================================================
print('\n== 14. Input validation ==')
expect_raises('Unknown device raises ValueError',
              lambda: assess([Observation('e1', 'NONEXISTENT-DEVICE',
                                          'CRITICAL', 1)]),
              ValueError)

expect_raises('Duplicate event_id raises ValueError',
              lambda: assess([Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 1),
                              Observation('e1', 'TPB-F1-CAM-R', 'CRITICAL', 1)]),
              ValueError)

expect_raises('Invalid level raises ValueError',
              lambda: assess([Observation('e1', 'TPB-F1-CAM-L',
                                          'SEVERE', 1)]),
              ValueError)

expect_raises('Location outside coverage raises ValueError',
              lambda: assess([Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL',
                                          1, location='AB-F4-R3')]),
              ValueError)

expect_raises('Unknown manual block raises ValueError',
              lambda: assess([], manual_blocks=['NONEXISTENT-NODE']),
              ValueError)

expect_raises('Invalid gate raises ValueError',
              lambda: assess([], unavailable_gates=('GATE-X',)),
              ValueError)

expect_raises('Unknown edge raises ValueError',
              lambda: assess([], closed_edges=[('TPB-F1-R1', 'AB-F1-R1')]),
              ValueError)


# ===========================================================================
# 15. Reset behaviour (fresh snapshot clears stale threats)
# ===========================================================================
print('\n== 15. Reset behaviour ==')
s_threat = assess([Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 1)])
check('Threat snapshot isolates upper floor -> HOLD',
      route('TPB-F4-R3', s_threat)['status'] == 'HOLD_FOR_AUTHORIZED_GUIDANCE')
check('Fresh empty snapshot restores route',
      route('TPB-F4-R3', assess([]))['status'] == 'MODELED_ROUTE_AVAILABLE')


# ===========================================================================
# 16. Threat at one gate allows full evacuation via opposite gate
# ===========================================================================
print('\n== 16. Gate threat and evacuation rerouting ==')
s_out = assess([Observation('e1', 'TPB-CAM-OUT-L', 'CRITICAL', 1,
                            location='TPB-OUT-L')])
check('Threat at Gate-W area: All rooms can still safely evacuate',
      all(route(r, s_out)['status'] == 'MODELED_ROUTE_AVAILABLE' for r in ROOMS))
check('Threat at Gate-W area: All rooms reroute to GATE-NE',
      all(route(r, s_out)['gate'] == 'GATE-NE' for r in ROOMS))
check('Tech Pro Building avoids Stair L and uses Stair R',
      any('STAIR-R' in n for n in (route('TPB-F1-R1', s_out)['route'] or [])))
check('Occupant currently at blocked node -> NO_CONFIRMED_ROUTE',
      route('TPB-F1-R1', s_out, current='TPB-OUT-L')['status']
      == 'NO_CONFIRMED_ROUTE')


# ===========================================================================
# 17. Deterministic tie-breaking
# ===========================================================================
print('\n== 17. Deterministic tie-breaking ==')
runs = [route('TPB-F4-R3', base) for _ in range(5)]
check('Repeated routing is deterministic',
      all(r['route'] == runs[0]['route'] and r['cost'] == runs[0]['cost']
          for r in runs))


# ===========================================================================
# 18. Performance
# ===========================================================================
print('\n== 18. Performance ==')
t0 = time.perf_counter()
for _ in range(50):
    all_routes(base)
elapsed = time.perf_counter() - t0
check(f'50 full all_routes sweeps in {elapsed:.2f}s (< 5s)', elapsed < 5.0)


# ===========================================================================
# 19. No route crosses a blocked or caution node
# ===========================================================================
print('\n== 19. No false routes across blocked/caution nodes ==')
s_big = assess([Observation('e1', 'TPB-F1-CAM-L', 'CRITICAL', 1)])
off_limits = set(s_big['blocked']) | set(s_big['caution'])
violations = []
for r in ROOMS:
    res = route(r, s_big)
    if res['status'] == 'MODELED_ROUTE_AVAILABLE':
        crossed = set(res['route']) & off_limits
        if crossed:
            violations.append((r, sorted(crossed)))
check('No route crosses a blocked or caution node',
      len(violations) == 0,
      detail=f'violations: {violations[:3]}')


# ===========================================================================
# 20. evaluate() output is JSON-serializable
# ===========================================================================
print('\n== 20. evaluate() serializability ==')
out = evaluate([])
try:
    json.dumps(out)
    check('evaluate() output is JSON-serializable', True)
except TypeError as e:
    check('evaluate() output is JSON-serializable', False, str(e))


# ===========================================================================
# 21. Prebaked scenarios all produce valid snapshots
# ===========================================================================
print('\n== 21. Prebaked scenarios ==')
scenarios = prebaked_scenarios()
check('At least 5 prebaked scenarios', len(scenarios) >= 5)
ok_all = True
for sc in scenarios:
    try:
        snap = assess(sc['observations'])
        for r in ROOMS:
            route(r, snap)
    except Exception as e:
        ok_all = False
        check(f"Scenario '{sc['name']}' runs cleanly", False, str(e))
if ok_all:
    check('All prebaked scenarios run cleanly', True)


# ===========================================================================
# Summary
# ===========================================================================
print('\n' + '=' * 60)
passed = sum(1 for _, ok, _ in _results if ok)
total = len(_results)
print(f'RESULT: {passed}/{total} passed')
if passed == total:
    print('ALL TESTS PASSED — Phase 2 complete.')
else:
    print('FAILED TESTS:')
    for name, ok, detail in _results:
        if not ok:
            print(f'  - {name}' + (f'  ({detail})' if detail else ''))
print('=' * 60)