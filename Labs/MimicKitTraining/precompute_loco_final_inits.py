"""Audit/bake locomotion final-phase initialization candidates offline."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import torch,yaml
from scipy.spatial.transform import Rotation as R
from prepare_perturbed_com2 import MJCFCharModel,MotionLib,mp_util,JointType,world_velocities,q
from ground_random_phat_poses import floor_heights

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion/final-phase-inits'
SRC=ROOT/'Saved/MimicKitLocomotion/final-phase-source'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);mp_util.init(0,1,'cpu',20261023)
    cfg=yaml.safe_load((SRC/'prepared/env_config.yaml').read_text().replace('/workspace/mimickit_trial',SRC.as_posix()))
    motions=OUT/'motions.yaml'
    motions.write_text((SRC/'prepared/motions.yaml').read_text().replace('/workspace/mimickit_trial',SRC.as_posix()))
    model=MJCFCharModel('cpu');model.load(cfg['char_file']);lib=MotionLib(str(motions),model,'cpu')
    names=model.get_body_names()
    idle=next(i for i in range(lib.get_num_motions()) if 'Stand_Idle' in lib.get_motion_file(i))
    _,idleq,*_=lib.calc_motion_frame(torch.tensor([idle]),torch.tensor([0.]))
    path=ROOT/'Saved/MimicKitEquipment/limp-inits/corpus.npz'
    with np.load(path,allow_pickle=False) as z:
        assert z['body_names'].tolist()==names
        dof=z['dof'].copy()
    rng=np.random.default_rng(2026102307)
    # Sixteen independent upright-cone rotations per original limp pose.
    count=len(dof)*16;indices=np.repeat(np.arange(len(dof)),16)
    cosine=rng.uniform(np.cos(np.pi/4),1,count);tilt=np.arccos(cosine)
    axis_angle=rng.uniform(-np.pi,np.pi,count);yaw=rng.uniform(-np.pi,np.pi,count)
    axis=np.stack((np.cos(axis_angle),np.sin(axis_angle),np.zeros(count)),1)
    quat=(R.from_rotvec(np.stack((np.zeros(count),np.zeros(count),yaw),1))*R.from_rotvec(axis*tilt[:,None])*R.from_quat(idleq[0].numpy())).as_quat().astype(np.float32)
    joints=model.dof_to_rot(torch.tensor(dof[indices],dtype=torch.float32))
    pos,rot=model.forward_kinematics(torch.zeros(count,3),torch.tensor(quat),joints)
    bodies=[];tree=ET.parse(cfg['char_file'])
    for name in names:
        b=tree.find(f".//body[@name='{name}']")
        bodies.append(dict(name=name,shapes=[dict(type=g.get('type','sphere'),size=list(map(float,g.get('size').split())),pos=list(map(float,g.get('pos','0 0 0').split())),quat=np.roll(list(map(float,g.get('quat','1 0 0 0').split())),-1).tolist()) for g in b.findall('geom')]))
    poses=torch.cat((pos,rot),-1).numpy();minimum=-floor_heights(poses,bodies).min(1)
    feasible=minimum<=.6
    report=dict(candidates=count,limp_poses=len(dof),feasible=int(feasible.sum()),infeasible=int((~feasible).sum()),
        poses_with_no_feasible_candidate=int((~feasible.reshape(-1,16).any(1)).sum()),
        minimum_height_range_m=[float(minimum.min()),float(minimum.max())],
        minimum_height_percentiles_m=np.percentile(minimum,[0,25,50,75,100]).tolist(),max_tilt_degrees=float(np.rad2deg(tilt).max()),
        source_limp_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_model_sha256=hashlib.sha256(Path(cfg['char_file']).read_bytes()).hexdigest(),
        seed=2026102307,meaning='Upright relative to idle frame0 pelvis; exact collider floor support. No invalid pose silently adjusted or discarded.')
    np.savez_compressed(OUT/'pose-candidates.npz',dof=dof[indices],root_quaternion_xyzw=quat,minimum_height=minimum,limp_index=indices,feasible=feasible,tilt_radians=tilt)
    # Bake all eligible authored joint/root states, excluding idle clips.
    pool=torch.cat([torch.arange(int(lib._motion_start_idx[i]),int(lib._motion_start_idx[i]+lib._motion_num_frames[i])) for i in range(lib.get_num_motions()) if 'Stand_Idle' not in lib.get_motion_file(i)])
    np.savez_compressed(OUT/'locomotion-frames.npz',frame=pool.numpy(),dof=lib.joint_rot_to_dof(lib._frame_joint_rot[pool]).numpy(),dof_velocity=lib._frame_dof_vel[pool].numpy(),root_velocity=lib._frame_root_vel[pool].numpy(),root_angular_velocity=lib._frame_root_ang_vel[pool].numpy())
    com=torch.tensor([list(map(float,tree.find(f".//body[@name='{name}']/inertial").get('pos','0 0 0').split())) for name in names])
    lift=rng.uniform(0,.6,count).astype(np.float32)
    root=np.zeros((count,3),np.float32);root[:,2]=minimum+lift+2e-6
    a=rng.integers(len(pool),size=count);b=rng.integers(len(pool),size=count)
    omega=lib._frame_root_ang_vel[pool[a]]
    rootv=lib._frame_root_vel[pool[a]]+torch.cross(omega,q.quat_rotate(torch.tensor(quat),com[0].expand(count,3)),dim=-1)
    plus=dict(root_pos=root,root_rot=quat,dof=dof[indices],root_vel=rootv.numpy(),root_ang=omega.numpy(),dof_vel=lib._frame_dof_vel[pool[b]].numpy(),pose_index=indices,root_frame=pool[a].numpy(),joint_frame=pool[b].numpy(),height_lift=lift,minimum_height=minimum.astype(np.float32))
    assert np.all(root[:,2]-minimum>=0)
    # Pushed rows: bake target frame, arbitrary joint pose/velocity and yaw while
    # retaining the authored trunk COM velocity. No per-reset IK or FK searches.
    mapping=torch.zeros(model.get_dof_size(),(len(names)-1)*3)
    for j in range(1,len(names)):
        joint=model.get_joint(j)
        if joint.joint_type==JointType.SPHERICAL:mapping[joint.dof_idx:joint.dof_idx+3,(j-1)*3:j*3]=torch.eye(3)
        elif joint.joint_type==JointType.HINGE:mapping[joint.dof_idx,(j-1)*3:j*3]=joint.axis
    parents=[int(p) for p in model._parent_indices]
    trunk=[names.index(n) for n in ['pelvis','spine_01','spine_02','spine_03','neck_01','head'] if n in names]
    table=json.loads((SRC/'prepared/com2_targets.json').read_text()) if (SRC/'prepared/com2_targets.json').exists() else json.loads(Path(cfg['perturbed_motion']['com2_targets']).read_text())
    trunk=[names.index(n) for n in table['bodies']];mass=torch.tensor(table['masses_kg']);mass/=mass.sum()
    pushed={k:[] for k in ['root_pos','root_rot','dof','root_vel','root_ang','dof_vel','motion_time','joint_frame','yaw_degrees']}
    per_motion=16384;bank_size=512;max_com_error=0.;rejected=0
    pooldof=lib.joint_rot_to_dof(lib._frame_joint_rot[pool])
    for motion in range(lib.get_num_motions()):
        times=torch.tensor(rng.uniform(0,float(lib.get_motion_length(motion)),per_motion),dtype=torch.float32)
        rp,rq,rv,rw,jr,jv=lib.calc_motion_frame(torch.full((per_motion,),motion),times)
        p0,q0=model.forward_kinematics(rp,rq,jr)
        v0,w0=world_velocities(p0,q0,rv,rw,(jv@mapping).view(per_motion,-1,3),parents)
        cv0=v0+torch.cross(w0,q.quat_rotate(q0,com.expand(per_motion,-1,-1)),dim=-1)
        target=(cv0[:,trunk]*mass[None,:,None]).sum(1)
        angles=torch.tensor(rng.uniform(-np.pi,np.pi,per_motion),dtype=torch.float32)
        yawq=torch.zeros(per_motion,4);yawq[:,2]=torch.sin(angles/2);yawq[:,3]=torch.cos(angles/2)
        rq=q.quat_mul(yawq,rq);rw=q.quat_rotate(yawq,rw)
        joint_index=torch.tensor(rng.integers(len(pool),size=per_motion))
        jd=pooldof[joint_index];jv=lib._frame_dof_vel[pool[joint_index]]
        pp,qq=model.forward_kinematics(rp,rq,model.dof_to_rot(jd))
        low=floor_heights(torch.cat((pp,qq),-1).numpy(),bodies).min(1)
        valid=torch.tensor(np.flatnonzero(low>=0)[:bank_size]);rejected+=int((low<0).sum())
        assert len(valid)==bank_size, (motion,len(valid))
        rp,rq,rv,rw,target,angles,times,joint_index,jd,jv,pp,qq=[x[valid] for x in (rp,rq,rv,rw,target,angles,times,joint_index,jd,jv,pp,qq)]
        v,w=world_velocities(pp,qq,rv,rw,(jv@mapping).view(bank_size,-1,3),parents)
        cv=v+torch.cross(w,q.quat_rotate(qq,com.expand(bank_size,-1,-1)),dim=-1)
        actual=(cv[:,trunk]*mass[None,:,None]).sum(1)
        # Keep all three COM components; the old yaw path preserved flat COM.
        shift=target-actual;cv+=shift[:,None];rvcom=cv[:,0]
        max_com_error=max(max_com_error,float(((cv[:,trunk]*mass[None,:,None]).sum(1)-target).abs().max()))
        for k,val in dict(root_pos=rp,root_rot=rq,dof=jd,root_vel=rvcom,root_ang=rw,dof_vel=jv,motion_time=times,joint_frame=pool[joint_index],yaw_degrees=angles*180/np.pi).items():pushed[k].append(val.numpy())
    np.savez_compressed(OUT/'initializations.npz',**{'plus_'+k:v for k,v in plus.items()},**{'push_'+k:np.stack(v) for k,v in pushed.items()},body_names=np.array(names))
    report.update(height_rule='minimum non-clipping pelvis height + uniform[0,0.6] metres; all plus candidates retained',plus_count=count,push_count=bank_size*lib.get_num_motions(),push_per_motion=bank_size,push_rejected_clipping_limb_samples=rejected,max_push_com_velocity_error=max_com_error,
        initializations_sha256=hashlib.sha256((OUT/'initializations.npz').read_bytes()).hexdigest())
    (OUT/'feasibility.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
