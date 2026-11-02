"""Bounded free conditional-gradient feasibility screen before any new learner."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-multifidelity-probe'
    previous=a.kernels_status(owner+'/prophecy-transfer-head-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    prior=json.loads((OUT/'prophecy-transfer-head-race-v1-reports/verified-transfer.json').read_text())
    assert not prior['candidate_for_independent_native_ppo_confirmation']
    if (OUT/'multifidelity-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-transfer-head-race/transfer.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names=['supermimic_multifidelity_probe.py','supermimic_rollout_calibration.py',
           'supermimic_race.py','supermimic_imagined_exact.py','supermimic_exact_reward.py',
           'supermimic_structured.py','supermimic_equivariant.py','supermimic_increments.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("MULTIFIDELITY_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+420
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['MULTIFIDELITY_','CALIBRATION_','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name,seed in [(0,'calibration',849200),(1,'validation',984200)]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  model=next(Path('/kaggle/input').rglob('increments-audited-world.pt'))
  args=[sys.executable,'-u',str(out/'supermimic_multifidelity_probe.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--model-file',str(model),'--seed',str(seed)]
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
  assert r['actor_updates']==r['policy_max_abs_delta']==r['world_max_abs_delta']==0
 print('MULTIFIDELITY_SCREEN_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'multifidelity.py','exec');target=OUT/slug;target.mkdir(exist_ok=True)
    (target/'multifidelity.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-transfer-head-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Multifidelity Probe',code_file='multifidelity.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (target/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(target),timeout=650);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,parent_seconds_bound=420,
        recipe='Frozen96009 and IncrementWorld, native original task and sigma.075. Calibration849200, heldout984200. Real120ticks, branches0/24/56/80, H8/32 GAE. Model coupled action epsilon plus4 independent copies from identical real state.64 fixed random motor-head gradient projections; all tensors frozen. Exact reward/FAIL parity. Coefficient fitted calibration only, evaluated heldout. No actor updates.',
        prospective_gate='Heldout gradient trace-variance ratio <.8 with95%world-cluster interval upper<1 and measured variance-times-cost<.95. Cost diagnostic conservatively reported with total actual computation; training comparison required regardless. No promotion from scalar-advantage correlation alone.',
        accounting='Prior326.300588s model preparation plus new setup/native capture/model branches/projection/analysis. Probe itself is diagnostic; no learning-speed claim.',
        source='MFPG-PPO https://arxiv.org/pdf/2610.02505 sections4.1 andA.2; QProp caveats https://arxiv.org/pdf/1802.10031 section4.1.',
        scope='Conditional same-state control-variate feasibility, not a faithful full MFPG-PPO reproduction. Real/learned critics are the same frozen checkpoint in this preliminary screen; no claim of optimal separate LF critics. No paid or production changes.')
    (OUT/'multifidelity-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
