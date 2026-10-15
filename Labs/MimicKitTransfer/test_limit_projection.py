"""GPU split correction against independent float64 generalized projection."""
import os,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
from probe_limit_projection import project,joint_metadata,errors
from probe_sequential_contacts import encode
from limit_projection_gpu import SplitLimitProjection


def main():
    out=probe.OUT/'causal_transfer';m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    joints=joint_metadata(m)
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:states=z['subin'][[11,12,18,24]].copy()
    q=[];inv=[];expected=[];rng=np.random.default_rng(123)
    for i in range(20):
        d=mujoco.MjData(m);d.qpos[:],_=encode(m,states[i%4])
        if i>=4:
            perturb=np.zeros(m.nv);perturb[6:]=rng.normal(0,.1,m.nv-6)
            mujoco.mj_integratePos(m,d.qpos,perturb,1.)
        mujoco.mj_forward(m,d);M=np.zeros((m.nv,m.nv));mujoco.mj_fullM(m,M,d.qM)
        q.append(d.qpos.copy());inv.append(np.linalg.inv(M));project(m,d,joints,20,frozen_inverse=inv[-1]);expected.append(d.qpos.copy())
    q=np.array(q);inv=np.array(inv);expected=np.array(expected)
    wp.init();wp.set_device('cuda:0');d=mjw.put_data(m,mujoco.MjData(m),nworld=len(q),nconmax=150,njmax=450)
    projection=SplitLimitProjection(m,d,joints,'cuda:0');wi=wp.array(inv.astype(np.float32),device='cuda:0')
    tiled='--tiled' in __import__('sys').argv
    shared='--shared' in __import__('sys').argv
    d.qpos.assign(q.astype(np.float32));projection.apply(wi,tiled=tiled,shared=shared);actual=d.qpos.numpy()
    assert np.isfinite(actual).all()
    np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=0,equal_nan=False)
    saved=wp.array(q.astype(np.float32),device='cuda:0')
    with wp.ScopedCapture(device='cuda:0') as capture:
        wp.copy(d.qpos,saved);projection.apply(wi,tiled=tiled,shared=shared)
    for _ in range(3):wp.capture_launch(capture.graph)
    np.testing.assert_array_equal(actual,d.qpos.numpy())
    report=dict(cases=len(q),tiled=tiled,shared=shared,max_qpos_error=float(abs(actual-expected).max()),capture_verified=True,
                diagnostic_metric='mass frozen within one projection stage; angular error recomputed per correction')
    print(json.dumps(report),flush=True);(out/('limit_projection_gpu'+('_shared' if shared else '_tiled' if tiled else '')+'.json')).write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
