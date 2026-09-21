import json
import math
import pathlib

root = pathlib.Path(__file__).resolve().parent
path = max(root.glob('fixed-capture-*.json'), key=lambda p: p.stat().st_mtime)
capture = json.loads(path.read_text(encoding='utf-8'))
rows = [r for r in capture['rows'] if r['t'] >= 5.0]
pairs = list(zip(rows, rows[1:]))
distance = lambda a, b: math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))
same = [(a,b) for a,b in pairs if distance(a['future'], b['future']) < 1.e-7]
recoveries = [(a,b) for a,b in same if a['dt'] >= 1.0/30.0 and b['dt'] < 1.0/30.0]
def event(a, b):
    return {'t': b['t'], 'previous_dt': a['dt'], 'dt': b['dt'],
            'previous_alpha': a['alpha'], 'alpha': b['alpha'],
            **{key+'_dx_cm': b[key][0]-a[key][0] for key in ('capsule','target','body','future')}}
result = {
    'source': path.name, 'reason': capture['reason'], 'error': capture['error'],
    'rows_after_warmup': len(rows), 'sampled_seconds': rows[-1]['t']-rows[0]['t'],
    'settings': capture['validation_settings'], 'injections': len(capture['injections']),
    'same_interval_pairs': len(same),
    'same_interval_alpha_reversals': [event(a,b) for a,b in same if b['alpha'] < a['alpha']-1.e-6],
    'slow_to_fast_same_interval_recoveries': [event(a,b) for a,b in recoveries],
    'backward_events_gt_0_01_cm': {key: [event(a,b) for a,b in pairs if b[key][0] < a[key][0]-.01]
                                  for key in ('capsule','target','body','future')},
    'minimum_forward_delta_cm': {key: min(b[key][0]-a[key][0] for a,b in pairs)
                                  for key in ('capsule','target','body','future')},
    'max_body_visible_error_cm': max(distance(r['body'],r['visible']) for r in rows),
    'mover_x_range_cm_s': [min(r['mover_v'][0] for r in rows), max(r['mover_v'][0] for r in rows)],
}
(root/'fixed-analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({**result, 'settings': 'See report',
                  'slow_to_fast_same_interval_recoveries': len(recoveries),
                  'backward_events_gt_0_01_cm': {k: len(v) for k,v in result['backward_events_gt_0_01_cm'].items()}},indent=2))
