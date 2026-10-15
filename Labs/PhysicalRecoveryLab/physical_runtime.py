"""Live checkpoint physics for Stepper. The same env/PD/limits as training."""
import argparse
import contextlib
import json
import sys
import traceback
from pathlib import Path
import numpy as np
import torch
import warp as wp
import mujoco
from recovery_env import RecoveryEnv
from policy import load_policy
from replay import WORLD_TO_VIEW,OUT

class PhysicalRuntime:
    def __init__(self,checkpoint,cube_count=8):
        config=torch.load(checkpoint,map_location='cpu',weights_only=False)['infos']['physical_recovery']
        self.env=RecoveryEnv(1,cube_count=cube_count,auto_reset=False,
            integrator=config.get('integrator','implicitfast'),native_motors=config.get('native_motors',False),relative_targets=config.get('relative_targets',False),
            ccd_iterations=config.get('ccd_iterations',50),gyroscopic_forces=config.get('gyroscopic_forces',True),
            pose_bank=config.get('pose_bank','rig-passive.npz'),raw_action_cost=config.get('previous_action_observation')=='requested',
            posture_profile=config.get('posture_reward',{}).get('profile','legacy'))
        self.policy,self.checkpoint=load_policy(checkpoint,self.env)
        self.model=self.env.sim.mj_model;self.data=mujoco.MjData(self.model)
        self.qpos=wp.to_torch(self.env.sim.wp_data.qpos)
        self.qvel=wp.to_torch(self.env.sim.wp_data.qvel)
        self.rig=json.loads((OUT/"rig.json").read_text())
        self.names=[b["name"] for b in self.rig["bodies"]]
        self.sites=[self.model.site(n+"_bone").id for n in self.names]
        self.geomids=[self.model.geom(b["name"]+f"_shape{k}").id for b in self.rig["bodies"] for k in range(len(b["shapes"]))]
        self.shapes=[]
        for b in self.rig["bodies"]:
            for shape in b["shapes"]:
                self.shapes.append({"bone":b["name"],"kind":shape["kind"],"radius":shape["radius_cm"]*.01,
                    "length":shape["cylinder_length_cm"]*.01,"dimensions":(np.array(shape["half_extent_cm"])*.02).tolist()})
        self.cubes=[]
        for i in range(cube_count):
            joint=self.model.joint(f"impact_cube_{i}_joint")
            self.cubes.append((int(joint.qposadr[0]),int(joint.dofadr[0]),self.model.geom(f"impact_cube_{i}_shape").id))
        self.next_cube=0;self.active_cubes=set();self.ticks=0

    @torch.inference_mode()
    def step(self,ticks=1):
        torch.cuda.set_stream(self.env.sim.physical_torch_stream);wp.set_stream(self.env.sim.physical_warp_stream)
        for _ in range(ticks):self.env.step(self.policy(self.env.get_observations()));self.ticks+=1
        return self.snapshot()

    def reset(self):
        self.env.reset(torch.ones(1,device=self.env.device,dtype=torch.bool))
        self.ticks=0;self.active_cubes.clear();self.next_cube=0
        return self.snapshot()

    def launch(self,origin_view):
        if not self.cubes:raise ValueError("This runtime has no cube pool")
        target=self.env.qpos[0,:3].cpu().numpy()+[0,0,.25]
        origin=np.asarray(origin_view)@WORLD_TO_VIEW
        distance=np.linalg.norm(target-origin)
        if distance<1.:origin=target+np.array([0,-3,1.])
        flight=max(.15,np.linalg.norm(target-origin)/10.)
        velocity=(target-origin)/flight+np.array([0,0,4.905*flight])
        slot=self.next_cube%len(self.cubes);self.next_cube+=1
        qa,da,_=self.cubes[slot]
        self.qpos[0,qa:qa+7]=torch.tensor(np.r_[origin,1,0,0,0],device=self.env.device)
        self.qvel[0,da:da+6]=torch.tensor(np.r_[velocity,0,0,0],device=self.env.device)
        self.active_cubes.add(slot)
        return self.snapshot()

    def snapshot(self):
        self.data.qpos[:]=self.qpos[0].cpu().numpy()
        mujoco.mj_kinematics(self.model,self.data)
        positions=self.data.site_xpos[self.sites]@WORLD_TO_VIEW.T
        rotations=self.data.site_xmat[self.sites].reshape(-1,3,3).transpose(0,2,1)@WORLD_TO_VIEW.T
        ids=list(self.geomids)+[self.cubes[i][2] for i in sorted(self.active_cubes)]
        centers=self.data.geom_xpos[ids]@WORLD_TO_VIEW.T
        axes=self.data.geom_xmat[ids].reshape(-1,3,3).transpose(0,2,1)@WORLD_TO_VIEW.T
        shapes=self.shapes+[{"bone":"impact_cube","kind":"box","dimensions":[.45]*3} for _ in self.active_cubes]
        return {"tick":self.ticks,"names":self.names,"parents":[next((j["parent"] for j in self.rig["joints"] if j["child"]==i),-1) for i in range(len(self.names))],
            "positions":positions.tolist(),"rotations":rotations.tolist(),"centers":centers.tolist(),"axes":axes.tolist(),"shapes":shapes,
            "cube_rig_contact_impulse_ns":self.env.cube_impulses[0].cpu().tolist() if self.env.cube_impulses is not None else [],
            "status":f"Physical checkpoint · tick {self.ticks} · Space: 30kg cube · 240Hz physics"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--checkpoint",required=True);args=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    protocol=sys.stdout
    # Warp's compilation logs stay out of the JSON protocol.
    with contextlib.redirect_stdout(sys.stderr):
        wp.init();runtime=PhysicalRuntime(args.checkpoint)
    def send(data):protocol.write(json.dumps(data,allow_nan=False)+"\n");protocol.flush()
    send(runtime.snapshot())
    for line in sys.stdin:
        try:
            command=json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                op=command["op"]
                if op=="quit":break
                if op=="step":result=runtime.step(max(1,min(4,int(command.get("ticks",1)))))
                elif op=="reset":result=runtime.reset()
                elif op=="launch":result=runtime.launch(command["origin"])
                elif op=="state":result=runtime.snapshot()
                else:raise ValueError(op)
            send(result)
        except Exception:
            send({"error":traceback.format_exc()});break

if __name__=="__main__":main()
