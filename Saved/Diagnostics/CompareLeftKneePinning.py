import pathlib,json,sys,contextlib,io,math
p=pathlib.Path(__file__).parent
sys.argv=['a','left-knee-245']
with contextlib.redirect_stdout(io.StringIO()):import AnalyzeRecoveryKnee as a
out={}
for tag in ('left-knee-245','left-knee-tolerance','left-knee-soft','left-knee-tolerance-wide'):
 r=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
 episodes=[]
 exits=[i for i in range(1,len(r)-60) if r[i-1]['attack']!='None' and r[i]['attack']=='None']
 for start in exits:
  vals=[]
  for i in range(start,start+60):
   b=r[i]['meshes']['PhysicalMesh'];prev=r[i-1]['meshes']['PhysicalMesh'];pp=r[i-2]['meshes']['PhysicalMesh'];q=a.step(prev,b,'l')
   q.update(frame=i+1,knee_step=a.norm(a.sub(b['calf_l']['p'],prev['calf_l']['p'])),ddz=b['pelvis']['p'][2]-2*prev['pelvis']['p'][2]+pp['pelvis']['p'][2])
   vals.append(q)
  episodes.append(dict(frame=start+1,max_thigh=max(x['thigh'] for x in vals),max_swivel=max(abs(x['swivel']) for x in vals),min_radius=min(x['radius1'] for x in vals),max_knee_step=max(x['knee_step'] for x in vals),pelvis_speed_change=max(abs(x['ddz']) for x in vals),straight_frames=[x['frame'] for x in vals if x['radius1']<2]))
 out[tag]=episodes
 print(tag,json.dumps(episodes))
(p/'LeftKnee245-pinning-comparison.json').write_text(json.dumps(out,indent=2))
