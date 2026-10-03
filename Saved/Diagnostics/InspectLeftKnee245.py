import json,pathlib,sys,contextlib,io
p=pathlib.Path(__file__).parent
tag=sys.argv[1] if len(sys.argv)>1 else 'left-knee-245'
sys.argv=['a',tag]
with contextlib.redirect_stdout(io.StringIO()):import AnalyzeRecoveryKnee as a
r=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
print('FRAME TIME THIGH SWIVEL KNEE_STEP PELVIS_DZ FOOT_DZ RADIUS ATTACK')
for j in range(232,259):
 b=r[j]['meshes']['PhysicalMesh'];pr=r[j-1]['meshes']['PhysicalMesh'];q=a.step(pr,b,'l')
 print(j+1,round(r[j]['t'],4),*[round(v,3) for v in (q['thigh'],q['swivel'],a.norm(a.sub(b['calf_l']['p'],pr['calf_l']['p'])),b['pelvis']['p'][2]-pr['pelvis']['p'][2],b['foot_l']['p'][2]-pr['foot_l']['p'][2],q['radius1'])],r[j]['attack'])
nn=[json.loads(x) for x in (p/('FootVibration-nn-'+tag+'.jsonl')).read_text().splitlines()]
nn=[x for x in nn if x['actor']==r[0]['actor']]
print('KEYS',list(nn[0]))
print('FRAME PATH UPPER LOWER DIST RADIUS')
for j in (242,243,244,245,246,247,248,249,250,251):
 for path in ('PhysicalMesh','previous','future','target'):
  b=r[j]['meshes'][path] if path=='PhysicalMesh' else {k:v[path] for k,v in r[j]['targets'].items()}
  h,k,f=[b[z+'_l']['p'] for z in ('thigh','calf','foot')]
  print(j+1,path,*[round(v,5) for v in (a.norm(a.sub(k,h)),a.norm(a.sub(f,k)),a.norm(a.sub(f,h)),a.geom(b,'l')[2])])
for x in nn:
 if 3.85<x['time']<4.4:
  print('NN',round(x['time'],4),{k:x[k] for k in ('attack','tempering','right_foot_tempering','walk_weight','left_walk_weight','right_walk_weight','pin_raw','pin_effective') if k in x})
