import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def geom(r,s):
 b=r['targets'];h,k,f=[np.array(b[n+'_'+s]['target']['p']) for n in ('thigh','calf','foot')];axis=unit(f-h);pole=unit(k-h-axis*((k-h)@axis))
 return axis,pole,k,R.from_quat(b['thigh_'+s]['target']['q'])
out={}
for mode in (0,1):
 d=json.loads((p/f'CalfAnkleConnection-knee-clean-variants-{mode}.json').read_text());assert d['reason']=='Complete',d['reason']
 rows=[r for r in d['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1'];cases=[]
 for i in range(1,len(rows)-1):
  if rows[i-1]['attack']=='None' or rows[i]['attack']!='None':continue
  case=dict(attack=rows[i-1]['attack'],tick=round(rows[i]['t']*60),legs={})
  for s in ('l','r'):
   vals=[]
   for j in range(i,min(i+65,len(rows))):
    if rows[j]['attack']!='None':break
    ax,pole,k,q=geom(rows[j],s);oldax,oldpole,oldk,oldq=geom(rows[j-1],s)
    carry=unit(oldpole-(oldax+ax)*(oldpole@ax)/max(1+oldax@ax,1e-9))
    vals.append([float(np.degrees(np.arccos(np.clip(carry@pole,-1,1)))),float(np.linalg.norm(k-oldk)),float(np.degrees((q*oldq.inv()).magnitude()))])
   assert np.isfinite(vals).all()
   case['legs'][s]=np.max(vals,axis=0).tolist()
  cases.append(case)
 out[str(mode)]=cases
 print(mode,len(cases))
 for c in cases:print(c['tick'],c['attack'].split(',')[0],{s:np.round(v,2).tolist() for s,v in c['legs'].items()})
(p/'KneeCleanVariants-verification.json').write_text(json.dumps(out,indent=2))
