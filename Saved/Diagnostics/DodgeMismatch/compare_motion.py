import json,numpy as np
from pathlib import Path
p=Path(__file__).parent
for name in ['updated_viewer_60.json','updated_viewer_82.json']:
 d=json.loads((p/name).read_text());r=d['rollout'];h=r['joint_names'].index('head');points=np.asarray(r['positions'])[:,h]*100
 print(name)
 for f in range(4,len(points)):print(f,np.round(points[f]-points[4],2).tolist())
for name in ['corrected_ue.json','trace_normal_ue.json','trace_continue_ue.json','timing_normal_ue.json','timing_continue_ue.json']:
 if not (p/name).exists():continue
 d=json.loads((p/name).read_text());rows={}
 for r in d['rows']:
  if r['attack'] and r['attack'][-1] not in rows:rows[r['attack'][-1]]=r
 if 4 not in rows:continue
 i=rows[4]['d']['names'].index('head');base=np.asarray(rows[4]['d']['future'][i]['p'])
 print(name)
 for f,r in rows.items():
  if f>=4:print(f,np.round((np.asarray(r['d']['future'][i]['p'])-base)[[0,2,1]],2).tolist())
