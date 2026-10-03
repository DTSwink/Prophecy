import json,pathlib,re,math,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/RunHandThigh');tag=sys.argv[1];d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error'];rs={r['tick']:r for r in d['rows']}
old=json.loads((p/'wrist_second_current.json').read_text());old={r['tick']:r for r in old['rows']}
log=(p/(tag+'.log')).read_text();audit=[]
for line in log.splitlines():
 if 'WristSplit' not in line:continue
 vals={k:float(v) for k,v in re.findall(r'(\w+)=([-\d.]+)',line.split('WristSplit')[1])}
 vals['tick']=min(rs,key=lambda t:abs(rs[t]['time']-vals['time']));audit.append(vals)
report={'rows':len(rs),'routes':[l.split('WristRoute')[1] for l in log.splitlines() if 'WristRoute' in l],'first':[],'second':[]}
for key,lo,hi in [('first',185,311),('second',367,493)]:
 for a in audit:
  if a['tick'] in ([187,189,191,199,201,217,279,281,283,299,301,303,305,307] if key=='first' else [369,371,379,381,389,399,457,459,461,479,481,483,485,487,489]):report[key].append(a)
report['position_differences']={}
for view in ['future','presented','mesh']:
 for bone in ['upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r']:
  vals=[(float(np.linalg.norm(np.array(r[view][bone]['p'])-old[t][view][bone]['p'])),t) for t,r in rs.items() if t in old and bone in r[view] and bone in old[t][view]]
  report['position_differences'][view+'/'+bone]=max(vals)
for key,lo,hi in [('first_end',297,311),('second_end',479,493),('reported',369,401)]:
 steps=[]
 for t in range(lo,hi+1):
  if t not in rs or t-1 not in rs:continue
  prev,cur=rs[t-1]['presented'],rs[t]['presented']
  q=R.from_quat(cur['hand_r']['q'])*R.from_quat(prev['hand_r']['q']).inv()
  hp=R.from_quat(cur['pelvis']['q']).inv().apply(np.array(cur['hand_r']['p'])-cur['pelvis']['p']);hpp=R.from_quat(prev['pelvis']['q']).inv().apply(np.array(prev['hand_r']['p'])-prev['pelvis']['p'])
  steps.append({'tick':t,'rotation_step':math.degrees(q.magnitude()),'pelvis_local_position_step':float(np.linalg.norm(hp-hpp))})
 report[key]=steps
(p/(tag+'_metrics.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
