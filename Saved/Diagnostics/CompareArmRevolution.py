import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202')
ns={};exec(pathlib.Path('Saved/Diagnostics/AnalyzePikeElbowCurrent.py').read_text().split('for mode in')[0],ns)
for mode in ('current','no_cone','no_inertia'):
 f=p/f'arm_revolution_{mode}.json'
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows'];print(mode,'mode',rows[190]['mode'])
 for lo,hi in ((189,220),(189,250),(189,310)):
  sel=[r for r in rows if lo<=r['tick']<=hi];pol=[];rot=[];tw=[]
  for a,b in zip(sel,sel[1:]):
   aa,bb=ns['sample'](a),ns['sample'](b);pol.append(ns['turn'](aa,bb))
   def q(row,bone):
    d=row['raw'];return R.from_quat(d['spine_05']['future']['q']).inv()*R.from_quat(d[bone]['future']['q'])
   d=(q(b,'upperarm_r')*q(a,'upperarm_r').inv()).as_rotvec();rot.append(np.linalg.norm(d));tw.append(np.dot(d,ns['unit'](aa['elbow']-aa['shoulder'])))
  print(lo,hi,'pole signed/abs',round(sum(pol),2),round(sum(abs(x) for x in pol),2),'upper angle path/twist',round(np.degrees(sum(rot)),2),round(np.degrees(sum(tw)),2))
 for t in (189,195,205,215,225,240,260,300):
  x=next(r for r in rows if r['tick']==t);a=ns['sample'](x);print(t,'elbow',np.round(a['elbow']-a['shoulder'],1),'pole',np.round(a['pole'],2),'radius',round(a['radius'],2))
