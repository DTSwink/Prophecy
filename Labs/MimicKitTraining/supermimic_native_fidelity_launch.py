"""Bounded free conditional-gradient feasibility screen before any new learner."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-native-fidelity-probe'
    previous=a.kernels_status(owner+'/prophecy-multifidelity-probe')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    prior=json.loads((OUT/'prophecy-multifidelity-probe-v1-reports/verified-multifidelity.json').read_text())
    assert not prior['candidate_for_training_test']
    if (OUT/'native-fidelity-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-transfer-head-race/transfer.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names=['supermimic_native_fidelity.py','supermimic_rollout_calibration.py',
           'supermimic_race.py','supermimic_imagined_exact.py','supermimic_exact_reward.py',
           'supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("NATIVE_FIDELITY_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+420
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['NATIVE_FIDELITY_','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'original'),(1,'cap4')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_native_fidelity.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded conditional multifidelity probe expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete']
  assert r['actor_updates']==r['policy_max_abs_delta']==0
 print('NATIVE_FIDELITY_SCREEN_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'native_fidelity.py','exec');target=OUT/slug;target.mkdir(exist_ok=True)
    (target/'native_fidelity.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-transfer-head-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Native Fidelity Probe',code_file='native_fidelity.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (target/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(target),timeout=650);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,parent_seconds_bound=420,
        recipe='Frozen96009 original native100/50 versus Newton/line-search caps4/4. Same240Hz physics/30Hz policy, original task/motors/contact/limits/sigma.075. Warmup849210; heldout984210/984211 deterministic and noisy, full300tick normal and120tick perturbed. Verify actual GPU options and unchanged actor.',
        prospective_gate='At least1.5x warmed evaluation throughput, no more than1pp perturbed failure regression or2pp normal regression, no more than5% return regression. If pass, run matched-time training and evaluate both in ORIGINAL native physics. This is not a training-speed result.',
        accounting='Fresh simulation screen; no model fitting reused. Both workers420s parent/650s Kaggle bound; setup/warmup/evaluations retained.',
        source='https://mujoco.readthedocs.io/en/stable/mjwarp/index.html#solver-iterations and MFPG-PPO https://arxiv.org/pdf/2610.02505 AppendixA.6.3.',
        scope='Isolated native-physics fidelity/cost screen only, all weights frozen. No frequency changes, production changes or paid compute.')
    (OUT/'native-fidelity-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
