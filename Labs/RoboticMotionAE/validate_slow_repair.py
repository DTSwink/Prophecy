"""Independent physics-FK and dense motion interpolation checks for candidates."""
import json,pickle
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R,Slerp
from repair_slow_targets import Geometry,ROOT,P,OUT,write,sha

def dense(g,frames,sub=8):
    t=np.arange(len(frames));q=np.linspace(0,len(frames)-1,(len(frames)-1)*sub+1)
    result=np.empty((len(q),40))
    for j in range(3):result[:,j]=np.interp(q,t,frames[:,j])
    result[:,3:6]=Slerp(t,R.from_rotvec(frames[:,3:6]))(q).as_rotvec()
    for joint in g.joints:
        i=6+joint.dof_idx;n=joint.get_dof_dim()
        if n==3:result[:,i:i+3]=Slerp(t,R.from_rotvec(frames[:,i:i+3]))(q).as_rotvec()
        else:result[:,i]=np.interp(q,t,frames[:,i])
    return result

def independent(g,f,m,d):
    d.qpos[:]=m.qpos0;d.qpos[:3]=f[:3];d.qpos[3:7]=R.from_rotvec(f[3:6]).as_quat()[[3,0,1,2]]
    for j in g.meta['joints']:
        kin=g.k.get_joint(g.names.index(j['body']));a=6+kin.dof_idx;adr=m.joint(j['name']).qposadr[0]
        if j['kind']=='ball':d.qpos[adr:adr+4]=R.from_rotvec(f[a:a+3]).as_quat()[[3,0,1,2]]
        else:d.qpos[adr]=f[a]
    mujoco.mj_kinematics(m,d)
    p,r=g.fk(f);g.set_pose(p,r);error=0.
    for i,geom in enumerate(g.gs):
        ix=m.geom(geom['name']).id
        np.testing.assert_allclose(m.geom_size[ix][:len(geom['size'])],geom['size'],atol=1e-12)
        error=max(error,float(np.abs(d.geom_xpos[ix]-g.d.geom_xpos[i]).max()),float(np.abs(d.geom_xmat[ix]-g.d.geom_xmat[i]).max()))
    assert error<3e-6,error
    return error

def validate(path):
    g=Geometry();data=pickle.loads(path.read_bytes());original=OUT/'before/motions'/path.name
    if not original.exists():original=P/'motions'/path.name
    before=pickle.loads(original.read_bytes());f=data['frames']
    assert data['loop_mode']==before['loop_mode']==1 and data['fps']==before['fps'] and f.shape==before['frames'].shape
    np.testing.assert_array_equal(f[:,:2],before['frames'][:,:2]);np.testing.assert_array_equal(f[:,3:6],before['frames'][:,3:6])
    m=mujoco.MjModel.from_xml_path(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn_physics.xml'));d=mujoco.MjData(m)
    worst_fk=max(independent(g,x,m,d) for x in f[::5])
    expanded=dense(g,f);ds=[];floors=[];lm=[]
    for x in expanded:
        ds.append(g.distances(x).min());floors.append(g.floors().min());lm.append(g.limit_margin(x).min())
    rotations=np.array([g.fk(x)[1] for x in f]);origrot=np.array([g.fk(x)[1] for x in before['frames']])
    def angle_step(rot):return R.from_matrix((rot[:-1].transpose(0,1,3,2)@rot[1:]).reshape(-1,3,3)).magnitude().reshape(len(rot)-1,15)*data['fps']
    speed=angle_step(rotations);oldspeed=angle_step(origrot)
    report=dict(clip=path.stem,sha256=sha(path),frames=len(f),dense_samples=len(expanded),
        independent_physics_fk_max_error=worst_fk,min_self_clearance_m=float(min(ds)),min_floor_height_m=float(min(floors)),
        min_joint_limit_margin=float(min(lm)),joint_violations=sum(any(g.limits(x).values()) for x in expanded),
        max_body_angvel_before=float(oldspeed.max()),max_body_angvel_after=float(speed.max()),
        root_xy_rotation_fps_loop_frame_count_preserved=True)
    report['passed']=bool(min(ds)>0 and min(floors)>0 and report['joint_violations']==0 and speed.max()<=max(.5,2*oldspeed.max()))
    write(OUT/'candidates'/f'{path.stem}-validation.json',report)
    print(json.dumps(report),flush=True);return report

if __name__=='__main__':
    reports=[validate(p) for p in sorted((OUT/'candidates').glob('*.pkl'))]
    write(OUT/'validation.json',dict(passed=len(reports)==8 and all(x['passed'] for x in reports),motions=reports))
