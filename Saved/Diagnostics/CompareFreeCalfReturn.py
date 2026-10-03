import json,pathlib,sys,contextlib,io,math
p=pathlib.Path(__file__).parent
sys.argv=['a','pin-jiggle-current']
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
 import AnalyzeCalfAnkleConnection as calf
def bend(b,s):
 h,k,f=[b[v+'_'+s]['p']for v in ('thigh','calf','foot')]
 return math.degrees(math.acos(max(-1,min(1,a.dot(a.unit(a.sub(k,h)),a.unit(a.sub(f,k)))))))
result={}
for tag in ('pin-jiggle-current','pin-jiggle-free-calf','pin-jiggle-final'):
 rows=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())['rows']
 episodes=[]
 for start in range(1,len(rows)-60):
  if rows[start]['attack']!='None' or rows[start-1]['attack']=='None':continue
  vals=[]
  for j in range(start,start+60):
   if rows[j]['attack']!='None':break
   b=rows[j]['meshes']['PhysicalMesh'];pr=rows[j-1]['meshes']['PhysicalMesh'];pp=rows[j-2]['meshes']['PhysicalMesh']
   vals.append(dict(frame=j+1,angle=bend(b,'l'),angle_step=bend(b,'l')-bend(pr,'l'),angle_accel=bend(b,'l')-2*bend(pr,'l')+bend(pp,'l'),
       thigh=a.step(pr,b,'l')['thigh'],foot_step=a.norm(a.sub(b['foot_l']['p'],pr['foot_l']['p'])),pelvis_accel=b['pelvis']['p'][2]-2*pr['pelvis']['p'][2]+pp['pelvis']['p'][2],
       tip_gap=calf.measure(b,'l')['tip_gap']))
  late=vals[30:]
  if not late:continue
  rec=dict(exit=start+1,minimum_bend=min(x['angle']for x in late),max_angle_step=max(abs(x['angle_step'])for x in late),max_angle_accel=max(abs(x['angle_accel'])for x in late),
     thigh_step=max(x['thigh']for x in late),foot_step=max(x['foot_step']for x in late),pelvis_accel=max(abs(x['pelvis_accel'])for x in late),final_gap=vals[-1]['tip_gap'])
  episodes.append(rec)
 result[tag]=episodes
 print(tag,json.dumps(episodes))
(p/'FreeCalfReturn-comparison.json').write_text(json.dumps(result,indent=2))
