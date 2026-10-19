"""Local, diagnostic-only solver counters and recovery-reset A/B."""
from diagnose_floor_guard_speed import *
import importlib.util

def main():
 out=ROOT/'Saved/MimicKitEquipment/floor-recovery'
 source=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
 if '--full-step' in sys.argv:
  source=source.replace('p.relaxation','correction_rate')
  source=source.replace('w,lane=wp.tid();dt=p.dt[0]',
   'w,lane=wp.tid();dt=p.dt[0]\n        correction_rate=p.relaxation\n        if wp.static(convergence_stop):correction_rate=1.0')
 source=source.replace('retry=False):','retry=False,exact_cycles=False,convergence_stop=False):',1)
 source=source.replace('ContactProblem,multiply,friction_bound','ContactProblem,multiply,friction_bound,absolute')
 source=source.replace('iterations:int,error:wp.array(dtype=int)):', 'iterations:int,error:wp.array(dtype=int),work:wp.array2d(dtype=int),history:wp.array3d(dtype=float),cycles:wp.array2d(dtype=int)):')
 source=source.replace('# A short scalar solve', 'if lane==0:work[w,0]+=1\n        # A short scalar solve')
 source=source.replace('for outer in range(60):','for outer in range(60):\n            if lane==0:work[w,1]+=1')
 source=source.replace('for outer in range(60):','previous=wp.tile_zeros(shape=(1,nv),dtype=float,storage="shared")\n        for outer in range(60):',1)
 source=source.replace('for it in range(iterations):','for it in range(iterations):\n                if wp.static(convergence_stop):wp.tile_assign(previous,v)\n                if lane==0:work[w,2]+=1')
 convergence_code='''if wp.static(convergence_stop):
                    if it%8==7:
                        change=wp.tile_extract(wp.tile_max(wp.tile_map(absolute,v-previous)),0)
                        if change<=2e-6:
                            residual=float(0.)
                            for c in range(p.nlimit[w]):
                                jj=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                                gap=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jj,v)),0)+p.limit_compliance[w,c]*p.limit_impulse[w,c]-p.limit_target[w,c]
                                err=wp.max(0.,-gap)
                                if p.limit_bilateral[w,c]!=0 or p.limit_impulse[w,c]>0.:err=wp.abs(gap)
                                residual=wp.max(residual,err)
                            for c in range(p.ncontact[w]):
                                jj=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                                speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jj,v)),0)
                                err=wp.max(0.,-speed)
                                if p.contact_impulse[w,c,0]>0.:err=wp.abs(speed)
                                residual=wp.max(residual,err)
                                if p.friction[w,c]>0.:
                                    j1=wp.tile_reshape(wp.tile_load(p.J[w,c,1],shape=(nv,)),shape=(1,nv))
                                    j2=wp.tile_reshape(wp.tile_load(p.J[w,c,2],shape=(nv,)),shape=(1,nv))
                                    v1=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j1,v)),0)
                                    v2=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j2,v)),0)
                                    old1=p.contact_impulse[w,c,1];old2=p.contact_impulse[w,c,2]
                                    t1=old1-v1/p.diagonal[w,c,1];t2=old2-v2/p.diagonal[w,c,2]
                                    bounds=friction_bound(p,w,c);length=wp.sqrt(t1*t1+t2*t2)
                                    scale=wp.min(1.,bounds[0]/wp.max(length,1e-30))
                                    residual=wp.max(residual,wp.abs(t1*scale-old1)*p.diagonal[w,c,1])
                                    residual=wp.max(residual,wp.abs(t2*scale-old2)*p.diagonal[w,c,2])
                                    if p.manifold.enabled:
                                        g=p.manifold.group[w,c]
                                        if p.manifold.size[w,g]>1:
                                            js=wp.tile_reshape(wp.tile_load(p.manifold.J[w,g,2],shape=(nv,)),shape=(1,nv))
                                            vs=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,js,v)),0)
                                            old=p.manifold.impulse[w,g,2]
                                            target=wp.clamp(old-vs/p.manifold.diagonal[w,g,2],-bounds[1],bounds[1])
                                            residual=wp.max(residual,wp.abs(target-old)*p.manifold.diagonal[w,g,2])
                            if residual<=2e-6:
                                if lane==0:
                                    cycles[w,0]+=1;cycles[w,1]+=iterations-it-1
                                break
                # No changed impulse'''
 # Keep candidate temporaries separate from the existing sweep. Reusing a
 # reshaped tile name inside the conditional makes Warp merge owning/view
 # shared tiles and produces invalid generated CUDA, even with equal shapes.
 import re
 for name in ('j1','j2','v1','v2','old1','old2','t1','t2','bounds','length','scale','g','speed','old','target'):
  convergence_code=re.sub(r'\b'+name+r'\b','check_'+name,convergence_code)
 source=source.replace('# No changed impulse',convergence_code)
 cycle_code='''if wp.static(exact_cycles):
                    equal=int(1);parity=it%2
                    for k in range(lane,nv,32):
                        value=wp.tile_extract(v,0,k)
                        if value!=history[w,parity,k]:equal=0
                        history[w,parity,k]=value
                    offset=nv
                    for k in range(lane,3*p.ncontact[w],32):
                        value=p.contact_impulse[w,k//3,k%3]
                        if value!=history[w,parity,offset+k]:equal=0
                        history[w,parity,offset+k]=value
                    offset+=3*p.contact_impulse.shape[1]
                    for k in range(lane,p.nlimit[w],32):
                        value=p.limit_impulse[w,k]
                        if value!=history[w,parity,offset+k]:equal=0
                        history[w,parity,offset+k]=value
                    offset+=p.limit_impulse.shape[1]
                    if p.manifold.enabled:
                        for k in range(lane,p.manifold.count[w],32):
                            value=p.manifold.impulse[w,k,2]
                            if value!=history[w,parity,offset+k]:equal=0
                            history[w,parity,offset+k]=value
                    same=wp.tile_extract(wp.tile_min(wp.tile(equal)),0)
                    if it>=2 and same>0 and (iterations-it-1)%2==0:
                        if lane==0:
                            cycles[w,0]+=1;cycles[w,1]+=iterations-it-1
                        break
                # No changed impulse'''
 source=source.replace('# No changed impulse',cycle_code)
 path=out/'diagnostic_block_contact.py';path.write_text(source)
 spec=importlib.util.spec_from_file_location('diagnostic_block_contact',path);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 if '--compile-only' in sys.argv:
  wp.init();wp.set_device('cuda:0')
  for retry in (False,True):
   kernel=mod.make_block_iteration(40,34,warm_start=True,retry=retry,convergence_stop=True)
   kernel.module.load('cuda:0',32)
  print('Candidate CUDA compilation passed',flush=True)
  return
 torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
 folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
 cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
 os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
 env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
 engine=env._engine;guard=engine.transfer_floor_guard;custom=engine.transfer_contact
 warm=mod.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True)
 cold=mod.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True,retry=True)
 warm_cycle=mod.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True,exact_cycles='--cycles' in sys.argv,convergence_stop='--converged' in sys.argv)
 cold_cycle=mod.make_block_iteration(custom.p.nv,custom.p.nmotor,warm_start=True,retry=True,exact_cycles='--cycles' in sys.argv,convergence_stop='--converged' in sys.argv)
 custom.block_kernel=warm;custom.retry_block_kernel=cold
 wc=wp.zeros((512,3),dtype=int);cc=wp.zeros_like(wc)
 history=wp.zeros((512,2,custom.p.nv+4*custom.capacity+custom.p.limit_impulse.shape[1]),dtype=float)
 cycles=wp.zeros((512,2),dtype=int)
 original=wp.launch_tiled
 def launch(kernel,*args,**kwargs):
  if kernel is warm or kernel is warm_cycle:kwargs['inputs']=kwargs['inputs']+[wc,history,cycles]
  if kernel is cold or kernel is cold_cycle:kwargs['inputs']=kwargs['inputs']+[cc,history,cycles]
  return original(kernel,*args,**kwargs)
 wp.launch_tiled=launch
 graphs={}
 for enabled in (False,True):
  engine.transfer_floor_guard=guard if enabled else None;engine._build_graphs();graphs[enabled]=engine._graph
 if '--cycles' in sys.argv or '--converged' in sys.argv:
  custom.block_kernel=warm_cycle;custom.retry_block_kernel=cold_cycle
  engine._build_graphs();graphs['cycles']=engine._graph
 engine.transfer_floor_guard=guard;wp.launch_tiled=original
 restore(agent,ROOT/'Saved/MimicKitEquipment/parallel-floor-stopped-latest.zip');agent.eval();agent.set_mode(AgentMode.TEST)
 reports=[]
 trials=((True,True,False),(True,True,True),(True,True,True),(True,True,False)) if '--invalidate' in sys.argv else ((False,False,False),(False,True,False),(True,True,False),(True,False,False))
 if '--cycles' in sys.argv or '--converged' in sys.argv:trials=((True,True,False),('cycles',True,False),('cycles',True,False),(True,True,False))
 warm_state=wp.to_torch(custom.p.warm_state)
 for enabled,reset,invalidate in trials:
  engine._graph=graphs[enabled];env._reset_after_getup=reset
  torch.manual_seed(761);np.random.seed(761);custom.p.warm_state.zero_();obs,info=env.reset()
  wc.zero_();cc.zero_();cycles.zero_();frame_times=[]
  for tick in range(90):
   torch.cuda.synchronize();begun=time.perf_counter()
   with torch.no_grad():action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
   ids=torch.nonzero(done,as_tuple=False).flatten()
   if len(ids):
    obs,info=env.reset(ids)
    if invalidate:warm_state[ids]=0
   torch.cuda.synchronize();frame_times.append(time.perf_counter()-begun)
  recovery=env._recovery_rows.cpu().numpy();a=wc.numpy();b=cc.numpy()
  groups={}
  for name,mask in [('recovery',recovery),('other',~recovery)]:
   groups[name]=dict(rows=int(mask.sum()),warm_sum=a[mask].sum(0).tolist(),retry_sum=b[mask].sum(0).tolist(),warm_max=a[mask].max(0).tolist(),retry_max=b[mask].max(0).tolist())
  report=dict(guard=enabled,reset_at_clip_end=reset,invalidate=invalidate,seconds=sum(frame_times),frame_median=float(np.median(frame_times[10:])),groups=groups,cycles=cycles.numpy().sum(0).tolist())
  reports.append(report);print(json.dumps(report),flush=True)
  filename='contact-work-full-step.json' if '--full-step' in sys.argv else 'contact-work-converged.json' if '--converged' in sys.argv else 'contact-work-cycles.json' if '--cycles' in sys.argv else 'contact-work-invalidate.json' if '--invalidate' in sys.argv else 'contact-work.json'
  (out/filename).write_text(json.dumps(reports,indent=2))
if __name__=='__main__':main()
