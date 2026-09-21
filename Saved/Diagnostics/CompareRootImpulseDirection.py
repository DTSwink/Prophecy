import json, math
from pathlib import Path
folder=Path(__file__).parent
results={}
for name in ['Before','After']:
    rows=json.loads((folder/f'RootImpulseDirection{name}.json').read_text())
    # First impulse, before the next impulse or low-speed balancing can take over.
    samples=[r for r in rows if 1.75 <= r['t'] <= 2.6 and r['balance'].startswith('(True, False')]
    assert len(samples)>10
    angles=[math.atan2(r['v'][1],r['v'][0]) for r in samples]
    accumulated=[0.]
    for a,b in zip(angles,angles[1:]):
        accumulated.append(accumulated[-1]+math.atan2(math.sin(b-a),math.cos(b-a)))
    results[name]={'samples':len(samples),'velocity_direction_sweep_degrees':math.degrees(max(accumulated)-min(accumulated)),
        'first_velocity':samples[0]['v'],'last_velocity':samples[-1]['v'],'first_yaw':samples[0]['yaw'],'last_yaw':samples[-1]['yaw']}
print(json.dumps(results,indent=2))
(folder/'RootImpulseDirectionComparison.json').write_text(json.dumps(results,indent=2))
