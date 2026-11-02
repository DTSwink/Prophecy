"""Isolated full-batch PPO signal audit. No optimization or production writes."""
import os,sys,json,hashlib,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
R=Path('/workspace/mimickit_trial');O=R/'crawl-forward-followup-20261102'
sys.path[:0]=[str(R/'pipeline'),str(R/'MimicKit/mimickit')]
import torch,numpy as np,warp as wp,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from learning.rl_util import compute_td_lambda_return
from util import mp_util,torch_util as q
from resume import restore

def stats(v):
 a=v.detach().cpu().numpy().ravel()
 return dict(mean=float(a.mean()),std=float(a.std()),q=np.quantile(a,[0,.1,.5,.9,1]).tolist())

def main():
 started=time.time();torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261102)
 wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793);os.chdir(R/'MimicKit')
 cfg,ec,ac=[yaml.safe_load((R/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 cfg.update(motion_file=str(R/'prepared/motions.yaml'),omni_manifest=str(R/'prepared/manifest.json'))
 env=DisabledSlowLocoEnv(cfg,ec,2048,'cuda:0',False);engine=env._engine;c=env._get_char_id()
 agent=OmniPPOAgent(ac,env,'cuda:0');pin=json.loads((O/'pin.json').read_text())
 assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()==pin['sha256']
 restored=restore(agent,pin['path']);agent.eval();agent._init_train();agent._sample_count=2000000000;agent.set_mode(AgentMode.TRAIN)
 obs,info=env.reset();agent._curr_obs,agent._curr_info=obs,info
 rows=(env._motion_ids==0).nonzero().flatten();hist={k:[] for k in ('code','cohort','age','done','root','velocity','bonus','pose_reward','action_mode','action_noise','joint_velocity','torque','return_reward','hand_velocity')};batches=[]
 print('READY',time.time()-started,flush=True)
 with torch.no_grad():
  for batch in range(4):
   bonus_buffer=[];penalty_buffer=[];selector=[]
   for tick in range(32):
    dist=agent._model.eval_actor(agent._obs_norm.normalize(obs));mode=agent._a_norm.unnormalize(dist.mode)
    action,ai=agent._decide_action(obs,info);agent._record_data_pre_step(obs,info,action,ai)
    ob2,r,done,inf2=env.step(action);agent._record_data_post_step(ob2,r,done,inf2)
    pos=engine.get_body_pos(c);rot=engine.get_body_rot(c);ang=engine.get_body_ang_vel(c)
    vel=engine.get_body_vel(c)-torch.cross(ang,q.quat_rotate(rot,env._body_com),dim=-1)
    vals=(env._codes,env._cohort,env._timestep_buf,done,pos[:,0],vel[:,0],env._crawl_forward_values,torch.exp(-env.loss_terms.sum(-1)),mode,action-mode,engine.get_dof_vel(c),engine._dof_forces[0],r,vel[:,[5,8]])
    for key,v in zip(hist,vals):hist[key].append(v[rows].cpu().numpy().copy())
    bonus_buffer.append(env._crawl_forward_values.clone());penalty_buffer.append(-((done==1)*env._failure_penalty_by_row))
    selector.append((env._motion_ids==0)&(env._codes==12)&env._injured)
    obs,info=env.reset((done!=0).nonzero().flatten());agent._curr_obs,agent._curr_info=obs,info;agent._exp_buffer.inc()
   result=agent._build_train_data();mask=torch.stack(selector);b=torch.stack(bonus_buffer);p=torch.stack(penalty_buffer)
   reward=agent._exp_buffer.get_data('reward');done=agent._exp_buffer.get_data('done');adv=agent._exp_buffer.get_data('adv');vals=agent._model.eval_critic(agent._obs_norm.normalize(agent._exp_buffer.get_data('obs'))).squeeze(-1)
   raw=agent._exp_buffer.get_data('tar_val')-vals
   bonus_return=compute_td_lambda_return(b,torch.zeros_like(b),done,agent._discount,agent._td_lambda)
   failure_return=compute_td_lambda_return(p,torch.zeros_like(p),done,agent._discount,agent._td_lambda)
   bs=stats(b[mask]);pr=stats(failure_return[mask]);br=stats(bonus_return[mask]);ra=stats(raw[mask]);va=stats(vals[mask])
   corr=float(torch.corrcoef(torch.stack((b[mask],adv[mask])))[0,1])
   batches.append(dict(batch=batch,eligible_transitions=int(mask.sum()),fraction=float(mask.float().mean()),global_adv_std=float(result['adv_std']),bonus=bs,bonus_td_lambda_contribution=br,failure_td_lambda_contribution=pr,raw_advantage=ra,critic_value=va,normalized_advantage=stats(adv[mask]),bonus_advantage_correlation=corr,failures=int(((done==1)&mask).sum()),terminal_targets=stats(agent._exp_buffer.get_data('tar_val')[(done==1)&mask]) if ((done==1)&mask).any() else None))
   np.savez_compressed(O/'trace.npz',**{k:np.array(v) for k,v in hist.items()})
   (O/'ppo-signal.json').write_text(json.dumps(batches,indent=2));print('BATCH',batch,flush=True)
 meta=dict(checkpoint=pin,resume=restored,worlds=2048,ticks=128,rows=rows.cpu().tolist(),noise_physical=(agent._a_norm._std*.05).cpu().tolist(),discount=agent._discount,td_lambda=agent._td_lambda,source='actual production environment, no optimizer or normalizer updates',seconds=time.time()-started)
 (O/'probe.json').write_text(json.dumps(meta,indent=2));print('COMPLETE',time.time()-started,flush=True)
if __name__=='__main__':main()
