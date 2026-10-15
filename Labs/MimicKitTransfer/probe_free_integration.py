"""No-contact/no-limit timestep convergence, independent of the policy."""
import os, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np, mujoco
from scipy.spatial.transform import Rotation as R
from probe_sequential_contacts import encode, decode
import native_probe


def main():
    out=probe.OUT/'causal_transfer'
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT | mujoco.mjtDisableBit.mjDSBL_LIMIT
                             | mujoco.mjtDisableBit.mjDSBL_EQUALITY | mujoco.mjtDisableBit.mjDSBL_ACTUATION
                             | mujoco.mjtDisableBit.mjDSBL_GRAVITY)
    native_probe.fixture_path=probe.OUT/'timestep/fixture.exe'
    os.environ.update(TRANSFER_NO_CONTACT='1',TRANSFER_NO_LIMITS='1',TRANSFER_NO_GRAVITY='1',
                      TRANSFER_NO_MOTORS='1',TRANSFER_NO_DRAG='1',TRANSFER_HIGH_ITERATIONS='1',TRANSFER_SUBSTEPS='1')
    states=np.load(out/'reference.npz')['subin']
    physics=json.loads((probe.SOURCE/'assets/uefn/physics.json').read_text())['bodies']
    inertia=np.array([physics[name]['inertia'] for name in native_probe.names])
    rows=[]
    for step in [8,48,160]:
        for motion in ['recorded','zero','rigid_spin']:
            st=states[step].copy()
            if motion=='zero':st[:,7:]=0
            if motion=='rigid_spin':
                angular=np.array([1.,2.,-1.5]);st[:,10:]=angular
                com=np.array([physics[name]['com'] for name in native_probe.names])
                center=st[:,:3]+R.from_quat(st[:,3:7]).apply(com)
                st[:,7:10]=np.cross(angular,center-center[0])+[.4,-.2,.1]
            for dt in [1/120,1/240,1/480,1/960]:
                os.environ['TRANSFER_DT']=str(dt);m.opt.timestep=dt
                d=mujoco.MjData(m);d.qpos[:],d.qvel[:]=encode(m,st)
                rot=R.from_quat(st[:,3:7]).as_matrix();omega=st[:,10:]
                gyro=np.cross(omega,np.einsum('bij,bj->bi',rot@inertia@rot.transpose(0,2,1),omega))
                d.xfrc_applied[1:,3:]=gyro
                mujoco.mj_step(m,d);actual=decode(m,d)
                native=native_probe.Native(st)
                try:result=native.request('step '+' '.join(['0']*34))
                finally:native.close()
                target=np.array(result['bodies'])
                row=dict(step=step,motion=motion,dt=dt,
                    position_m=float(np.linalg.norm(actual[:,:3]-target[:,:3],axis=1).max()),
                    angle_rad=float((R.from_quat(actual[:,3:7])*R.from_quat(target[:,3:7]).inv()).magnitude().max()),
                    velocity_m_s=float(np.linalg.norm(actual[:,7:10]-target[:,7:10],axis=1).max()),
                    angular_rad_s=float(np.linalg.norm(actual[:,10:]-target[:,10:],axis=1).max()))
                rows.append(row);print(json.dumps(row),flush=True)
    (out/'free_integration.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')


if __name__=='__main__':main()
