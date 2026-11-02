"""Bounded free-T4 screen: online versus SHAC-style target bootstrap critic."""
import hashlib
import json
from supermimic_kaggle import api,ROOT,OUT


def launch():
    a=api();owner=a.config_values['username'];slug='prophecy-target-critic-race'
    previous=a.kernels_status(owner+'/prophecy-colored-ppo-race')
    assert type(previous).to_dict(previous)['status']=='COMPLETE'
    assert (OUT/'prophecy-colored-ppo-race-v1-reports/verified-student.json').exists()
    if (OUT/'target-critic-launch.json').exists():
        current=a.kernels_status(owner+'/'+slug)
        assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCELED','CANCEL_ACKNOWLEDGED')
    code=(OUT/'prophecy-ppo-short-world-race/ppo_world.py').read_text().split('\nimport threading\nprocesses=[]')[0]
    assert 'EARLIER_CHECKPOINT_VERIFIED' in code
    names=['supermimic_target_critic.py','supermimic_pilot.py','supermimic_imagined_exact.py',
           'supermimic_exact_reward.py','supermimic_race.py','supermimic_structured.py',
           'supermimic_equivariant.py','supermimic_increments.py']
    sources={name:(ROOT/'Labs/MimicKitTraining'/name).read_text() for name in names}
    for name,source in sources.items():code+='\n(out/'+repr(name)+').write_text('+repr(source)+')\n'
    hashes={name:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}
    code+='print("TARGET_CRITIC_SOURCE_VERIFIED",'+repr(hashes)+',flush=True)\n'
    code+='''
import threading
processes=[]
deadline=time.monotonic()+1000
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['TARGET_CRITIC','BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','IMAGINED_SCORE_VERIFIED','PROGRESS','EVALUATION','PILOT_COMPLETE','SKELETON_OK','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
try:
 for gpu,name in [(0,'online'),(1,'target')]:
  folder=out/name;folder.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
  args=[sys.executable,'-u',str(out/'supermimic_target_critic.py'),'--root',str(root),'--checkpoint',str(checkpoint),
        '--output',str(folder),'--method',name]
  process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start();processes.append((name,process,thread))
  print('WORKER_STARTED',name,'gpu',gpu,flush=True)
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True);raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded target critic screen expired')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5);assert p.returncode==0
  r=json.loads((out/n/'result.json').read_text());assert r['complete']
  assert r['accepted_actor_updates']>0 and r['actor_parameter_delta_l2']>0
 left=json.loads((out/'online/result.json').read_text());right=json.loads((out/'target/result.json').read_text())
 assert left['checkpoint_sha256']==right['checkpoint_sha256']
 assert any(u['metrics'].get('target_delta_l2',0)>0 for u in right['updates'])
 assert not any(u['metrics'].get('separate_bootstrap_critic',False) for u in left['updates'])
 print('TARGET_CRITIC_RACE_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
'''
    compile(code,'target_critic.py','exec')
    folder=OUT/slug;folder.mkdir(exist_ok=True);(folder/'target_critic.py').write_text(code,encoding='utf-8')
    meta=json.loads((OUT/'prophecy-ppo-short-world-race/kernel-metadata.json').read_text())
    meta.update(id=owner+'/'+slug,title='Prophecy Target Critic Race',code_file='target_critic.py')
    assert meta['is_private'] and meta['enable_gpu'] and not meta['kernel_sources']
    (folder/'kernel-metadata.json').write_text(json.dumps(meta))
    response=a.kernels_push(str(folder),timeout=1200);receipt=type(response).to_dict(response)
    receipt.update(code_sha256=hashlib.sha256(code.encode()).hexdigest(),source_sha256=hashes,
        bounded_parent_seconds=1000,seconds_per_arm_including_checks=300,
        recipe='Same96009, warm IncrementWorld and8tick stochastic BPTT. Actor Adam1.125e-6(.9,.95), critic2e-4, original reward/termination/phase/exploration. Candidate changes only actor and lambda-return bootstrap to a frozen target critic: .4 old+.6 online after each critic fit. Online-critic BPTT control; not native-PPO comparison. Seed849140, eval984140/984141 det+production iid noise.90s checks stop regressions;120tick screening limits normal conclusions. Prospective lead>=2pp noisy perturbed failure and positive paired return95% interval, no>1pp det/normal regression. Requires longer independent-seed native-PPO confirmation with300tick normal before promotion. Prior326.300588s preparation additional; all setup/check/fitting cost reported. No paid compute or production changes.',
        primary_sources=['https://arxiv.org/abs/2204.07137','https://github.com/NVlabs/DiffRL/blob/a4c0dd1696d3c3b885ce85a3cb64370b580cb913/algorithms/shac.py'])
    (OUT/'target-critic-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':launch()
