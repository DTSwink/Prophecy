"""Isolated paired PPO comparison; main trainer/files are never mutated."""
import sys,json,time,types,gc,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,numpy as np,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
OUT=ROOT/'clipping-ab';OUT.mkdir(exist_ok=True)
started=time.time()
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798)
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False)
result=dict(worlds=128,updates_per_arm=80,transitions_per_arm=80*128*32,
    intervention='hard +/-10 versus same center with 0.1 slope outside +/-10; means/std unchanged',
    live_run_changed=False,trials=[])
def publish():
    result['elapsed_seconds']=time.time()-started
    temp=OUT/'result.tmp';temp.write_text(json.dumps(result,indent=2));temp.replace(OUT/'result.json')
def soft_tail(self,x):
    raw=(x-self._mean)/self._std;center=raw.clamp(-self._clip,self._clip)
    return (center+.1*(raw-center)).to(self.dtype)
def evaluate(agent):
    agent.eval();agent.set_mode(AgentMode.TEST);records=[];start_hashes=[]
    with torch.no_grad():
        for seed in [9851,9852]:
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            obs,info=agent._reset_envs()
            start_hashes.append(hashlib.sha256(obs.cpu().numpy().tobytes()).hexdigest())
            getup=env._perturbed_getup.clone();normal=env._recovery_rows & ~env._perturbed_rows
            side=env._recovery_motion.clone();normal_start=env._recovery_start.clone()
            active=getup|normal;peak=env._engine.get_body_pos(0)[:,env._head_id,2].clone()
            final=peak.clone();returns=torch.zeros(128,device='cuda');success=torch.zeros_like(active)
            for tick in range(180):
                action,_=agent._decide_action(obs,info)
                obs,reward,done,info=env.step(action)
                height=env._engine.get_body_pos(0)[:,env._head_id,2]
                peak=torch.where(active,torch.maximum(peak,height),peak)
                final=torch.where(active,height,final);returns+=reward*active
                success |= active & (height>=env._head_reset_height[env._motion_ids])
                active &= done==0
                ids=torch.where(done!=0)[0]
                if len(ids):obs,info=agent._reset_envs(ids)
            for w in torch.where(getup|normal)[0].tolist():
                records.append(dict(seed=seed,world=w,perturbed=bool(getup[w]),side=int(side[w]),
                    start_seconds=float(normal_start[w]),peak=float(peak[w]),final=float(final[w]),
                    reward_sum=float(returns[w]),success=bool(success[w])))
    summaries={}
    for name,pred in [('front',lambda r:r['perturbed'] and r['side']==0),
                      ('back',lambda r:r['perturbed'] and r['side']==1),
                      ('normal_getup',lambda r:not r['perturbed']),
                      ('normal_frame0',lambda r:not r['perturbed'] and r['start_seconds']==0.)]:
        rows=[r for r in records if pred(r)]
        summaries[name]=dict(n=len(rows),successes=sum(r['success'] for r in rows),
            peak_mean=float(np.mean([r['peak'] for r in rows])),
            final_mean=float(np.mean([r['final'] for r in rows])),
            reward_mean=float(np.mean([r['reward_sum'] for r in rows]))) if rows else {}
    return dict(summary=summaries,rows=records,start_hashes=start_hashes)

for seed in [6411,6412]:
    for mode in ['hard_clip','soft_tail']:
        agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,OUT/'checkpoint.zip');agent._init_train()
        if mode=='soft_tail':agent._obs_norm.normalize=types.MethodType(soft_tail,agent._obs_norm)
        trial=dict(seed=seed,mode=mode,checkpoint=restored,updates=[]);result['trials'].append(trial)
        trial['before']=evaluate(agent);publish()
        torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);np.random.seed(seed)
        agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
        trial['training_start_hash']=hashlib.sha256(agent._curr_obs.cpu().numpy().tobytes()).hexdigest()
        for update in range(80):
            agent._iter=update
            info=agent._train_iter()
            agent._sample_count+=128*agent._steps_per_iter
            if (update+1)%20==0:
                trial['updates'].append(dict(update=update+1,**{k:float(info[k]) for k in
                    ['critic_loss','actor_loss','policy_kl','actor_steps_accepted','actor_steps_rejected','actor_learning_rate']}))
                publish();print(json.dumps(dict(seed=seed,mode=mode,update=update+1,seconds=time.time()-started)),flush=True)
        trial['after']=evaluate(agent);publish()
        print(json.dumps(dict(seed=seed,mode=mode,before=trial['before']['summary'],after=trial['after']['summary'])),flush=True)
        del agent;gc.collect();torch.cuda.empty_cache()
result['complete']=True;publish();print('AB COMPLETE',flush=True)
