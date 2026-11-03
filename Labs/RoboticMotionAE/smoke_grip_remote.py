import os,sys,json,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
r=Path('/workspace/mimickit_trial');p=r/'grip-preflight'
sys.path[:0]=[str(p/'pipeline'),str(p/'MimicKit/mimickit')]
import torch,warp as wp,numpy as np,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util
from resume import restore
os.chdir(p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
cfg,ec,ac=[yaml.safe_load((p/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
ec['uefn_asset_directory']=str(p/'assets/uefn')
env=DisabledSlowLocoEnv(cfg,ec,32,'cuda:0',False);eng=env._engine
assert eng.torque_envelope_report['axes']['right_lower_arm']['applied_nm']==150
assert eng.torque_envelope_report['axes']['left_lower_arm']['applied_nm']==150
m=eng._solver.mj_model;factors=eng.transfer_contact.ground_friction_factors.numpy()
assert sum(factors==3)==4
for i in range(m.nbody):
 expected=3 if any(m.body(i).name.endswith(n) for n in ec['transfer_ground_friction_multipliers']) else 1
 assert factors[i]==expected
# Exercise exact production kernel: both contact orders, unmodified foot/self-contact, inactive slots.
from sequential_contact_adapter import scale_ground_grip
mu=wp.array(np.ones((1,6),np.float32),device='cuda:0')
wp.launch(scale_ground_grip,(1,6),inputs=[wp.array([5],dtype=int,device='cuda:0'),wp.array(np.arange(6,dtype=np.int32)[None],device='cuda:0'),wp.array([[0,1],[1,0],[0,2],[1,2],[0,3],[0,1]],dtype=wp.vec2i,device='cuda:0'),wp.array([0,1,2,3],dtype=int,device='cuda:0'),mu,wp.array([1.,3.,1.,3.],dtype=float,device='cuda:0')])
np.testing.assert_equal(mu.numpy(),[[3,3,1,1,3,1]])
name='20261102_220414_uefn_slowloco_disabled_curriculum_crawl_only_signed5_2048';old=r/'runs'/name
backup=json.loads((old/'backup_status.json').read_text());checkpoint=old/backup['key'].split('/')[-1]
agent=OmniPPOAgent(ac,env,'cuda:0');res=restore(agent,str(checkpoint));agent.eval();agent.set_mode(AgentMode.TEST)
obs,info=env.reset()
seen=set()
with torch.no_grad():
 for tick in range(32):
  act,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(act)
  assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
  adapter=eng.transfer_contact;pp=adapter.p;cnt=pp.ncontact.numpy();ids=adapter.contactids.numpy();geom=eng._solver.mjw_data.contact.geom.numpy();bodies=eng._solver.mjw_model.geom_bodyid.numpy();actual=pp.manifold.friction.numpy();groups=pp.manifold.group.numpy();base=eng._solver.mjw_data.contact.friction.numpy()
  for w in range(32):
   for c in range(cnt[w]):
    ident=ids[w,c];a,b=bodies[geom[ident]]
    factor=factors[b] if a==0 else factors[a] if b==0 else 1
    g=groups[w,c]
    if g<0:continue
    assert abs(actual[w,g]-base[ident,0]*factor)<1e-5, (w,c,g,float(actual[w,g]),float(base[ident,0]),float(factor))
    if factor==3:seen.add(int(b if a==0 else a))
  idsreset=(done!=0).nonzero().flatten()
  if len(idsreset):obs,info=env.reset(idsreset)
eng.validate_transfer_solver()
(p/'smoke.json').write_text(json.dumps(dict(passed=True,ticks=32,worlds=32,checkpoint=str(checkpoint),torque=eng.torque_envelope_report,ground_friction=factors.tolist(),boosted_contact_bodies_seen=list(seen),optimizer_restored=res['optimizer_restored'])))
print('PASS grip, caps, latest checkpoint, finite physics')
