"""Compact evidence index for the isolated motor feasibility diagnostics."""
import json
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[2]/'Saved/MimicKitMotorAudit'
out={}
policy=root/'policy_all_checked.json'
if policy.exists():
    p=json.loads(policy.read_text());groups={}
    for r in p['rows']:groups.setdefault(r['motion'],[]).append(r)
    out['frozen_policy']=dict(worlds=p['worlds'],passed=p['passed'],tested_seconds=p['settings']['seconds'],
        all_phases_pass=[n for n,r in groups.items() if all(x['passed'] for x in r)],
        failures=[dict(motion=n,seconds=[x['seconds'] for x in r],passed=sum(x['passed'] for x in r)) for n,r in groups.items() if not all(x['passed'] for x in r)],
        numerical_errors_during_first_episode=[dict(motion=r['motion'],phase=r['phase'],tick=r['first_solver_error_tick']) for r in p['rows'] if r['solver_error_during_episode']],
        numerical_errors_after_first_episode=[dict(motion=r['motion'],phase=r['phase'],tick=r['first_solver_error_tick'],first_failure_seconds=r['seconds']) for r in p['rows'] if r['first_solver_error_tick']>=0 and not r['solver_error_during_episode']])
for tag in ['search_forward_stock','search_forward_matched','search_forward_extended','search_forward_windowed']:
    path=root/(tag+'.json')
    if not path.exists():continue
    r=json.loads(path.read_text());data=np.load(path.with_suffix('.npz'));p=data['pose'][:,0,0,:3]
    out[tag]={k:r.get(k) for k in ['seconds','passed','requested_horizon_seconds','max_distance_m','repeat_passed','repeat_count','reproducibility_range_m','elapsed_seconds','solver_metrics_row0']}
    out[tag].update(recorded_displacement_m=(p[-1]-p[0]).tolist(),pelvis_height_m=[float(p[:,2].min()),float(p[:,2].max())])
    if 'delivered_peak_torque_nm' in r:
        out[tag]['largest_torque_cap_ratio']=float(np.max(np.array(r['delivered_peak_torque_nm'])/r['torque_caps_nm']))
(root/'summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
