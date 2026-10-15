"""Bounded, synchronized training-collection benchmark; no checkpoint mutation."""
import argparse
from collections import defaultdict
import json
import time
import subprocess
import torch
import warp as wp
from recovery_env import RecoveryEnv, OUT
from policy import load_policy


def telemetry():
    return subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,temperature.gpu,clocks.sm,power.draw','--format=csv,noheader,nounits'],text=True).strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--worlds',type=int,default=1024)
    p.add_argument('--steps',type=int,default=96)
    p.add_argument('--warmup',type=int,default=24)
    p.add_argument('--standing-fraction',type=float,default=0.)
    p.add_argument('--stochastic',action='store_true')
    p.add_argument('--contacts',type=int,default=256)
    p.add_argument('--constraints',type=int,default=768)
    p.add_argument('--profile',action='store_true')
    p.add_argument('--solver',choices=('newton','cg'),default='newton')
    p.add_argument('--label',default='baseline')
    p.add_argument('--jacobian',choices=('auto','dense','sparse'),default='auto')
    p.add_argument('--integrator',choices=('implicitfast','euler'),default='implicitfast')
    p.add_argument('--checkpoint',default=str(OUT/'runs/fixed_prone_01/model_275.pt'))
    args=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();torch.manual_seed(42)
    config=torch.load(args.checkpoint,map_location='cpu',weights_only=False)['infos']['physical_recovery']
    env=RecoveryEnv(args.worlds,jacobian=args.jacobian,integrator=args.integrator,native_motors=config.get('native_motors',False),relative_targets=config.get('relative_targets',False),solver=args.solver,standing_fraction=args.standing_fraction,
        contact_capacity=args.contacts,constraint_capacity=args.constraints,ccd_iterations=config.get('ccd_iterations',50),gyroscopic_forces=config.get('gyroscopic_forces',True),
        pose_bank=config.get('pose_bank','rig-passive.npz'),raw_action_cost=config.get('previous_action_observation')=='requested',
        posture_profile=config.get('posture_reward',{}).get('profile','legacy'))
    policy,_=load_policy(args.checkpoint,env,allow_physics_override=True)
    # Isolate physics/reset/observation GPU intervals without forcing per-phase synchronization.
    events=defaultdict(list)
    def wrap(label,fn):
        def measured(*a,**kw):
            start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
            start.record();value=fn(*a,**kw);end.record();events[label].append((start,end))
            return value
        return measured
    launch=wp.capture_launch
    def graph(g,*a,**kw):
        return wrap('physics',launch)(g,*a,**kw)
    with torch.inference_mode():
        for _ in range(args.warmup):env.step(policy(env.get_observations(),stochastic_output=args.stochastic))
        wp.capture_launch=graph
        env.reset=wrap('reset',env.reset)
        env.get_observations=wrap('observations',env.get_observations)
        step=wrap('env_total',env.step)
        act=wrap('inference',policy)
        obs=env.get_observations();events.clear();torch.cuda.synchronize()
        before=telemetry();begin=time.perf_counter()
        for _ in range(args.steps):
            obs,_,_,_=step(act(obs,stochastic_output=args.stochastic))
        torch.cuda.synchronize();elapsed=time.perf_counter()-begin
        timings={k:sum(a.elapsed_time(b) for a,b in pairs)/len(pairs) for k,pairs in events.items()}
        result={'label':args.label,'solver':args.solver,'jacobian':args.jacobian,'integrator':args.integrator,'worlds':args.worlds,'policy_ticks':args.steps,'wall_seconds':elapsed,
            'standing_fraction':args.standing_fraction,'stochastic':args.stochastic,'warmup_ticks':args.warmup,'checkpoint':args.checkpoint,
            'contact_capacity':args.contacts,'constraint_capacity':args.constraints,'peak_constraints_contacts':env.controller.capacity_max.numpy().tolist(),
            'final_solver_iterations':{'max':int(env.sim.wp_data.solver_niter.numpy().max()),'mean':float(env.sim.wp_data.solver_niter.numpy().mean())},
            'transitions_per_second':args.worlds*args.steps/elapsed,'gpu_ms_per_tick':timings,
            'gpu_before':before,'gpu_after':telemetry(),
            'memory_peak_mib':torch.cuda.max_memory_allocated()/2**20,
            'finite':bool(torch.isfinite(env.qpos).all() and torch.isfinite(env.qvel).all())}
        if args.profile:
            wp.capture_launch=launch
            with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as prof:
                for _ in range(2):env.step(policy(env.get_observations(),stochastic_output=args.stochastic))
                torch.cuda.synchronize()
            (OUT/f'profile-{args.label}-{args.worlds}.txt').write_text(prof.key_averages().table(sort_by='self_cuda_time_total',row_limit=40),encoding='utf-8')
            prof.export_chrome_trace(str(OUT/f'profile-{args.label}-{args.worlds}.json'))
    path=OUT/f'benchmark-{args.label}-{args.worlds}.json'
    path.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
