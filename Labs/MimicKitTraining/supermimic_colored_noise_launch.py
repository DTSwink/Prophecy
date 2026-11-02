"""Free bounded CN-PPO screen after planning-student analysis is complete."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-colored-ppo-race'
    status=a.kernels_status(owner+'/prophecy-planning-student-race')
    assert type(status).to_dict(status)['status']=='COMPLETE'
    prior=json.loads((OUT/'prophecy-planning-student-race-v1-reports/verified-student.json').read_text())
    assert not prior['candidate_for_longer_independent_confirmation']
    if (OUT/'colored-ppo-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-native-planning-probe/planning.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    names=['supermimic_planning_student.py','supermimic_planning_probe.py','supermimic_race.py','supermimic_colored_noise.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for name,source in sources.items():code+='\n(out/'+repr(name)+').write_text('+repr(source)+')\n'
    hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()}
    provenance=json.loads((OUT/'research/cn-ppo/provenance.json').read_text())
    code+='(out/"CN-PPO-provenance.json").write_text('+repr(json.dumps(provenance))+')\n'
    code+='(out/"CN-PPO-LICENSE").write_text('+repr((OUT/'research/cn-ppo/LICENSE').read_text())+')\n'
    code+='print("COLORED_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1100
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['STUDENT_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name,beta in [(0,'white',0.),(1,'colored',.5)]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_planning_student.py'),'--root',str(root),
        '--checkpoint',str(checkpoint),'--output',str(folder),'--arm','ppo','--seconds','300',
        '--training-seed','849130','--evaluation-seed','984130','--noise-beta',str(beta)]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded colored PPO race expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete'] and r['accepted_actor_updates']>0
  assert r['noise_audit']['calls']==32*r['accepted_actor_updates'] and r['actor_parameter_delta_l2']>0
 print('COLORED_PPO_RACE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'colored_ppo.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'colored_ppo.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-native-planning-probe/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Colored PPO Race',code_file='colored_ppo.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1200);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,primary_commit=provenance['commit'],
       recipe='CN-PPO arxiv2312.11091v2/official source f242244. NativePPO restored96009/task/Adam unchanged. Sampling-only beta0 versus beta.5;1024-long Gaussian sequences, no episode resets, existing sigma.075. Torch FFT with exact theoretical marginal variance1 (not per-sequence normalization), time-major GPU cache. Gaussian marginal logprob unchanged as authors; no claim of exact correlated trajectory ratios. Both300s learning, early regression check150s; final independent984130/131 full300normal/120pert, deterministic and original iid exploration. Seed849130. Audit actual noise RMS,lag1,callcount and parameter updates. Three CPU checks pass. Gate: >=1pp fewer noisy failures than control plus positive paired return interval; no>1pp normal/deterministic regression. Require longer independent training seeds before promotion. No learned model, demonstration reuse, paid resources or production changes.')
    (OUT/'colored-ppo-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
