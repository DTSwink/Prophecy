"""Verify actual updated simulator's first sitting tick; no policy training."""
import preflight_slow_policy as p
import os,json,numpy as np,torch
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry
os.chdir(p.p/'MimicKit');torch.set_num_threads(2)
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6752)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
assert ec['transfer_floor_aware_projection'] is True
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);eng=env._engine;char=env._get_char_id();g=Geometry()
ids=(env._fixed_motion_ids==7).nonzero().flatten();idx=int(ids[0]);results=[]
for mode in ['zero_command','passive']:
 if mode=='passive':p.wp.to_torch(eng.transfer_contact.p.motor_enabled).zero_()
 env.reset();row=[]
 for t in range(1,31):
  env.step(torch.zeros((64,34),device='cuda:0'))
  pos=eng.get_body_pos(char)[idx].cpu().numpy();rot=eng.get_body_rot(char)[idx].cpu().numpy();g.set_pose(pos,R.from_quat(rot).as_matrix())
  if t==1:
   assert (env._done_buf[ids]==0).all()
   assert float(env.target_distances_sq[ids].sqrt().max())<.05
   assert min(v for x,v in zip(g.gs,g.floors()) if x['body'] in ('right_foot','left_foot'))>-.01
  if t in (1,3,10,30):row.append(dict(tick=t,done=int(env._done_buf[idx]),max_error_cm=float(env.target_distances_sq[idx].sqrt().max()*100),foot_floor_cm={n:float(min(v for x,v in zip(g.gs,g.floors()) if x['body']==n)*100) for n in ('right_foot','left_foot')}))
 results.append(dict(mode=mode,steps=row))
report=dict(passed=True,first_tick_sitting_worlds=8,results=results)
(p.out/'hip-limits-20261031/first-tick-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
