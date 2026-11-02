"""FastTD3-style real-transition C51 adapter versus original PPO."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-offpolicy-c51-race'
    previous=a.kernels_status(owner+'/prophecy-supermimic-direct-tracking')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'offpolicy-c51-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    sources={name:(ROOT/'Labs/MimicKitTraining'/name).read_text() for name in (
        'supermimic_pilot.py','supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py','supermimic_offpolicy.py','vendor/holosoma_fast_sac.py','vendor/holosoma_LICENSE','vendor/holosoma_NOTICE','vendor/holosoma_provenance.json')}
    code+="(out/'vendor').mkdir(exist_ok=True)\n"
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1100

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','OFFPOLICY_START','OFFPOLICY_PHASE_PARITY','Q_WARMUP','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)

try:
 for gpu,name,extra in [(0,'ppo',['--native-ppo']),
                         (1,'c51_td3',['--offpolicy-td3','--actor-lr','3e-5','--offpolicy-bc-alpha','2.5'])]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--horizon','32','--seconds','240','--fast','--noisy-eval',
        '--actor-lr','1.125e-6','--eval-interval','60','--training-seed','57361']+extra
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
  if time.monotonic()>deadline:raise TimeoutError('Bounded off-policy C51 test expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
  r=json.loads((out/n/'result.json').read_text())
  assert r['complete']
  print('CANDIDATE_FINISHED',n,'actor_updates',r['accepted_actor_updates'],flush=True)
 print('OFFPOLICY_C51_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'offpolicy_c51.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'offpolicy_c51.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Offpolicy C51 Race',code_file='offpolicy_c51.py')
    meta['dataset_sources']=[x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1350);receipt=type(response).to_dict(response)
    receipt.update(seconds_per_candidate=240,budget_includes_intermediate_evaluation=True,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=119475,
        candidate='PPO versus checkpoint-compatible FastTD3-style adaptation using official pinned Holosoma C51 critic. Same task, original policy/normalizers, fixed exploration0.075, deterministic phase feedback. New action-value critic, mean Q, three-step returns, pre-reset timeout bootstrap and zero failure bootstrap, support[-105,105],2048batch, two Q steps per simulator tick, delayed actor, Polyak0.005. Frozen actor256tick real-data warmup then at most90s Qfit, heldout every5s and restore best critic+optimizer, early stop after30s minimum and15s without validation improvement; actor gate heldout MSE<half constant and correlation>0.6. TD3+BC normalized Q objective alpha2.5 plus action regression; retain50% initial real data in each batch with50% current replay. Warmup counts inside240s with60s real checks (first candidate check at least20s after warmup). ActorAdam3e-5 with existing0.18 KL rollback; criticAdamW3e-4. Not a faithful whole-framework reproduction. Early actual-simulator regression stop, original checkpoint preserved.',
        timing_caveat='No reused world model. Compiled simulator cache reused equally. Baseline/setup, Q collection/warmup and evaluation timings separately retained; all Q preparation counts against240s wall budget.')
    (OUT/'offpolicy-c51-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':launch()
