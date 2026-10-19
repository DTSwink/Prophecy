"""Paired saved-rollout PPO math/gradient/optimizer and timing audit."""
from diagnose_floor_guard_speed import *
import copy,gc
from followup_ppo import actor_loss,install

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 cfg['idle_row_fraction']=.18;cfg['idle_recovery']['target_termination_bodies']=['right_foot','left_foot']
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 agent._compute_actor_loss=agent._compute_actor_loss_reference
 checkpoint=ROOT/'Saved/MimicKitEquipment/idle18-resume-latest.zip';restore(agent,checkpoint)
 agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
 with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
 agent._build_train_data();batch=agent._exp_buffer.sample(2048)
 report=dict(checkpoint=str(checkpoint),loss_gradient_checks=[],runs=[])
 for fraction in (1.,.5):
  b={k:v.clone() for k,v in batch.items()};b['rand_action_mask'][int(2048*fraction):]=0
  values=[];grads=[]
  for method in (agent._compute_actor_loss,lambda b:actor_loss(agent,b)):
   agent.zero_grad(set_to_none=True);r=method(b);r['actor_loss'].backward()
   values.append({k:float(v.detach()) for k,v in r.items()});grads.append([p.grad.clone() for p in agent._model.get_actor_params() if p.requires_grad])
  for a,b in zip(grads[0],grads[1]):torch.testing.assert_close(a,b,atol=3e-5,rtol=3e-4)
  assert max(abs(values[0][k]-values[1][k]) for k in values[0])<2e-5
  report['loss_gradient_checks'].append(dict(random_fraction=fraction,max_gradient_difference=max(float((a-b).abs().max()) for a,b in zip(*grads)),values=values))
 del r,method
 agent.zero_grad(set_to_none=True);gc.collect()
 saved=copy.deepcopy(agent.state_dict());optim={k:copy.deepcopy(getattr(agent,'_'+k+'_optimizer')._optimizer.state_dict()) for k in ('actor','critic')}
 if '--trace' in sys.argv:
  other=OmniPPOAgent(ac,env,'cuda:0');other.load_state_dict(saved)
  other._actor_optimizer._optimizer.load_state_dict(copy.deepcopy(optim['actor']))
  original=agent._compute_actor_loss;rows=[]
  for i in range(40):
   batch=agent._exp_buffer.sample(2048)
   one=original(batch);two=actor_loss(other,batch)
   loss_delta=float(abs(one['actor_loss']-two['actor_loss']))
   agent._actor_optimizer.step(one['actor_loss']);other._actor_optimizer.step(two['actor_loss'])
   delta=max(float((a-b).abs().max()) for a,b in zip(agent._model.get_actor_params(),other._model.get_actor_params()))
   rows.append(dict(step=i,loss_difference=loss_delta,parameter_difference=delta))
  (ROOT/'Saved/MimicKitEquipment/optimization-followup/ppo-trace.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows),flush=True);return
 steps={k:getattr(agent,'_'+k+'_optimizer')._steps for k in optim}
 def reset():
  agent.load_state_dict(saved)
  for k in optim:
   wrapper=getattr(agent,'_'+k+'_optimizer');wrapper._optimizer.load_state_dict(copy.deepcopy(optim[k]));wrapper._steps=steps[k]
  torch.manual_seed(762);agent._exp_buffer._reset_sample_buf()
 results={}
 for mode in ('baseline','shared','captured','captured','baseline'):
  info=None;agent.zero_grad(set_to_none=True);gc.collect()
  reset();uninstall=None if mode=='baseline' else install(agent,capture=mode=='captured')
  times=[]
  for i in range(4):
   torch.cuda.synchronize();begun=time.perf_counter();info=agent._update_model();torch.cuda.synchronize();times.append(time.perf_counter()-begun)
   info={k:v.detach() for k,v in info.items()}
   assert all(torch.isfinite(p).all() for p in agent.parameters())
   if i==0:results.setdefault(mode,[p.detach().clone() for p in agent.parameters()])
  if uninstall:uninstall()
  row=dict(mode=mode,seconds=times,steady_mean=float(np.mean(times[1:])),actor_steps=agent._actor_optimizer._steps-steps['actor'],critic_steps=agent._critic_optimizer._steps-steps['critic'])
  report['runs'].append(row);print(json.dumps(row),flush=True)
  path=ROOT/'Saved/MimicKitEquipment/optimization-followup/ppo-v4.json';path.write_text(json.dumps(report,indent=2))
 diffs={}
 for mode in ('shared','captured'):
  diff=max(float((a-b).abs().max()) for a,b in zip(results['baseline'],results[mode]));diffs[mode]=diff
  print('Parameter difference',mode,diff,flush=True)
  report['after_one_update_parameter_max_difference']=diffs;path.write_text(json.dumps(report,indent=2))
  report.setdefault('parameter_differences',{})[mode]={name:float((a-b).abs().max()) for (name,_),a,b in zip(agent.named_parameters(),results['baseline'],results[mode]) if float((a-b).abs().max())>1e-7}
 report['after_one_update_parameter_max_difference']=diffs;report['passed']=max(diffs.values())<2e-6;path.write_text(json.dumps(report,indent=2));print(json.dumps(diffs),flush=True)

if __name__=='__main__':main()
