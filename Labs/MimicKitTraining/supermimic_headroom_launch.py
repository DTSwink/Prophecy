"""Private frozen checkpoint/evaluation audit, on two free Kaggle T4s."""
import hashlib
import io
import json
import zipfile

from supermimic_kaggle import api, ROOT, OUT

EARLY = ROOT/'Saved/MimicKitLocomotion/preserved-latest/20261021_171453_uefn_locomotion_ae30_mse30_yaw180_1024/checkpoint_0096009_final.zip'
EARLY_SHA = '837b98a83ec5e86219bfbb2a1fd100054f6889c865f4f2e61b8dcddae4042542'
DATASET = 'prophecy-supermimic-earlier96009'


def prepare():
    import torch
    assert hashlib.sha256(EARLY.read_bytes()).hexdigest() == EARLY_SHA
    folder = OUT/'earlier96009-dataset'; folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(EARLY) as z, zipfile.ZipFile(OUT/'dataset/checkpoint.zip') as original:
        assert z.testzip() is None
        a = torch.load(io.BytesIO(z.read('model.pt')), map_location='cpu', weights_only=True)
        b = torch.load(io.BytesIO(original.read('model.pt')), map_location='cpu', weights_only=True)
        assert a.keys() == b.keys() and all(a[k].shape == b[k].shape for k in a)
        for key in ['_obs_norm._mean','_obs_norm._std','_a_norm._mean','_a_norm._std']:
            assert torch.equal(a[key], b[key]), key
        members = {}
        for name in ['model.pt','resume_state.pt']:
            data = z.read(name); (folder/name).write_bytes(data)
            members[name] = hashlib.sha256(data).hexdigest()
    provenance = dict(original_sha256=EARLY_SHA, original_checkpoint=96009, members=members,
        samples=1640431616, purpose='Frozen earlier policy under unchanged119475 experiment task; original training objective differed.',
        model_shapes_match=True, observation_and_action_normalizers_exactly_equal=True)
    (folder/'earlier96009-provenance.json').write_text(json.dumps(provenance, indent=2))
    a = api(); owner = a.config_values['username']
    (folder/'dataset-metadata.json').write_text(json.dumps(dict(title='Prophecy SuperMimic Earlier 96009',
        id=owner+'/'+DATASET, licenses=[dict(name='other')],
        description='Private original model and optimizer state for an isolated frozen-policy audit. No credentials.')))
    receipt_path = OUT/'earlier96009-dataset-upload.json'
    if receipt_path.exists():
        old = json.loads(receipt_path.read_text())
        assert old['members'] == members and old['original_sha256'] == EARLY_SHA
        print('EARLIER_DATASET_ALREADY_PREPARED', owner+'/'+DATASET, flush=True)
        return
    response = a.dataset_create_new(str(folder), public=False, quiet=True, convert_to_csv=False)
    receipt = dict(provenance, response=str(response), dataset=owner+'/'+DATASET)
    receipt_path.write_text(json.dumps(receipt, indent=2))
    print('EARLIER_DATASET_UPLOADED', json.dumps(receipt), flush=True)


def launch():
    a = api(); owner = a.config_values['username']; slug = 'prophecy-supermimic-headroom'
    state = a.kernels_status(owner+'/prophecy-native-awr-race')
    assert type(state).to_dict(state)['status'] == 'COMPLETE'
    receipt_path = OUT/'headroom-launch.json'
    if receipt_path.exists():
        current = a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ['COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED']
    provenance = json.loads((OUT/'earlier96009-dataset/earlier96009-provenance.json').read_text())
    code = (OUT/'prophecy-ppo-phase-stability-race/pilots.py').read_text().split('import threading\nprocesses=[]')[0]
    # A unique filename avoids interfering with the original dataset discovery.
    code += '''
early_provenance = next(Path('/kaggle/input').rglob('earlier96009-provenance.json'))
early_src = early_provenance.parent
early_receipt = json.loads(early_provenance.read_text())
assert early_receipt == EARLY_PROVENANCE
early_checkpoint = out/'early96009.zip'
with zipfile.ZipFile(early_checkpoint, 'w') as z:
 for name, digest in early_receipt['members'].items():
  data = (early_src/name).read_bytes()
  assert hashlib.sha256(data).hexdigest() == digest
  z.writestr(name, data)
print('EARLIER_CHECKPOINT_VERIFIED', early_receipt['original_sha256'], flush=True)
'''.replace('EARLY_PROVENANCE', repr(provenance))
    sources = {n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in ['supermimic_headroom.py','supermimic_race.py']}
    for n, s in sources.items():
        code += '(out/'+repr(n)+').write_text('+repr(s)+')\n'
    code += '''
import threading
processes=[]
deadline=time.monotonic()+700
def relay(name, process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['AUDIT_', 'Traceback', 'Error']):print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name,cp in [(0,'current',checkpoint),(1,'early',early_checkpoint)]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_headroom.py'),'--root',str(root),'--checkpoint',str(cp),'--output',str(folder)]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start()
  processes.append((name,process,thread));print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-5000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Frozen headroom audit expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  r=json.loads((out/n/'result.json').read_text())
  assert not p.returncode and r['complete'] and r['model_max_abs_delta']==0
 print('HEADROOM_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code, 'headroom.py', 'exec')
    folder = OUT/slug; folder.mkdir(exist_ok=True)
    (folder/'headroom.py').write_text(code, encoding='utf-8')
    meta = json.loads((OUT/'prophecy-ppo-phase-stability-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy SuperMimic Headroom',code_file='headroom.py')
    meta['dataset_sources'] = [x for x in meta['dataset_sources'] if not x.endswith('warm-start')]
    meta['dataset_sources'].append(owner+'/'+DATASET)
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response = a.kernels_push(str(folder), timeout=950)
    receipt = type(response).to_dict(response)
    receipt.update(source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
        code_sha256=hashlib.sha256(code.encode()).hexdigest(), earlier_checkpoint=provenance,
        audit='Frozen119475 versus96009 on identical119475 task: first120ticks and continuous480ticks, deterministic and sigma.075. No training or fitted-model reuse. Current shared compilation cache reused. Earlier weights came from a different objective; this is an evaluation audit, not a learning speed claim.')
    receipt_path.write_text(json.dumps(receipt, indent=2)); print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'prepare':prepare()
    elif sys.argv[1] == 'launch':launch()
    else:raise ValueError(sys.argv[1])
