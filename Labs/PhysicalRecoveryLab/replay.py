"""Actual training poses in the existing Stepper replayer's schema (metres, Y up)."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"
STEPPER=Path("C:/Users/singerie/Documents/Cursor/stepper")
WORLD_TO_VIEW=np.array([[1,0,0],[0,0,1],[0,-1,0]],dtype=float)

def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(data,separators=(",",":"),allow_nan=False),encoding="utf-8")
    temporary.replace(path)

class ReplayWriter:
    def __init__(self,name):
        self.directory=STEPPER/"training/runs"/("physical_recovery_"+name)
        self.debug=self.directory/"debug";self.debug.mkdir(parents=True,exist_ok=True)
        self.rig=json.loads((OUT/"rig.json").read_text())
        self.model=mujoco.MjModel.from_xml_path(str(OUT/"uefn.xml"));self.data=mujoco.MjData(self.model)
        self.names=[b["name"] for b in self.rig["bodies"]]
        self.sites=[self.model.site(n+"_bone").id for n in self.names]
        self.bones=[[j["parent"],j["child"]] for j in self.rig["joints"]]
        self.toes=[]
        for name in ("ball_l","ball_r"):
            bone=next(b for b in self.rig["skeleton"] if b["name"]==name)
            parent=self.names.index(self.rig["skeleton"][bone["parent"]]["name"])
            local=bone["local"]
            self.bones.append([parent,len(self.names)]);self.names.append(name)
            self.toes.append((parent,np.array(local["position_cm"])*.01,Rotation.from_quat(local["rotation_xyzw"]).as_matrix()))
        self.colliders=[]
        for body in self.rig["bodies"]:
            for shape in body["shapes"]:
                self.colliders.append({"bone":body["name"],"kind":shape["kind"],
                    "position":(np.array(shape["local"]["position_cm"])*.01).tolist(),
                    "axes":Rotation.from_quat(shape["local"]["rotation_xyzw"]).as_matrix().T.tolist(),
                    "radius":shape["radius_cm"]*.01,"length":shape["cylinder_length_cm"]*.01,
                    "dimensions":(np.array(shape["half_extent_cm"])*.02).tolist()})
        self.marker=self.debug/"training.active.json"
        write_json(self.marker,{"pid":os.getpid(),"kind":"physical_recovery_v1"})

    def publish(self,qpos,iteration,checkpoint,metrics=None):
        positions=[];basis=[];root_positions=[];root_axes=[]
        for pose in np.asarray(qpos).reshape(-1,self.model.nq):
            self.data.qpos[:]=pose
            # Kinematics only: this never resimulates or changes the recorded rollout.
            mujoco.mj_kinematics(self.model,self.data)
            points=self.data.site_xpos[self.sites]@WORLD_TO_VIEW.T
            axes=self.data.site_xmat[self.sites].reshape(-1,3,3).transpose(0,2,1)@WORLD_TO_VIEW.T
            for parent,offset,rotation in self.toes:
                points=np.concatenate([points,(points[parent]+offset@axes[parent])[None]],axis=0)
                axes=np.concatenate([axes,(rotation.T@axes[parent])[None]],axis=0)
            positions.append(points)
            basis.append(axes);root_positions.append(positions[-1][0]);root_axes.append(axes[0])
        count=len(positions)
        payload={"schema_version":2,"computed_at":datetime.now(timezone.utc).isoformat(),
            "run_id":self.directory.name,"step":int(iteration),"fps":30,"joint_names":self.names,"bones":self.bones,
            "rows":[{"row":0,"clip_id":0,"clip_name":"Physical get-up · actual training world 0",
                "clip_path":str(checkpoint),"start":0,"effective_k":count-1,"virtual":False,"noisy":False,
                "has_sword":False,"locomotion_category":"physical_getup","gaze_normalized":[0,0]}],
            "positions":[np.asarray(positions).tolist()],"basis":[np.asarray(basis).tolist()],
            "controller_root_pos":[np.asarray(root_positions).tolist()],"controller_root_rot":[np.asarray(root_axes).tolist()],
            "frozen_root_pos":[np.asarray(root_positions).tolist()],"frozen_root_rot":[np.asarray(root_axes).tolist()],
            "source_frame":[list(range(count))],"source_clip_name":[["actual training world 0"]*count],
            "metadata":{"body_mode":"full","checkpoint_kind":"physical_recovery_v1","checkpoint":str(checkpoint),
                "has_sword":False,"capture_source":"actual_training_physics","physics_hz":240,"policy_hz":30,
                "physical_colliders":self.colliders,"display_geometry":"Exact exported PHAT collider surfaces",
                "training_progress":metrics or {},"step_unit":"PPO iteration"},
            "message":"Actual physical training rollout, including exploration. No reconstructed target animation."}
        write_json(self.debug/"last_batch_rollout.json",payload)
        write_json(self.directory/"status.json",{"state":"running","iteration":int(iteration),
            "updated_at":datetime.now(timezone.utc).isoformat(),"checkpoint":str(checkpoint),"metrics":metrics or {}})

    def close(self):
        self.marker.unlink(missing_ok=True)

