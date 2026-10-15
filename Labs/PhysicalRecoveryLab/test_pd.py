"""Controller bounds, root isolation and zero-action physical rollout."""
from pathlib import Path
import json
import numpy as np
import torch
import warp as wp
from scipy.spatial.transform import Rotation as R
from test_phat_constraints import reference
from rig_dynamics import build
from joint_pd import JointPD

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

def main():
    wp.init(); sim,meta=build(8); controller=JointPD(sim,meta)
    q=np.tile(np.array(meta["reference_qpos"],dtype=np.float32),(8,1))
    q[:,2]+=.01
    with wp.ScopedDevice("cuda:0"):
        wp.copy(sim.wp_data.qpos,wp.array(q,dtype=float)); sim.wp_data.qvel.zero_()
        wp.capture_launch(sim.forward_graph)
        rest=controller.torques.numpy()
        # Authored locked connector axes contain ~1e-5 rad of float rounding.
        # Check the resulting tiny correction against independent SciPy rotations.
        expected=[]
        for i,j in enumerate(meta["joints"]):
            current=np.array(j["reference_wxyz"]); target=reference(current)
            target[np.array(j["modes"])==2]=0
            sw=R.from_quat([0,target[1],target[2],np.sqrt(1-target[1]**2-target[2]**2)])
            tw=R.from_rotvec([target[0],0,0])
            error=(R.from_quat(current[[1,2,3,0]]).inv()*sw*tw).as_rotvec()
            expected.append(controller.gains.numpy()[i,0]*error)
        assert np.max(np.abs(rest-np.asarray(expected)[None]))<5e-5,(rest,np.asarray(expected))
        torch.manual_seed(192)
        controller.actions.uniform_(-3,3)
        wp.capture_launch(sim.forward_graph)
        torque=controller.torques.numpy()
        cap=controller.gains.numpy()[:,2]
        assert (np.linalg.norm(torque,axis=-1)<=cap[None,:]+1e-4).all()
        assert np.max(np.abs(sim.wp_data.qfrc_applied.numpy()[:,:6]))==0
        controller.actions.zero_()
        states=[]
        for step in range(1200):
            wp.capture_launch(sim.step_graph)
            if step%60==0: states.append(sim.wp_data.qpos.numpy().copy())
        wp.synchronize()
        final=sim.wp_data.qpos.numpy(); forces=sim.wp_data.qfrc_applied.numpy()
        assert np.isfinite(final).all() and np.isfinite(forces).all()
        assert np.max(np.abs(forces[:,:6]))==0
        assert (np.linalg.norm(controller.torques.numpy(),axis=-1)<=cap[None,:]+1e-4).all()
    report={"passed":True,"action_count":controller.num_actions,"floating_root_force_max":0,
            "initial_rest_torque_max_nm":float(abs(rest).max()),"random_action_max_joint_torque_nm":float(np.linalg.norm(torque,axis=-1).max()),
            "zero_action_after_5s_pelvis_height_m":final[:,2].tolist(),"contract":controller.contract}
    np.savez_compressed(OUT/"pd-zero-action.npz",qpos=final,samples=np.array(states))
    (OUT/"pd-tests.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    (OUT/"controller.json").write_text(json.dumps(controller.contract,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="contract"},indent=2))
if __name__=="__main__":main()
