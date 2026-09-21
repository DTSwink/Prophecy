import json, pathlib, re, hashlib
import numpy as np
from scipy.spatial.transform import Rotation
p=pathlib.Path(__file__).resolve().parent
def angles(a,b):
    dots=np.abs(np.sum(a*b,axis=1))/(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1))
    return np.degrees(2*np.arccos(np.clip(dots,0,1)))
result={}
for mode in ('baseline','chaos','speculative_long','final'):
    path=p/(mode+'.json')
    data=json.loads(path.read_text())
    assert data['reason']=='Complete'
    result[mode]={}
    for name in sorted({r['actor'] for r in data['rows']}):
        rows=[r for r in data['rows'] if r['actor']==name and r['t']>=5]
        hand=np.array([r['bones']['hand_l']['q'] for r in rows])
        fore=np.array([r['bones']['lowerarm_l']['q'] for r in rows])
        target=np.array([r['bones']['hand_l']['target'] for r in rows])
        rel=(Rotation.from_quat(fore).inv()*Rotation.from_quat(hand)).as_quat()
        step=angles(hand[:-1],hand[1:])
        speeds=np.linalg.norm([r['bones']['hand_l']['w'] for r in rows],axis=1)
        result[mode][name]={'samples':len(rows),'hand_step_max_deg':float(step.max()),
          'hand_step_p99_deg':float(np.percentile(step,99)),
          'wrist_relative_step_max_deg':float(angles(rel[:-1],rel[1:]).max()),
          'target_step_max_deg':float(angles(target[:-1],target[1:]).max()),
          'angular_speed_max_rad_s':float(speeds.max()),
          'steps_over_20_deg':int((step>20).sum()),
          'step_seconds_min':min(np.diff([r['t'] for r in rows])),
          'step_seconds_max':max(np.diff([r['t'] for r in rows]))}
        if mode=='final':
            assert all(r['jolt'] and r['limits'].count('45.0')==3 for r in rows)
    result[mode]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
log=(p/'FinalAutomation.log').read_text(errors='replace')
start=log.index('Found 6 automation tests')
log=log[start:]
tests=re.findall(r'Test Completed\. Result=\{(.*?)\} Name=\{.*?\} Path=\{(.*?)\}',log)
assert len(tests)==6 and all(status=='Success' for status,name in tests)
result['automation']={'tests':tests,'errors':[x for x in log.splitlines() if 'Error:' in x],
    'warnings':[x for x in log.splitlines() if 'LogAutomationController: Warning:' in x]}
assert not result['automation']['errors']
assert 'Result: Succeeded' in (p/'Build.log').read_text()
(p/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
