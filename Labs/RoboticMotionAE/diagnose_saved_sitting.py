"""Local first-tick ablations; no live training edits."""
import preflight_slow_policy as p
import os,json,time,numpy as np,torch
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry
os.chdir(p.p/'MimicKit');torch.set_num_threads(2)
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6752)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);eng=env._engine;char=env._get_char_id();g=Geometry()
idx=int((env._fixed_motion_ids==7).nonzero()[0]);apply=eng.transfer_projection.apply
from floor_projection_guard import FloorProjectionGuard
guard=FloorProjectionGuard(eng._solver.mj_model,eng._solver.mjw_data,'cuda:0',parallel=True)
mask=p.wp.to_torch(eng.transfer_contact.p.motor_enabled);original_mask=mask.clone()
def record(t):
 pos=eng.get_body_pos(char)[idx].cpu().numpy();rot=eng.get_body_rot(char)[idx].cpu().numpy()
 g.set_pose(pos,R.from_quat(rot).as_matrix())
 return dict(tick=t,done=int(env._done_buf[idx]),floor_cm={n:float(min(v for x,v in zip(g.gs,g.floors()) if x['body']==n)*100) for n in g.names},
     deviation_cm=(env.target_distances_sq[idx].sqrt()*100).cpu().tolist(),positions=pos.tolist())
report={}
for mode in ['stock_zero_command','no_projection','no_motors','floor_guard']:
 eng.transfer_projection.apply=(lambda *a,**kw:None) if mode=='no_projection' else apply
 eng.transfer_floor_guard=guard if mode=='floor_guard' else None
 mask.copy_(original_mask)
 if mode=='no_motors':mask.zero_()
 eng._build_graphs();env.reset();rows=[record(0)]
 for t in range(1,4):env.step(torch.zeros((64,34),device='cuda:0'));rows.append(record(t))
 report[mode]=rows
 print(mode,[(r['tick'],r['done'],round(r['floor_cm']['right_foot'],2),[round(x,2) for x in r['deviation_cm']]) for r in rows],flush=True)
out=p.out/'user-pose-20261031/first-tick-diagnosis.json';out.write_text(json.dumps(report,indent=2))
