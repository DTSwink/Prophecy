"""Audit complete policy-update directions in MuJoCo, with a native PPO control."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-supermimic-policy-step'
    previous=a.kernels_status(owner+'/prophecy-supermimic-earlier-policy')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'policy-step-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    early_provenance=json.loads((OUT/'earlier96009-dataset/earlier96009-provenance.json').read_text())
    audit=json.loads((OUT/'prophecy-supermimic-headroom-reports/verified-headroom.json').read_text())
    assert audit['arms']['early']['modes']['noisy']['perturbed_loco']['first120_failure_percent']>15
    code+="\n"+"early_receipt="+repr(early_provenance)+"\n"
    code+='''
early_src=next(Path('/kaggle/input').rglob('earlier96009-provenance.json')).parent
assert json.loads((early_src/'earlier96009-provenance.json').read_text())==early_receipt
checkpoint=out/'checkpoint96009.zip'
with zipfile.ZipFile(checkpoint,'w') as z:
 for name,digest in early_receipt['members'].items():
  data=(early_src/name).read_bytes()
  assert hashlib.sha256(data).hexdigest()==digest
  z.writestr(name,data)
print('EARLIER_CHECKPOINT_VERIFIED',early_receipt['original_sha256'],flush=True)
'''
    sources={name:(ROOT/'Labs/MimicKitTraining'/name).read_text() for name in (
        'supermimic_policy_step_audit.py','supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py')}
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1000

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['POLICY_AUDIT','BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)

try:
 for gpu,name in [(0,'ppo'),(1,'model')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_policy_step_audit.py'),'--root',str(root),
        '--checkpoint',str(checkpoint),'--output',str(folder),'--method',name]
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
  if time.monotonic()>deadline:raise TimeoutError('Bounded stochastic full-imagination test expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete'] and r['final_model_max_abs_delta']==0 and r['original_proposal_l2']>0
  print('CANDIDATE_FINISHED',n,'proposal_l2',r['original_proposal_l2'],flush=True)
 print('POLICY_STEP_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'policy_step.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'policy_step.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy SuperMimic Policy Step',code_file='policy_step.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    meta['dataset_sources'].extend([owner+'/prophecy-supermimic-increment-model',owner+'/prophecy-supermimic-earlier96009'])
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1250);receipt=type(response).to_dict(response)
    receipt.update(bounded_parent_seconds=1000,training=False,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=96009,earlier_checkpoint=early_provenance,
        candidate='Whole-policy parameter-direction audit from96009. Worker0 takes one real native PPO rollout/update; worker1 uses first validated full-world actor update after fitting. Restore original critic and policy, then evaluate baseline and signed raw/normalized directions on two new seeds, deterministic and sigma.075. Normalized magnitude caps BOTH signs at action KL.05 on a separate calibration rollout. Original model restored exactly at completion. No selection/promoted checkpoint; this is a local gradient diagnostic, not a learning-speed result.',
        timing_caveat='Reuses preceding shared-data increment world-model fitting and compiled cache. Fit cost must be added before any speedup claim.')
    (OUT/'policy-step-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':launch()
