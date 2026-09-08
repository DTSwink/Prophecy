"""Compare saved source/reference data without importing numerical runtimes."""
import json
import math
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'Saved/BossBindAudit/20260907'
read = lambda name: json.loads((OUT / (name + '.json')).read_text())
source = read('source')
rig = next(o for o in source['objects'] if o['name'] == 'UEFN_WORKING_CLEAN_RIG.001')
mesh = next(o for o in source['objects'] if o['name'] == 'boss')
fitted = read('unreal_fitted')
current = read('unreal_current')
convert = lambda p: [p[0] * 100, -p[1] * 100, p[2] * 100]
heads = {n: convert([b['rest_world'][i][3] for i in range(3)]) for n,b in rig['bones'].items()}

def nearest_vertex_errors(points, targets):
    grid = defaultdict(list)
    key = lambda p: tuple(math.floor(v * 100) for v in p)
    for p in targets:
        grid[key(p)].append(p)
    errors, unmatched = [], []
    for idx, p in enumerate(points):
        cell = key(p)
        candidates = [q for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1)
                      for q in grid.get((cell[0]+x,cell[1]+y,cell[2]+z), ())]
        if candidates:
            errors.append(min(math.dist(p, q) for q in candidates))
        else:
            unmatched.append(idx)
    return {'maximum_matched_cm': max(errors), 'matched': len(errors), 'unmatched_count': len(unmatched)}

report = {'source': source['file'], 'fitted_mesh': fitted['path'],
          'fitted_assigned_skeleton': fitted['skeleton'],
          'source_to_fitted_vertices': nearest_vertex_errors([convert(p) for p in mesh['evaluated_world']], fitted['positions']),
          'source_to_current_vertices': nearest_vertex_errors([convert(p) for p in mesh['evaluated_world']], current['positions']),
          'source_to_fitted_joint_max_cm': max(math.dist(p, fitted['bones'][n]['position']) for n,p in heads.items()),
          'source_to_current_joint_errors_cm': {n: math.dist(p, current['bones'][n]['position']) for n,p in heads.items()}}
(OUT / 'comparison.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k:v for k,v in report.items() if k != 'source_to_current_joint_errors_cm'}, indent=2))
