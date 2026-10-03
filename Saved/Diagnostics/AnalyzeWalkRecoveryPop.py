import pathlib,json,sys,contextlib,io,math
tag=sys.argv[1] if len(sys.argv)>1 else 'walk-recovery-pop'
sys.argv=['analysis',tag]
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
p=pathlib.Path(__file__).parent
r=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
r=[x for x in r if x['actor'].endswith('_C_1')]
exits=[i for i in range(1,len(r)-60) if r[i-1]['attack']!='None' and r[i]['attack']=='None']
out=[]
for n,i in enumerate(exits):
 vals=[]
 for j in range(i,i+60):
  x=r[j];b=x['meshes']['PhysicalMesh'];prev=r[j-1]['meshes']['PhysicalMesh'];pp=r[j-2]['meshes']['PhysicalMesh']
  dz=b['pelvis']['p'][2]-prev['pelvis']['p'][2];lastdz=prev['pelvis']['p'][2]-pp['pelvis']['p'][2]
  q=a.step(prev,b,'r');rec=dict(t=x['t'],frame=j-i,pelvis_z=b['pelvis']['p'][2],dz=dz,ddz=dz-lastdz,
   right_knee_step=a.norm(a.sub(b['calf_r']['p'],prev['calf_r']['p'])),**q)
  vals.append(rec)
 print('exit',n,'time',r[i]['t'],'max pelvis accel',max(abs(x['ddz']) for x in vals),'max knee',max(x['right_knee_step'] for x in vals),
  'thigh',max(x['thigh'] for x in vals),'swivel',max(abs(x['swivel']) for x in vals))
 out.append(vals)
 if n==0:
  print('frame time pelvisZ dz ddz kneeStep thigh swivel')
  for q in vals[:42]:print(q['frame'],*[round(q[k],3) for k in ('t','pelvis_z','dz','ddz','right_knee_step','thigh','swivel')])
(p/('WalkRecoveryPop-'+tag+'.json')).write_text(json.dumps(out,indent=2))
path=p/('FootVibration-nn-'+tag+'.jsonl')
if path.exists():
 nn=[json.loads(x) for x in path.read_text().splitlines()]
 nn=[x for x in nn if x['actor'].endswith('_C_1') and not x['attack'] and r[exits[0]]['t']-.04<=x['time']<r[exits[0]]['t']+.7]
 print('NN time prevPelvisZ rawZ pubZ walkWeights tempering')
 for x in nn:
  print(round(x['time'],4),round(x['previous_lower'][2]*100,3),round(x['lower_delta'][2]*100,3),round(x['published_lower'][2]*100,3),
   [round(x[k],3) for k in ('walk_weight','left_walk_weight','right_walk_weight')],
   [round(v,3) for v in x.get('tempering',[])], [round(v,3) for v in x.get('right_foot_tempering',[])])
