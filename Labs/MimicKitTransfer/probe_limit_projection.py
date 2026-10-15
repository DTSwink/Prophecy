"""CPU reference for Jolt-style split angular position correction.

Diagnostic only. Uses generalized mass to move the whole articulation; never
clips a joint quaternion while leaving its parent/root fixed. No velocities,
forces, motor gains, limits or production configuration are changed.
"""
import os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco
from scipy.spatial.transform import Rotation as R
import native_probe
from native_probe import Native,names
from probe_sequential_contacts import encode,decode


def clamp_swing_twist(quat, angles):
    q=R.from_quat(quat).as_quat()
    twist=np.array([q[0],0.,0.,q[3]])
    if np.linalg.norm(twist)<1e-12: twist=np.array([0.,0.,0.,1.])
    twist/=np.linalg.norm(twist)
    swing=(R.from_quat(q)*R.from_quat(twist).inv()).as_quat()
    if swing[3]<0:swing=-swing
    if twist[3]<0:twist=-twist
    if abs(twist[0])>np.sin(angles[0]/2):
        twist=np.array([np.sign(twist[0])*np.sin(angles[0]/2),0.,0.,np.cos(angles[0]/2)])
    axes=np.sin(np.asarray(angles[1:])/2);point=swing[1:3].copy()
    if np.sum((point/axes)**2)>1:
        # Closest Euclidean point on Jolt's swing ellipse, not radial scaling.
        a2=axes**2;lo=0.;hi=float(np.linalg.norm(axes*point))
        for _ in range(60):
            mid=(lo+hi)*.5
            if np.sum((axes*point/(a2+mid))**2)>1:lo=mid
            else:hi=mid
        point=a2*point/(a2+(lo+hi)*.5)
        swing=np.r_[0.,point,np.sqrt(max(0.,1.-point@point))]
    return R.from_quat(swing)*R.from_quat(twist)


def joint_metadata(m):
    meta=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    result=[]
    for j in meta['joints']:
        body=next(i for i in range(1,m.nbody) if m.body(i).name.endswith(j['body']))
        idx=m.body_jntadr[body]
        result.append((idx,j))
    return result


def errors(m,qpos,joints):
    values=[]
    for idx,j in joints:
        qa=m.jnt_qposadr[idx];da=m.jnt_dofadr[idx]
        if j['kind']=='ball':
            assert j['modes']==[1,1,1]
            cur=R.from_quat(np.roll(j['reference_wxyz'],-1))*R.from_quat(np.roll(qpos[qa:qa+4],-1))
            target=clamp_swing_twist(cur.as_quat(),j['limits_rad'])
            delta=(target.inv()*cur).as_quat()
            if delta[3]<0:delta=-delta
            err=2*delta[:3]
            if np.linalg.norm(err)>1e-9:values.append((da,err))
        else:
            if m.jnt_limited[idx]:
                err=qpos[qa]-np.clip(qpos[qa],*m.jnt_range[idx])
                if abs(err)>1e-9:values.append((da,np.array([err])))
    return values


def project(m,d,joints,iterations,beta=.2,frozen_inverse=None):
    for _ in range(iterations):
        if not errors(m,d.qpos,joints):break
        for joint in joints:
            active=errors(m,d.qpos,[joint])
            if not active:continue
            da,err=active[0]
            mujoco.mj_forward(m,d)
            M=np.zeros((m.nv,m.nv));mujoco.mj_fullM(m,M,d.qM)
            inv=np.linalg.inv(M) if frozen_inverse is None else frozen_inverse;ids=np.arange(da,da+len(err))
            dq=inv[:,ids]@np.linalg.solve(inv[np.ix_(ids,ids)],-beta*err)
            mujoco.mj_integratePos(m,d.qpos,dq,1.)


def main():
    out=probe.OUT/'causal_transfer'
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:states=z['subin'][[11,12,18,24]].copy()
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_CONTACT|mujoco.mjtDisableBit.mjDSBL_ACTUATION)
    m.opt.gravity[:]=0
    joints=joint_metadata(m)
    native_probe.fixture_path=probe.OUT/'point-contact/profile/fixture.exe'
    for key in list(os.environ):
        if key.startswith('TRANSFER_'):del os.environ[key]
    os.environ.update(TRANSFER_NO_MOTORS='1',TRANSFER_NO_CONTACT='1',TRANSFER_NO_GRAVITY='1',TRANSFER_NO_DRAG='1',
                      TRANSFER_SUBSTEPS='1',TRANSFER_RIG_VELOCITY_STEPS='100',TRANSFER_RIG_POSITION_STEPS='20')
    rows=[]
    for i,state in enumerate(states):
        state[:,7:]=0
        d=mujoco.MjData(m);d.qpos[:],d.qvel[:]=encode(m,state)
        before=decode(m,d);initial=errors(m,d.qpos,joints)
        masses=m.body_mass[1:];mujoco.mj_forward(m,d);com=np.sum(d.xipos[1:]*masses[:,None],axis=0)/masses.sum()
        project(m,d,joints,20)
        after=decode(m,d);mujoco.mj_forward(m,d)
        delta_com=np.linalg.norm(np.sum(d.xipos[1:]*masses[:,None],axis=0)/masses.sum()-com)
        n=Native(state)
        try:actual=np.array(n.request('step '+' '.join(['0']*34))['bodies'])
        finally:n.close()
        angle=np.degrees((R.from_quat(actual[:,3:7]).inv()*R.from_quat(after[:,3:7])).magnitude())
        row=dict(case=i,initial_error_rad=max([np.linalg.norm(e) for _,e in initial],default=0),
                 remaining_error_rad=max([np.linalg.norm(e) for _,e in errors(m,d.qpos,joints)],default=0),
                 com_drift_m=float(delta_com),max_position_difference_m=float(np.linalg.norm(actual[:,:3]-after[:,:3],axis=-1).max()),
                 max_angle_difference_deg=float(angle.max()),max_native_velocity=float(abs(actual[:,7:]).max()),
                 unchanged_velocity=bool(np.array_equal(d.qvel,np.zeros(m.nv))))
        rows.append(row);print(json.dumps(row),flush=True)
    (out/'limit_projection.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
