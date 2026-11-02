"""Launch the predeclared free planning-student/native-PPO screen."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-planning-student-race'
    previous=a.kernels_status(owner+'/prophecy-native-planning-probe')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    verified=json.loads((OUT/'prophecy-native-planning-probe-v1-reports/verified-planning.json').read_text())
    assert verified['candidate_for_distillation_and_matched_ppo_race']
    if (OUT/'planning-student-launch.json').exists():
        status=a.kernels_status(owner+'/'+slug)
        assert type(status).to_dict(status)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-native-planning-probe/planning.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    names=['supermimic_planning_student.py','supermimic_planning_probe.py','supermimic_race.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for name,source in sources.items():code+='\n(out/'+repr(name)+').write_text('+repr(source)+')\n'
    hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()}
    code+='print("STUDENT_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
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
 for gpu,name in [(0,'ppo'),(1,'student')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_planning_student.py'),'--root',str(root),
        '--checkpoint',str(checkpoint),'--output',str(folder),'--arm',name,'--seconds','300']
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded planning-student race expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete'] and r['accepted_actor_updates']>0
 print('PLANNING_STUDENT_RACE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'student.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'student.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-native-planning-probe/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Planning Student Race',code_file='student.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1200);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        training_seconds_ceiling_per_arm=300,parent_seconds_bound=1100,
        recipe='Original96009/native physics/task unchanged. NativePPO restored Adam1.125e-6 versus zero-initial2x256SiLU motor residual student, original actor/phase/critic frozen. Student inputs existing154obs only. Four fresh training reset batches849120+1000..3; two8candidate CEM rounds actual32tick native score,8tick residual. Actual120tick teacher collection, equal early-target/zero-anchor BC Adam3e-4, at most1000updates, choose by whole-world heldout BC error only. All planning/collection/fit charged to300s ceiling; if done sooner compare shorter cost honestly. Eval fresh984120/121, full300normal/120pert, deterministic andsigma.075; early regression check at150s. Prospectively advance only if noisy failure>=1pp lower thanPPO and returnCI positive; det not>1pp worse and normal not>1pp worse. One trainingseed screen; require independent-seed longer confirmation before claiming speedup. No reused model fitting, no production changes.')
    (OUT/'planning-student-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
