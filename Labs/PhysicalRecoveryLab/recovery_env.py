"""Contained get-up VecEnv using mjlab simulation, Warp PD and RSL-RL PPO.

Observations/actions remain on the GPU. No pose assistance or gravity cancellation.
The reward terms follow mjlab_playground's get-up task (uprightness, torso/waist
height, upright-gated reference posture), adapted to the mannequin's bone axes.
"""
from pathlib import Path
import json
import hashlib
import numpy as np
import torch
from tensordict import TensorDict
import warp as wp
import mujoco
import mujoco_warp as mjw
from rsl_rl.env import VecEnv
from rig_dynamics import build
from joint_pd import JointPD
from posture_reward import PostureReward

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

def inverse_rotate(q,v):
    xyz=-q[...,1:]
    t=2*torch.cross(xyz,v,dim=-1)
    return v+q[...,:1]*t+torch.cross(xyz,t,dim=-1)

class RecoveryEnv(VecEnv):
    def __init__(self,num_envs=256,episode_seconds=8,initial="fixed",cube_count=0,auto_reset=True,jacobian="auto",integrator="euler",native_motors=False,relative_targets=False,solver="newton",standing_fraction=0.,action_rate_sum=False,contact_capacity=256,constraint_capacity=768,ccd_iterations=50,gyroscopic_forces=True,reward_dt_scale=False,pose_bank="rig-passive.npz",raw_action_cost=False,posture_profile='legacy'):
        if not 0<=standing_fraction<=1:raise ValueError('Standing fraction must be in [0,1]')
        self.standing_fraction=standing_fraction
        self.action_rate_sum=action_rate_sum
        self.raw_action_cost=raw_action_cost
        self.reward_scale=1/30 if reward_dt_scale else 1.
        self.num_envs=num_envs; self.device="cuda:0"
        self.sim,self.metadata=build(num_envs,cube_count=cube_count,jacobian=jacobian,integrator=integrator,native_motors=native_motors,solver=solver,
            contact_capacity=contact_capacity,constraint_capacity=constraint_capacity,ccd_iterations=ccd_iterations,gyroscopic_forces=gyroscopic_forces)
        self.auto_reset=auto_reset
        self.controller=JointPD(self.sim,self.metadata,relative_targets=relative_targets)
        self.capacity_overflow=wp.to_torch(self.controller.capacity_overflow)
        self.num_actions=self.controller.num_actions
        self.max_episode_length=round(episode_seconds*30)
        self.episode_length_buf=torch.zeros(num_envs,device=self.device,dtype=torch.long)
        self.common_step_counter=0
        self.qpos=wp.to_torch(self.sim.wp_data.qpos)[:,:self.metadata["nq"]]
        self.qvel=wp.to_torch(self.sim.wp_data.qvel)[:,:self.metadata["nv"]]
        self.reference=torch.tensor(self.metadata["reference_qpos"],device=self.device)
        self.standing_start=self.reference.clone()
        self.started_standing=torch.zeros(num_envs,device=self.device,dtype=torch.bool)
        if standing_fraction:
            model=self.sim.mj_model;data=mujoco.MjData(model)
            data.qpos[:self.metadata['nq']]=self.metadata['reference_qpos'];mujoco.mj_kinematics(model,data)
            bottoms=[]
            for name in ('foot_l_shape0','foot_r_shape0'):
                g=model.geom(name).id
                if model.geom_type[g]!=mujoco.mjtGeom.mjGEOM_BOX:
                    raise ValueError('Revalidate standing initialization for changed foot geometry')
                bottoms.append(data.geom_xpos[g,2]-np.abs(data.geom_xmat[g].reshape(3,3)[2])@model.geom_size[g])
            self.standing_start[2]+=.001-min(bottoms) # 1mm initial clearance, no runtime support.
        self.reference_joints=self.reference[7:].reshape(1,-1,4)
        self.posture_reward=PostureReward(self.metadata,self.device,posture_profile)
        self.gravity=torch.tensor([0.,0.,-1.],device=self.device).expand(num_envs,-1)
        self.reference_gravity=inverse_rotate(self.reference[3:7].expand(num_envs,-1),self.gravity)
        self.previous_actions=torch.zeros_like(self.controller.actions)
        self.previous_cost_actions=torch.zeros_like(self.previous_actions)
        self.standing_steps=torch.zeros(num_envs,device=self.device,dtype=torch.long)
        self.ever_stood=torch.zeros(num_envs,device=self.device,dtype=torch.bool)
        self.root_height=float(self.metadata["reference_qpos"][2])
        self.site_positions=wp.to_torch(self.sim.wp_data.site_xpos)
        self.chest_site=self.sim.mj_model.site("spine_05_bone").id
        # Reference body site is derived from the exported PHAT, not a tuned robot height.
        rig=json.loads((OUT/"rig.json").read_text())
        self.chest_height=next(b["reference"]["position_cm"][2]*.01 for b in rig["bodies"] if b["name"]=="spine_05")
        if Path(pose_bank).name!=pose_bank or Path(pose_bank).suffix!='.npz':
            raise ValueError('Pose bank must be a .npz filename within Saved/Robotics')
        bank_path=OUT/pose_bank
        passive=np.load(bank_path)
        passive_report=json.loads(bank_path.with_suffix('.json').read_text())
        if passive_report["rig_sha256"]!=self.metadata["rig_sha256"]:
            raise RuntimeError("Fallen bank belongs to a different PHAT export")
        bank_hash=hashlib.sha256(bank_path.read_bytes()).hexdigest()
        if passive_report.get('bank_sha256',bank_hash)!=bank_hash:raise ValueError('Fallen bank changed after validation')
        good=np.max(np.abs(passive["qvel"]),axis=1)<.05
        if not good.any(): raise RuntimeError("No sufficiently settled fallen starting pose available")
        bank=passive["qpos"][good]
        if initial=="fixed": bank=bank[:1]
        self.bank=torch.tensor(bank,device=self.device)
        self.initial=initial
        self.history=torch.zeros((240,1,self.metadata["nq"]),device=self.device)
        self.history_count=0
        self.cfg={"kind":"physical_recovery_v1","initial":initial,"num_envs":num_envs,
            'pose_bank':pose_bank,'pose_bank_sha256':bank_hash,
            "episode_seconds":episode_seconds,"physics_hz":240,"policy_hz":30,
            "standing_practice_fraction":standing_fraction,
            'reward_action_rate_reduction':'sum' if action_rate_sum else 'mean',
            'reward_action_rate_source':'requested' if raw_action_cost else 'applied',
            'previous_action_observation':'requested' if raw_action_cost else 'applied',
            'reward_scale':self.reward_scale,
            'posture_reward':self.posture_reward.contract,
            'contact_capacity':contact_capacity,'constraint_capacity':constraint_capacity,
            'ccd_iterations':ccd_iterations,
            'gyroscopic_forces':gyroscopic_forces,
            "rig_sha256":self.metadata["rig_sha256"],"controller":self.controller.contract,
            "integrator":integrator,"solver":solver,"native_motors":native_motors,"relative_targets":relative_targets,
            "native_euler_damping":False if integrator=="euler" else None,
            "observation":"root-local gravity, root-local angular/linear velocity, ground-relative pelvis height, canonical joint WXYZ, joint velocity, previous action"}
        self.unwrapped=self
        self.reset_mask=torch.ones(num_envs,device=self.device,dtype=torch.bool)
        self.reset_mask_wp=wp.from_torch(self.reset_mask)
        self.cube_impulses=None
        if cube_count:
            from contact_metrics import accumulate_cube_impulses
            model=self.sim.mj_model
            slots=np.full(model.ngeom,-1,dtype=np.int32);rig_geom=np.zeros(model.ngeom,dtype=bool)
            for i in range(cube_count):slots[model.geom(f'impact_cube_{i}_shape').id]=i
            for body in rig['bodies']:
                for i in range(len(body['shapes'])):rig_geom[model.geom(body['name']+f'_shape{i}').id]=True
            self.cube_slots=wp.array(slots,dtype=int,device=self.device);self.rig_geoms=wp.array(rig_geom,dtype=bool,device=self.device)
            self.cube_impulses_wp=wp.zeros((num_envs,cube_count),dtype=float,device=self.device)
            self.cube_impulses=wp.to_torch(self.cube_impulses_wp)
        # One launch advances all eight physics substeps of a fixed 30 Hz policy tick.
        with wp.ScopedDevice("cuda:0"),wp.ScopedCapture() as capture:
            for _ in range(8):
                mjw.step(self.sim.wp_model,self.sim.wp_data)
                if cube_count:
                    d=self.sim.wp_data
                    wp.launch(accumulate_cube_impulses,dim=d.naconmax,inputs=[d.nacon,d.contact.geom,d.contact.worldid,
                        d.contact.efc_address,d.efc.force,self.cube_slots,self.rig_geoms,1/240,self.cube_impulses_wp])
        self.policy_step_graph=capture.graph
        self.reset(self.reset_mask)

    def reset(self,mask):
        self.reset_mask.copy_(mask)
        mjw.reset_data(self.sim.wp_model,self.sim.wp_data,reset=self.reset_mask_wp)
        choices=torch.randint(len(self.bank),(self.num_envs,),device=self.device)
        # Fixed-size masked writes avoid a CPU sync for extracting reset indices.
        starting=self.bank[choices]
        starts_standing=torch.zeros_like(mask)
        if self.standing_fraction:
            starts_standing=torch.rand(self.num_envs,device=self.device)<self.standing_fraction
            starting=torch.where(starts_standing[:,None],self.standing_start,starting)
        self.started_standing.copy_(torch.where(mask,starts_standing,self.started_standing))
        self.qpos.copy_(torch.where(mask[:,None],starting,self.qpos))
        self.qvel.masked_fill_(mask[:,None],0)
        self.episode_length_buf.masked_fill_(mask,0)
        self.controller.actions.masked_fill_(mask[:,None],0)
        self.previous_actions.masked_fill_(mask[:,None],0)
        self.previous_cost_actions.masked_fill_(mask[:,None],0)
        self.standing_steps.masked_fill_(mask,0)
        self.ever_stood.masked_fill_(mask,False)
        if self.cube_impulses is not None:self.cube_impulses.masked_fill_(mask[:,None],0.)

    def get_observations(self):
        root=self.qpos[:,3:7]
        gravity=inverse_rotate(root,self.gravity)
        local_velocity=inverse_rotate(root,self.qvel[:,:3])
        joints=self.qpos[:,7:].reshape(self.num_envs,-1,4)
        joints=joints*torch.where(joints[...,:1]<0,-1.,1.)
        obs=torch.cat([gravity,self.qvel[:,3:6]*.25,local_velocity*.5,self.qpos[:,2:3],
                       joints.flatten(1),self.qvel[:,6:]*.05,self.previous_actions],dim=1)
        return TensorDict({"actor":obs,"critic":obs},batch_size=[self.num_envs])

    def step(self,actions):
        self.controller.actions.copy_(actions.clamp(-self.controller.action_bound,self.controller.action_bound))
        wp.capture_launch(self.policy_step_graph)
        if self.capacity_overflow.item():
            raise RuntimeError(f'Physics capacity exceeded (constraint/contact peaks {self.controller.capacity_max.numpy().tolist()}); no further training allowed')
        self.previous_actions.copy_(actions if self.raw_action_cost else self.controller.actions)
        self.history[self.common_step_counter%len(self.history),0].copy_(self.qpos[0])
        self.history_count=min(self.history_count+1,len(self.history))
        self.episode_length_buf+=1; self.common_step_counter+=1
        gravity=inverse_rotate(self.qpos[:,3:7],self.gravity)
        gravity_error=(gravity-self.reference_gravity).square().sum(-1)
        upright=torch.exp(-2*gravity_error)
        waist=(self.qpos[:,2].clamp(0,self.root_height).exp()-1)/(np.exp(self.root_height)-1)
        chest=(self.site_positions[:,self.chest_site,2].clamp(0,self.chest_height).exp()-1)/(np.exp(self.chest_height)-1)
        joint_q=self.qpos[:,7:].reshape(self.num_envs,-1,4)
        posture=self.posture_reward(joint_q,gravity_error)
        cost_actions=actions if self.raw_action_cost else self.previous_actions
        squared_changes=(cost_actions-self.previous_cost_actions).square()
        self.previous_cost_actions.copy_(cost_actions)
        rate=squared_changes.sum(-1) if self.action_rate_sum else squared_changes.mean(-1)
        speed_cost=self.qvel[:,6:].square().clamp(max=400).mean(-1)
        reward=2*waist+chest+upright+.5*posture-.01*rate-.0001*speed_cost
        reward*=self.reward_scale
        standing=(gravity_error<.1)&(self.qpos[:,2]>.9*self.root_height)&(self.qvel[:,:3].norm(dim=-1)<.5)
        self.standing_steps.copy_(torch.where(standing,self.standing_steps+1,0))
        self.ever_stood|=self.standing_steps>=30
        timeouts=self.episode_length_buf>=self.max_episode_length
        floor=(~self.started_standing).float();floor_count=floor.sum().clamp(min=1)
        extras={"time_outs":timeouts,"log":{"Recovery/upright":(upright*floor).sum()/floor_count,
            'Policy/request_saturation':(actions.abs()>self.controller.action_bound).float().mean(),
            'Policy/request_abs':actions.abs().mean(),
            "Recovery/waist":(waist*floor).sum()/floor_count,
            "Recovery/posture":(posture*floor).sum()/floor_count,
            "Recovery/stood_1s":(self.ever_stood.float()*floor).sum()/floor_count,
            "Recovery/pelvis_z":(self.qpos[:,2]*floor).sum()/floor_count,
            "Practice/stood_1s":(self.ever_stood&self.started_standing).float().sum()/self.started_standing.sum().clamp(min=1)}}
        done=timeouts.clone()
        # The mask reset runs on GPU even when no world ended; capture/optimization follows measurement.
        if self.auto_reset:self.reset(timeouts)
        return self.get_observations(),reward,done,extras
