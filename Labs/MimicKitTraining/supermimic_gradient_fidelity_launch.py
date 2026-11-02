"""Bounded fixed-policy model-gradient audit; no new fitting or policy learning."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-supermimic-gradient-fidelity'
    previous=a.kernels_status(owner+'/prophecy-supermimic-critic-context')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'gradient-fidelity-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    sources={name:(ROOT/'Labs/MimicKitTraining'/name).read_text() for name in (
        'supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py','supermimic_gradient_fidelity.py','supermimic_decoupled.py')}
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+900

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','FIDELITY_AUDIT','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)

try:
 common=['--gradient-fidelity','--increment-model','--hard-imagined-failure','--imagined-exact','--exact-reward','--actor-batch','1024','--warm-model','increments-audited']
 for gpu,name,extra in [(0,'deterministic',common),
                         (1,'noisy',common+['--noisy-eval'])]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--horizon','32','--seconds','480','--fast',
        '--actor-lr','1.125e-6','--eval-interval','90','--training-seed','57361']+extra
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start()
  processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True)
    raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded gradient-fidelity audit expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete'] and r['policy_parameter_delta_l2']==0. and r['actor_updates']==0
  print('CANDIDATE_FINISHED',n,'verified_probes',len(r['probes']),flush=True)
 print('GRADIENT_FIDELITY_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'gradient_fidelity.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'gradient_fidelity.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy SuperMimic Gradient Fidelity',code_file='gradient_fidelity.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    meta['dataset_sources'].append(owner+'/prophecy-supermimic-increment-model')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1100);receipt=type(response).to_dict(response)
    receipt.update(seconds_per_candidate=480,budget_includes_intermediate_evaluation=True,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=119475,
        candidate='Read-only original-policy audit, same verified increment model. Analytic dense H1 and H32 with real forward states/learned Jacobian versus free H32 dense/full advice. Two reset seeds, two episode ages, matched +/-0.01 action probes followed through real 120-frame episodes; deterministic and production exploration. Initial command IDs preserved, autoregressive phase derivative retained, exact score/mean reconstruction checked. No learning claim.',
        timing_caveat='Reuses preceding shared-data increment world-model fitting and compiled cache. Fit cost must be added before any speedup claim.')
    (OUT/'gradient-fidelity-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':launch()
