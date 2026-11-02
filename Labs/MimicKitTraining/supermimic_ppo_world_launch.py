"""Compare native PPO using real versus learned simulator rollouts."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch(short=False):
    a=api();owner=a.config_values['username'];slug='prophecy-ppo-short-world-race' if short else 'prophecy-ppo-world-race'
    receipt_name='ppo-short-world-launch.json' if short else 'ppo-world-launch.json'
    previous=a.kernels_status(owner+('/prophecy-model-rollout-calibration' if short else '/prophecy-supermimic-policy-step'))
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/receipt_name).exists():
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
        'supermimic_ppo_world.py','supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py')}
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1000

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['PPO_WORLD_VERIFIED','BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)

try:
 for gpu,name in [(0,'ppo'),(1,'ppo_world')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_ppo_world.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name,'--seconds','300','--seed','57361']
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
  if time.monotonic()>deadline:raise TimeoutError('Bounded PPO-world test expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete']
  print('CANDIDATE_FINISHED',n,'actor_updates',r['accepted_actor_updates'],flush=True)
 print('PPO_WORLD_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    if short:
        calibration=json.loads((OUT/'prophecy-model-rollout-calibration-reports/verified-calibration.json').read_text())
        eight=calibration['arms']['final']['groups']['noisy/closed_loop/h8/perturbed_loco']
        long=calibration['arms']['final']['groups']['noisy/closed_loop/h32/perturbed_loco']
        assert long['return_mae']>4*eight['return_mae']
        code=code.replace("[(0,'ppo'),(1,'ppo_world')]","[(0,'ppo'),(1,'ppo_short')]")
    compile(code,'ppo_world.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'ppo_world.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy PPO Short World Race' if short else 'Prophecy PPO World Race',code_file='ppo_world.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    meta['dataset_sources'].extend([owner+'/prophecy-supermimic-increment-model',owner+'/prophecy-supermimic-earlier96009'])
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1250);receipt=type(response).to_dict(response)
    receipt.update(seconds_per_candidate=300,budget_includes_intermediate_evaluation=True,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=96009,earlier_checkpoint=early_provenance,
        candidate='PPO-WM control inspired by SuperMimic Figure5(b)/Section4.2. Earlier96009 under frozen119475 task, native PPO on real rollouts versus native PPO on32-step detached learned-model rollouts. Both restore original Adam moments/LRs; same critic targets, loss, noise, phase masks and KLguard. Model scored with audited analytic reward and perturbed hard failures; normal termination sampled from learned probability. Replay-state resets after imagined failure/timeout.300s including75s real checks and online collection/fitting. No world gradient reaches actor. Reused world326.30s extra. Screen, not exact paper replication.',
        timing_caveat='Reuses preceding shared-data increment world-model fitting and compiled cache. Fit cost must be added before any speedup claim.')
    if short:
        receipt['candidate']='Native real PPO versus native PPO with four independent8tick model segments per1024worlds, same32768transitions/update. TIME boundaries bootstrap the predicted endpoint, reset to real replay states and prevent GAE crossing; no artificial failure penalty. Other settings identical to preceding32tick test, including original audited warm model and online fitting cost. Calibration found32tick optimism and lower8tick error. Inspired by MBPO short branched rollouts; not a reproduction or verified speed gain.300s perarm with75s real checks; no production changes.'
        receipt['branch_horizon']=8
        receipt['model_validation_horizon']=8
        receipt['candidate']+=' v2 additionally matches held-out model-validation horizon to8ticks; v1 retained a32tick gate and paused actor updates unnecessarily for its shorter rollout length. Native batch still32768; gate error thresholds unchanged.'
    (OUT/receipt_name).write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':
    import sys
    launch(short='--short' in sys.argv[1:])
