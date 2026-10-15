"""Identical-input full GPU substep comparison; bounded 512-world benchmark."""
import os,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
from probe_sequential_contacts import encode
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter
from limit_projection_gpu import SplitLimitProjection
from probe_limit_projection import joint_metadata
import sys
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
from runtime import install_limits


def main():
    out=probe.OUT/'causal_transfer';wp.init();wp.set_device('cuda:0')
    tiled='--tiled' in sys.argv
    shared='--shared' in sys.argv;manifolds='--manifolds' in sys.argv
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:data={k:z[k] for k in z.files}
    steps=np.arange(512)%24+8
    m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'));m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    wm=mjw.put_model(m);d=mjw.put_data(m,mujoco.MjData(m),nworld=512,nconmax=150,njmax=450)
    install_limits(m,wm);motor=CoupledVelocityMotors(wm,d,m);motor.install()
    q,v=zip(*(encode(m,s) for s in data['subin'][steps]));q=wp.array(np.asarray(q,np.float32),device='cuda:0');v=wp.array(np.asarray(v,np.float32),device='cuda:0')
    ctrl=np.zeros((512,m.nu),np.float32);ctrl[:,motor.ids]=data['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
    d.ctrl.assign(ctrl);d.xfrc_applied.assign(data['forces'][steps].astype(np.float32))
    projection=SplitLimitProjection(m,d,joint_metadata(m),'cuda:0');rows=[];reference=None
    preprojection=wp.empty_like(d.qpos)
    for block in (False,True):
        custom=SequentialContactAdapter(wm,d,m,motor,iterations=100 if block else 1000,
            allow_soft_limits=True,hard_limit_control=True,relaxation=.5,block_motors=block,manifolds=manifolds)
        custom.install()
        def tick():
            wp.copy(d.qpos,q);wp.copy(d.qvel,v);mjw.step(wm,d);wp.copy(preprojection,d.qpos);projection.apply(custom.p.inv,tiled=tiled,shared=shared)
        tick()
        with wp.ScopedCapture(device='cuda:0') as capture:tick()
        for _ in range(3):wp.capture_launch(capture.graph)
        wp.synchronize_device('cuda:0');start=time.perf_counter()
        for _ in range(12):wp.capture_launch(capture.graph)
        wp.synchronize_device('cuda:0');ms=(time.perf_counter()-start)*1000/12
        np.testing.assert_array_equal(custom.error.numpy(),0)
        actual=np.concatenate([d.qpos.numpy(),d.qvel.numpy()],axis=1);assert np.isfinite(actual).all()
        if reference is None:reference=actual
        else:np.testing.assert_allclose(actual,reference,atol=3e-4,rtol=2e-5,equal_nan=False)
        row=dict(block=block,tiled_projection=tiled,shared_projection=shared,manifolds=manifolds,worlds=512,full_substep_ms=ms,max_state_difference=float(abs(actual-reference).max()),
                 motor_defect_nm=float(motor.stats.numpy()[:,0].max()),scope='fixed captured impact inputs, includes reset/collision/motors/contacts/integration/split projection; excludes policy')
        for name in ('projection','solve'):
            with wp.ScopedCapture(device='cuda:0') as component:
                if name=='projection':
                    wp.copy(d.qpos,preprojection);projection.apply(custom.p.inv,tiled=tiled,shared=shared)
                else:
                    wp.copy(d.qvel,v);custom.solve(wm,d)
            for _ in range(3):wp.capture_launch(component.graph)
            wp.synchronize_device('cuda:0');start=time.perf_counter()
            for _ in range(12):wp.capture_launch(component.graph)
            wp.synchronize_device('cuda:0');row[name+'_ms']=(time.perf_counter()-start)*1000/12
            np.testing.assert_array_equal(custom.error.numpy(),0)
        rows.append(row);print(json.dumps(row),flush=True);custom.restore()
    (out/('contact_solvers_benchmark'+('_shared' if shared else '_tiled' if tiled else '')+('_manifolds' if manifolds else '')+'.json')).write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
