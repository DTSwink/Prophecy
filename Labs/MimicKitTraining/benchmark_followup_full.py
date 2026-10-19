"""Full PPO paired benchmark, all physics unchanged, no saved model changes."""
from diagnose_floor_guard_speed import *
from followup_ppo import install
import gc

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6795)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 cfg['idle_row_fraction']=.18;cfg['idle_recovery']['target_termination_bodies']=['right_foot','left_foot']
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit');env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
 agent=OmniPPOAgent(ac,env,'cuda:0');checkpoint=ROOT/'Saved/MimicKitEquipment/idle18-resume-latest.zip'
 agent._compute_actor_loss=agent._compute_actor_loss_reference
 captured='--captured' in sys.argv;rows=[]
 for mode in ('baseline','candidate','candidate','baseline'):
  restore(agent,checkpoint);agent.zero_grad(set_to_none=True);gc.collect();torch.manual_seed(563);np.random.seed(563)
  env._engine.transfer_contact.p.warm_state.zero_();agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
  remove=install(agent,capture=captured) if mode=='candidate' else None
  times=[]
  for i in range(4):
   agent.eval();torch.cuda.synchronize();begun=time.perf_counter()
   with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
   torch.cuda.synchronize();rollout=time.perf_counter()-begun
   agent._build_train_data();info=agent._update_model();torch.cuda.synchronize();total=time.perf_counter()-begun
   info={k:v.detach() for k,v in info.items()}
   assert all(torch.isfinite(v).all() for v in agent._exp_buffer._buffers.values())
   assert all(torch.isfinite(p).all() for p in agent.parameters())
   warning=env._engine.validate_transfer_solver()
   times.append(dict(total=total,rollout=rollout,warning=warning))
  if remove:remove()
  rows.append(dict(mode=mode,times=times));print(json.dumps(rows[-1]),flush=True)
  name='full-captured.json' if captured else 'full-shared.json'
  (ROOT/'Saved/MimicKitEquipment/optimization-followup'/name).write_text(json.dumps(dict(worlds=512,updates_per_block=4,capture=captured,runs=rows),indent=2))
  del info
if __name__=='__main__':main()
