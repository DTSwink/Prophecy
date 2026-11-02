"""Two free T4s: same model-based learner, ReLU versus calibrated smooth actor."""
import hashlib
import json
from supermimic_kaggle import api, ROOT, OUT


def launch():
    a = api(); owner = a.config_values['username']; slug = 'prophecy-smooth-actor-race'
    previous = a.kernels_status(owner+'/prophecy-failure-replay-calibration')
    assert type(previous).to_dict(previous)['status'] == 'COMPLETE'
    if (OUT/'smooth-actor-launch.json').exists():
        current = a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code = (OUT/'prophecy-ppo-short-world-race/ppo_world.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names = ['supermimic_smooth_actor.py','supermimic_policy_step_audit.py','supermimic_pilot.py',
             'supermimic_imagined_exact.py','supermimic_exact_reward.py','supermimic_race.py',
             'supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py']
    sources = {name: (ROOT/'Labs/MimicKitTraining'/name).read_text() for name in names}
    for name, source in sources.items():
        code += '\n(out/'+repr(name)+').write_text('+repr(source)+')\n'
    hashes = {n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code += 'print("SMOOTH_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code += '''
import threading
processes=[]
deadline=time.monotonic()+900
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['SMOOTH_','BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'relu'),(1,'smooth')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_smooth_actor.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded smooth actor experiment expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete']
  assert r['actor_activation']['parameter_max_abs_delta']==0
  assert r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
 left=json.loads((out/'relu/result.json').read_text());right=json.loads((out/'smooth/result.json').read_text())
 assert left['checkpoint_sha256']==right['checkpoint_sha256']
 print('SMOOTH_RACE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'smooth_actor.py','exec')
    folder = OUT/slug; folder.mkdir(exist_ok=True)
    (folder/'smooth_actor.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-short-world-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Smooth Actor Race',code_file='smooth_actor.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1100);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        bounded_parent_seconds=900,seconds_per_arm=240,
        candidate='Same frozen96009 weights and warm IncrementWorld. Same8tick stochastic analytic-reward BPTT learner, ReLU versus beta-SiLU. Select smooth beta from fixed grid on independent calibration observations to preserve mean/p99 action KL<=.001/.01 and phase RMS/max<=.002/.02; heldout can reject only. No parameter or critic change during preparation, no distillation. Reject initial real-simulator regression before learning. Same seeds849108 training and984107/984108 evaluation.240s including90s periodic real checks; early regression stop. Compare real failures/returns with and without production exploration; report actual updates. Prospective screening lead: >=2pp lower noisy perturbed failure plus positive paired return interval, deterministic/normal failures no more than1pp worse. Any lead needs independent longer nativePPO confirmation and full300tick normal evaluation. Prior326.30s model fit and both-arm preparation are additional. Free Kaggle only; production untouched.',
        sources=['https://github.com/CuboiLeo/SuperMimic-Reproduced/blob/main/src/supermimic/world_model/dynamics.py',
                 'https://github.com/zita-ch/supermimic_vibed/blob/main/supermimic/networks.py'])
    (OUT/'smooth-actor-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    launch()
