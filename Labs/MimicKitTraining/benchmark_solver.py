"""Isolated sparse/dense comparison. Same body, settings and recorded actions."""
import argparse
import gc
import io
import json
import os
from pathlib import Path
import time
import zipfile
import torch
import yaml
import train
from head_height import HeadHeightEnv
import newton

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--worlds',type=int,default=4096);a=p.parse_args()
    root=train.ROOT;os.chdir(train.REPO);torch.set_num_threads(1)
    env_config=yaml.safe_load((root/'pipeline/head_height_env.yaml').read_text())
    engine_config=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
    agent_config=yaml.safe_load((root/'pipeline/head_height_agent.yaml').read_text())
    from learning.ppo_agent import PPOAgent
    train.upstream.mp_util.init(0,1,'cuda:0',6742)
    ctor=newton.solvers.SolverMuJoCo
    records={};actions=[];poses=[];rotations=[];reports={}
    for variant in ['sparse','dense']:
        began=time.perf_counter()
        class SelectedSolver(ctor):
            def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs,jacobian=variant)
        newton.solvers.SolverMuJoCo=SelectedSolver
        try: env=HeadHeightEnv(env_config,engine_config,a.worlds,'cuda:0',False)
        finally: newton.solvers.SolverMuJoCo=ctor
        agent=PPOAgent(agent_config,env,'cuda:0')
        with zipfile.ZipFile(a.checkpoint) as z:
            agent.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True))
        agent.eval();torch.manual_seed(20261014);torch.cuda.manual_seed_all(20261014)
        env.reset()
        for _ in range(6): env.step(env._init_dof_pos.expand(a.worlds,-1))
        obs,info=env.reset()
        torch.cuda.synchronize();setup=time.perf_counter()-began
        events=[];original_step=env._engine.step
        def timed_physics():
            s=torch.cuda.Event(enable_timing=True);e=torch.cuda.Event(enable_timing=True)
            s.record();original_step();e.record();events.append((s,e))
        env._engine.step=timed_physics
        max_pos=0.;max_angle=0.;square_pos=0.;count=0
        begun=time.perf_counter()
        with torch.no_grad():
            for i in range(45):
                if variant=='sparse':
                    action,_=agent._decide_action(obs,info);actions.append(action.clone())
                else: action=actions[i]
                obs,reward,done,info=env.step(action)
                assert torch.isfinite(obs).all()
                pos=env._engine.get_body_pos(env._get_char_id()).clone()
                rot=env._engine.get_body_rot(env._get_char_id()).clone()
                if variant=='sparse': poses.append(pos);rotations.append(rot)
                else:
                    delta=(pos-poses[i]).norm(dim=-1)
                    dot=(rot*rotations[i]).sum(dim=-1).abs().clamp(0,1)
                    angle=2*torch.acos(dot)*180/torch.pi
                    max_pos=max(max_pos,delta.max().item());max_angle=max(max_angle,angle.max().item())
                    square_pos+=delta.square().sum().item();count+=delta.numel()
                    if i==0: reports['first_step']=dict(max_body_position_m=max_pos,max_body_angle_deg=max_angle)
        torch.cuda.synchronize()
        physics_ms=sum(s.elapsed_time(e) for s,e in events)
        records[variant]=dict(setup_seconds=setup,physics_ms=physics_ms,steps=45,worlds=a.worlds,
            physics_transitions_per_second=a.worlds*45/(physics_ms/1000),
            peak_minimum_mean_m=reward.mean().item(),finite=bool(torch.isfinite(obs).all()),
            complete=bool((done==2).all()),elapsed_seconds=time.perf_counter()-begun)
        if variant=='dense': reports['whole_episode']=dict(max_body_position_m=max_pos,max_body_angle_deg=max_angle,rms_body_position_m=(square_pos/count)**.5)
        print('SOLVER_BENCHMARK',variant,json.dumps(records[variant]),flush=True)
        del agent,env;gc.collect();torch.cuda.empty_cache()
    result=dict(records=records,comparison=reports,physics_speedup=records['sparse']['physics_ms']/records['dense']['physics_ms'],
        note='Open-loop replay of all4096 sampled policy action sequences, identical supine reset and six-step warmup. No updates to a training policy. Same accuracy/iteration settings; different supported matrix layout.')
    (root/'solver_benchmark.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__': main()
