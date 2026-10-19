"""CPU coordinate invariance; no GPU work and no cloud allocation."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'), str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import os
os.environ['PYGLET_HEADLESS']='true'
import numpy as np, mujoco, warp as wp
from scipy.spatial.transform import Rotation as R
from native_uefn_engine import configure_native_model, convert_ball_coordinates

def main():
    folder=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
    path=folder/'causal_transfer/sequential_model.mjb'
    before=mujoco.MjModel.from_binary_path(str(path)); after=mujoco.MjModel.from_binary_path(str(path))
    meta=json.loads((folder/'source/assets/uefn/limits.json').read_text())
    refs,bounds=configure_native_model(after,meta)
    rng=np.random.default_rng(74); qs=np.tile(before.qpos0,(128,1)).astype(np.float32)
    for j in range(before.njnt):
        if before.jnt_type[j]==mujoco.mjtJoint.mjJNT_BALL:
            s=before.jnt_qposadr[j];qs[:,s:s+4]=np.roll(R.from_rotvec(rng.normal(0,.4,(128,3))).as_quat(),1,axis=-1)
    wp.init()
    with wp.ScopedDevice('cpu'):
        src=wp.array(qs); dst=wp.empty_like(src); restored=wp.empty_like(src)
        args=[wp.array(before.jnt_qposadr.astype(np.int32)),wp.array(np.r_[before.jnt_qposadr[1:],before.nq].astype(np.int32)),
              wp.array((before.jnt_type==mujoco.mjtJoint.mjJNT_BALL).astype(np.int32)),wp.array(refs,dtype=wp.quat)]
        wp.launch(convert_ball_coordinates,dim=(128,before.njnt),inputs=[src,dst,*args,0],device='cpu')
        wp.launch(convert_ball_coordinates,dim=(128,before.njnt),inputs=[dst,restored,*args,1],device='cpu')
        np.testing.assert_allclose(restored.numpy(),qs,atol=2e-7)
        # In-place reset mapping must agree with the separate-buffer mapping.
        wp.launch(convert_ball_coordinates,dim=(128,before.njnt),inputs=[src,src,*args,0],device='cpu')
        np.testing.assert_array_equal(src.numpy(),dst.numpy())
    a=mujoco.MjData(before); b=mujoco.MjData(after); peak=0.
    for x,y in zip(qs,dst.numpy()):
        a.qpos[:]=x; b.qpos[:]=y
        mujoco.mj_kinematics(before,a);mujoco.mj_kinematics(after,b)
        peak=max(peak,float(abs(a.xpos-b.xpos).max()))
        np.testing.assert_allclose(a.xpos,b.xpos,atol=4e-7)
        np.testing.assert_allclose(a.xmat,b.xmat,atol=4e-7)
    print(json.dumps(dict(passed=True,random_states=128,body_position_max_error_m=peak,native_ball_limits=len(bounds))))

if __name__=='__main__':main()
