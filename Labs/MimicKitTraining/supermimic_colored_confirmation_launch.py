"""Longer independent-seed test of the unresolved CN-PPO short screen."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-colored-ppo-confirmation'
    previous=a.kernels_status(owner+'/prophecy-target-critic-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    assert (OUT/'prophecy-target-critic-race-v1-reports/verified-comparison.json').exists()
    if (OUT/'colored-confirmation-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-native-planning-probe/planning.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    names=['supermimic_planning_student.py','supermimic_planning_probe.py','supermimic_race.py','supermimic_colored_noise.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for name,source in sources.items():code+='\n(out/'+repr(name)+').write_text('+repr(source)+')\n'
    hashes={name:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}
    provenance=json.loads((OUT/'research/cn-ppo/provenance.json').read_text())
    code+='(out/"CN-PPO-provenance.json").write_text('+repr(json.dumps(provenance))+')\n'
    code+='(out/"CN-PPO-LICENSE").write_text('+repr((OUT/'research/cn-ppo/LICENSE').read_text())+')\n'
    code+='print("COLORED_CONFIRMATION_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+3100
manifest=dict(complete=False,stages=[],planned_training_seeds=[849150,849151])
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['STUDENT_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for stage,seed in enumerate([849150,849151]):
  current=[]
  for index,(label,beta) in enumerate([('white',0.),('colored',.5)]):
   name=label+'_'+str(seed);gpu=(index+stage)%2
   folder=out/name;folder.mkdir(exist_ok=True)
   env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
   args=[sys.executable,'-u',str(out/'supermimic_planning_student.py'),'--root',str(root),
         '--checkpoint',str(checkpoint),'--output',str(folder),'--arm','ppo','--seconds','900',
         '--training-seed',str(seed),'--evaluation-seed',str(984150+stage*2),
         '--noise-beta',str(beta),'--check-interval','150']
   process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
   thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start()
   item=(name,process,thread);processes.append(item);current.append(item)
   print('WORKER_STARTED',name,'gpu',gpu,flush=True)
  while any(p.poll() is None for _,p,_ in current):
   print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in current],flush=True)
   for n,p,t in current:
    if p.poll() not in (None,0):
     t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
   candidate=out/('colored_'+str(seed))/'result.json'
   if candidate.exists() and json.loads(candidate.read_text()).get('stop_reason'):
    (out/('white_'+str(seed))/'STOP_REQUEST').write_text('Candidate failed its predeclared regression test')
   if time.monotonic()>deadline:raise TimeoutError('Bounded colored confirmation expired')
   time.sleep(15)
  reports={}
  for n,p,t in current:
   t.join(timeout=5);assert p.returncode==0
   r=json.loads((out/n/'result.json').read_text());reports[n.split('_')[0]]=r
   assert r['complete'] and r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
   assert r['noise_audit']['calls']==32*r['accepted_actor_updates']
   assert r['evaluation_preserves_training_rng']
  assert reports['white']['checkpoint_sha256']==reports['colored']['checkpoint_sha256']
  manifest['stages'].append(dict(seed=seed,arms=[n for n,p,t in current],
      stopped={n:r['stop_reason'] for n,r in reports.items()}))
  (out/'confirmation.json').write_text(json.dumps(manifest,indent=2))
  print('COLORED_CONFIRMATION_STAGE_COMPLETE',seed,flush=True)
  if reports['colored']['stop_reason']:
   manifest['remaining_stages_skipped']='Candidate failed early native-simulator regression gate';break
 manifest['complete']=True;(out/'confirmation.json').write_text(json.dumps(manifest,indent=2))
 print('COLORED_CONFIRMATION_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'colored_confirmation.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'colored_confirmation.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-native-planning-probe/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Colored PPO Confirmation',code_file='colored_confirmation.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=3300);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        parent_seconds=3100,learning_seconds_per_arm=900,training_seeds=[849150,849151],
        rationale='Prior300s CN-PPO screen was statistically unresolved for perturbed loco, not proof of no moderate gain. Native PPO itself gained only~1pp. Correlated noise did help normal noisy failures. Test two independent training seeds for900s actual learning each; swap GPU assignment on second seed. No hyperparameter selection from these seeds.',
        recipe='Same96009/frozen119475task/sigma.075/PPO and Adam; beta0 vs.5 cached1024 Gaussian sequence. All other settings identical. No learned-model fitting. Full300tick normal/120pert deterministic+production iid evaluation. Intermediate150s checks use both matched reset seeds and preserve training RNG; evaluation cannot consume training-noise cache. Reject candidate noisy perturbed failure >initial+5pp or normal det>3%; stop paired control and skip remaining seed if candidate fails. Per-seed final actual time must match within5s unless stopped; stopped comparisons not speed claims. All setup/check costs reported.',
        gate='For a promising faster-learning result require both seeds candidate noisy failure<=control and improved versus own start, average candidate reduction relative to control>=1pp, pooled paired return95%CI positive, no>1pp deterministic/normal regression per seed, both completed full budgets. Inspect matched learning curves, not only final endpoint. Independent seeds n=2 remains a precision limitation; report it.',
        primary_sources=['https://arxiv.org/html/2312.11091v2','https://github.com/jkbjh/cn-ppo-paper-code'])
    (OUT/'colored-confirmation-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
