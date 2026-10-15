"""CPU impact isolation: Jolt's pair-local tangent metric vs articulation metric."""
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


def main():
    out=probe.OUT/'causal_transfer'
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:data={k:z[k] for k in z.files}
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'));m.opt.timestep=1/240
    m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_ACTUATION|mujoco.mjtDisableBit.mjDSBL_LIMIT)
    ids=np.flatnonzero(m.actuator_biasprm[:,2]<0);gain=m.actuator_gainprm[ids,0]
    caps=np.where(m.actuator_forcelimited[ids],m.actuator_forcerange[ids,1],np.inf)
    for a,ident in enumerate(ids):
        joint=m.actuator_trnid[ident,0]
        if m.jnt_actfrclimited[joint]:caps[a]=min(caps[a],m.jnt_actfrcrange[joint,1])
    assert np.isfinite(caps).all() and np.all(caps>0)
    caps/=240
    dofs=m.jnt_dofadr[m.actuator_trnid[ids,0]]+np.argmax(abs(m.actuator_gear[ids,:3]),axis=1)
    assert len(ids)==34
    native_probe.fixture_path=probe.OUT/'point-contact/profile/fixture.exe'
    for key in list(os.environ):
        if key.startswith('TRANSFER_'):del os.environ[key]
    os.environ.update(TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1',TRANSFER_NO_LIMITS='1',
        TRANSFER_SUBSTEPS='1',TRANSFER_RIG_VELOCITY_STEPS='100',TRANSFER_RIG_POSITION_STEPS='20')
    report=[]
    for step in (19,21,31):
        state=data['subin'][step];action=data['actions'][step//8,0].clip(-2*np.pi,2*np.pi)
        n=Native(state)
        try:result=n.request('step '+' '.join(map(str,action)))
        finally:n.close()
        actual=np.array(result['bodies'])
        for metric in ('articulated','jolt_pair'):
            d=mujoco.MjData(m);d.qpos[:],d.qvel[:]=encode(m,state);d.xfrc_applied[:]=data['forces'][step]
            mujoco.mj_forward(m,d);M=np.zeros((m.nv,m.nv));mujoco.mj_fullM(m,M,d.qM);inv=np.linalg.inv(M)
            v=d.qvel+m.opt.timestep*d.qacc_smooth;motor=np.zeros(34);contacts=[]
            for c in d.contact:
                if c.dist>=0:continue
                normal=c.frame[:3];t1=np.array([normal[2],0,-normal[0]]) if abs(normal[0])>abs(normal[1]) else np.array([0,normal[2],-normal[1]])
                t1/=np.linalg.norm(t1);frame=np.array([normal,t1,np.cross(normal,t1)])
                J=np.zeros((3,m.nv));pair=np.zeros(3)
                for sign,geom in [(-1,c.geom[0]),(1,c.geom[1])]:
                    b=m.geom_bodyid[geom];jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jac(m,d,jp,jr,c.pos,b);J+=sign*frame@jp
                    if not b:continue
                    I=d.ximat[b].reshape(3,3)@np.diag(1/m.body_inertia[b])@d.ximat[b].reshape(3,3).T
                    for a in range(3):
                        cross=np.cross(c.pos-d.xipos[b],frame[a]);pair[a]+=1/m.body_mass[b]+cross@I@cross
                response=inv@J.T;diagonal=np.diag(J@response).copy()
                if metric=='jolt_pair':diagonal[1:]=pair[1:]
                contacts.append([J,response,diagonal,np.zeros(3),float(c.friction[0]) if c.dim==3 else 0.])
            for it in range(2000):
                for a,dof in enumerate(dofs):
                    comp=240/gain[a];value=np.clip(motor[a]+(action[a]-v[dof]-comp*motor[a])/(inv[dof,dof]+comp),-caps[a],caps[a])
                    value=(value+motor[a])*.5;v+=inv[:,dof]*(value-motor[a]);motor[a]=value
                for J,response,diag,impulse,mu in contacts:
                    if mu:
                        tangent=impulse[1:]-(J[1:]@v)/diag[1:];bound=mu*impulse[0];length=np.linalg.norm(tangent)
                        if length>bound:tangent*=bound/max(length,1e-30)
                        tangent=(tangent+impulse[1:])*.5;v+=response[:,1:]@(tangent-impulse[1:]);impulse[1:]=tangent
                    normal=max(0,impulse[0]-J[0]@v/diag[0]);normal=(normal+impulse[0])*.5
                    v+=response[:,0]*(normal-impulse[0]);impulse[0]=normal
            d.qvel[:]=v;mujoco.mj_integratePos(m,d.qpos,v,m.opt.timestep);pred=decode(m,d)
            row=dict(step=step,metric=metric,contacts=len(contacts),native_manifold_sizes=[len(c['points']) for c in result['contacts']] if result['contacts'] and 'points' in result['contacts'][0] else [],
                     motor_defect_nm=float(abs(motor*240-np.clip(gain*(action-v[dofs]),-caps*240,caps*240)).max()),
                     max_angvel_difference=float(np.linalg.norm(pred[:,10:]-actual[:,10:],axis=-1).max()))
            report.append(row);print(json.dumps(row),flush=True)
    (out/'friction_metric.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
