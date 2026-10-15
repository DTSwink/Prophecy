"""Substep telemetry with an unchanged target, isolating controller chatter."""
import json
import argparse
from scipy.spatial.transform import Rotation
import numpy as np
import torch
import warp as wp
from recovery_env import RecoveryEnv,OUT


def main():
    p=argparse.ArgumentParser();p.add_argument('--kp',type=float,default=1);p.add_argument('--kd',type=float,default=1)
    p.add_argument('--label',default='controller-audit');p.add_argument('--airborne',action='store_true')
    p.add_argument('--seconds',type=int,default=4);p.add_argument('--require-settled',action='store_true');args=p.parse_args()
    torch.set_num_threads(1);wp.init()
    env=RecoveryEnv(4,auto_reset=False,integrator='euler')
    gains=env.controller.gains.numpy();gains[:,0]*=args.kp;gains[:,1]*=args.kd
    wp.copy(env.controller.gains,wp.array(gains,dtype=wp.vec3,device='cuda:0'))
    # Two reference-pose and two fallen copies; no policy, no changing targets.
    env.qpos[:2].copy_(env.reference[None,:].expand(2,-1));env.qpos[:2,2]+=.015
    if args.airborne:
        # Diagnostic only: remove gravity to isolate controller settling from a
        # fall. Production training gravity and all collisions remain unchanged.
        env.sim.wp_model.opt.gravity.fill_(wp.vec3(0.))
        q=np.tile(env.reference.cpu().numpy(),(4,1));q[:,2]=3
        rng=np.random.default_rng(412)
        for j in range(22):
            rot=Rotation.from_quat(q[:,7+4*j:11+4*j][:,[1,2,3,0]])
            rot=rot*Rotation.from_rotvec(rng.normal(0,.025,(4,3)))
            q[:,7+4*j:11+4*j]=rot.as_quat()[:,[3,0,1,2]]
        env.qpos.copy_(torch.as_tensor(q,device='cuda'))
    env.qvel.zero_();env.controller.actions.zero_()
    velocity=[];torque=[];position=[]
    for step in range(args.seconds*240):
        wp.capture_launch(env.sim.step_graph)
        if step>=(args.seconds-1)*240:
            velocity.append(env.qvel.cpu().numpy().copy())
            torque.append(env.controller.torques.numpy().copy())
            position.append(env.qpos.cpu().numpy().copy())
    v=np.array(velocity);t=np.array(torque);q=np.array(position);rows=[]
    for i,j in enumerate(env.metadata['joints']):
        adr=env.sim.mj_model.joint(j['name']).dofadr[0]
        w=v[:,:,adr:adr+3]
        flips=((w[1:]*w[:-1]<0)&(np.abs(w[1:])>1)&(np.abs(w[:-1])>1)).mean()
        rows.append({'body':j['body'],'speed_p95_rad_s':float(np.percentile(np.linalg.norm(w,axis=-1),95)),
                     'fast_axis_sign_flip_fraction':float(flips),'torque_p95_nm':float(np.percentile(np.linalg.norm(t[:,:,i],axis=-1),95))})
    passed=bool(np.isfinite(q).all()) and max(r['speed_p95_rad_s'] for r in rows)<.1 and max(r['fast_axis_sign_flip_fraction'] for r in rows)==0
    report={'passed':passed,'controller':env.controller.contract,'rig_sha256':env.metadata['rig_sha256'],
            'constant_zero_actions':True,'airborne_diagnostic':args.airborne,'kp_scale':args.kp,'kd_scale':args.kd,'measured_seconds':[args.seconds-1,args.seconds],'joints':rows,'finite':bool(np.isfinite(q).all())}
    (OUT/(args.label+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    np.savez_compressed(OUT/(args.label+'.npz'),qpos=q,qvel=v,torques=t)
    print(json.dumps(report,indent=2))
    if args.require_settled:
        assert args.airborne and args.seconds>=8 and args.kp==1 and args.kd==1,'Require the standard actual-rig settling fixture'
        assert passed,report


if __name__=='__main__':main()
