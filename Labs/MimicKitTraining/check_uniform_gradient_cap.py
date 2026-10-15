"""Two bounded controls, one at a time. Original fixed noise vs uniform+stock cap.

No periodic model archives. Save one final resumable candidate if it stays finite.
"""
import argparse,os,sys,json,time,zipfile,random
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,numpy as np,yaml
import run as upstream
from neutral_pose import NeutralPoseEnv
from agent_noise import PerAgentNoisePPO
from learning.ppo_agent import PPOAgent
from observe import Recorder
from health import install_guard

p=argparse.ArgumentParser();p.add_argument('variant',choices=['fixed','capped']);p.add_argument('--cap',type=float,default=1.);a=p.parse_args()
assert a.cap>0
suffix='' if a.cap==1. else '_'+format(a.cap,'g')
out=ROOT/('uniform_check_'+a.variant+suffix);out.mkdir(exist_ok=False)
torch.set_num_threads(1);torch.set_num_interop_threads(1);os.chdir(ROOT/'MimicKit')
cfg=yaml.safe_load((ROOT/'pipeline/neutral_pose_env.yaml').read_text())
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
acfg=yaml.safe_load((ROOT/'pipeline/head_height_agent.yaml').read_text());acfg.update(iters_per_output=50,iters_per_log=50)
if a.variant=='capped':
    acfg.update(per_agent_noise_seed=20261014,per_agent_noise_distribution='uniform_zero_to_action_std_fixed_per_world')
    acfg['actor_optimizer']['grad_clip']=a.cap
for name,data in [('env_config',cfg),('engine_config',engine),('agent_config',acfg)]:
    (out/(name+'.yaml')).write_text(yaml.safe_dump(data,sort_keys=False))
args=upstream.load_args(['train','--rand_seed','20261014','--visualize','false','--logger','tb'])
upstream.mp_util.init(0,1,'cuda:0',6741);upstream.set_rand_seed(args)
env=NeutralPoseEnv(cfg,engine,512,'cuda:0',False)
agent=(PerAgentNoisePPO if a.variant=='capped' else PPOAgent)(acfg,env,'cuda:0')
recorder=Recorder(env,out);original_test=agent._rollout_test;original_iter=agent._train_iter
start=time.time();latest={}
def test(count):
    recorder.start()
    try:result=original_test(count)
    finally:recorder.enabled=False
    metadata=dict(training_action_noise_std=.05 if a.variant=='fixed' else None,
                  rollout_action_noise_std=0.,losses=dict(test_mse_m2=-float(result['mean_return'])))
    if a.variant=='capped':metadata.update(training_action_noise_distribution='uniform_fixed_per_agent',training_action_noise_range=[0.,.05])
    replay=recorder.finish(agent._iter,agent._sample_count,metadata)
    latest.update(result,iteration=agent._iter,replay=replay)
    with (out/'evaluations.jsonl').open('a') as f:f.write(json.dumps(dict(iteration=agent._iter,mse=-float(result['mean_return'])))+'\n')
    return result
def failure(detail):
    (out/'failure.json').write_text(json.dumps(dict(iteration=agent._iter,**detail),indent=2))
install_guard(agent,failure)
def iteration():
    assert time.time()<json.loads((ROOT/'private.json').read_text())['deadline_unix']-120
    result=original_iter()
    assert all(bool(torch.isfinite(p).all()) for p in agent.parameters()),'Nonfinite model'
    if agent._iter%10==0:
        status=dict(iteration=agent._iter,samples=(agent._iter+1)*16384,seconds=time.time()-start,
                    train_mse=-float(result['mean_return']),clip_fraction=float(result['clip_frac']))
        (out/'status.json').write_text(json.dumps(status))
    return result
agent._train_iter=iteration;agent._rollout_test=test;agent._output_train_model=lambda *args:None
try:
    agent.train_model(200*16384,str(out),False,'tb')
    agent.test_model(agent._test_episodes)
    report=dict(variant=a.variant,grad_clip=a.cap if a.variant=='capped' else None,finite=True,completed_updates=agent._iter,samples=agent._sample_count,
                final_test_mse=-float(latest['mean_return']),elapsed_seconds=time.time()-start)
    (out/'report.json').write_text(json.dumps(report,indent=2));print('CONTROL_RESULT',json.dumps(report),flush=True)
    if a.variant=='capped':
        agent.save(str(out/'model.pt'))
        state=dict(completed_iteration=agent._iter-1,samples=agent._sample_count,
            actor_optimizer=agent._actor_optimizer._optimizer.state_dict(),critic_optimizer=agent._critic_optimizer._optimizer.state_dict(),
            actor_steps=agent._actor_optimizer._steps,critic_steps=agent._critic_optimizer._steps,
            torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),numpy_rng=np.random.get_state(),python_rng=random.getstate(),
            normalizer_aux={name:{key:getattr(mod,key) for key in ['_mean_sq','_new_count','_new_sum','_new_sum_sq']}
                for name,mod in agent.named_modules() if hasattr(mod,'_new_sum_sq')},physics_episode_state_saved=False)
        torch.save(state,out/'resume_state.pt')
        with zipfile.ZipFile(out/'candidate.zip','w',compression=zipfile.ZIP_STORED) as z:
            for name in ['model.pt','resume_state.pt','env_config.yaml','engine_config.yaml','agent_config.yaml','replay.npz','report.json']:
                z.write(out/name,name)
except BaseException as error:
    failure(dict(reason=repr(error)));raise
