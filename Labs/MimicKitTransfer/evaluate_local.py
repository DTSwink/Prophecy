"""Fixed-phase MJ rollout, reusable verbatim in the native Jolt comparison."""
import argparse,json,time
from pathlib import Path
from train_local import ROOT,SOURCE,LocalTransferEnv,OmniPPOAgent,mp_util,np,torch,wp,yaml,os
from learning.base_agent import AgentMode


def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--worlds',type=int,default=16)
    p.add_argument('--ticks',type=int,default=300);p.add_argument('--label',required=True);a=p.parse_args()
    directory=a.run.resolve();out=ROOT/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'
    assert not (out/(a.label+'.npz')).exists(),'Preserve previous evaluation'
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0')
    mp_util.init(0,1,'cuda:0',6732);os.chdir(SOURCE/'MimicKit')
    configs={name:yaml.safe_load((directory/(name+'_config.yaml')).read_text()) for name in ('env','engine','agent')}
    configs['engine']['transfer_capture_failures']=False
    env=LocalTransferEnv(configs['env'],configs['engine'],a.worlds,'cuda:0',False)
    agent=OmniPPOAgent(configs['agent'],env,'cuda:0');agent.load(str(directory/'model.pt'))
    agent.eval();agent.set_mode(AgentMode.TEST)
    phases=torch.arange(a.worlds,device='cuda:0')/a.worlds
    duration=float(env._motion_lib.get_motion_lengths()[0])
    env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long,device='cuda:0'),phases[:n]*duration)
    obs,info=env.reset();engine=env._engine
    engine._sim_state.pre_step_update();engine._body_velocity.update(engine._sim_state.raw_state)
    def state():
        raw=engine._sim_state.raw_state
        return np.concatenate([raw.body_q.numpy().reshape(a.worlds,15,7),raw.body_qd.numpy().reshape(a.worlds,15,6)],-1)
    arrays=dict(initial=state(),states=[],obs=[],actions=[],targets=[],target_velocities=[],dist=[])
    first_done=[0]*a.worlds;first_flags=[0]*a.worlds;started=time.perf_counter()
    for tick in range(a.ticks):
        with torch.no_grad():action,_=agent._decide_action(obs,info)
        arrays['obs'].append(obs.cpu().numpy().copy());arrays['actions'].append(action.cpu().numpy().copy())
        obs,_,done,info=env.step(action)
        engine.validate_transfer_solver()
        arrays['states'].append(state())
        arrays['targets'].append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1).cpu().numpy().copy())
        arrays['target_velocities'].append(torch.cat([env.reward_target_vel,env.reward_target_ang],-1).cpu().numpy().copy())
        arrays['dist'].append(env.target_distances_sq.sqrt().cpu().numpy().copy())
        for w,flag in enumerate(done.cpu().tolist()):
            if flag and not first_done[w]:first_done[w]=tick+1;first_flags[w]=flag
        if tick%60==59:print('EVAL',tick+1,first_done,flush=True)
    for name,value in arrays.items():assert np.isfinite(value).all(),name
    np.savez_compressed(out/(a.label+'.npz'),**arrays)
    report=dict(first_done=first_done,first_flags=first_flags,worlds=a.worlds,ticks=a.ticks,
        checkpoint=str(directory/'model.pt'),max_distance=np.max(arrays['dist'],axis=(0,2)).tolist(),
        seconds=time.perf_counter()-started,scalar_fallbacks=int(engine.transfer_contact.p.fallback_count.numpy().sum()))
    (out/(a.label+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
