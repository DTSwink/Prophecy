import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
def u(v):return v/max(np.linalg.norm(v),1e-12)
def measure(r,side):
 d=r['targets'];h,k,f=[np.array(d[n+'_'+side]['p']) for n in ('thigh','calf','foot')];axis=u(f-h);rad=k-h-axis*np.dot(k-h,axis);return R.from_quat(d['foot_'+side]['q']).inv().apply(u(rad)),R.from_quat(d['thigh_'+side]['q'])
def angle(a,b):return float(np.degrees(np.arccos(np.clip(a@b,-1,1))))
summary=[]
for mode in ('kick-baseline','kick-enabled','baseline','enabled'):
 rows=json.loads((p/('PunchPole-'+mode+'-live.json')).read_text())['rows'];out=[]
 for i,r in enumerate(rows):
  if not i or rows[i-1]['attack']=='None' or r['attack']!='None':continue
  rec=dict(tick=r['tick'],attack=rows[i-1]['attack'])
  for side in ('l','r'):
   turns=[];thigh=[]
   for j in range(i,min(i+18,len(rows))):
    if rows[j]['attack']!='None':break
    a,aq=measure(rows[j-1],side);b,bq=measure(rows[j],side);turns.append(angle(a,b));thigh.append(float(np.degrees((aq.inv()*bq).magnitude())))
   rec[side]=dict(max_foot_relative=max(turns),max_thigh=max(thigh))
  out.append(rec)
 summary.append(dict(mode=mode,exits=out))
print(json.dumps(summary,indent=2));(p/'PunchPole-live-summary.json').write_text(json.dumps(summary,indent=2))
