"""Free, bounded frozen-model uncertainty screen; no learning or paid compute."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-uncertain-planner'
    for previous in ['prophecy-frozen-feature-student','prophecy-rwm-history-calibration']:
        state=a.kernels_status(owner+'/'+previous)
        assert type(state).to_dict(state)['status']=='COMPLETE'
    if (OUT/'uncertain-planner-launch.json').exists():
        state=a.kernels_status(owner+'/'+slug)
        assert type(state).to_dict(state)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-rwm-history-calibration/rwm.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code and 'rwm_source=' in code
    names=['supermimic_uncertain_planner.py','supermimic_rwm_history.py','supermimic_planning_probe.py',
           'supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_increments.py','supermimic_race.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("UNCERTAIN_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
matches=[p for p in Path('/kaggle/input').rglob('world_model.pt') if p.parent.name=='recurrent']
assert len(matches)==1,matches
model_file=matches[0]
assert hashlib.sha256(model_file.read_bytes()).hexdigest()=='0f0c6ca2bc1b53b410350db0b2f8cdd468ae52f3e3bc98fedb9e4c14ee2e0bb9'
print('UNCERTAIN_MODEL_VERIFIED',str(model_file),flush=True)
import threading
processes=[]
deadline=time.monotonic()+900
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['UNCERTAIN_','Traceback','Error']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,seed in enumerate([984180,984181]):
  name='seed_'+str(seed);folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_uncertain_planner.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--source',str(rwm_source),'--model-file',str(model_file),'--seed',str(seed)]
  if gpu==0:args+=['--calibration-owner']
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded uncertainty ranking screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete'] and r['policy_max_abs_delta']==r['world_max_abs_delta']==0
 print('UNCERTAIN_SCREEN_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'uncertain.py','exec');target=OUT/slug;target.mkdir(exist_ok=True)
    (target/'uncertain.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-rwm-history-calibration/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Uncertain Planner',code_file='uncertain.py',
                kernel_sources=[owner+'/prophecy-rwm-history-calibration'])
    assert meta['is_private'] and meta['enable_gpu']
    (target/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(target),timeout=1100);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,parent_seconds_bound=900,
        model_sha256='0f0c6ca2bc1b53b410350db0b2f8cdd468ae52f3e3bc98fedb9e4c14ee2e0bb9',
        recipe='Frozen original96009 policy and saved RWM.16fixed action-bias candidates includingzero;32tick modeled return plus originalcritic. First8tick bias only. Calibrate nonnegative optimism/disagreement coefficient on reset849180 trainingworlds,10% heldout diagnostics. Freeze before new984180/181starts. Compare raw/penalized/control in actual120tick MuJoCo deterministic and original iid sigma.075. All actor/world tensors unchanged. Adaptation, NOT faithful MOPO/PETS reproduction.',
        uncertainty='Maximum next-state normalized Euclidean ensemble distance from mean, five heads sharing GRU. Fit only candidate-minuszero score optimism versus cumulative candidate-minuszero uncertainty.',
        prospective_gate='Teacher candidate only if pooled noisyfailure>=1pp better, positive paired motion-cluster returnCI, bothseeds nonworse, deterministic/normal outcomes not>1pp worse, and model16candidate planning faster than measured native16candidate calibrationpool. For uncertainty claim also improve vs unpenalized. No policy-learning claim; normal rows evaluated120 rather than300ticks.',
        accounting='Prior326.300588s warm fitting+24.322179s collection+180.577244s recurrent fitting remains charged. New calibration/model-ranking/evaluations/setup reported separately.16fixedpool differs from prior2roundnativeCEM; not a direct algorithm comparison.',
        primary_sources=['https://arxiv.org/abs/2005.13239','https://github.com/tianheyu927/mopo','https://arxiv.org/abs/1805.12114'])
    (OUT/'uncertain-planner-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
