import json,pathlib,sys,contextlib,io,numpy as np
p=pathlib.Path(__file__).parent
sys.argv=['a','pin-jiggle-final']
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
ns={'__file__':str(p/'ReplayWalkKneeGeometry.py')}
exec((p/'ReplayWalkKneeGeometry.py').read_text().split('rows=[r for r in map(json.loads')[0],ns)
result={}
for tag in ('pin-jiggle-current','pin-jiggle-final'):
 data=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
 rows=data['rows'];steps=[]
 for i in range(1,len(rows)):
  if rows[i]['t']<2 or rows[i]['attack']!='None' or rows[i-1]['attack']!='None':continue
  for side in ('l','r'):
   q=a.step(rows[i-1]['meshes']['PhysicalMesh'],rows[i]['meshes']['PhysicalMesh'],side)
   q.update(frame=i+1,side=side);steps.append(q)
 clearance=[];worst=[]
 for row in map(json.loads,(p/('FootVibration-nn-'+tag+'.jsonl')).read_text().splitlines()):
  if row['actor']!=rows[0]['actor'] or row['attack'] or row['time']<2:continue
  s=np.array(row['published_lower'])
  for side,key in enumerate(('left_walk_weight','right_walk_weight')):
   # On a direction switch the weight metadata can still describe the prior
   # recovery while a single Run output is already selected. Only use the Walk
   # geometry oracle for confirmed Walk selection or an explicit dual output.
   if row[key]==1 and (row['walk_policy'] or 'walk_delta' in row):
    c=100*(s[11+16*side]-ns['minimum'](s,side));clearance.append(c)
    worst.append((c,row['time'],side))
 result[tag]={'complete':data['reason'],'frames':len(rows),'recovery_max_thigh_step':max(q['thigh']for q in steps),
  'recovery_max_swivel_step':max(abs(q['swivel'])for q in steps),'pure_walk_min_clearance_cm':min(clearance),
  'pure_walk_floor_samples':len(clearance),'worst_floor':sorted(worst)[:3]}
print(json.dumps(result,indent=2))
(p/'FreeCalfReturn-verification.json').write_text(json.dumps(result,indent=2))
