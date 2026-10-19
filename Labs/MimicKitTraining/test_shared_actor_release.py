"""Production actor update: physical PPO smoke and unbiased phase metrics."""
from diagnose_floor_guard_speed import *
from followup_ppo import actor_loss
torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6795)
folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
cfg['idle_row_fraction']=.18;cfg['idle_recovery']['target_termination_bodies']=['right_foot','left_foot']
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit');env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,ROOT/'Saved/MimicKitEquipment/idle18-resume-latest.zip')
agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
agent._build_train_data();batch=agent._exp_buffer.sample(2048)
production=agent._compute_actor_loss(batch);candidate=actor_loss(agent,batch)
for k in production:torch.testing.assert_close(production[k],candidate[k],atol=0,rtol=0)
assert production['auto_phase_weighted'].data_ptr()!=production['phase_prediction_weighted'].data_ptr()
assert production['auto_phase_mse'].data_ptr()!=production['phase_prediction_mse'].data_ptr()
del production,candidate
raw=[];method=agent._compute_actor_loss
def tracking(b):
 result=method(b);raw.append(result['auto_phase_weighted'].detach().clone());return result
agent._compute_actor_loss=tracking
torch.cuda.synchronize();begin=time.perf_counter();result=agent._update_model();torch.cuda.synchronize()
torch.testing.assert_close(result['auto_phase_weighted'],torch.stack(raw).mean())
torch.testing.assert_close(result['auto_phase_weighted'],result['phase_prediction_weighted'])
assert all(torch.isfinite(p).all() for p in agent.parameters())
report=dict(passed=True,physical_rollout_ticks=32,worlds=512,optimizer_seconds=time.perf_counter()-begin,phase_metric=float(result['auto_phase_weighted']),phase_expected=float(torch.stack(raw).mean()),warning=env._engine.validate_transfer_solver())
(ROOT/'Saved/MimicKitEquipment/optimization-followup/production-actor-smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
