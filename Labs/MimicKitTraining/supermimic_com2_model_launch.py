"""Free bounded task-aware COM2 model-prediction comparison."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-com2-model-calibration'
    previous=a.kernels_status(owner+'/prophecy-termination-calibration')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'com2-model-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-ppo-short-world-race/ppo_world.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names=['supermimic_rwm_history.py','supermimic_rollout_calibration.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    source=OUT/'research/rsl-rl-rwm'
    official={n:(source/'rsl_rl/modules/architectures'/n).read_text() for n in ['rnn.py','mlp.py']}
    official['LICENSE']=(source/'LICENSE').read_text()
    code+='\nrwm_source=out/"official-rwm";rwm_source.mkdir(exist_ok=True)\n'
    for n,s in official.items():code+='(rwm_source/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in {**sources,**official}.items()}
    code+='print("RWM_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+950
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['RWM_','CALIBRATION_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'control'),(1,'com2')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_rwm_history.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name,'--source',str(rwm_source),'--seconds','180','--task-calibration',
        '--task-gradient-ratio','0.5','--calibration-seeds','984103,984104']
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('RWM bounded diagnostic expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete'] and r['actor_updates']==0 and r['policy_max_abs_delta']==0
 left=json.loads((out/'control/result.json').read_text());right=json.loads((out/'com2/result.json').read_text())
 assert left['dataset_sha256']==right['dataset_sha256']
 print('ALL_RWM_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
 for name in ['rwm-shared-data.pt','rwm-shared-data.partial']:(out/name).unlink(missing_ok=True)
'''
    compile(code,'rwm.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'rwm.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-short-world-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy COM2 Model Calibration',code_file='rwm.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1200);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        official_commit='18eebcdd7145284c8d5eed5d8ed1a4b96c649693',seconds_per_arm=180,
        kind='V2: Frozen96009 policy; same warm model/data/Adam/180s as v1. Extra COM2 coefficient calibrated once so initial gradient norm is50% of state gradient, not50% of scalar loss. Two NEW evaluation seeds984103/984104, det/noisy. Prospective short-rollout gate:8tick closed-loop return MAE >=25% lower in both modes,32tick return MAE <=105% of control,8tick state NSE <=110%. V1 failed its original32tick gate and is not promoted. No actor update or learning-speed claim. Prior326.30s fitting extra; no production changes.')
    (OUT/'com2-model-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
