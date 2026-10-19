"""User-requested cohort and recovery-only termination change; disposable physics."""
from diagnose_floor_guard_speed import *
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798)
folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
cfg['idle_row_fraction']=.18
cfg['idle_recovery']['target_termination_bodies']=['right_foot','left_foot']
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,ROOT/'Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip')
agent.eval();agent.set_mode(AgentMode.TEST)
counts={str(g):int((env._gaits[env._fixed_motion_ids]==g).sum()) for g in (-1,0,1)}
assert counts=={'-1':92,'0':168,'1':252},counts
assert len(env._recovery_ids)==74 and env._recovery_target_indices==[3,4]
obs,info=env.reset()
for _ in range(8):
    with torch.no_grad():action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
    ids=torch.nonzero(done,as_tuple=False).flatten()
    if len(ids):obs,info=env.reset(ids)
assert torch.isfinite(obs).all()
report=dict(passed=True,counts=counts,recovery_rows=74,ordinary_idle=18,physics_ticks=8,solver=env._engine.validate_transfer_solver())
(ROOT/'Saved/MimicKitEquipment/idle18-smoke.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
