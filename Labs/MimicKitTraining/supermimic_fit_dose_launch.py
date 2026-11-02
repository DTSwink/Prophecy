"""Paired bounded model-fit batch comparison; policy stays frozen."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch(capacity=False):
    a=api();owner=a.config_values['username'];slug='prophecy-supermimic-capacity' if capacity else 'prophecy-supermimic-fit-dose'
    receipt_name='capacity-launch.json' if capacity else 'fit-dose-launch.json'
    previous=a.kernels_status(owner+('/prophecy-supermimic-full-phase' if capacity else '/prophecy-supermimic-gradient-fidelity'))
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/receipt_name).exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    sources={name:(ROOT/'Labs/MimicKitTraining'/name).read_text() for name in (
        'supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py','supermimic_fit_dose.py','supermimic_decoupled.py','supermimic_capacity.py')}
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    code+='CAPACITY='+repr(capacity)+'\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+780

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','FIT_DOSE','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)

try:
 common=['--increment-model','--hard-imagined-failure','--imagined-exact','--exact-reward','--actor-batch','1024','--warm-model','increments-audited']
 variants=([(0,'width1024',common+['--fit-dose','256','--capacity-width','1024']),
            (1,'width2048',common+['--fit-dose','256','--capacity-width','2048'])] if CAPACITY else
           [(0,'batch256',common+['--fit-dose','256']),(1,'batch2048',common+['--fit-dose','2048'])])
 for gpu,name,extra in variants:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--horizon','32','--seconds','360','--fast',
        '--actor-lr','1.125e-6','--eval-interval','90','--training-seed','84731']+extra
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
  if time.monotonic()>deadline:raise TimeoutError('Bounded paired model-fit audit expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete'] and r['policy_parameter_delta_l2']==0. and r['actor_updates']==0
  print('CANDIDATE_FINISHED',n,'model_steps',r['checks'][-1]['steps'],flush=True)
 print('CAPACITY_COMPLETE' if CAPACITY else 'FIT_DOSE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'fit_dose.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'fit_dose.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy SuperMimic Capacity' if capacity else 'Prophecy SuperMimic Fit Dose',code_file='fit_dose.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    meta['dataset_sources'].append(owner+'/prophecy-supermimic-increment-model')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1000);receipt=type(response).to_dict(response)
    receipt.update(seconds_per_candidate=360,budget_includes_intermediate_evaluation=True,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=119475,
        candidate='Frozen original policy119475; same verified increment-model warm start, identical fresh262144 transitions and held-out worlds. Fit8-step windows for360s at batch256 versus2048, compare held-out H1/H8/H32 predictions using recorded and autoregressive policy actions. Check every60s; stop after consecutive20-percent forecast regressions. No policy-learning claim.',
        timing_caveat='Reuses preceding shared-data increment world-model fitting and compiled cache. Fit cost must be added before any speedup claim.')
    if capacity:
        receipt['candidate']='Frozen original119475 policy; verified warm increment model width1024 versus function-preserving doubling to2048. LayerNorm-aware Net2Wider-style duplicated units, cancelling outgoing perturbations permit independent learning. Same fresh262144 transitions, held-out worlds, frozen normalizers, batch256x8, Adam2e-4,360s fit with60s checks and early regression stops. GPU initial parity mandatory. Gate another actor test on >=15% lower H32 action forecast error without worse state error at matched fit time. No policy learning in this diagnostic.'
    (OUT/receipt_name).write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':launch()
