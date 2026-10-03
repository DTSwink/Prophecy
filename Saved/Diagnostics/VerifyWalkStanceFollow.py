import json,pathlib,sys,contextlib,io,math
sys.argv=['verify','walk-plane-follow']
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
 import AnalyzeCalfAnkleConnection as calf
p=pathlib.Path(__file__).parent
results={}
for tag in ('walk-recovery-pop','walk-plane-follow'):
 d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
 r=[x for x in d['rows'] if x['actor']=='BP_ProphecyManualPoseAgent_C_1']
 exits=[i for i in range(1,len(r)-60) if 'kick' in r[i-1]['attack'] and r[i]['attack']=='None']
 cases=[];back=0;samples=0;maxangle=0
 for i,x in enumerate(r):
  if x['attack']!='None' or x['t']<1.94:continue
  b=x['meshes']['PhysicalMesh'];axis,pole,rad=a.geom(b,'r')
  toe=a.sub(b['ball_r']['p'],b['foot_r']['p']);forward=a.unit([toe[0],toe[1],0])
  projected=a.unit(a.sub(forward,a.mul(axis,a.dot(axis,forward))))
  angle=abs(math.degrees(math.atan2(a.dot(axis,a.cross(projected,pole)),a.dot(projected,pole))))
  samples+=1;back+=angle>90;maxangle=max(maxangle,angle)
 for i in exits:
  case={}
  for s in ('l','r'):
   steps=[a.step(r[j-1]['meshes']['PhysicalMesh'],r[j]['meshes']['PhysicalMesh'],s)for j in range(i,i+60)]
   tips=[calf.measure(r[j]['meshes']['PhysicalMesh'],s)for j in range(i,i+61)]
   case[s]={'thigh_step':max(v['thigh']for v in steps),'swivel_step':max(abs(v['swivel'])for v in steps),
    'entry_gap_step':abs(tips[1]['tip_gap']-tips[0]['tip_gap']),
    'scale_change':max(abs(x-y)for v in tips[:60] for x,y in zip(v['scale'],tips[0]['scale'])),
    'final_gap':tips[-1]['tip_gap']}
  cases.append(case)
 results[tag]={'complete_exits':len(exits),'backward_samples':back,'samples':samples,'max_knee_toe_angle':maxangle,'cases':cases}
 print(tag,'exits',len(exits),'backward',back,'/',samples,'max knee/foot',maxangle)
 for s in ('l','r'):print(s,{k:max(c[s][k]for c in cases)for k in cases[0][s]})
v=results['walk-plane-follow'];assert v['complete_exits']>=5
assert v['backward_samples']==0
assert max(c['r']['swivel_step']for c in v['cases'])<10
for c in v['cases']:
 for s in ('l','r'):
  assert c[s]['entry_gap_step']<.02,c
  assert c[s]['scale_change']<1e-4,c
  assert c[s]['final_gap']<.02,c
(p/'WalkStanceFollow-verification.json').write_text(json.dumps(results,indent=2))
print('PASS: supporting knee, calf scale continuity, and ankle-gap convergence.')
