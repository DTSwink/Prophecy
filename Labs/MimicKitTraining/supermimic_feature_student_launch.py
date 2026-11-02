"""Reuse the completed teacher dataset; do not recollect or duplicate live jobs."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-frozen-feature-student'
    prior=a.kernels_status(owner+'/prophecy-planning-student-fit')
    assert type(prior).to_dict(prior)['status']=='COMPLETE'
    folder=OUT/'prophecy-planning-student-fit-v1-reports'
    conclusion=json.loads((folder/'verified-student.json').read_text())
    assert not conclusion['candidate_for_longer_independent_confirmation']
    if (OUT/'feature-student-launch.json').exists():
        old=a.kernels_status(owner+'/'+slug)
        assert type(old).to_dict(old)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    reports={name:hashlib.sha256((folder/name/'result.json').read_bytes()).hexdigest() for name in ['ppo','student']}
    teacher=json.loads((folder/'student/result.json').read_text())
    code=(OUT/'prophecy-native-planning-probe/planning.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    names=['supermimic_feature_student.py','supermimic_planning_student.py','supermimic_planning_probe.py','supermimic_race.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("FEATURE_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='expected_reports='+repr(reports)+'\nexpected_teacher_sha='+repr(teacher['teacher_data_sha256'])+'\n'
    code+='''
matches=[p for p in Path('/kaggle/input').rglob('teacher_data.pt') if p.parent.name=='student']
assert len(matches)==1,matches
source=matches[0].parent.parent
assert hashlib.sha256(matches[0].read_bytes()).hexdigest()==expected_teacher_sha
for arm,digest in expected_reports.items():
 assert hashlib.sha256((source/arm/'result.json').read_bytes()).hexdigest()==digest
 assert (source/arm/'policy_final.pt').is_file()
print('FEATURE_REUSED_DATA_VERIFIED',str(source),expected_teacher_sha,flush=True)
import threading
processes=[]
deadline=time.monotonic()+600
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['FEATURE_','Traceback','Error']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'ppo'),(1,'features')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_feature_student.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--source',str(source),'--arm',name]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded frozen-feature fitting screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  assert json.loads((out/n/'result.json').read_text())['complete']
 print('FEATURE_SCREEN_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'features.py','exec');target=OUT/slug;target.mkdir(exist_ok=True)
    (target/'features.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-native-planning-probe/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Frozen Feature Student',code_file='features.py',kernel_sources=[owner+'/prophecy-planning-student-fit'])
    assert meta['is_private'] and meta['enable_gpu']
    (target/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(target),timeout=800);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        reused_reports_sha256=reports,teacher_data_sha256=teacher['teacher_data_sha256'],
        parent_seconds_bound=600,
        rationale='Full-budget raw-observation student overfits: heldout explained energy peaked9.9% at5000fits then fell to1.9% by20000, without physical gain. Test pretrained motor features with a small regularized output correction, reusing exact teacher data.',
        recipe='Original96009/frozen119475task,1024environments, native physics and sigma.075. Frozen512D pretrained actor features, bounded linear34D correction. Balanced teacher/zero-anchor ridge solve; alpha grid.0001/.001/.01/.1/1 selected only on heldout worlds. Phase/critic/base exactly preserved. Reuse teacher849160 and compare with its already-trained nativePPO79updates/301.679s. Evaluate old984160/161 and new984170/171 for300normal/120pert ticks, deterministic and original iid exploration. No new teacher collection or PPO training.',
        accounting='Charge prior209.731s collection plus new data loading/feature extraction/fitting/validation/saving; report prior586.822s complete student worker and new setup/evaluations separately. Cannot claim a fresh end-to-end speedup by ignoring reuse.',
        gate='Promising only if noisy failure>=1pp lower thanPPO on BOTH existing and fresh cohorts, positive pooled motion-cluster returnCI, det/normal not>1pp worse per cohort, unchanged base tensors, and collection+fit<=PPOlearning+5s. Then independent new teacher/trainingseed confirmation. One exact solve is a real fitted update, not thousands of SGD steps.',
        primary_source='https://static-wordpress.akamaized.net/montreal.ubisoft.com/wp-content/uploads/2021/11/24183638/SuperTrack.pdf',
        scope='Inspired by SuperTrack last-layer policy transfer. This is supervised planned-residual ridge fitting, NOT a SuperTrack reproduction.')
    (OUT/'feature-student-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
