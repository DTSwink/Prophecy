"""Offline collider floor-clearance check for recorded physics comparisons."""
from getup_transfer import *
import mujoco

def minimum(path):
    m=mujoco.MjModel.from_binary_path(str(OUT/'recovery-benchmark.mjb'))
    x=np.load(path);state=x['states'];shape=state.shape[:2];lowest=np.full(shape,np.inf)
    for g in range(m.ngeom):
        b=int(m.geom_bodyid[g])-1
        if b<0 or not (m.geom_contype[g] or m.geom_conaffinity[g]):continue
        rot=R.from_quat(state[:,:,b,3:7].reshape(-1,4))
        pos=state[:,:,b,:3].reshape(-1,3)+rot.apply(np.broadcast_to(m.geom_pos[g],(len(rot),3)))
        world=(rot*R.from_quat(np.roll(m.geom_quat[g],-1))).as_matrix()
        kind=int(m.geom_type[g]);size=m.geom_size[g]
        if kind==int(mujoco.mjtGeom.mjGEOM_SPHERE):extent=np.full(len(rot),size[0])
        elif kind==int(mujoco.mjtGeom.mjGEOM_CAPSULE):extent=size[0]+size[1]*np.abs(world[:,2,2])
        elif kind==int(mujoco.mjtGeom.mjGEOM_BOX):extent=np.abs(world[:,2,:])@size
        else:raise ValueError(kind)
        lowest=np.minimum(lowest,(pos[:,2]-extent).reshape(shape))
    ends=x['endticks'] if 'endticks' in x else np.full(shape[1],shape[0]-1)
    return dict(file=path.name,initial_minimum_m=float(lowest[0].min()),
        before_end_minimum_m=[float(lowest[:int(t)+1,w].min()) for w,t in enumerate(ends)],
        maximum_penetration_cm=float(max(0,-min(lowest[:int(t)+1,w].min() for w,t in enumerate(ends)))*100))

if __name__=='__main__':
    reports=[minimum(Path(p)) for p in sys.argv[1:]]
    (OUT/'floor-comparison.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports))
