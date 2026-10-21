"""Bounded isolated profiler; never modifies the live trainer or its outputs."""
import sys,json,time,os,types
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-audit-20261020';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from profile_training import run_profiled_update
torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
r=ROOT/'runs/20261020_065209_uefn_replay_getup_selection_linear_512';b=json.loads((r/'backup_status.json').read_text());restore(agent,r/Path(b['key']).name);agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
for i in range(2):agent._iter=i;agent._train_iter()
# CPU call profile plus nested phase/CUDA-stream ranges for one PPO update.
import cProfile,pstats,io
prof=cProfile.Profile();prof.enable();run_profiled_update(agent,agent._train_iter,OUT,0);prof.disable()
s=io.StringIO();pstats.Stats(prof,stream=s).sort_stats('cumtime').print_stats(55);(OUT/'python_calls.txt').write_text(s.getvalue())
# Isolate AE cost at identical recorded state, old/all rows vs only contributing rows.
prior=env._prior;ids=env._perturbed_ids;keep=~env._perturbed_getup[ids];oldpos=prior.positions;oldrot=prior.rotations;oldvalid=prior.valid
with torch.no_grad():
 baseline=prior.cost().clone(); measurements=[]
 for reduced in [False,True,True,False]:
  prior.positions=oldpos[keep].clone() if reduced else oldpos;prior.rotations=oldrot[keep].clone() if reduced else oldrot;prior.valid=oldvalid[keep].clone() if reduced else oldvalid
  for _ in range(3):value=prior.cost()
  torch.cuda.synchronize();t=time.perf_counter()
  for _ in range(30):value=prior.cost()
  torch.cuda.synchronize();elapsed=time.perf_counter()-t
  if reduced:torch.testing.assert_close(value,baseline[keep],atol=2e-6,rtol=2e-5)
  measurements.append(dict(reduced=reduced,rows=len(prior.valid),seconds=elapsed,iterations=30))
 prior.positions=oldpos;prior.rotations=oldrot;prior.valid=oldvalid
(OUT/'ae_compare.json').write_text(json.dumps(dict(measurements=measurements,excluded_getups=int((~keep).sum()),checkpoint=b),indent=2))
print('PROFILE_COMPLETE',flush=True)
