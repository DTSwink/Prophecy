"""Same-state local GPU timing; never starts or modifies a cloud run."""
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

def measure(fn,repeats=20):
 with wp.ScopedCapture() as capture:fn()
 for _ in range(3):wp.capture_launch(capture.graph)
 torch.cuda.synchronize();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True)
 a.record()
 for _ in range(repeats):wp.capture_launch(capture.graph)
 b.record();b.synchronize()
 return a.elapsed_time(b)/repeats

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 ec['transfer_floor_aware_projection']=True
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 engine=env._engine;guard=engine.transfer_floor_guard;graphs={True:engine._graph}
 engine.transfer_floor_guard=None;engine._build_graphs();graphs[False]=engine._graph;engine.transfer_floor_guard=guard
 restore(agent,ROOT/'Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip');agent.eval();agent.set_mode(AgentMode.TEST)
 reports=[]
 for enabled in ((False,True) if '--profile' in sys.argv else (False,True,True,False)):
  engine._graph=graphs[enabled];torch.manual_seed(761);np.random.seed(761);obs,info=env.reset()
  for i in range(24):
   with torch.no_grad():action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
   ids=torch.nonzero(done,as_tuple=False).flatten()
   if len(ids):obs,info=env.reset(ids)
  if '--profile' in sys.argv:
   from collections import defaultdict
   aggregate=defaultdict(float)
   p=engine.transfer_contact.p
   old_counts=p.fallback_count.numpy().copy();old_steps=p.fallback_steps.numpy().copy()
   with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as prof:
    for _ in range(4):wp.capture_launch(engine._graph)
    torch.cuda.synchronize()
   for event in prof.events():
    if str(event.device_type).endswith('CUDA'):aggregate[event.name]+=event.device_time_total/1000/4
   report=dict(guard=enabled,kernel_ms=sorted(aggregate.items(),key=lambda x:-x[1]),fallback_count=int((p.fallback_count.numpy()-old_counts).sum()),fallback_steps=int((p.fallback_steps.numpy()-old_steps).sum()),coupled_results=engine.transfer_contact.coupled_problem.result.numpy().sum(0).tolist())
   reports.append(report);print(json.dumps(report),flush=True)
   (ROOT/'Saved/MimicKitEquipment/floor-recovery/kernel-profile.json').write_text(json.dumps(reports,indent=2))
   continue
  q=engine._solver.mjw_data.qpos;original=wp.clone(q)
  if enabled:before=wp.clone(guard.before)
  else:before=wp.clone(q)
  inv=engine.transfer_contact.p.inv
  timings=[]
  for passes in (1,2,5,20):
   def project():
    wp.copy(q,before);engine.transfer_projection.apply(inv,iterations=passes,shared=True)
   ms=measure(project)
   timings.append(dict(passes=passes,projection_ms=ms))
  proposal=wp.clone(q)
  def floor():
   wp.copy(q,proposal);wp.copy(guard.before,before);guard.apply()
  ms=measure(floor)
  fractions=guard.fractions.numpy()
  wp.copy(q,original)
  # Full captured physics tick; advancing states is deliberately reported
  # separately from the identical-state microbenchmarks above.
  start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
  start.record()
  for _ in range(8):wp.capture_launch(engine._graph)
  end.record();end.synchronize()
  report=dict(guard=enabled,projection=timings,guard_ms=ms,blocked=int((fractions<1).sum()),fraction_mean=float(fractions.mean()),physics_tick_ms=start.elapsed_time(end)/8)
  reports.append(report);print(json.dumps(report),flush=True)
  np.savez_compressed(ROOT/'Saved/MimicKitEquipment/floor-recovery'/('speed-state-'+str(enabled)+'.npz'),before=before.numpy(),after=proposal.numpy(),inverse=inv.numpy())
  (ROOT/'Saved/MimicKitEquipment/floor-recovery/speed-diagnosis.json').write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
