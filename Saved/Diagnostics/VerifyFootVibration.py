import json,pathlib,sys,contextlib,io,math
sys.argv=['verify','foot-vibration-fixed']
with contextlib.redirect_stdout(io.StringIO()):
 import AnalyzeRecoveryKnee as a
 import AnalyzeCalfAnkleConnection as calf
p=pathlib.Path(__file__).parent
results={}
for tag in ('foot-vibration','foot-vibration-fixed'):
 d=json.loads((p/('CalfAnkleConnection-'+tag+'.json')).read_text())
 r=[x for x in d['rows'] if x['actor']=='BP_ProphecyManualPoseAgent_C_1']
 exits=[i for i in range(1,len(r)-60) if 'kick' in r[i-1]['attack'] and r[i]['attack']=='None']
 cases=[];back=0;samples=0;maxangle=0;height=[]
 for i,x in enumerate(r):
  if x['attack']!='None' or x['t']<1.94:continue
  b=x['meshes']['PhysicalMesh'];axis,pole,rad=a.geom(b,'r')
  toe=a.sub(b['ball_r']['p'],b['foot_r']['p']);forward=a.unit([toe[0],toe[1],0])
  projected=a.unit(a.sub(forward,a.mul(axis,a.dot(axis,forward))))
  angle=abs(math.degrees(math.atan2(a.dot(axis,a.cross(projected,pole)),a.dot(projected,pole))))
  samples+=1;back+=angle>90;maxangle=max(maxangle,angle)
 for i in exits:
  z=[r[j]['meshes']['PhysicalMesh']['foot_r']['p'][2]for j in range(i,i+60)]
  peak=0.;dip=0.
  for v in z[:14]:peak=max(peak,v);dip=max(dip,peak-v)
  apex=max(range(len(z)),key=z.__getitem__)
  rise_error=max([0.]+[z[j]-z[j+1]for j in range(apex)])
  fall_error=max([0.]+[z[j+1]-z[j]for j in range(apex,len(z)-1)])
  low=z[apex];late_rise=0.
  for value in z[apex:]:
   low=min(low,value);late_rise=max(late_rise,value-low)
  height.append(dict(early_dip_cm=dip,rise_error_cm=rise_error,fall_error_cm=fall_error,late_rise_cm=late_rise))
  case={}
  for s in ('l','r'):
   steps=[a.step(r[j-1]['meshes']['PhysicalMesh'],r[j]['meshes']['PhysicalMesh'],s)for j in range(i,i+60)]
   tips=[calf.measure(r[j]['meshes']['PhysicalMesh'],s)for j in range(i,i+61)]
   case[s]={'thigh_step':max(v['thigh']for v in steps),'swivel_step':max(abs(v['swivel'])for v in steps),
    'entry_gap_step':abs(tips[1]['tip_gap']-tips[0]['tip_gap']),
    'scale_change':max(abs(x-y)for v in tips[:60] for x,y in zip(v['scale'],tips[0]['scale'])),
    'final_gap':tips[-1]['tip_gap']}
  cases.append(case)
 results[tag]={'complete_exits':len(exits),'backward_samples':back,'samples':samples,'max_knee_toe_angle':maxangle,'cases':cases,'height':height}
 print(tag,'height',height)
 print(tag,'exits',len(exits),'backward',back,'/',samples,'max knee/foot',maxangle)
 for s in ('l','r'):print(s,{k:max(c[s][k]for c in cases)for k in cases[0][s]})
v=results['foot-vibration-fixed'];assert v['complete_exits']>=5
assert v['backward_samples']==0
# Regression: the measured exit+5..7 reversal while the foot is rising. Ordinary
# NN locomotion is not contractually a monotone height curve across the entire
# following second. Keep every later reversal above as a reported limitation;
# do not label the full curve vibration-free or discard those measurements.
assert max(h['early_dip_cm'] for h in results['foot-vibration']['height'])>.9
assert all(h['early_dip_cm']<.02 and h['rise_error_cm']<.02 for h in v['height']),v['height']
assert max(c['r']['swivel_step']for c in v['cases'])<10
for c in v['cases']:
 for s in ('l','r'):
  assert c[s]['entry_gap_step']<.02,c
  assert c[s]['scale_change']<1e-4,c
  assert c[s]['final_gap']<.02,c
(p/'FootVibration-final-verification.json').write_text(json.dumps(results,indent=2))
print('PASS: recorded early height reversal removed; supporting knee, calf scale and ankle-gap checks passed.')
print('RESIDUAL: maximum later NN return rise (cm)',max(h['late_rise_cm'] for h in v['height']))
