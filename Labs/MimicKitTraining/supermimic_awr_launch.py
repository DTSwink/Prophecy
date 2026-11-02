"""Bounded native MimicKit AWR screen against the unmodified PPO objective."""
import hashlib
import json
from supermimic_kaggle import api, ROOT, OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-native-awr-race'
    previous=a.kernels_status(owner+'/prophecy-offpolicy-c51-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    receipt_path=OUT/'native-awr-launch.json'
    if receipt_path.exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    names=['supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py',
        'supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py',
        'supermimic_increments.py','supermimic_awr.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='(out/'+repr(n)+').write_text('+repr(s)+')\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1000
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','PROGRESS','EVALUATION','PILOT_COMPLETE','NATIVE_AWR_INSTALLED','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name,extra in [(0,'ppo',[]),(1,'awr',['--native-awr','--awr-replay-rollouts','4'])]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--horizon','32','--seconds','240','--fast','--noisy-eval','--native-ppo',
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
  if time.monotonic()>deadline:raise TimeoutError('Bounded native AWR screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete'] and r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
  print('CANDIDATE_FINISHED',n,'updates',r['accepted_actor_updates'],flush=True)
 print('NATIVE_AWR_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'native_awr.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'native_awr.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Native AWR Race',code_file='native_awr.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1250);receipt=type(response).to_dict(response)
    receipt.update(seconds_per_candidate=240,eval_interval=90,original_checkpoint=119475,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),
        candidate='Pinned existing MimicKit AWR target/actor-loss methods, temperature1 and weight cap20. FIFO last4 rollouts (up to131072 samples), independent32tick segments, recompute returns/advantage weights after critic fitting as in original AWR implementation. Same original number of critic/actor minibatch updates per NEW rollout; no fourfold update multiplier. PPO checkpoint architecture/optimizer state and actor LR1.125e-6, critic target formula, phase supervision, sigma0.075, task and full-rollout KLguard0.18 unchanged. This is an adaptation of replay AWR, not exact paper reproduction. First real rollout asserts exact critic target parity. No Q/dynamics fitting or derivatives.',
        timing_caveat='240s includes intermediate real noisy+deterministic evaluations. Setup/baseline/final evaluation separate; common compiled simulator cache reused, no pretrained world/Q model.')
    receipt_path.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
