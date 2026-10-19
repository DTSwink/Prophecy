"""Independent saved difficult equations and deliberate rejection controls."""
import importlib.util,sys
from make_register_contact_candidate import generate,ROOT
from test_block_cycle import main

precondition='--preconditioned' in sys.argv
production='--production' in sys.argv
if not production:
 path=generate(accelerated='--accelerated' in sys.argv or precondition,precondition=precondition)
 spec=importlib.util.spec_from_file_location('block_contact_gpu',path)
 candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
if precondition:
 import warp as wp
 kernels=set();buffers={};factory=candidate.make_block_iteration;launch=wp.launch_tiled
 def make(*a,**kw):
  k=factory(*a,**kw);kernels.add(k);return k
 def wrapped(k,*a,**kw):
  if k in kernels:
   p=kw['inputs'][0]
   if id(p) not in buffers:buffers[id(p)]=wp.zeros((p.velocity.shape[0],p.J.shape[1],3),dtype=float,device=p.velocity.device)
   kw['inputs']=kw['inputs']+[buffers[id(p)]]
  return launch(k,*a,**kw)
 candidate.make_block_iteration=make;wp.launch_tiled=wrapped
folder=ROOT/'Saved/MimicKitEquipment/floor-recovery'/('production-register-reference' if production else 'preconditioned-reference' if precondition else 'accelerated-reference' if '--accelerated' in sys.argv else 'register-reference')
for graph in (False,True):main(graph=graph,report_dir=folder)
print('PASS independent float64, graph, stale branch rejection, finite warnings and nonfinite rejection',flush=True)
