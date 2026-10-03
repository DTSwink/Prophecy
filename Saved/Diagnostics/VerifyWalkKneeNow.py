import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics');f=p/'WalkKneeNowOff-same-frame.json'
if not f.exists():print('Still capturing');raise SystemExit
s=json.loads(f.read_text(encoding='utf-8'));o={}
for side in ('l','r'):
 def geo(d):
  h,k,f=[np.array(d[n+'_'+side]['target']['p']) for n in ('thigh','calf','foot')];u=k-h;v=f-k
  return float(np.degrees(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))
 a=s['before'];b=s['after'];diff=np.array(a['foot_'+side]['target']['p'])-b['foot_'+side]['target']['p']
 o[side]=dict(bend_enabled=geo(a),bend_disabled=geo(b),foot_correction=diff.tolist(),foot_correction_cm=float(np.linalg.norm(diff)))
print(o)
base={r['clock']:r for r in json.loads((p/'WalkKneeNow-capture.json').read_text(encoding='utf-8'))['rows']};test=json.loads((p/'WalkKneeNowOff-capture.json').read_text(encoding='utf-8'))
o['prefix_error']=max(np.linalg.norm(np.array(r['targets'][n]['target']['p'])-base[r['clock']]['targets'][n]['target']['p']) for r in test['rows'] for n in r['targets']);o['reason']=test['reason'];print('prefix',o['prefix_error'],'reason',o['reason']);(p/'WalkKneeNow-verification.json').write_text(json.dumps(o,indent=2),encoding='utf-8')
