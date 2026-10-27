"""Deterministic mock detector adapter.

Simulates the future YOLO + Librosa pipeline so the routing and dashboard can
be developed and demoed before real models are wired in.

INTERFACE:
    fake_scores(device_id, profile)         -> {'acoustic','pose','object'}
    observation_from_scores(event_id, ...)  -> (Observation, classification_dict)
    prebaked_scenarios()                    -> list of {name, observations}
"""
import random
from dynamic_evacuation import DEVICES, Observation, classify_threat


def fake_scores(device_id, rng=None, profile='random'):
    """Return scores in [0, 100] for a device.

    profile:
      'random'   -> uniform noise (smoke tests)
      'normal'   -> low scores (should classify NORMAL)
      'warning'  -> mid scores (should classify WARNING)
      'critical' -> high scores (should classify CRITICAL)
    """
    if device_id not in DEVICES:
        raise ValueError(f'Unknown device: {device_id}')
    rng = rng or random
    if profile == 'normal':
        return {'acoustic': rng.randint(5, 20),
                'pose': rng.randint(5, 20),
                'object': rng.randint(0, 15)}
    if profile == 'warning':
        return {'acoustic': rng.randint(40, 70),
                'pose': rng.randint(30, 55),
                'object': rng.randint(25, 50)}
    if profile == 'critical':
        return {'acoustic': rng.randint(70, 100),
                'pose': rng.randint(70, 100),
                'object': rng.randint(80, 100)}
    return {'acoustic': rng.randint(0, 100),
            'pose': rng.randint(0, 100),
            'object': rng.randint(0, 100)}


def observation_from_scores(event_id, device_id, scores,
                            incident_id=None, location=None):
    """Classify the scores and wrap them into a canonical Observation.

    Returns (observation, classification_dict).
    """
    c = classify_threat(scores['acoustic'], scores['pose'], scores['object'])
    obs = Observation(
        event_id=event_id,
        device_id=device_id,
        level=c['level'],
        count=1,
        location=location,
        incident_id=incident_id,
    )
    return obs, c


def prebaked_scenarios():
    """One-click demo scenarios for the dashboard.

    Each returns a list of Observation objects with fixed, readable values so
    the demo is reproducible.
    """
    def make(event_id, device_id, a, p, o, count=1,
             incident_id=None, location=None):
        c = classify_threat(a, p, o)
        return Observation(event_id=event_id, device_id=device_id,
                           level=c['level'], count=count,
                           incident_id=incident_id, location=location)

    return [
        {
            'name': 'Baseline — no observations',
            'observations': [],
        },
        {
            'name': 'Single CRITICAL at Tech Pro Floor 1 (left camera)',
            'observations': [
                make('e1', 'TPB-F1-CAM-L', 85, 80, 95, count=2,
                     incident_id='inc-1'),
            ],
        },
        {
            'name': 'Two overlapping CRITICAL cameras, Tech Pro Floor 1',
            'observations': [
                make('e1', 'TPB-F1-CAM-L', 85, 80, 95, count=2,
                     incident_id='inc-1'),
                make('e2', 'TPB-F1-CAM-R', 80, 75, 90, count=1,
                     incident_id='inc-1'),
            ],
        },
        {
            'name': 'Simultaneous CRITICALs in Tech Pro and Laboratory',
            'observations': [
                make('e1', 'TPB-F2-CAM-L', 85, 80, 95, count=1,
                     incident_id='inc-A'),
                make('e2', 'LB-F1-CAM-R', 90, 85, 92, count=1,
                     incident_id='inc-B'),
            ],
        },
        {
            'name': 'CRITICAL outdoor camera — Academic east approach',
            'observations': [
                make('e1', 'AB-CAM-OUT-R', 80, 70, 90, count=1,
                     incident_id='inc-outdoor'),
            ],
        },
        {
            'name': 'CRITICAL at Gate-W perimeter approach (West Gate)',
            'observations': [
                make('e1', 'TPB-CAM-OUT-L', 85, 80, 95, count=1,
                     incident_id='inc-gate-w'),
            ],
        },
        {
            'name': 'CRITICAL at Gate-NE perimeter approach (Northeast Gate)',
            'observations': [
                make('e1', 'TPB-CAM-OUT-R', 85, 80, 95, count=1,
                     incident_id='inc-gate-ne'),
            ],
        },
        {
            'name': 'WARNING-only — Tech Pro Floor 3',
            'observations': [
                make('e1', 'TPB-F3-CAM-L', 60, 45, 40, count=1),
            ],
        },
    ]


if __name__ == '__main__':
    scenarios = prebaked_scenarios()
    print(f'Loaded {len(scenarios)} prebaked scenarios:')
    for s in scenarios:
        print(f"  - {s['name']}  ({len(s['observations'])} observation(s))")
