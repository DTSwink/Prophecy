"""Bounded fit-dose diagnostic, only after the active CN confirmation is analyzed."""
import hashlib
import json
from supermimic_kaggle import api, ROOT, OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-planning-student-fit'
    prior=a.kernels_status(owner+'/prophecy-colored-ppo-confirmation')
    assert type(prior).to_dict(prior)['status']=='COMPLETE'
    conclusion=json.loads((OUT/'prophecy-colored-ppo-confirmation-v1-reports/verified-confirmation.json').read_text())
    assert not conclusion['promising_faster_learning'],'Replicate the promising result before another candidate'
    if (OUT/'student-fit-launch.json').exists():
        previous=a.kernels_status(owner+'/'+slug)
        assert type(previous).to_dict(previous)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-native-planning-probe/planning.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    names=['supermimic_planning_student.py','supermimic_planning_probe.py','supermimic_race.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("STUDENT_FIT_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1100
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['STUDENT_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'ppo'),(1,'student')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_planning_student.py'),'--root',str(root),
        '--checkpoint',str(checkpoint),'--output',str(folder),'--arm',name,'--seconds','300',
        '--training-seed','849160','--evaluation-seed','984160']
  if name=='student':args+=['--student-max-updates','50000','--audit-student']
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded planning-student fit audit expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete'] and r['accepted_actor_updates']>0
  if n=='student':
   assert r['original_parameter_max_abs_delta']==0 and r['teacher_data_bytes']>0
   assert hashlib.sha256((out/n/'teacher_data.pt').read_bytes()).hexdigest()==r['teacher_data_sha256']
 print('STUDENT_FIT_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'student_fit.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'student_fit.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-native-planning-probe/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Planning Student Fit',code_file='student_fit.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1200);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        training_seconds_ceiling_per_arm=300,parent_seconds_bound=1100,
        rationale='Prior student used215.58s total but211.96s for four teacher collections; remaining fitting/control work was only3.62s. Its1000-update cap left unused budget, and no same-data zero-target baseline was recorded. Check whether fitting longer learns heldout corrections, without changing teacher, architecture or deployment inputs.',
        recipe='Same96009/task/physics, restored nativePPO versus same frozen-base residual student. Seed849160, eval984160/161. Student four fresh planning batches charged to300s;50k update safety cap, time cap binding in expectation. Holdout-only model selection, log full train/heldout teacher and anchor MSE relative to zero at1000/5000/10000/20000 updates, save exact dataset withSHA. Keep all1000-update/default behavior unchanged for other callers. Full300normal/120pert real evaluations with and without original exploration,150s regression stop. No inference planner. Production and original checkpoints untouched.',
        gate='Diagnostics: does full-budget fitting reduce heldout teacher MSE at least10% versus zero while preserving anchors? This alone is NOT success. Use existing planning-student analyzer: require noisy failure>=1pp lower than equal-timePPO and positive paired returnCI, det/normal not>1pp worse, no regression stop. Require independent longer confirmation before speed claim. Include collection, setup, audit/save and eval costs; one trainingseed is only screening.',
        primary_sources=['https://arxiv.org/abs/2608.12063','https://papers.nips.cc/paper_files/paper/2024/file/01fb6de3360f9e32862665580e2c5853-Paper-Conference.pdf'],
        method_scope='Fit-dose diagnosis of prior native-CEM residual imitation, NOT a reproduction of SMPC2RL, SPO or MPO.')
    (OUT/'student-fit-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
