"""Bounded randomized-action physical stress; captures first numerical failure."""
import argparse
import json
import numpy as np
import torch
import warp as wp
from recovery_env import RecoveryEnv,OUT


def main():
    p=argparse.ArgumentParser();p.add_argument('--worlds',type=int,default=256)
    p.add_argument('--ticks',type=int,default=240);p.add_argument('--label',default='stress-physics')
    p.add_argument('--kp',type=float,default=1);p.add_argument('--kd',type=float,default=1)
    p.add_argument('--integrator',default='euler');p.add_argument('--hold-action',action='store_true');args=p.parse_args()
    torch.set_num_threads(1);wp.init();torch.manual_seed(42)
    env=RecoveryEnv(args.worlds,integrator=args.integrator)
    gains=env.controller.gains.numpy();gains[:,0]*=args.kp;gains[:,1]*=args.kd
    wp.copy(env.controller.gains,wp.array(gains,dtype=wp.vec3,device='cuda'))
    history=[];peaks=[];failed=False
    held=torch.randn_like(env.controller.actions).clamp(-1,1)
    for tick in range(args.ticks):
        actions=held if args.hold_action else torch.randn_like(env.controller.actions).clamp(-1,1)
        env.controller.actions.copy_(actions)
        for sub in range(8):
            beforeq=env.qpos.cpu().numpy().copy();beforev=env.qvel.cpu().numpy().copy()
            wp.capture_launch(env.sim.step_graph)
            q=env.qpos.cpu().numpy().copy();v=env.qvel.cpu().numpy().copy()
            valid=np.isfinite(q).all(1)&np.isfinite(v).all(1)
            if not valid.all():
                bad=int(np.flatnonzero(~valid)[0]);failed=True
                np.savez_compressed(OUT/(args.label+'-failure.npz'),qpos=beforeq[bad],qvel=beforev[bad],
                    actions=actions[bad].cpu().numpy(),next_qpos=q[bad],next_qvel=v[bad],
                    qacc=env.sim.wp_data.qacc.numpy()[bad],qM=env.sim.wp_data.qM.numpy()[bad],
                    qLD=env.sim.wp_data.qLD.numpy()[bad],D=env.sim.wp_data.efc.D.numpy()[bad],
                    nefc=env.sim.wp_data.nefc.numpy()[bad],J=env.sim.wp_data.efc.J.numpy()[bad])
                print(f'Failure tick {tick} substep {sub} world {bad} previous velocity {np.abs(beforev[bad]).max()}',flush=True)
                break
        peaks.append(float(np.nanmax(np.abs(v))))
        if failed:break
        if tick%30==0:print(f'tick {tick} peak velocity {peaks[-1]:.3f}',flush=True)
    report={'passed':not failed,'worlds':args.worlds,'policy_ticks':tick+1,'last_substep':sub,
        'max_abs_velocity':max(peaks),'velocity_peaks':peaks,'kp_scale':args.kp,'kd_scale':args.kd,
        'capacity_peaks':env.controller.capacity_max.numpy().tolist(),'capacity_overflow':int(env.capacity_overflow.item())}
    (OUT/(args.label+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    assert not failed,report


if __name__=='__main__':main()
