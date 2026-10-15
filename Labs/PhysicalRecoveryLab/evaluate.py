"""Deterministic physical rollout; measures recovery and stores actual poses."""
import argparse
import json
import time
import numpy as np
import torch
import warp as wp
from recovery_env import RecoveryEnv,OUT,inverse_rotate
from policy import load_policy

def main():
    p=argparse.ArgumentParser();p.add_argument("--checkpoint",required=True);p.add_argument("--worlds",type=int,default=16)
    p.add_argument("--seconds",type=float,default=10);p.add_argument("--initial",choices=("fixed","bank"),default="fixed")
    p.add_argument("--output",default="evaluation");p.add_argument('--standing-start',action='store_true')
    p.add_argument('--pose-bank');p.add_argument('--all-bank-poses',action='store_true');a=p.parse_args()
    torch.set_num_threads(1);wp.init();torch.manual_seed(112358)
    config=torch.load(a.checkpoint,map_location='cpu',weights_only=False)['infos']['physical_recovery']
    env=RecoveryEnv(a.worlds,episode_seconds=a.seconds,initial=a.initial,auto_reset=False,
        integrator=config.get('integrator','implicitfast'),native_motors=config.get('native_motors',False),relative_targets=config.get('relative_targets',False),
        standing_fraction=1. if a.standing_start else 0.,ccd_iterations=config.get('ccd_iterations',50),gyroscopic_forces=config.get('gyroscopic_forces',True),
        pose_bank=a.pose_bank or config.get('pose_bank','rig-passive.npz'),raw_action_cost=config.get('previous_action_observation')=='requested',
        posture_profile=config.get('posture_reward',{}).get('profile','legacy'))
    if a.all_bank_poses:
        if a.initial!='bank' or a.standing_start or len(env.bank)!=a.worlds:
            raise ValueError('All-bank evaluation requires --initial bank and one world per admitted pose')
        env.qpos.copy_(env.bank);env.qvel.zero_()
    policy,state=load_policy(a.checkpoint,env);trajectory=[];heights=[];error=[];standing=[];start=time.perf_counter()
    support_history=[];supported_standing=[];supported_count=np.zeros(a.worlds,dtype=int)
    floor=env.sim.mj_model.geom('ground').id
    feet={env.sim.mj_model.geom(n+'_shape0').id for n in ('foot_l','foot_r')}
    weight=env.metadata['mass_kg']*9.81
    with torch.inference_mode():
        for _ in range(round(a.seconds*30)):
            env.step(policy(env.get_observations()))
            trajectory.append(env.qpos.cpu().numpy().copy())
            heights.append(env.qpos[:,2].cpu().numpy().copy())
            error.append((inverse_rotate(env.qpos[:,3:7],env.gravity)-env.reference_gravity).square().sum(-1).cpu().numpy())
            standing.append(env.standing_steps.cpu().numpy().copy())
            # Evaluate actual solved contacts: height/orientation alone must not
            # count a jump or a pose supported by knees/hands as standing.
            data=env.sim.wp_data;n=int(data.nacon.numpy()[0])
            pairs=data.contact.geom.numpy()[:n];world=data.contact.worldid.numpy()[:n]
            rows=data.contact.efc_address.numpy()[:n,0];forces=data.efc.force.numpy()
            foot_force=np.zeros(a.worlds);ground_force=np.zeros(a.worlds)
            for pair,w,row in zip(pairs,world,rows):
                if row<0 or floor not in pair:continue
                normal=max(0,float(forces[w,row]));ground_force[w]+=normal
                if any(int(g) in feet for g in pair):foot_force[w]+=normal
            good=(standing[-1]>0)&(foot_force>.5*weight)&(foot_force>=.9*ground_force)
            good&=env.qvel[:,3:6].norm(dim=-1).cpu().numpy()<.5
            supported_count=np.where(good,supported_count+1,0)
            supported_standing.append(supported_count.copy());support_history.append(foot_force.copy())
    q=np.array(trajectory);np.savez_compressed(OUT/(a.output+".npz"),qpos=q,heights=heights,gravity_error=error,
        standing_steps=standing,foot_support_newtons=support_history,supported_standing_steps=supported_standing)
    report={"checkpoint":a.checkpoint,"iteration":int(state["iter"]),"seconds":a.seconds,"worlds":a.worlds,
        "initial":"standing" if a.standing_start else a.initial,"worlds_stood_for_1_second":int((np.max(supported_standing,axis=0)>=30).sum()),
        "pose_bank":env.cfg['pose_bank'],"pose_bank_sha256":env.cfg['pose_bank_sha256'],"all_bank_poses":a.all_bank_poses,
        "worlds_met_pose_only_1_second":int((np.max(standing,axis=0)>=30).sum()),
        "support_requirement":"1s upright/high pelvis/slow root, feet >50% bodyweight and >=90% total ground support, root angular speed <.5rad/s",
        "pelvis_peak_m":np.max(heights,axis=0).tolist(),"pelvis_final_m":np.array(heights)[-1].tolist(),
        "final_gravity_error":np.array(error)[-1].tolist(),"finite":bool(np.isfinite(q).all()),"wall_seconds":time.perf_counter()-start}
    (OUT/(a.output+".json")).write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2))

if __name__=="__main__":main()
