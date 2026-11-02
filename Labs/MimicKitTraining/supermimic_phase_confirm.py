"""Two independent, bounded free-Kaggle confirmations of the phase screen.

Each pair starts from the original checkpoint; nothing resumes an experimental
winner. Two T4s run the pair concurrently, then swap treatments for seed two.
"""
import hashlib
import json
from pathlib import Path

from supermimic_kaggle import ROOT, OUT, api


def launch():
    a=api(); owner=a.config_values['username']; slug='prophecy-ppo-phase-confirmation'
    previous=a.kernels_status(owner+'/prophecy-ppo-phase-stability-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'phase-confirmation-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    # The screen improved deterministic locomotion; noisy results were tied
    # within uncertainty. This is a replication, not a promotion decision.
    reports=OUT/'prophecy-ppo-phase-stability-race-reports'
    baseline=json.loads((reports/'ppo/result.json').read_text())
    candidate=json.loads((reports/'frozen_phase/result.json').read_text())
    for r in (baseline,candidate):
        assert r['complete'] and r['actor_parameter_delta_l2']>0
    assert candidate['final_phase_stability']['predictor_parameter_delta_l2']==0
    assert candidate['final_noisy_rates']['perturbed_loco']<=baseline['final_noisy_rates']['perturbed_loco']+1
    assert candidate['final_rates']['perturbed_loco']<baseline['final_rates']['perturbed_loco']
    # Reuse the manifest-verified, already exercised bootstrap. Embedded source
    # is refreshed below, before workers start. Never touch the production tree.
    original=(OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text()
    code=original.split('import threading\nprocesses=[]')[0]
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in (
        'supermimic_pilot.py','supermimic_phase_stability.py')}
    for name,source in sources.items():code+='(out/'+repr(name)+').write_text('+repr(source)+')\n'
    pairs=[[(0,'ppo_seed92719',92719,False),(1,'frozen_seed92719',92719,True)],
           [(0,'frozen_seed38147',38147,True),(1,'ppo_seed38147',38147,False)]]
    code+='''
import threading
all_reports=[]
deadline=time.monotonic()+1900

def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','PROGRESS','EVALUATION','PILOT_COMPLETE','Error','Traceback','SKELETON_OK']):
    print('['+name+'] '+line.rstrip(),flush=True)

for pair in PAIRS:
 processes=[]
 try:
  for gpu,name,seed,frozen in pair:
   folder=out/name;folder.mkdir(exist_ok=True)
   env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
   args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
         '--output',str(folder),'--horizon','1','--seconds','600','--native-ppo','--fast','--noisy-eval',
         '--phase-stability','--actor-lr','1.125e-6','--eval-interval','150','--training-seed',str(seed)]
   if frozen:args.append('--freeze-phase-predictor')
   process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
   thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start()
   processes.append((name,process,thread))
   print('WORKER_STARTED',name,'gpu',gpu,'seed',seed,flush=True)
  while any(p.poll() is None for _,p,_ in processes):
   print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
   for n,p,t in processes:
    if p.poll() not in (None,0):
     t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True)
     raise RuntimeError(n+' failed')
   if time.monotonic()>deadline:raise TimeoutError('Bounded phase confirmation expired')
   time.sleep(15)
  for n,p,t in processes:
   t.join(timeout=5)
   if p.returncode:raise RuntimeError(n+' failed')
   r=json.loads((out/n/'result.json').read_text())
   assert r['complete'] and r['actor_parameter_delta_l2']>0
   assert r['final_phase_stability']['predictor_parameter_delta_l2']==0
   all_reports.append(n)
  print('PAIR_COMPLETE',all_reports[-2:],flush=True)
 finally:
  for n,p,t in processes:
   if p.poll() is None:p.terminate()
  for n,p,t in processes:
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:p.kill()
print('PHASE_CONFIRMATION_COMPLETE',all_reports,flush=True)
'''.replace('PAIRS',repr(pairs))
    compile(code,'phase_confirmation.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'phase_confirmation.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy PPO Phase Confirmation',code_file='phase_confirmation.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=2100);receipt=type(response).to_dict(response)
    receipt.update(pairs=pairs,seconds_per_candidate=600,budget_includes_intermediate_evaluation=True,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(),original_checkpoint=119475)
    (OUT/'phase-confirmation-launch.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':launch()
