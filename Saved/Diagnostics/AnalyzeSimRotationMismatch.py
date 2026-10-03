import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
label=sys.argv[1] if len(sys.argv)>1 else 'before'
d=json.loads(Path(f'Saved/Diagnostics/SimRotationMismatch-{label}.json').read_text());rows=d['rows']
print('CAPTURE',d['reason'],len(rows))
if not rows:raise SystemExit(1)
print('MODES',sorted(set(r['mode'] for r in rows)),'TICKS',rows[0]['tick'],rows[-1]['tick'],'MESHES',list(rows[0]['meshes']))
def angle(a,b):return float(np.degrees((R.from_quat(a['q']).inv()*R.from_quat(b['q'])).magnitude()))
def dist(a,b):return float(np.linalg.norm(np.array(a['p'])-b['p']))
summary={}
for bone in rows[-1]['targets']:
 vals=[];full=[];debug=[];local=[]
 for r in rows:
  if bone not in r['targets']:continue
  target=r['targets'][bone]['target'];physical=r['meshes'].get('PhysicalMesh',{}).get(bone)
  if physical:vals.append((angle(target,physical),dist(target,physical),r['tick']))
  if bone in r['full']:full.append((angle(target,r['full'][bone]),dist(target,r['full'][bone]),r['tick']))
  for name,m in r['meshes'].items():
   if name.startswith('KinematicDebugMesh') and bone in m:debug.append((angle(target,m[bone]),dist(target,m[bone]),r['tick']))
  if bone.startswith('ball_') and physical:
   foot='foot_'+bone[-1];pt=r['meshes']['PhysicalMesh'][foot];tt=r['targets'][foot]['target']
   delta=(R.from_quat(pt['q']).inv()*R.from_quat(physical['q'])).inv()*(R.from_quat(tt['q']).inv()*R.from_quat(target['q']))
   local.append(float(np.degrees(delta.magnitude())))
 summary[bone]=dict(physical_median_deg=float(np.median([v[0] for v in vals])) if vals else None,physical_worst=max(vals) if vals else None,full_worst=max(full) if full else None,debug_worst=max(debug) if debug else None,toe_local_max=max(local) if local else None)
print(json.dumps(summary,indent=2));Path(f'Saved/Diagnostics/SimRotationMismatch-{label}-summary.json').write_text(json.dumps(summary,indent=2))
