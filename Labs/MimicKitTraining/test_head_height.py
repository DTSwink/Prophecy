"""Task accounting plus actual Newton smoke test, before a fresh training run."""
import os,sys,json
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml
from head_height import HeadHeightEnv

os.chdir(root/'MimicKit');torch.set_num_threads(1)
cfg=yaml.safe_load((root/'pipeline/head_height_env.yaml').read_text());engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
e=HeadHeightEnv(cfg,engine,64,'cuda:0',False);obs,_=e.reset();assert torch.isfinite(obs).all()
peak=e._heights().clone();initial=peak.clone();total=torch.zeros(64,device='cuda:0');action=e._init_dof_pos.expand(64,-1)
for t in range(1,46):
 obs,r,d,info=e.step(action);peak=torch.maximum(peak,e._heights());total+=r
 assert torch.isfinite(obs).all() and torch.isfinite(r).all()
 assert (d==(2 if t==45 else 0)).all()
 assert torch.allclose(obs[:,-2:],peak)
assert torch.allclose(total,peak.amin(dim=-1))
e.reset(torch.tensor([0,3],device='cuda:0'));assert e._timestep_buf[0]==0 and e._timestep_buf[1]==45
assert torch.allclose(e._body_peaks[[0,3]],e._heights()[[0,3]])
report=dict(passed=True,worlds=64,steps=45,duration_seconds=45*e._engine.get_timestep(),initial_body_height_mean_m=float(initial.mean()),passive_minimum_peaks_mean_m=float(peak.amin(dim=-1).mean()),observation_size=obs.shape[-1],physics_graph=e._engine._graph is not None)
(root/'head_height_smoke.json').write_text(json.dumps(report,indent=2));print('HEAD_HEIGHT_SMOKE_PASS',json.dumps(report),flush=True)
