"""Free, bounded native-MuJoCo planning-feasibility screen on two reset seeds."""
import hashlib
import json
from supermimic_kaggle import api, ROOT, OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-teacher-consistency'
    previous=a.kernels_status(owner+'/prophecy-native-fidelity-probe')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'teacher-consistency-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-ppo-short-world-race/ppo_world.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in ['supermimic_teacher_consistency.py','supermimic_race.py']}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    provenance=json.loads((OUT/'research/judo/provenance.json').read_text())
    code+='\n(out/"judo-provenance.json").write_text('+repr(json.dumps(provenance))+')\n'
    code+='(out/"JUDO-LICENSE").write_text('+repr((OUT/'research/judo/LICENSE').read_text())+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("PLANNING_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+500
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['PLANNING_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,seed in [(0,984220),(1,984221)]:
  name='seed_'+str(seed);folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_teacher_consistency.py'),'--root',str(root),
        '--checkpoint',str(checkpoint),'--output',str(folder),'--seed',str(seed)]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded planning screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete'] and r['actor_updates']==0 and r['policy_max_abs_delta']==0
 print('PLANNING_PROBE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'planning.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'planning.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-short-world-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Teacher Consistency',code_file='planning.py')
    meta['dataset_sources']=[d for d in meta['dataset_sources'] if not d.endswith('/prophecy-supermimic-increment-model')]
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=750);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        recipe='V2 measures three repeated zero32tick trajectories and per-tick action/obs drift before two independent16candidate CEM searches on fresh cohorts984220/984221. Save observations, residuals and scores; evaluate zero, two winners and their mean120ticks deterministic/noisy. Frozen96009, unchanged240Hz/30Hz/task/sigma.075.',
        parent_seconds_bound=500,accounting='Both searches/evaluations/setup charged. Prior teacher collection209.731s retained; no policy training or speedup claim.',
        next_gate='Mean must improve noisy physical return with paired95%CI above0 and reduce failures >=1pp versus zero on both cohorts before any new distillation trial. Independent winner variability alone is not proof of label failure.',
        research='POPLIN arxiv1906.08649 sections4.4/5.4 identifies action-space distillation collapse; guided policy search PMLR32/levine14 requires compatibility of teacher trajectories and policy. This diagnoses the issue, not a reproduction.',
        scope='Free Kaggle only, original simulator and weights unchanged, no production interference.')
    (OUT/'teacher-consistency-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
