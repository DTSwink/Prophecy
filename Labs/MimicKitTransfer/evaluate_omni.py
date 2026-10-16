"""One noiseless episode per clip/phase after the owned training segment stops.

Reports every admitted clip separately; preserves each first episode for native
comparison. Finished worlds reset normally but never count as a second success.
"""
import argparse,hashlib,json,time
from pathlib import Path
from train_local import ROOT,SOURCE,LocalTransferEnv,OmniPPOAgent,mp_util,np,torch,wp,yaml,os
from learning.base_agent import AgentMode


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path)
    p.add_argument('--phases',type=int,default=4);p.add_argument('--label',required=True)
    a=p.parse_args();directory=a.run.resolve()
    status=json.loads((directory/'status.json').read_text())
    assert status['state'] in ('completed','stopped'), 'Wait for owned trainer; do not start a second GPU workload'
    assert a.phases>0
    out=directory/'evaluations';out.mkdir(exist_ok=True)
    assert not (out/(a.label+'.json')).exists() and not (out/(a.label+'.npz')).exists()
    configs={n:yaml.safe_load((directory/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    motion_path=Path(configs['env']['motion_file'])
    motion_files=[r['file'] for r in yaml.safe_load(motion_path.read_text())['motions']]
    worlds=len(motion_files)*a.phases
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6732);os.chdir(SOURCE/'MimicKit')
    configs['engine']['transfer_capture_failures']=False
    env=LocalTransferEnv(configs['env'],configs['engine'],worlds,'cuda:0',False)
    agent=OmniPPOAgent(configs['agent'],env,'cuda:0');agent.load(str(directory/'model.pt'))
    agent.eval();agent.set_mode(AgentMode.TEST)
    clips=torch.arange(len(motion_files),device='cuda:0').repeat_interleave(a.phases)
    phases=torch.arange(a.phases,device='cuda:0').repeat(len(motion_files))/a.phases
    sampler=env._sample_motion_times
    env._sample_motion_times=lambda n:(clips,phases*env._motion_lib.get_motion_length(clips))
    obs,info=env.reset();env._sample_motion_times=sampler
    engine=env._engine;engine._sim_state.pre_step_update();engine._body_velocity.update(engine._sim_state.raw_state)
    def state():
        raw=engine._sim_state.raw_state
        return np.concatenate([raw.body_q.numpy().reshape(worlds,15,7),raw.body_qd.numpy().reshape(worlds,15,6)],-1)
    initial=state();ended=np.zeros(worlds,dtype=bool)
    histories=[dict(states=[initial[w]],obs=[],actions=[],targets=[],distance=[]) for w in range(worlds)]
    flags=np.zeros(worlds,dtype=int);started=time.perf_counter()
    horizon=round(float(configs['env']['episode_length'])*30)
    for tick in range(horizon+1):
        with torch.no_grad():action,_=agent._decide_action(obs,info)
        before=obs.cpu().numpy().copy();actions=action.cpu().numpy()
        obs,_,done,info=env.step(action);engine.validate_transfer_solver()
        physical=state();target=torch.cat([env.reward_target_pos,env.reward_target_rot],-1).cpu().numpy()
        distances=env.target_distances_sq.sqrt().cpu().numpy();done_cpu=done.cpu().numpy()
        for w in np.flatnonzero(~ended):
            record=histories[w]
            for name,value in (('states',physical[w]),('obs',before[w]),('actions',actions[w]),
                               ('targets',target[w]),('distance',distances[w])):record[name].append(value.copy())
            if done_cpu[w]:ended[w]=True;flags[w]=done_cpu[w]
        if ended.all():break
        reset_ids=done.nonzero(as_tuple=False).flatten()
        if len(reset_ids):obs,info=env.reset(reset_ids)
    rows=[];captures={}
    for w,record in enumerate(histories):
        count=len(record['actions']);clip=w//a.phases
        rows.append(dict(clip=Path(motion_files[clip]).stem,phase=(w%a.phases)/a.phases,
            ticks=count,terminal=int(flags[w]),completed_horizon=bool(flags[w]==3),
            max_target_m=float(np.max(record['distance'])),reset_after_first_episode=True))
        for name,value in record.items():
            array=np.asarray(value);assert np.isfinite(array).all(),(w,name)
            captures[f'{w}_{name}']=array
    report=dict(checkpoint=str(directory/'model.pt'),sha256=hashlib.sha256((directory/'model.pt').read_bytes()).hexdigest(),
        worlds=worlds,phases_per_clip=a.phases,seconds=time.perf_counter()-started,
        completed_horizon=sum(r['completed_horizon'] for r in rows),horizon_ticks=horizon,rows=rows)
    np.savez_compressed(out/(a.label+'.npz'),**captures)
    (out/(a.label+'.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
