"""Actual collider support heights in preserved motion, not skin vertices."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco
from scipy.spatial.transform import Rotation as R
from native_probe import names


def main(label,native=False):
    folder=probe.OUT/'causal_transfer'
    with np.load(folder/(label+'.npz')) as z:
        if native:
            worlds=sorted((k for k in z.files if k.startswith('world')),key=lambda k:int(k[5:]))
            assert len({len(z[k]) for k in worlds})==1,'Native audit requires equally completed rollouts'
            states=np.stack([z[k] for k in worlds],axis=1)
        else:states=z['states']
    m=mujoco.MjModel.from_binary_path(str(folder/'sequential_model.mjb'))
    rows=[]
    for g in range(m.ngeom):
        b=int(m.geom_bodyid[g])
        if not b:continue
        ident=next(i for i,n in enumerate(names) if m.body(b).name.endswith(n))
        s=states[:,:,ident];rot=R.from_quat(s[:,:,3:7].reshape(-1,4))
        center=s[:,:,:3].reshape(-1,3)+rot.apply(m.geom_pos[g])
        geomrot=rot*R.from_quat(np.roll(m.geom_quat[g],-1))
        kind=int(m.geom_type[g]);size=m.geom_size[g]
        if kind==int(mujoco.mjtGeom.mjGEOM_SPHERE):extent=np.full(len(center),size[0])
        elif kind==int(mujoco.mjtGeom.mjGEOM_CAPSULE):extent=size[0]+size[1]*abs(geomrot.apply([0,0,1])[:,2])
        elif kind==int(mujoco.mjtGeom.mjGEOM_BOX):extent=abs(geomrot.as_matrix()[:,2])@size
        else:raise ValueError(kind)
        low=(center[:,2]-extent).reshape(states.shape[:2]);minimum=float(low.min())
        tick,world=np.unravel_index(low.argmin(),low.shape)
        rows.append(dict(body=names[ident],geom=m.geom(g).name,min_height_m=minimum,tick=int(tick if native else tick+1),
            world=int(world),frames_beyond_jolt_slop=int((low<-.02).sum())))
    report=dict(source=label,rows=sorted(rows,key=lambda r:r['min_height_m']))
    (folder/(label+'_ground_depth.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main(sys.argv[1],'--native' in sys.argv)
