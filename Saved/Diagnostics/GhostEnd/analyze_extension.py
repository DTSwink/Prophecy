import json,pathlib,re,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
def groups(file):
 result=[]
 for x in [json.loads(l) for l in file.read_text().splitlines()]:
  if not result or x['frame']<=result[-1][-1]['frame']:result.append([])
  result[-1].append(x)
 return result
def angle(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(a,b),-1,1))))
axis=R.from_quat(json.loads((p/'grip.json').read_text())).apply([0,0,1]);mirror=np.diag([1,-1,1])
def aim(x):
 m=np.array(x['output'][323:332]).reshape(3,3)@np.array(x['native_rotation']).reshape(3,3).T
 return R.from_quat(x['anchor'][3:]).apply((mirror@m@mirror).T@axis)
base=groups(p/'steps.jsonl');new=groups(p/'extension_steps.jsonl')
report={}
for tag in ['extension','disabled','threshold0','threshold180']:
 if not (p/(tag+'.json')).exists():continue
 capture=json.loads((p/(tag+'.json')).read_text());assert not capture['error'],capture['error']
 g=groups(p/(tag+'_steps.jsonl'))
 entries=[]
 for i,a in enumerate(g):
  same=[(x,y) for x,y in zip(a,base[i])]
  entries.append(dict(family=a[0]['family'],hit=next(x['frame'] for x in a if x['output'][432]>.5),last_frame=a[-1]['frame'],prefix_output_max_error=max(float(np.max(np.abs(np.array(x['output'])-y['output']))) for x,y in same)))
 report[tag]=dict(attacks=entries,decisions=re.findall(r'AttackEndExtension actor=.*', (p/(tag+'.log')).read_text()))
report['second_final_sword_vs_first_final_degrees']=angle(aim(new[1][-1]),aim(new[0][-1]))
report['second_added_sword_turn_degrees']=angle(aim(new[1][-2]),aim(new[1][-1]))
assert [a[-1]['frame'] for a in new]==[18,19]
assert report['second_added_sword_turn_degrees']>50.688107
assert report['second_final_sword_vs_first_final_degrees']<2
assert max(a['prefix_output_max_error'] for a in report['extension']['attacks'])<1e-4
if 'disabled' in report:
 assert [a['last_frame'] for a in report['disabled']['attacks']]==[18,18]
 assert not report['disabled']['decisions']
 assert max(a['prefix_output_max_error'] for a in report['disabled']['attacks'])<1e-4
 enabled=groups(p/'extension_steps.jsonl');disabled=groups(p/'disabled_steps.jsonl')
 report['enabled_vs_disabled_common_output_max_error']=max(float(np.max(np.abs(np.array(x['output'])-y['output']))) for a,b in zip(enabled,disabled) for x,y in zip(a,b))
 assert report['enabled_vs_disabled_common_output_max_error']<1e-4
if 'threshold180' in report:
 assert [a['last_frame'] for a in report['threshold180']['attacks']]==[18,18]
 assert not report['threshold180']['decisions']
(p/'extension_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
