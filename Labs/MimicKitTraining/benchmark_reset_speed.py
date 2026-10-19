"""Validate cached starts and benchmark full local PPO; no cloud or save writes."""
from diagnose_floor_guard_speed import *

def main():
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 model=env._kin_char_model;fast=model.forward_kinematics;checkpoint=ROOT/'Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip'
 graphs=None;work=None
 if '--register' in sys.argv or '--accelerated' in sys.argv or '--preconditioned' in sys.argv:
  import importlib.util
  from make_register_contact_candidate import generate
  path=generate(accelerated='--accelerated' in sys.argv or '--preconditioned' in sys.argv,precondition='--preconditioned' in sys.argv)
  if '--accelerated' in sys.argv or '--preconditioned' in sys.argv:
   source=path.read_text().replace('error:wp.array(dtype=int)', 'error:wp.array(dtype=int),work:wp.array2d(dtype=int)')
   source=source.replace('            for it in range(iterations):','            pass_count=int(0)\n            for it in range(iterations):\n                pass_count=it+1')
   source=source.replace('            changed=bool(False)','            if lane==0:\n                work[w,0]+=1;work[w,1]+=pass_count;work[w,2]=wp.max(work[w,2],pass_count)\n            changed=bool(False)')
   path=path.with_stem(path.stem+'_counted');path.write_text(source)
   work=wp.zeros((512,3),dtype=int)
  spec=importlib.util.spec_from_file_location('block_contact_register_candidate',path)
  candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
  engine=env._engine;custom=engine.transfer_contact
  metric=wp.zeros((512,custom.capacity,3),dtype=float) if '--preconditioned' in sys.argv else None
  graphs={False:engine._graph}
  custom.block_kernel=candidate.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True)
  custom.retry_block_kernel=candidate.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True,retry=True)
  original=wp.launch_tiled
  def launch(kernel,*a,**kw):
   if kernel in (custom.block_kernel,custom.retry_block_kernel):
    if work is not None:kw['inputs']=kw['inputs']+[work]
    if metric is not None:kw['inputs']=kw['inputs']+[metric]
   return original(kernel,*a,**kw)
  wp.launch_tiled=launch
  engine._build_graphs();graphs[True]=engine._graph;wp.launch_tiled=original
 if '--shared' in sys.argv:
  import importlib.util
  from make_shared_contact_candidate import generate
  path=generate();spec=importlib.util.spec_from_file_location('block_contact_shared_candidate',path)
  candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
  engine=env._engine;custom=engine.transfer_contact;nv=custom.p.nv;motors=custom.p.nmotor
  graphs={False:engine._graph}
  custom.block_kernel=candidate.make_block_iteration(nv,motors,warm_start=True,shared_fallback=True)
  custom.retry_block_kernel=candidate.make_block_iteration(nv,motors,warm_start=True,retry=True,shared_fallback=True)
  pairs={custom.block_kernel:candidate.make_block_iteration(nv,motors,warm_start=True,shared_rows=True),
         custom.retry_block_kernel:candidate.make_block_iteration(nv,motors,warm_start=True,retry=True,shared_rows=True)}
  original=wp.launch_tiled
  def launch(kernel,*a,**kw):
   if kernel in pairs:original(pairs[kernel],*a,**kw)
   return original(kernel,*a,**kw)
  wp.launch_tiled=launch
  engine._build_graphs();graphs[True]=engine._graph;wp.launch_tiled=original
 lib=env._recovery_reset_lib;cache_error=0.;frame_count=0
 for motion in range(2):
  frames=torch.arange(int(lib._motion_num_frames[motion]),device='cuda:0',dtype=torch.float32)
  ids=torch.full((len(frames),),motion,device='cuda:0',dtype=torch.long)
  starts=frames*lib.get_motion_length(ids)/(lib._motion_num_frames[ids]-1)
  reference=lib.joint_rot_to_dof(lib.calc_motion_frame(ids,starts)[4])
  cached=env._reset_dof_cache[motion,:len(frames)]
  torch.testing.assert_close(cached,reference,atol=0,rtol=0)
  frame_count+=len(frames);cache_error=max(cache_error,float((cached-reference).abs().max()))
 def configure(enabled):
  model.forward_kinematics=fast if enabled else fast.reference
  env._cache_recovery_spawns=enabled
  if graphs is not None:env._engine._graph=graphs[enabled]
 # Same RNG, exact same sampled starts and joint angles; only FK roundoff allowed.
 snapshots=[]
 for enabled in (False,True):
  configure(enabled);torch.manual_seed(761);np.random.seed(761);obs,info=env.reset()
  snapshots.append({name:getattr(env,name).clone() for name in ('_ref_body_pos','_ref_body_rot','_ref_dof_pos','_motion_ids','_recovery_start','_feedback_phase')})
  snapshots[-1]['actual_dof']=env._engine.get_dof_pos(env._get_char_id()).clone()
  snapshots[-1]['obs']=obs.clone()
 diffs={}
 for name,a in snapshots[0].items():
  b=snapshots[1][name]
  torch.testing.assert_close(a,b,atol=3e-6,rtol=3e-6)
  diffs[name]=float((a-b).abs().max())
 reports=[]
 for enabled in ((True,) if '--production-smoke' in sys.argv else (False,True,True,False)):
  configure(enabled);restore(agent,checkpoint);torch.manual_seed(761);np.random.seed(761)
  env._engine.transfer_contact.p.warm_state.zero_()
  agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
  if work is not None:work.zero_()
  times=[]
  for i in range(2 if '--production-smoke' in sys.argv else 3 if graphs else 5):
   agent.eval();torch.cuda.synchronize();start=time.perf_counter()
   with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
   torch.cuda.synchronize();rollout=time.perf_counter()-start
   agent._build_train_data();agent._update_model();torch.cuda.synchronize();whole=time.perf_counter()-start
   warning=env._engine.validate_transfer_solver()
   assert all(torch.isfinite(v).all() for v in agent._exp_buffer._buffers.values())
   assert all(torch.isfinite(p).all() for p in agent.parameters())
   if i>=1:times.append(dict(whole=whole,rollout=rollout,solver_warning=warning))
  report=dict(optimized=enabled,times=times)
  if work is not None and enabled:
   counts=work.numpy();report['solver_outer_calls']=int(counts[:,0].sum());report['contact_passes']=int(counts[:,1].sum())
   report['mean_contact_passes']=float(counts[:,1].sum()/max(1,counts[:,0].sum()));report['max_contact_passes']=int(counts[:,2].max())
  reports.append(report);print(json.dumps(reports[-1]),flush=True)
  result=dict(cache_frames=frame_count,cache_max_error=cache_error,reset_max_errors=diffs,runs=reports)
  filename='production-speed-smoke.json' if '--production-smoke' in sys.argv else 'preconditioned-speed-ppo.json' if '--preconditioned' in sys.argv else 'accelerated-speed-ppo.json' if '--accelerated' in sys.argv else 'register-speed-ppo.json' if '--register' in sys.argv else 'shared-speed-ppo.json' if graphs else 'reset-speed-ppo.json'
  (ROOT/'Saved/MimicKitEquipment/floor-recovery'/filename).write_text(json.dumps(result,indent=2))
 print('PASS',flush=True)
if __name__=='__main__':main()
