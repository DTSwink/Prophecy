"""GPU manifold equations versus separately assembled float64 CPU equations."""
import os,sys,json,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
from probe_sequential_contacts import encode
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter


def main():
    out=probe.OUT/'causal_transfer';steps=np.array([19,21,31])
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:data={k:z[k] for k in z.files}
    with np.load(out/'friction_metric_velocities.npz') as z:expected=np.array([z[f'step{s}_jolt_manifold'] for s in steps])
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_LIMIT|mujoco.mjtDisableBit.mjDSBL_EQUALITY)
    wp.init();wp.set_device('cuda:0');wm=mjw.put_model(m)
    wd=mjw.put_data(m,mujoco.MjData(m),nworld=len(steps),nconmax=128,njmax=256)
    sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
    from runtime import install_hook
    install_hook();wm.uefn_compound_limits=types.SimpleNamespace(equalities=lambda m,d:None,limits=lambda m,d:None)
    motors=CoupledVelocityMotors(wm,wd,m);motors.install()
    q,v=zip(*(encode(m,data['subin'][s]) for s in steps));q=np.asarray(q,np.float32);v=np.asarray(v,np.float32)
    ctrl=np.zeros((len(steps),m.nu),np.float32);ctrl[:,motors.ids]=data['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
    wd.ctrl.assign(ctrl);wd.xfrc_applied.assign(data['forces'][steps].astype(np.float32));report=[]
    for block in (False,True):
        custom=SequentialContactAdapter(wm,wd,m,motors,iterations=100 if block else 2000,
            relaxation=.5,block_motors=block,manifolds=True);custom.install()
        try:
            wd.qpos.assign(q);wd.qvel.assign(v);wd.qacc_warmstart.zero_();mjw.step(wm,wd)
            np.testing.assert_array_equal(custom.error.numpy(),0)
            actual=wd.qvel.numpy();np.testing.assert_allclose(actual,expected,atol=2e-4,rtol=2e-5,equal_nan=False)
            p=custom.p.manifold
            row=dict(block=block,cases=len(steps),max_generalized_velocity_error=float(abs(actual-expected).max()),
                manifolds=p.count.numpy().tolist(),motor_defect_nm=float(custom.p.stats.numpy().max()))
            qw=wp.array(q,device='cuda:0');vw=wp.array(v,device='cuda:0')
            with wp.ScopedCapture(device='cuda:0') as cap:
                wp.copy(wd.qpos,qw);wp.copy(wd.qvel,vw);mjw.step(wm,wd)
            for _ in range(3):wp.capture_launch(cap.graph)
            np.testing.assert_array_equal(custom.error.numpy(),0)
            np.testing.assert_allclose(wd.qvel.numpy(),expected,atol=2e-4,rtol=2e-5,equal_nan=False)
            row['captured_replay_verified']=True;report.append(row);print(json.dumps(row),flush=True)
        finally:custom.restore()
    (out/'contact_manifolds_gpu.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
