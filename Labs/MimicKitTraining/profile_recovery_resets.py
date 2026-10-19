"""Attribute reset versus physics cost locally; no paid run or saved weights."""
from diagnose_floor_guard_speed import *
from collections import defaultdict

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 restore(agent,ROOT/'Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip');agent.eval();agent.set_mode(AgentMode.TEST)
 totals=defaultdict(float);calls=defaultdict(int)
 def instrument(obj,name,label):
  original=getattr(obj,name)
  def wrapper(*args,**kwargs):
   torch.cuda.synchronize();start=time.perf_counter();value=original(*args,**kwargs);torch.cuda.synchronize()
   totals[label]+=time.perf_counter()-start;calls[label]+=1
   return value
  setattr(obj,name,wrapper)
 for obj,name,label in [(env._engine,'step','physics'),(env,'reset','reset_total'),(env,'_reset_envs','reset_state'),(env,'_reset_ref_motion','reset_reference'),(env,'_ref_state_init','reset_spawn'),(env,'_reset_char_rigid_body_state','reset_fk'),(env,'_post_physics_step','post_physics')]:instrument(obj,name,label)
 reports=[]
 model=env._kin_char_model;fused=model.forward_kinematics
 trials=(False,True,True,False)
 for setting in trials:
  reset=True if '--fk' in sys.argv else setting
  if '--fk' in sys.argv:model.forward_kinematics=fused if setting else fused.reference
  env._reset_after_getup=reset;env._engine.transfer_contact.p.warm_state.zero_();torch.manual_seed(761);np.random.seed(761)
  obs,info=env.reset();totals.clear();calls.clear();begun=time.perf_counter()
  for tick in range(60):
   with torch.no_grad():action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
   ids=torch.nonzero(done,as_tuple=False).flatten()
   if len(ids):obs,info=env.reset(ids)
  report=dict(reset=reset,fused=setting if '--fk' in sys.argv else True,seconds=time.perf_counter()-begun,totals=dict(totals),calls=dict(calls));reports.append(report);print(json.dumps(report),flush=True)
  filename='reset-profile-fused.json' if '--fk' in sys.argv else 'reset-profile.json'
  (ROOT/'Saved/MimicKitEquipment/floor-recovery'/filename).write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
