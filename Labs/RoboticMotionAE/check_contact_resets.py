"""Disposable local physics check: eight matched phases per native motion."""
import preflight_slow_policy as p
import os,json,numpy as np,torch,sys,hashlib
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry
from clean_slow_contacts import OUT,NAMES
os.chdir(p.p/'MimicKit');torch.set_num_threads(2)
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6752)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
variant='before' if '--before' in sys.argv else 'after'
motion_file=OUT/f'reset-check-motions-{variant}.yaml'
folder=p.p/'motions' if variant=='before' else OUT/'candidates'
input_sha256={n:hashlib.sha256((folder/f'{n}.pkl').read_bytes()).hexdigest() for n in NAMES}
motion_file.write_text(p.yaml.safe_dump(dict(motions=[dict(file=str(folder/f'{n}.pkl'),weight=1.) for n in NAMES])))
cfg['motion_file']=str(motion_file)
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);eng=env._engine;char=env._get_char_id();g=Geometry()
phases=torch.arange(64,device='cuda:0')%8/8.
env._motion_lib.sample_time=lambda ids,truncate_time=None:env._motion_lib.get_motion_length(ids)*phases[:len(ids)]
env.reset();rows=[]
for tick in range(4):
 if tick:env.step(torch.zeros((64,34),device='cuda:0'))
 pos=eng.get_body_pos(char).cpu().numpy();rot=eng.get_body_rot(char).cpu().numpy()
 floor=[]
 for x,q in zip(pos,rot):g.set_pose(x,R.from_quat(q).as_matrix());floor.append(g.floors())
 rows.append(dict(tick=tick,floor_cm=(np.array(floor)*100).tolist(),done=env._done_buf.cpu().tolist(),target_error_cm=(env.target_distances_sq.sqrt()*100).cpu().tolist()))
report=dict(note='Zero velocity commands, not a policy-quality or survival evaluation. Training unchanged.',input_sha256=input_sha256,motion_names=NAMES,motion_ids=env._fixed_motion_ids.cpu().tolist(),phase=phases.cpu().tolist(),geometry_names=[x['name'] for x in g.gs],rows=rows)
(OUT/f'physics-reset-check-{variant}.json').write_text(json.dumps(report,indent=2))
print(json.dumps(dict(reset_floor_min_cm=float(np.min(rows[0]['floor_cm'])),tick1_floor_min_cm=float(np.min(rows[1]['floor_cm'])),tick1_failures=int(np.count_nonzero(rows[1]['done'])),tick3_failures=int(np.count_nonzero(rows[3]['done'])))),flush=True)
