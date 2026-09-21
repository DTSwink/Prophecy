import json,pathlib,re,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
def row(n):return next(r for r in json.loads((p/f'bool_{n}.json').read_text())['rows'] if r['actor'].endswith('_C_1') and abs(r['t']-5/60)<1e-6)
a,b,live=row('false'),row('early'),row('replay')
text=pathlib.Path('Saved/Logs/GameAnimationSample3.log').read_text(errors='replace').rsplit('WRIST_BOOL_START replay',1)[-1]
lines=[s for s in text.splitlines() if 'WRISTREPLAY' in s]
(p/'FirstStepReplay.log').write_text('\n'.join(lines))
qs={}
for s in lines:
 m=re.search(r'variant=(\d) bone=(\w+) q=(.*)',s)
 if m:qs[int(m[1]),m[2]]=[float(x) for x in m[3].split(',')]
def deg(x,y):return float(np.degrees((R.from_quat(x).inv()*R.from_quat(y)).magnitude()))
result={}
for bone in ['lowerarm_r','hand_r','lowerarm_l','hand_l']:
 result[bone]={'replica_vs_live':deg(qs[0,bone],live['bones'][bone]['q']), 'live_replay_vs_original':deg(live['bones'][bone]['q'],b['bones'][bone]['q']), 'variants':{}}
 for i in range(6):result[bone]['variants'][i]={'difference_from_current':deg(qs[i,bone],qs[0,bone]),'difference_from_bool_false':deg(qs[i,bone],a['bones'][bone]['q'])}
print(json.dumps(result,indent=2));(p/'first_step_replay_analysis.json').write_text(json.dumps(result,indent=2))
