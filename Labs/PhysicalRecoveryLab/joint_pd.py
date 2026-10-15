"""Torque-bounded relative joint PD; no root actuation or pose overwrite."""
import json
from pathlib import Path
import numpy as np
import torch
import warp as wp
from mujoco_warp._src import math as mm
from phat_constraints import coordinates

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"

@wp.kernel
def audit_capacity(nefc:wp.array(dtype=int),nacon:wp.array(dtype=int),maximum:wp.array(dtype=int),
                   njmax:int,naconmax:int,overflow:wp.array(dtype=int)):
    world=wp.tid()
    wp.atomic_max(maximum,0,nefc[world])
    if nefc[world]>njmax:wp.atomic_max(overflow,0,1)
    if world==0:
        wp.atomic_max(maximum,1,nacon[0])
        if nacon[0]>naconmax:wp.atomic_max(overflow,0,1)

@wp.kernel
def apply_pd(qpos:wp.array2d(dtype=float),qvel:wp.array2d(dtype=float),
             qadr:wp.array(dtype=int),dadr:wp.array(dtype=int),joints:wp.array(dtype=int),
             indices:wp.array(dtype=wp.vec3i),limits:wp.array(dtype=wp.vec3),refs:wp.array(dtype=wp.vec3),
             gains:wp.array(dtype=wp.vec3),actions:wp.array2d(dtype=float),
             force:wp.array2d(dtype=float),torques:wp.array2d(dtype=wp.vec3),native:bool,ctrl:wp.array2d(dtype=float),relative:bool):
    world,index=wp.tid(); joint=joints[index]; qa=qadr[joint]; da=dadr[joint]
    ids=indices[index]; angles=limits[index]; rest=refs[index]
    current=wp.quat(qpos[world,qa],qpos[world,qa+1],qpos[world,qa+2],qpos[world,qa+3])
    gain=gains[index]
    action_bound=float(1.0)
    if relative:
        rest=coordinates(current)
        action_bound=4.0
    target=wp.vec3(0.0)
    for k in range(3):
        if ids[k]>=0:
            scale=angles[k]
            if relative:scale=0.25*(gain[2]/wp.sqrt(3.0))/gain[0]
            if k>0: scale=wp.sin(scale*0.5)
            target[k]=rest[k]+wp.clamp(actions[world,ids[k]],-action_bound,action_bound)*scale
    target[0]=wp.clamp(target[0],-angles[0],angles[0])
    radius=float(0.0)
    for k in range(1,3):
        if ids[k]>=0:
            value=target[k]/wp.sin(angles[k]*0.5); radius+=value*value
    radius=wp.max(1.0,wp.sqrt(radius))
    sy=target[1]/radius; sz=target[2]/radius
    swing=wp.quat(wp.sqrt(wp.max(0.0,1.0-sy*sy-sz*sz)),0.0,sy,sz)
    twist=wp.quat(wp.cos(target[0]*0.5),wp.sin(target[0]*0.5),0.0,0.0)
    desired=mm.mul_quat(swing,twist)
    error=mm.quat_to_vel(mm.mul_quat(mm.quat_inv(current),desired))
    velocity=wp.vec3(qvel[world,da],qvel[world,da+1],qvel[world,da+2])
    torque=gain[0]*error-gain[1]*velocity
    torque*=wp.min(1.0,gain[2]/wp.max(wp.length(torque),1.0e-8))
    for k in range(3):
        if native:
            ctrl[world,index*3+k]=gain[0]*error[k]
            bound=gain[2]/wp.sqrt(3.0)
            torque[k]=wp.clamp(gain[0]*error[k]-gain[1]*velocity[k],-bound,bound)
            force[world,da+k]=0.0
        else:force[world,da+k]=torque[k]
    torques[world,index]=torque

@wp.kernel
def apply_body_damping(cvel:wp.array2d(dtype=wp.spatial_vector),xipos:wp.array2d(dtype=wp.vec3),
    subtree_com:wp.array2d(dtype=wp.vec3),rootid:wp.array(dtype=int),mass:wp.array2d(dtype=float),
    damping:wp.array(dtype=float),forces:wp.array2d(dtype=wp.spatial_vector),
    cancel_gyroscopic:bool,inertia:wp.array2d(dtype=wp.vec3),ximat:wp.array2d(dtype=wp.mat33)):
    world,body=wp.tid()
    velocity=cvel[world,body]
    angular=wp.spatial_top(velocity)
    offset=xipos[world,body]-subtree_com[world,rootid[body]]
    linear=wp.spatial_bottom(velocity)+wp.cross(angular,offset)
    force=-mass[world%mass.shape[0],body]*damping[body]*linear
    torque=wp.vec3(0.)
    if cancel_gyroscopic:
        # Jolt's default mApplyGyroscopicForce=false omits w x (I w).
        # MuJoCo includes it in bias forces; adding the same term cancels
        # exactly that engine term. This is independent of policy actions.
        basis=ximat[world,body]
        momentum=basis*wp.cw_mul(inertia[world%inertia.shape[0],body],wp.transpose(basis)*angular)
        torque=wp.cross(angular,momentum)
    # xfrc is force, torque, unlike MuJoCo's cvel order.
    forces[world,body]=wp.spatial_vector(force,torque)


