"""Sample legal joint poses, let them physically fall, retain quiet floor poses.

No runtime support, pose correction, speed clamp or overwritten historical bank.
"""
import argparse
import hashlib
import json
import time
import numpy as np
import mujoco
import torch
import warp as wp
from scipy.spatial.transform import Rotation as R
from recovery_env import RecoveryEnv,OUT
from test_phat_constraints import reference


def main():
    p=argparse.ArgumentParser();p.add_argument('--worlds',type=int,default=128);p.add_argument('--seconds',type=int,default=32)
    p.add_argument('--output',default='fallen-varied-01');args=p.parse_args()
    if '/' in args.output or '\\' in args.output:raise ValueError('Expected a simple output name')
    output=OUT/(args.output+'.npz')
    if output.exists():raise ValueError('Bank already exists; use a new name to preserve checkpoints')
    torch.set_num_threads(1);torch.manual_seed(734);wp.init();rng=np.random.default_rng(734)
    env=RecoveryEnv(args.worlds,auto_reset=False,integrator='implicitfast',native_motors=True,relative_targets=True,
        ccd_iterations=100,gyroscopic_forces=False)
    model=env.sim.mj_model;data=mujoco.MjData(model)
    def sample(count):
        result=np.tile(env.reference.cpu().numpy(),(count,1))
        for j in env.metadata['joints']:
            qa=int(model.joint(j['name']).qposadr[0]);limits=np.array(j['limits_rad']);active=np.array(j['modes'])!=2
            target=np.tile(reference(np.array(j['reference_wxyz'])),(count,1))
            target+=rng.uniform(-.6,.6,(count,3))*np.r_[limits[0],np.sin(limits[1:]/2)]
            target[:,~active]=0;target[:,0]=np.clip(target[:,0],-limits[0],limits[0])
            normalized=np.zeros((count,2))
            for axis in (1,2):
                if active[axis]:normalized[:,axis-1]=target[:,axis]/np.sin(limits[axis]/2)
            target[:,1:]/=np.maximum(1,np.linalg.norm(normalized,axis=1))[:,None]
            swing=R.from_quat(np.c_[np.zeros(count),target[:,1:],np.sqrt(np.maximum(0,1-(target[:,1:]**2).sum(1)))])
            twist=R.from_rotvec(np.c_[target[:,0],np.zeros((count,2))])
            result[:,qa:qa+4]=(swing*twist).as_quat()[:,[3,0,1,2]]
        result[:,3:7]=R.random(count,random_state=rng).as_quat()[:,[3,0,1,2]]
        return result
    starting=sample(args.worlds);rejections=0
    for world in range(args.worlds):
        for attempt in range(100):
            data.qpos[:]=starting[world];data.qpos[2]+=3;mujoco.mj_forward(model,data)
            penetration=min((c.dist for c in data.contact if all(g>0 for g in c.geom)),default=0.)
            if penetration>=-.005:break
            rejections+=1;starting[world]=sample(1)[0]
        else:raise RuntimeError('Unable to sample a pose without deep self-intersection; no pose assistance applied')
        data.qpos[:]=starting[world];mujoco.mj_kinematics(model,data);bottom=float('inf')
        for geom in range(1,model.ngeom):
            kind=model.geom_type[geom];size=model.geom_size[geom];basis=data.geom_xmat[geom].reshape(3,3)
            if kind==mujoco.mjtGeom.mjGEOM_BOX:extent=abs(basis[2])@size
            elif kind==mujoco.mjtGeom.mjGEOM_CAPSULE:extent=size[0]+abs(basis[2,2])*size[1]
            elif kind==mujoco.mjtGeom.mjGEOM_SPHERE:extent=size[0]
            else:raise ValueError('Unsupported bank geometry')
            bottom=min(bottom,data.geom_xpos[geom,2]-extent)
        starting[world,2]+=.15-bottom
    env.qpos.copy_(torch.tensor(starting,device='cuda'));env.qvel.zero_();env.controller.actions.zero_()
    quiet=torch.zeros(args.worlds,dtype=torch.int32,device='cuda');accepted=torch.zeros(args.worlds,dtype=torch.bool,device='cuda')
    poses=torch.zeros_like(env.qpos);speeds=torch.zeros_like(env.qvel);at_tick=torch.zeros_like(quiet)
    d=env.sim.wp_data;cv=wp.to_torch(d.cvel);positions=wp.to_torch(d.xipos);com=wp.to_torch(d.subtree_com)
    roots=torch.tensor(model.body_rootid,dtype=torch.long,device='cuda');peak=0.;start=time.perf_counter()
    for tick in range(args.seconds*30):
        wp.capture_launch(env.policy_step_graph)
        if env.capacity_overflow.item():raise RuntimeError('Capacity exceeded during bank generation')
        angular=cv[:,:,:3];linear=cv[:,:,3:]+torch.cross(angular,positions-com[:,roots],dim=-1)
        general=env.qvel.abs().amax(1);body_speed=torch.maximum(angular.norm(dim=-1).amax(1),linear.norm(dim=-1).amax(1))
        maximum=float(general.max());peak=max(peak,maximum)
        if not torch.isfinite(env.qpos).all() or not torch.isfinite(env.qvel).all() or maximum>500:
            np.savez_compressed(OUT/(args.output+'-failure.npz'),qpos=env.qpos.cpu().numpy(),qvel=env.qvel.cpu().numpy())
            raise RuntimeError(f'Nonfinite/runaway candidate bank at tick{tick}; no bank admitted')
        low=(general<.05)&(body_speed<.05)&(env.qpos[:,2]<.8*env.root_height)
        quiet=torch.where(low,quiet+1,0);take=(quiet>=30)&(~accepted)
        poses.copy_(torch.where(take[:,None],env.qpos,poses));speeds.copy_(torch.where(take[:,None],env.qvel,speeds))
        at_tick.copy_(torch.where(take,tick+1,at_tick));accepted|=take
        if (tick+1)%240==0:print(f'{(tick+1)/30:.0f}s: {int(accepted.sum())}/{args.worlds} quiet floor poses',flush=True)
        if accepted.all():break
    mask=accepted.cpu().numpy();count=int(mask.sum())
    if count<8:raise RuntimeError(f'Only {count} quiet floor poses; need at least8 before admitting this bank')
    q=poses.cpu().numpy()[mask];v=speeds.cpu().numpy()[mask]
    np.savez_compressed(output,qpos=q,qvel=v,candidate_indices=np.flatnonzero(mask),settled_tick=at_tick.cpu().numpy()[mask])
    report={'passed':True,'rig_sha256':env.metadata['rig_sha256'],'xml_sha256':env.metadata['xml_sha256'],
        'bank_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'seed':734,'candidates':args.worlds,'accepted':count,
        'initial_self_intersection_rejections':rejections,'maximum_initial_self_penetration_m':.005,
        'requirement':'1s continuously below .05 generalized/body angular and linear speeds; pelvis below80% reference height',
        'source':'Random PHAT-legal joint configurations and uniform root rotations, lowest collider .15m above ground, actual gravity/contacts; zero current-relative actions',
        'environment':env.cfg,'maximum_seconds':args.seconds,'wall_seconds':time.perf_counter()-start,
        'peak_generalized_velocity':peak,'final_retained_max_abs_velocity':float(abs(v).max())}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
