"""Bounded free comparison of SuperTrack-style output-layer transfer."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-transfer-head-race'
    previous=a.kernels_status(owner+'/prophecy-uncertain-planner')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    prior=json.loads((OUT/'prophecy-uncertain-planner-v1-reports/verified-uncertainty.json').read_text())
    assert not any(prior['candidate_for_distillation_race'].values())
    if (OUT/'transfer-head-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-target-critic-race/target_critic.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names=['supermimic_transfer_head.py','supermimic_pilot.py','supermimic_imagined_exact.py',
           'supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py',
           'supermimic_equivariant.py','supermimic_increments.py']
    sources={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in names}
    for n,s in sources.items():code+='\n(out/'+repr(n)+').write_text('+repr(s)+')\n'
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()}
    code+='print("TRANSFER_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+800
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(m in line for m in ['TRANSFER_','BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'full'),(1,'heads')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_transfer_head.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded output-layer transfer screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete']
  assert r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
  assert r['output_layer_transfer']['head_parameter_delta_l2']>0
 heads=json.loads((out/'heads/result.json').read_text());full=json.loads((out/'full/result.json').read_text())
 assert heads['output_layer_transfer']['feature_max_abs_delta']==0 and full['output_layer_transfer']['feature_max_abs_delta']>0
 print('TRANSFER_SCREEN_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'transfer.py','exec');target=OUT/slug;target.mkdir(exist_ok=True)
    (target/'transfer.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-target-critic-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Transfer Head Race',code_file='transfer.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (target/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(target),timeout=1000);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,parent_seconds_bound=800,
        seconds_per_arm_including_checks=240,
        rationale='SuperTrack section5.2 freezes all but the final policy layer for transfer. Earlier tests updated all pretrained actor features; frozen-feature supervisedBC is a different algorithm and did not test this model-gradient constraint.',
        recipe='Original96009, native task/physics and sigma.075, same warm IncrementWorld and online model/critic fitting.8tick stochastic BPTT,Adam1.125e-6(.9,.95),1024batch. Full actor versus hidden layers frozen with motor/phase output layers trainable; fixed Gaussian logstd preserved. Input-state derivatives through frozen features retained. Seed849190; heldout984190/984191.75s det/noisy checks and existing early regression stops.',
        prospective_gate='Requires own starting noisyfailure improve>=1pp, full-actor comparison>=2pp better and positive paired returnCI, no>1pp deterministic/normal regressions, real headupdates, hiddenfeatures unchanged, approximately matched actual learning time. Only then independent nativePPO confirmation with300tick normal horizons.120tick screen is not production promotion.',
        accounting='Prior326.300588s world-model preparation plus new setup/warmup/fitting/checks/learning/evaluation explicitly retained. No end-to-end speed claim from reusing fitted model.',
        source='SuperTrack section5.2 https://static-wordpress.akamaized.net/montreal.ubisoft.com/wp-content/uploads/2021/11/24183638/SuperTrack.pdf',
        scope='Adapted final-layer transfer ablation, not faithful SuperTrack reproduction. No production or paid compute changes.')
    (OUT/'transfer-head-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