def gains_for(name):
    # Coupled-chain inertia matters: individually stable limbs can still form
    # an unstable mode together. These 240 Hz gains pass the full-mass audit
    # and the recorded policy trajectory that broke the preceding controller.
    if name.startswith("thigh"): return (105,.75,180)
    if name.startswith("calf"): return (90,.6,140)
    if name.startswith("foot"): return (54,.36,100)
    if name.startswith("spine"): return (45,.36,90)
    if name.startswith("upperarm"): return (48,.3,75)
    if name.startswith("lowerarm"): return (30,.21,55)
    if name.startswith("clavicle"): return (30,.21,55)
    if name.startswith("hand"): return (9,.06,15)
    return (10.5,.09,18) # neck and head


def motor_gains_for(name):
    # Explicit experimental contract: restore stiffness and stronger damping
    # using MuJoCo's supported bounded native actuators/implicit derivative.
    kp,kd,cap=gains_for(name)
    return (kp/.3,kd/.03,cap)


class JointPD:
    def __init__(self,sim,metadata,relative_targets=False):
        self.sim=sim; self.metadata=metadata; self.device=sim.device
        self.relative_targets=relative_targets
        if relative_targets and not sim.native_motors:raise ValueError('Relative trial uses native motors')
        self.action_bound=4. if relative_targets else 1.
        m=sim.mj_model; wm=sim.wp_model; wd=sim.wp_data
        indices=[]; refs=[]; limits=[]; joints=[]; gains=[]; names=[]
        count=0
        for j in metadata["joints"]:
            ids=[]
            for axis,mode in enumerate(j["modes"]):
                ids.append(count if mode!=2 else -1)
                if mode!=2:
                    names.append(j["body"]+":"+("twist","swing_y","swing_z")[axis]); count+=1
            indices.append(ids); limits.append(j["limits_rad"])
            q=np.array(j["reference_wxyz"]); w,x,y,z=q; n=np.hypot(w,x)
            refs.append([(2*np.arctan2(x,w)+np.pi)%(2*np.pi)-np.pi,(w*y-x*z)/n,(x*y+w*z)/n])
            joints.append(m.joint(j["name"]).id)
            gains.append((motor_gains_for if sim.native_motors else gains_for)(j["body"]))
        self.num_actions=count; self.action_names=names
        self.actions=torch.zeros((sim.num_envs,count),device=self.device)
        self.actions_wp=wp.from_torch(self.actions)
        self.joints=wp.array(joints,dtype=int,device=self.device)
        self.indices=wp.array(indices,dtype=wp.vec3i,device=self.device)
        self.limits=wp.array(limits,dtype=wp.vec3,device=self.device)
        self.refs=wp.array(refs,dtype=wp.vec3,device=self.device)
        self.gains=wp.array(gains,dtype=wp.vec3,device=self.device)
        self.torques=wp.zeros((sim.num_envs,len(joints)),dtype=wp.vec3,device=self.device)
        self.capacity_max=wp.zeros(2,dtype=int,device=self.device)
        self.capacity_overflow=wp.zeros(1,dtype=int,device=self.device)
        rig=json.loads((OUT/"rig.json").read_text())
        damping=np.zeros(m.nbody,dtype=np.float32)
        for b in rig["bodies"]:
            if b["angular_damping"]!=0: raise ValueError("Angular body damping needs its own calibrated mapping")
            damping[m.body(b["name"]).id]=b["linear_damping"]
        self.damping=wp.array(damping,dtype=float,device=self.device)
        self.contract={"action_names":names,"action_count":count,"joint_gains_kp_kd_max_nm":gains,
            "control_hz":30,"physics_hz":240,"floating_root_actuation":False,
            "target":"Reference-relative twist angle and swing half-quaternion coordinates, projected into authored limit surface",
            "torque":"Body-local relative quaternion error PD, per-joint vector-norm cap in Nm",
            "body_linear_damping":"Force = -mass * original PHAT damping * COM velocity; no angular damping in source"}
        if sim.native_motors:
            self.contract['torque']='Native implicit-damped PD; independent axis caps = original vector cap / sqrt(3)'
        if relative_targets:
            self.contract['relative_targets']=True
            self.contract['action_bound']=self.action_bound
            self.contract['target']='Current PHAT coordinates + action * (0.25 * axis torque cap / Kp) radians; sine-half-angle swing increment; projected into authored limits each physics step'
        wm.callback.control=self.apply
        sim.create_graph()

    def apply(self,m,d):
        wp.launch(audit_capacity,dim=d.nworld,inputs=[d.nefc,d.nacon,self.capacity_max,d.njmax,d.naconmax,self.capacity_overflow])
        wp.launch(apply_pd,dim=(d.nworld,len(self.joints)),inputs=[d.qpos,d.qvel,m.jnt_qposadr,m.jnt_dofadr,
            self.joints,self.indices,self.limits,self.refs,self.gains,self.actions_wp,d.qfrc_applied,self.torques,
            self.sim.native_motors,d.ctrl,self.relative_targets])
        wp.launch(apply_body_damping,dim=(d.nworld,m.nbody),inputs=[d.cvel,d.xipos,d.subtree_com,m.body_rootid,
            m.body_mass,self.damping,d.xfrc_applied,not self.sim.gyroscopic_forces,m.body_inertia,d.ximat])
