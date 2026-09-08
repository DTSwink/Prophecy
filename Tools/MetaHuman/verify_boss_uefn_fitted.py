"""Verify fitted bind preservation and actual UE CPU skinning against LBS."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/BossUEFNCompatible/20260907'
AUDIT = ROOT / 'Saved/BossBindAudit/20260907'
read = lambda p: json.loads(p.read_text())

def matrix(t):
    x,y,z,w = t['rotation']
    r = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                  [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                  [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    m = np.eye(4)
    m[:3,:3] = r @ np.diag(t['scale'])
    m[:3,3] = t['position']
    return m

def main():
    fitted = read(AUDIT/'unreal_uefn_fitted.json')
    native = read(AUDIT/'unreal_native.json')
    source = read(AUDIT/'source.json')
    rig = next(o for o in source['objects'] if o['name']=='UEFN_WORKING_CLEAN_RIG.001')
    mesh = next(o for o in source['objects'] if o['name']=='boss')
    assert set(fitted['bones']) == set(native['bones'])
    assert all(b['parent']==native['bones'][n]['parent'] for n,b in fitted['bones'].items())
    coords = np.array(mesh['evaluated_world'])*[100,-100,100]
    surface = cKDTree(fitted['positions']).query(coords)[0]
    joint = max(np.linalg.norm(np.array([b['rest_world'][i][3] for i in range(3)])*[100,-100,100]
                               -np.array(fitted['bones'][n]['position'])) for n,b in rig['bones'].items())
    assert surface.max()<.001 and joint<.001
    runtime = read(OUT/'runtime.json')
    assert runtime['passed'], runtime['error']
    max_nn = max(v for s in runtime['samples'] for v in s['position_errors_cm'].values())
    assert max_nn < .001
    displacement = np.linalg.norm(np.array(runtime['samples'][-1]['root'])-runtime['samples'][0]['root'])
    assert displacement > 100., 'Locomotion test did not move'
    rows=[]
    for label in ('idle','walk','run'):
        pose=read(OUT/(label+'_skin.json'))
        matrices = {n:matrix(pose['bones'][n]) @ np.linalg.inv(matrix(b)) for n,b in fitted['bones'].items()}
        expected=[]
        for p,weights in zip(fitted['positions'],fitted['weights']):
            point=np.array([*p,1.])
            expected.append(sum(w*(matrices[n]@point)[:3] for n,w in weights.items()))
        distances=cKDTree(pose['positions']).query(expected)[0]
        rows.append({'phase':label,'max_skin_error_cm':float(distances.max()),'mean_skin_error_cm':float(distances.mean())})
        # Render weights are packed/quantized; this is not a floating-point-only comparison.
        assert distances.max()<.1, rows[-1]
    result={'passed':True,'surface_max_cm':float(surface.max()),'joint_max_cm':float(joint),
            'bone_count':len(fitted['bones']),'hierarchy_matches_native':True,
            'max_nn_socket_error_cm':max_nn,'locomotion_distance_cm':float(displacement),'skinning':rows}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
