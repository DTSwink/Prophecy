"""Bounded frozen-model diagnostic; reuse completed outputs, do not refit."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-model-rollout-calibration'
    previous=a.kernels_status(owner+'/prophecy-ppo-world-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    if (OUT/'rollout-calibration-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-ppo-world-race/ppo_world.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    source=(ROOT/'Labs/MimicKitTraining/supermimic_rollout_calibration.py').read_text()
    code+='\n(out/"supermimic_rollout_calibration.py").write_text('+repr(source)+')\n'
    provenance=json.loads((OUT/'ppo-world-v1-models/provenance.json').read_text())
    code+='artifacts='+repr(provenance)+'\n'
    code+='''
models={}
for name,receipt in artifacts['files'].items():
 matches=[p for p in Path('/kaggle/input').rglob(name) if p.parent.name=='ppo_world']
 assert len(matches)==1,(name,matches)
 p=matches[0];assert p.stat().st_size==receipt['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256']
 models[name]=str(p)
print('CALIBRATION_MODELS_VERIFIED',artifacts,flush=True)
import threading
processes=[]
deadline=time.monotonic()+600
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['CALIBRATION_','Error','Traceback']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'initial'),(1,'final')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_rollout_calibration.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--policy',name,'--model-file',models['world_model.pt'],'--policy-file',models['policy_final.pt']]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Frozen calibration expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  assert json.loads((out/n/'result.json').read_text())['complete']
 print('ALL_CALIBRATION_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'calibration.py','exec');folder=OUT/slug;folder.mkdir(exist_ok=True)
    (folder/'calibration.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-world-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Model Rollout Calibration',code_file='calibration.py',kernel_sources=[owner+'/prophecy-ppo-world-race'])
    assert meta['is_private'] and meta['enable_gpu']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=800);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),worker_sha256=hashlib.sha256(source.encode()).hexdigest(),
        reused_artifacts=provenance,kind='Frozen closed-loop model calibration; no actor/world updates. Initial96009 and completedPPO-WM policy against identical fitted world. Two independent new reset seeds, deterministic/production noise, four branch ages, horizons1/4/8/16/32, logged-control versus closed-loop. Native task unchanged;600s parent/800s Kaggle bound. Not a learning race.')
    (OUT/'rollout-calibration-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
