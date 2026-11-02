"""Opaque, depth-tested retarget inspection; no Matplotlib overlap judgments."""
import json, numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry, OUT as OLD, write
from repair_slow_arms import OUT

g=Geometry();d=np.load(OLD/'candidates/sitting.npz');variants={}
for name,frames in [('source',d['wanted']),('original',d['before'])]:
    rows=[]
    for f in frames:
        p,r=(f[:,:3,3],f[:,:3,:3]) if name=='source' else g.fk(f)
        g.set_pose(p,r)
        rows.append(dict(p=g.d.geom_xpos.tolist(),q=R.from_matrix(g.d.geom_xmat.reshape(-1,3,3)).as_quat().tolist(),
            arm_leg_penetration_cm=max(0.,-min(g.distance(a,b) for a,b in g.armleg))*100))
    variants[name]=rows
draft=np.load(OUT/'sitting.npz');variants['draft']=[]
for f in draft['after']:
    p,r=g.fk(f);g.set_pose(p,r)
    variants['draft'].append(dict(p=g.d.geom_xpos.tolist(),q=R.from_matrix(g.d.geom_xmat.reshape(-1,3,3)).as_quat().tolist(),
        arm_leg_penetration_cm=max(0.,-min(g.distance(a,b) for a,b in g.armleg))*100))
write(OUT/'view-data.json',dict(geometry=g.gs,variants=variants,frames=len(d['before'])))
for filename in ['index.html','view.js']:
    (OUT/filename).write_text((__import__('pathlib').Path(__file__).parent/'arm_viewer'/filename).read_text(encoding='utf-8'),encoding='utf-8')
# Keep the user's existing URL useful, without showing rejected full-body data.
(OLD/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=../arm-ik-20261031/"><a href="../arm-ik-20261031/">Open arm-only inspection</a>',encoding='utf-8')
print(OUT)
