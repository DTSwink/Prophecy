"""Local paired full PPO benchmark. No cloud calls or checkpoint writes."""
import os,sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Labs/MimicKitTraining'),str(ROOT/'Labs/MimicKitTransfer'),str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import torch,numpy as np,warp as wp,yaml
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from util import mp_util
from learning.base_agent import AgentMode
from floor_projection_guard import FloorProjectionGuard
from floor_projection_parallel import apply_parallel

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6799)
 FloorProjectionGuard.apply=apply_parallel
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 ec['transfer_floor_aware_projection']=True
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 engine=env._engine;guard=engine.transfer_floor_guard;graphs={True:engine._graph}
 engine.transfer_floor_guard=None;engine._build_graphs();graphs[False]=engine._graph;engine.transfer_floor_guard=guard
 checkpoint=ROOT/'Saved/MimicKitEquipment/floor-recovery-study-checkpoint.zip'
 reports=[]
 for enabled in (False,True,True,False):
  engine._graph=graphs[enabled];restore(agent,checkpoint);torch.manual_seed(761);np.random.seed(761)
  agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
  times=[]
  for i in range(6):
   agent.eval();torch.cuda.synchronize();begun=time.perf_counter()
   with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
   torch.cuda.synchronize();rollout=time.perf_counter()-begun
   agent._build_train_data();agent._update_model();torch.cuda.synchronize();whole=time.perf_counter()-begun
   env._engine.validate_transfer_solver()
   assert all(torch.isfinite(v).all() for v in agent._exp_buffer._buffers.values())
   assert all(torch.isfinite(p).all() for p in agent.parameters())
   if i>=2:times.append(dict(whole=whole,rollout=rollout))
  reports.append(dict(guard=enabled,times=times));print(json.dumps(reports[-1]),flush=True)
  (ROOT/'Saved/MimicKitEquipment/floor-recovery/parallel-ppo-benchmark.json').write_text(json.dumps(reports,indent=2))
 means={str(enabled):float(np.median([t['whole'] for r in reports if r['guard']==enabled for t in r['times']])) for enabled in (False,True)}
 print(json.dumps(dict(medians=means,ratio=means['True']/means['False'],updates=24,transitions=24*512*agent._steps_per_iter)),flush=True)
if __name__=='__main__':main()
