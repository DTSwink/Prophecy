"""Isolated private Kaggle experiments; no live-training or billing mutations."""
from contextlib import contextmanager
from pathlib import Path
import json
import hashlib,shutil,zipfile
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk import KaggleClient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/MimicKitSuperMimic'

@contextmanager
def token_client():
    # The installed legacy CLI lacks token support. Use its normal SDK with
    # the already-configured bearer token, without modifying global credentials.
    token = (Path.home()/'.kaggle/access_token').read_text().strip()
    with KaggleClient() as client:
        client._http_client._session.auth = None
        client._http_client._session.headers['Authorization'] = 'Bearer '+token
        yield client

def api():
    a=KaggleApi(); a.authenticate(); a.build_kaggle_client=token_client
    return a

def preflight():
    a=api(); username=a.config_values['username']
    p=OUT/'preflight'; p.mkdir(parents=True,exist_ok=True)
    code='''import json,platform,subprocess,time
from pathlib import Path
import torch
report=dict(python=platform.python_version(),torch=torch.__version__,cuda=torch.version.cuda,gpus=[])
for i in range(torch.cuda.device_count()):
 p=torch.cuda.get_device_properties(i)
 report['gpus'].append(dict(name=p.name,memory=p.total_memory,capability=[p.major,p.minor]))
report['nvidia_smi']=subprocess.run(['nvidia-smi'],capture_output=True,text=True).stdout
Path('/kaggle/working/preflight.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert report['gpus'], 'Kaggle did not allocate a GPU'
'''
    (p/'preflight.py').write_text(code)
    meta=dict(id=username+'/prophecy-supermimic-preflight',title='Prophecy SuperMimic Preflight',
        code_file='preflight.py',language='python',kernel_type='script',is_private=True,
        enable_gpu=True,enable_internet=True,dataset_sources=[],competition_sources=[],kernel_sources=[])
    (p/'kernel-metadata.json').write_text(json.dumps(meta,indent=2))
    r=a.kernels_push(str(p),timeout=120)
    result=type(r).to_dict(r)
    (OUT/'preflight-launch.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))

def prepare_data():
    plan=json.loads((ROOT/'Saved/MimicKitLocomotion/getup-success-prepared.json').read_text())
    p=OUT/'dataset';p.mkdir(parents=True,exist_ok=True)
    receipt={}
    for kind,name in [('checkpoint','checkpoint.zip'),('source','source.zip')]:
        item=plan[kind]; f=Path(item['local'])
        assert hashlib.sha256(f.read_bytes()).hexdigest()==item['sha256']
        with zipfile.ZipFile(f) as z:
            assert z.testzip() is None
            assert not any(any(w in n.lower() for w in ['private.json','credentials','.pem','.env','access_token']) for n in z.namelist())
        shutil.copyfile(f,p/name);receipt[kind]=item
    receipt['checkpoint_role']='Exact initialization checkpoint of the currently running locomotion continuation; isolated copy'
    (p/'provenance.json').write_text(json.dumps(receipt,indent=2))
    a=api();username=a.config_values['username']
    meta=dict(title='Prophecy SuperMimic Private Race',id=username+'/prophecy-supermimic-private-race',
              licenses=[{'name':'other'}],description='Private frozen inputs for an isolated learning-speed comparison. No credentials.')
    (p/'dataset-metadata.json').write_text(json.dumps(meta))
    r=a.dataset_create_new(str(p),public=False,quiet=True,convert_to_csv=False)
    print(r)

def runtime_preflight():
    a=api();username=a.config_values['username'];p=OUT/'runtime-preflight';p.mkdir(parents=True,exist_ok=True)
    code='''import subprocess,sys,json,zipfile,os,hashlib,time,shutil
from pathlib import Path
out=Path('/kaggle/working');src=Path('/kaggle/input/prophecy-supermimic-private-race')
if not src.exists():src=next(p.parent for p in Path('/kaggle/input').rglob('provenance.json') if (p.parent/'checkpoint/model.pt').exists())
receipt=json.loads((src/'provenance.json').read_text())
root=out/'runtime';root.mkdir(exist_ok=True)
for kind,files in MANIFEST.items():
 for n,digest in files.items():
  f=src/kind/n
  assert hashlib.sha256(f.read_bytes()).hexdigest()==digest, str(f)
shutil.copytree(src/'source',root,dirs_exist_ok=True)
checkpoint=out/'checkpoint.zip'
with zipfile.ZipFile(checkpoint,'w') as z:
 for n in MANIFEST['checkpoint']:z.write(src/'checkpoint'/n,n)
for p in root.rglob('*.yaml'):
 p.write_text(p.read_text().replace('/workspace/mimickit_trial',str(root)))
subprocess.run([sys.executable,'-m','pip','install','--quiet','mujoco==3.5.0','mujoco-warp==3.5.0.2','warp-lang==1.12.1','newton==1.0.0','newton-actuators==0.1.1','pyglet==2.1.19','gymnasium','tensorboardX'],check=True)
os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')]
os.chdir(root/'MimicKit')
import torch,warp as wp,yaml
torch.set_num_threads(2);wp.init();wp.set_device('cuda:0')
from util import mp_util
mp_util.init(0,1,'cuda:0',6793)
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
r=restore(agent,checkpoint);agent._init_train();agent._curr_obs,agent._curr_info=agent._reset_envs()
start=time.perf_counter();metrics=agent._train_iter();torch.cuda.synchronize()
result=dict(gpu=torch.cuda.get_device_name(),torch=torch.__version__,restored=r,update_seconds=time.perf_counter()-start,
 metrics={k:float(v) for k,v in metrics.items()})
(out/'runtime-preflight.json').write_text(json.dumps(result,indent=2));print('RUNTIME_PREFLIGHT',json.dumps(result))
'''
    manifest={}
    for kind in ['source','checkpoint']:
        with zipfile.ZipFile(OUT/'dataset'/(kind+'.zip')) as z:
            manifest[kind]={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/')}
    code=code.replace('MANIFEST',repr(manifest))
    (p/'runtime_preflight.py').write_text(code)
    meta=dict(id=username+'/prophecy-supermimic-runtime-preflight',title='Prophecy SuperMimic Runtime Preflight',
        code_file='runtime_preflight.py',language='python',kernel_type='script',is_private=True,enable_gpu=True,
        enable_internet=True,dataset_sources=[username+'/prophecy-supermimic-private-race'],kernel_sources=[],competition_sources=[])
    (p/'kernel-metadata.json').write_text(json.dumps(meta))
    r=a.kernels_push(str(p),timeout=900);result=type(r).to_dict(r)
    (OUT/'runtime-preflight-launch.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

def launch_race(seconds=1800):
    a=api();username=a.config_values['username'];p=OUT/'race';p.mkdir(parents=True,exist_ok=True)
    # Reuse the exact manifest-checked Kaggle bootstrap, before any GPU imports.
    bootstrap=(OUT/'runtime-preflight/runtime_preflight.py').read_text().split("os.environ['PYGLET_HEADLESS']")[0]
    bootstrap+="\n(out/'runtime_provenance.json').write_text(json.dumps(dict(original=receipt,verification='Every extracted source/checkpoint member SHA256 matched original archives'),indent=2))\n"
    runner=(ROOT/'Labs/MimicKitTraining/supermimic_race.py').read_text()
    code=bootstrap+'\n'+"(out/'supermimic_race.py').write_text("+repr(runner)+")\n"
    code+='''
processes=[]
for gpu,method in enumerate(['ppo','world_model']):
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2')
 folder=out/method;folder.mkdir(exist_ok=True)
 log=(out/(method+'.log')).open('w')
 args=[sys.executable,'-u',str(out/'supermimic_race.py'),'--root',str(root),'--checkpoint',str(checkpoint),
       '--output',str(folder),'--method',method,'--seconds',SECONDS]
 processes.append((method,subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT),log))
deadline=time.monotonic()+TOTAL_TIMEOUT
try:
 while any(p.poll() is None for _,p,_ in processes):
  for method,p,log in processes:
   if p.poll() not in (None,0):
    print((out/(method+'.log')).read_text()[-12000:]);raise RuntimeError(method+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Bounded Kaggle comparison expired')
  time.sleep(10)
 for method,p,log in processes:
  if p.returncode:raise RuntimeError(method+' failed')
 print('RACE COMPLETE: inspect ppo/result.json and world_model/result.json')
finally:
 for method,p,log in processes:
  if p.poll() is None:p.terminate()
 for method,p,log in processes:
  try:p.wait(timeout=15)
  except subprocess.TimeoutExpired:p.kill()
  log.close()
'''.replace('SECONDS',repr(str(seconds))).replace('TOTAL_TIMEOUT',str(seconds+1800))
    (p/'race.py').write_text(code)
    meta=dict(id=username+'/prophecy-supermimic-vs-ppo',title='Prophecy SuperMimic vs PPO',code_file='race.py',
        language='python',kernel_type='script',is_private=True,enable_gpu=True,enable_internet=True,
        dataset_sources=[username+'/prophecy-supermimic-private-race'],kernel_sources=[],competition_sources=[])
    (p/'kernel-metadata.json').write_text(json.dumps(meta))
    r=a.kernels_push(str(p),timeout=seconds+2400);result=type(r).to_dict(r)
    (OUT/'race-launch.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

def prepare_warm_data():
    """Keep only verified fitted weights; avoid mounting entire prior outputs."""
    p=OUT/'warm-dataset';p.mkdir(exist_ok=True)
    model=OUT/'cautious-world-model.pt'
    expected='6b1296f404065ac69e2c3987999d6601d468d6378c23c7991c77459044557cec'
    if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest()!=expected:
        with token_client() as c:
            h=c._http_client
            url=h._endpoint.rstrip('/')+'/api/v1/kernels/output/download/madmad74100/prophecy-supermimic-cautious-pilots/small_step/world_model.pt'
            with h._session.get(url,params={'versionNumber':1},stream=True,timeout=(15,60)) as r:
                r.raise_for_status()
                with model.with_suffix('.partial').open('wb') as f:
                    for chunk in r.iter_content(1024*1024):f.write(chunk)
        assert hashlib.sha256(model.with_suffix('.partial').read_bytes()).hexdigest()==expected
        model.with_suffix('.partial').replace(model)
    with zipfile.ZipFile(p/'small_step.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(model,'world_model.pt')
    (p/'warm-model.json').write_text(json.dumps(dict(source='madmad74100/prophecy-supermimic-cautious-pilots',
        version=1,file='small_step/world_model.pt',sha256=expected),indent=2))
    meta=dict(title='Prophecy SuperMimic Warm Start',id='madmad74100/prophecy-supermimic-warm-start',
              licenses=[{'name':'other'}],description='Private verified fitted model for isolated experiments.')
    (p/'dataset-metadata.json').write_text(json.dumps(meta))
    r=api().dataset_create_new(str(p),public=False,quiet=True,convert_to_csv=False)
    print('WARM_DATA_UPLOADED',r,'sha256',expected,flush=True)


def prepare_direction_data():
    """Preserve the audited derivative model privately, without notebook outputs."""
    import torch
    ref='madmad74100/prophecy-supermimic-direction-model-audit'
    state=api().kernels_status(ref)
    assert type(state).to_dict(state)['status']=='COMPLETE'
    audit=json.loads((OUT/'prophecy-supermimic-direction-model-audit-reports'/'directional'/'result.json').read_text())
    assert audit['complete'] and audit['policy_parameter_delta_l2']==0
    assert audit['gradient_audit']['passed'] and audit['provenance']['directional_supervision']
    p=OUT/'direction-dataset';p.mkdir(exist_ok=True)
    model=p/'directional-world-model.pt'
    hashes=[]
    for repeat in range(2):
        with token_client() as c:
            h=c._http_client
            url=h._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/directional/world_model.pt'
            with h._session.get(url,params={'versionNumber':1},stream=True,timeout=(15,60)) as r:
                r.raise_for_status();digest=hashlib.sha256()
                with model.with_suffix('.partial').open('wb') as f:
                    for chunk in r.iter_content(1024*1024):f.write(chunk);digest.update(chunk)
            hashes.append(digest.hexdigest())
    assert hashes[0]==hashes[1]
    weights=torch.load(model.with_suffix('.partial'),map_location='cpu',weights_only=True)
    assert weights['directional_supervision'] and not weights['integrated'] and not weights['regularized']
    assert all(torch.isfinite(v).all() for v in weights['model'].values())
    model.with_suffix('.partial').replace(model)
    receipt=dict(source=ref,version=1,sha256=hashes[0],bytes=model.stat().st_size,
        prior_fit_seconds=audit['fit_seconds'],prior_collection_seconds=audit['collection_seconds'],
        prior_worker_setup_seconds=audit['provenance']['setup_and_baseline_seconds'],
        prior_parent_setup_seconds=53.625422348,
        prior_total_audit_seconds=audit['total_audit_seconds'],
        accounting='Post-fit pilot only. Add prior fitting, collection and setup before claiming an end-to-end learning speedup.')
    (p/'directional-model-provenance.json').write_text(json.dumps(receipt,indent=2))
    meta=dict(title='Prophecy SuperMimic Derivative Model',id='madmad74100/prophecy-supermimic-derivative-model',
        licenses=[{'name':'other'}],description='Private audited derivative model for an isolated free experiment.')
    (p/'dataset-metadata.json').write_text(json.dumps(meta))
    response=api().dataset_create_new(str(p),public=False,quiet=True,convert_to_csv=False)
    (OUT/'direction-dataset-upload.json').write_text(json.dumps(dict(receipt=receipt,response=str(response)),indent=2))
    print('DIRECTION_MODEL_UPLOADED',response,json.dumps(receipt),flush=True)


def prepare_cache_data():
    """Private compiled artifacts only; no notebook runtime or policy copies."""
    from concurrent.futures import ThreadPoolExecutor
    import requests,os
    entries=json.loads((OUT/'cache-output-index.json').read_text())
    assert not entries['next_page_token'], 'Complete the selective cache index first'
    folder=OUT/'compiled-cache-dataset';folder.mkdir(exist_ok=True)
    cache=OUT/'downloaded-warp-cache'
    if os.name=='nt':cache=Path('\\\\?\\'+str(cache.resolve()))
    cache.mkdir(exist_ok=True)
    def fetch(item):
        name=item['fileName'].replace('\\','/')
        assert name.startswith('warp-cache/') and '..' not in name.split('/')
        path=cache/name;path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            r=requests.get(item['url'],timeout=(10,45));r.raise_for_status()
            if len(r.content)>50*1024*1024:raise ValueError('Unexpectedly large cache artifact')
            path.write_bytes(r.content)
        return dict(file=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with ThreadPoolExecutor(max_workers=8) as pool:manifest=list(pool.map(fetch,entries['files']))
    with zipfile.ZipFile(folder/'compiled-cache.zip','w',zipfile.ZIP_DEFLATED) as z:
        for row in manifest:z.write(cache/row['file'],row['file'])
    (folder/'cache-manifest.json').write_text(json.dumps(dict(source='madmad74100/prophecy-supermimic-decoupled-pilots',version=1,warp='1.12.1',gpu='Tesla T4',files=manifest),indent=2))
    (folder/'dataset-metadata.json').write_text(json.dumps(dict(title='Prophecy SuperMimic Compiled Cache',
        id='madmad74100/prophecy-supermimic-compiled-cache',licenses=[{'name':'other'}],
        description='Private compiled Warp artifacts for isolated free T4 tests. No policies or credentials.')))
    result=api().dataset_create_new(str(folder),public=False,quiet=True,convert_to_csv=False)
    receipt=dict(result=str(result),files=len(manifest),bytes=sum(r['bytes'] for r in manifest),
        zip_sha256=hashlib.sha256((folder/'compiled-cache.zip').read_bytes()).hexdigest())
    (OUT/'compiled-cache-upload.json').write_text(json.dumps(receipt,indent=2));print('CACHE_UPLOADED',json.dumps(receipt),flush=True)


def launch_pilots(seconds=240,fast=False,cautious=False,audit=False,one_step=False,compact=False,noise_race=False,decoupled=False,reward_audit=False,exact_pilots=False,short_exact=False,failure_pilots=False,freeze_pilots=False,phase_pilots=False,exact_critic_race=False,integration_audit=False,smooth_audit=False,value_audit=False,value_add_mse=False,direction_audit=False,direction_policy=False,objective_audit=False,advantage_race=False,phase_stability_race=False):
    a=api();username=a.config_values['username'];slug='prophecy-supermimic-gradient-audit' if audit else ('prophecy-supermimic-cautious-pilots' if cautious else ('prophecy-supermimic-fast-pilots' if fast else 'prophecy-supermimic-quick-pilots'))
    arms=[('small_step',4,[]),('fixed_critic',4,['--freeze-critic'])] if cautious else [('h'+str(h),h,[]) for h in ([4,8] if fast else [8,16])]
    extra=['--fast','--warm-model','fast-h4','--actor-lr','1.125e-6'] if cautious else (['--fast','--warm-model','auto'] if fast else [])
    if audit:arms=[('h1',1,[]),('h4',4,[])];extra=['--gradient-audit','--warm-model','cautious']
    if one_step:
        slug='prophecy-supermimic-one-step-pilots'
        arms=[('imagined_critic',1,[]),('real_critic',1,['--real-critic'])]
        extra=['--fast','--warm-model','cautious','--actor-lr','1.125e-6']
    if noise_race:
        previous=a.kernels_status(username+'/prophecy-supermimic-one-step-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-noisy-race'
        if (OUT/'noisy-race-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('ppo',1,['--native-ppo']),('stochastic_model',1,['--real-critic','--stochastic-actor'])]
        extra=['--fast','--warm-model','cautious','--actor-lr','1.125e-6','--noisy-eval']
    if decoupled:
        previous=a.kernels_status(username+'/prophecy-supermimic-noisy-race')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-decoupled-pilots'
        if (OUT/'decoupled-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('h4',4,[]),('h16',16,[])]
        extra=['--fast','--warm-model','cautious','--actor-lr','1.125e-6','--noisy-eval','--real-critic','--decoupled']
    if reward_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-decoupled-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-exact-reward-audit'
        if (OUT/'exact-reward-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('h1',1,[]),('h4',4,[])]
        extra=['--reward-audit','--warm-model','cautious']
    if exact_pilots:
        previous=a.kernels_status(username+'/prophecy-supermimic-exact-reward-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        for arm in ['h1','h4']:
            verified=json.loads((OUT/'prophecy-supermimic-exact-reward-audit-reports'/arm/'result.json').read_text())
            assert verified['complete'] and verified['passed'] and len(verified['probes'])==6
        slug='prophecy-supermimic-exact-reward-pilots'
        if (OUT/'exact-reward-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('small_step',32,['--actor-lr','1.125e-6']),('larger_step',32,['--actor-lr','1.125e-5'])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--real-critic','--decoupled','--exact-reward','--critic-weight','0']
    if short_exact:
        previous=a.kernels_status(username+'/prophecy-supermimic-exact-reward-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-short-exact-pilots'
        if (OUT/'short-exact-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('h1',1,[]),('h4',4,[])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--real-critic','--decoupled','--exact-reward','--critic-weight','0',
               '--actor-lr','1.125e-5','--actor-batch','2048','--fresh-ticks','8','--eval-interval','90']
    if failure_pilots:
        previous=a.kernels_status(username+'/prophecy-supermimic-short-exact-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-failure-gradient-pilots'
        if (OUT/'failure-gradient-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('learned_failure',4,[]),('analytic_failure',4,['--analytic-failure'])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--real-critic','--decoupled','--exact-reward','--critic-weight','0',
               '--actor-lr','1.125e-6','--actor-batch','2048','--fresh-ticks','8','--eval-interval','60']
    if freeze_pilots:
        previous=a.kernels_status(username+'/prophecy-supermimic-failure-gradient-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        validated=json.loads((OUT/'prophecy-supermimic-failure-gradient-pilots-reports'/'analytic_failure'/'result.json').read_text())
        assert validated['complete'] and validated['accepted_actor_updates']>0
        assert all(u['metrics'].get('failure_class_mismatches',0)==0 for u in validated['updates'])
        slug='prophecy-supermimic-frozen-model-pilots'
        if (OUT/'frozen-model-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('refitted',4,[]),('frozen',4,['--freeze-world'])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--real-critic','--decoupled','--exact-reward','--critic-weight','0',
               '--actor-lr','1.125e-6','--actor-batch','2048','--fresh-ticks','8','--eval-interval','90','--analytic-failure']
    if phase_pilots:
        previous=a.kernels_status(username+'/prophecy-supermimic-frozen-model-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        validated=json.loads((OUT/'prophecy-supermimic-frozen-model-pilots-reports'/'frozen'/'result.json').read_text())
        assert validated['complete'] and validated['accepted_actor_updates']>0 and validated['world_model_parameter_delta_l2']==0
        slug='prophecy-supermimic-phase-gradient-pilots'
        if (OUT/'phase-gradient-pilots-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('phase_backprop',4,[]),('phase_detached',4,['--stop-phase-gradient'])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--real-critic','--decoupled','--exact-reward','--critic-weight','0',
               '--actor-lr','1.125e-6','--actor-batch','2048','--fresh-ticks','8','--eval-interval','90','--analytic-failure','--freeze-world']
    if exact_critic_race:
        previous=a.kernels_status(username+'/prophecy-supermimic-phase-gradient-pilots')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-exact-critic-race'
        if (OUT/'exact-critic-race-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('ppo',1,['--native-ppo']),('exact_critic',16,['--real-critic','--decoupled','--exact-reward','--critic-weight','1',
            '--actor-batch','512','--fresh-ticks','16','--analytic-failure','--stop-phase-gradient'])]
        extra=['--fast','--warm-model','cautious','--noisy-eval','--actor-lr','1.125e-6','--eval-interval','90']
    if integration_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-exact-critic-race')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-integration-audit'
        if (OUT/'integration-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('residual',16,[]),('integrated',16,['--integrated-model'])]
        extra=['--model-audit']
    if smooth_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-integration-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        paired=json.loads((OUT/'prophecy-supermimic-integration-audit-reports'/'verified-model-comparison.json').read_text())
        assert paired['shared_identical_dataset'] and not paired['actor_changed']
        slug='prophecy-supermimic-smooth-model-audit'
        if (OUT/'smooth-model-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('residual',16,[]),('regularized',16,['--regularized-model'])]
        extra=['--model-audit']
    if value_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-smooth-model-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        verified=json.loads((OUT/'prophecy-supermimic-smooth-model-audit-reports'/'verified-model-comparison.json').read_text())
        assert verified['shared_identical_dataset'] and not verified['actor_changed']
        slug='prophecy-supermimic-value-model-audit'
        if (OUT/'value-model-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('residual',16,[]),('value_weighted',16,['--value-weighted-model'])]
        if value_add_mse:arms[1][2].append('--value-add-mse')
        extra=['--model-audit','--value-model-audit']
    if direction_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-value-model-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        verified=json.loads((OUT/'prophecy-supermimic-value-model-audit-v3-reports'/'verified-model-comparison.json').read_text())
        assert verified['shared_identical_dataset'] and not verified['actor_changed']
        slug='prophecy-supermimic-direction-model-audit'
        if (OUT/'direction-model-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('residual',16,[]),('directional',16,['--directional-supervision'])]
        extra=['--model-audit','--direction-model-audit']
    if direction_policy:
        previous=a.kernels_status(username+'/prophecy-supermimic-direction-model-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        assert (OUT/'direction-dataset-upload.json').exists()
        slug='prophecy-supermimic-direction-policy-pilot'
        if (OUT/'direction-policy-pilot-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('ppo',1,['--native-ppo']),('directional_actor',16,['--real-critic','--decoupled','--exact-reward',
            '--critic-weight','1','--actor-batch','512','--fresh-ticks','16','--analytic-failure',
            '--stop-phase-gradient','--freeze-world','--warm-model','directional'])]
        extra=['--fast','--noisy-eval','--actor-lr','1.125e-6','--eval-interval','90']
    if objective_audit:
        previous=a.kernels_status(username+'/prophecy-supermimic-direction-policy-pilot')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-supermimic-objective-audit'
        if (OUT/'objective-audit-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('deterministic',16,[]),('noisy',16,['--noisy-eval'])]
        extra=['--objective-audit','--warm-model','directional']
    if advantage_race:
        previous=a.kernels_status(username+'/prophecy-supermimic-objective-audit')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-ppo-advantage-cap-race'
        if (OUT/'advantage-cap-race-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('ppo',1,['--advantage-clip','4']),('cap10',1,['--advantage-clip','10'])]
        extra=['--native-ppo','--fast','--noisy-eval','--actor-lr','1.125e-6','--eval-interval','90']
    if phase_stability_race:
        previous=a.kernels_status(username+'/prophecy-ppo-advantage-cap-race')
        assert type(previous).to_dict(previous)['status']=='COMPLETE'
        slug='prophecy-ppo-phase-stability-race'
        if (OUT/'phase-stability-race-launch.json').exists():
            current=a.kernels_status(username+'/'+slug)
            assert type(current).to_dict(current)['status'] in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED','CANCELED')
        arms=[('ppo',1,[]),('frozen_phase',1,['--freeze-phase-predictor'])]
        extra=['--native-ppo','--fast','--noisy-eval','--phase-stability','--actor-lr','1.125e-6','--eval-interval','90']
    p=OUT/slug;p.mkdir(exist_ok=True)
    bootstrap=(OUT/'runtime-preflight/runtime_preflight.py').read_text().split("os.environ['PYGLET_HEADLESS']")[0]
    bootstrap="print('BOOTSTRAP_STARTED',flush=True)\n"+bootstrap
    bootstrap=bootstrap.replace("receipt=json.loads((src/'provenance.json').read_text())",
        "print('BOOTSTRAP_DATA_LOCATED',str(src),flush=True)\nreceipt=json.loads((src/'provenance.json').read_text())")
    bootstrap=bootstrap.replace("shutil.copytree(src/'source',root,dirs_exist_ok=True)",
        "print('BOOTSTRAP_HASHES_VERIFIED',flush=True)\nshutil.copytree(src/'source',root,dirs_exist_ok=True)\nprint('BOOTSTRAP_SOURCE_COPIED',flush=True)")
    bootstrap=bootstrap.replace("subprocess.run([sys.executable,'-m','pip'",
        "print('BOOTSTRAP_PIP_START',flush=True)\nsubprocess.run([sys.executable,'-m','pip'")
    bootstrap=bootstrap.replace("'tensorboardX'],check=True)",
        "'tensorboardX'],check=True,timeout=180)\nprint('BOOTSTRAP_PIP_DONE',flush=True)")
    files={n:(ROOT/'Labs/MimicKitTraining'/n).read_text() for n in
           ['supermimic_race.py','supermimic_structured.py','supermimic_pilot.py','supermimic_gradient_audit.py','supermimic_decoupled.py','supermimic_exact_reward.py','supermimic_reward_audit.py','supermimic_model_audit.py','supermimic_derivatives.py','supermimic_objective_audit.py','supermimic_advantage.py','supermimic_phase_stability.py']}
    code=bootstrap+'\n'
    code+='''
cache=Path.home()/'.cache/warp/1.12.1'
for saved_cache in Path('/kaggle/input').rglob('warp-cache'):
 if saved_cache.is_dir():
  shutil.copytree(saved_cache,cache,dirs_exist_ok=True)
  print('RESTORED_KERNEL_CACHE',flush=True);break
'''
    for name,source in files.items():code+="(out/"+repr(name)+").write_text("+repr(source)+")\n"
    code+='''
import threading
processes=[]
def relay(name,process):
 with (out/(name+'.log')).open('w') as f:
  for line in process.stdout:
   f.write(line);f.flush()
   if any(marker in line for marker in ['BASELINE','WARM_MODEL','GRAPH_FIT_VERIFIED','GRADIENT_AUDIT','REWARD_AUDIT','MODEL_AUDIT','OBJECTIVE_AUDIT','SKELETON_OK','PROGRESS','EVALUATION','PILOT_COMPLETE','Error','Traceback']):
    print('['+name+'] '+line.rstrip(),flush=True)
for gpu,(name,horizon,arm_args) in enumerate(ARMS):
 folder=out/name;folder.mkdir(exist_ok=True)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),PYGLET_HEADLESS='true',OMP_NUM_THREADS='2',PYTHONUNBUFFERED='1')
 args=[sys.executable,'-u',str(out/'supermimic_pilot.py'),'--root',str(root),'--checkpoint',str(checkpoint),
       '--output',str(folder),'--horizon',str(horizon),'--seconds',SECONDS]+EXTRA_ARGS+arm_args
 process=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
 thread=threading.Thread(target=relay,args=(name,process),daemon=True);thread.start()
 processes.append((name,process,thread))
deadline=time.monotonic()+900
try:
 while any(p.poll() is None for _,p,_ in processes):
  print('WORKERS_ALIVE',[(n,p.poll()) for n,p,_ in processes],flush=True)
  for n,p,t in processes:
   if p.poll() not in (None,0):
    t.join(timeout=5);print((out/(n+'.log')).read_text()[-7000:],flush=True)
    raise RuntimeError(n+' failed')
  if time.monotonic()>deadline:raise TimeoutError('Quick pilots exceeded 15-minute setup/test bound')
  time.sleep(15)
 for n,p,t in processes:
  t.join(timeout=5)
  if p.returncode:raise RuntimeError(n+' failed')
 print('QUICK_PILOTS_COMPLETE',flush=True)
finally:
 for n,p,t in processes:
  if p.poll() is None:p.terminate()
 for n,p,t in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill()
 if cache.exists():shutil.copytree(cache,out/'warp-cache',dirs_exist_ok=True)
 for temporary_name in ['model-audit-shared-replay.pt','model-audit-shared-replay.partial']:
  (out/temporary_name).unlink(missing_ok=True)
'''.replace('SECONDS',repr(str(seconds))).replace('ARMS',repr(arms)).replace('EXTRA_ARGS',repr(extra))
    (p/'pilots.py').write_text(code)
    meta=dict(id=username+'/'+slug,title='Prophecy SuperMimic Gradient Audit' if audit else ('Prophecy SuperMimic Cautious Pilots' if cautious else ('Prophecy SuperMimic Fast Pilots' if fast else 'Prophecy SuperMimic Quick Pilots')),
        code_file='pilots.py',language='python',kernel_type='script',is_private=True,enable_gpu=True,
        enable_internet=True,dataset_sources=[username+'/prophecy-supermimic-private-race'],
        kernel_sources=[username+'/prophecy-supermimic-cautious-pilots'] if audit else ([username+'/prophecy-supermimic-fast-pilots'] if cautious else ([username+'/prophecy-supermimic-quick-pilots'] if fast else [])),competition_sources=[])
    if one_step:
        meta['title']='Prophecy SuperMimic One Step Pilots'
        meta['kernel_sources']=[username+'/prophecy-supermimic-cautious-pilots',username+'/prophecy-supermimic-gradient-audit']
    if compact:
        assert one_step or noise_race or decoupled or reward_audit or exact_pilots or short_exact or failure_pilots or freeze_pilots or phase_pilots or exact_critic_race or integration_audit or smooth_audit or value_audit or direction_audit or direction_policy or objective_audit or advantage_race or phase_stability_race
        if one_step:
            status=a.kernels_status(username+'/'+slug)
            state=type(status).to_dict(status)['status']
            assert state in ('CANCEL_ACKNOWLEDGED','CANCELED','ERROR','COMPLETE'), state
        meta['kernel_sources']=[]
        meta['dataset_sources'].append(username+'/prophecy-supermimic-warm-start')
        if (OUT/'compiled-cache-upload.json').exists():
            meta['dataset_sources'].append(username+'/prophecy-supermimic-compiled-cache')
    if noise_race:meta['title']='Prophecy SuperMimic Noisy Race'
    if decoupled:meta['title']='Prophecy SuperMimic Decoupled Pilots'
    if reward_audit:meta['title']='Prophecy SuperMimic Exact Reward Audit'
    if exact_pilots:meta['title']='Prophecy SuperMimic Exact Reward Pilots'
    if short_exact:meta['title']='Prophecy SuperMimic Short Exact Pilots'
    if failure_pilots:meta['title']='Prophecy SuperMimic Failure Gradient Pilots'
    if freeze_pilots:meta['title']='Prophecy SuperMimic Frozen Model Pilots'
    if phase_pilots:meta['title']='Prophecy SuperMimic Phase Gradient Pilots'
    if exact_critic_race:meta['title']='Prophecy SuperMimic Exact Critic Race'
    if integration_audit:meta['title']='Prophecy SuperMimic Integration Audit'
    if smooth_audit:meta['title']='Prophecy SuperMimic Smooth Model Audit'
    if value_audit:meta['title']='Prophecy SuperMimic Value Model Audit'
    if direction_audit:meta['title']='Prophecy SuperMimic Direction Model Audit'
    if direction_policy:
        meta['title']='Prophecy SuperMimic Direction Policy Pilot'
        meta['dataset_sources'].append(username+'/prophecy-supermimic-derivative-model')
    if objective_audit:
        meta['title']='Prophecy SuperMimic Objective Audit'
        meta['dataset_sources'].append(username+'/prophecy-supermimic-derivative-model')
    if advantage_race:meta['title']='Prophecy PPO Advantage Cap Race'
    if phase_stability_race:meta['title']='Prophecy PPO Phase Stability Race'
    (p/'kernel-metadata.json').write_text(json.dumps(meta))
    r=a.kernels_push(str(p),timeout=1100);result=type(r).to_dict(r)
    result.update(seconds_per_candidate=seconds,arms=arms,extra_args=extra,
        source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in files.items()})
    receipt_name='one-step-pilots-launch.json' if one_step else ('gradient-audit-launch.json' if audit else ('cautious-pilots-launch.json' if cautious else ('fast-pilots-launch.json' if fast else 'quick-pilots-launch.json')))
    if noise_race:receipt_name='noisy-race-launch.json'
    if decoupled:receipt_name='decoupled-pilots-launch.json'
    if reward_audit:receipt_name='exact-reward-audit-launch.json'
    if exact_pilots:receipt_name='exact-reward-pilots-launch.json'
    if short_exact:receipt_name='short-exact-pilots-launch.json'
    if failure_pilots:receipt_name='failure-gradient-pilots-launch.json'
    if freeze_pilots:receipt_name='frozen-model-pilots-launch.json'
    if phase_pilots:receipt_name='phase-gradient-pilots-launch.json'
    if exact_critic_race:receipt_name='exact-critic-race-launch.json'
    if integration_audit:receipt_name='integration-audit-launch.json'
    if smooth_audit:receipt_name='smooth-model-audit-launch.json'
    if value_audit:receipt_name='value-model-audit-launch.json'
    if direction_audit:receipt_name='direction-model-audit-launch.json'
    if direction_policy:receipt_name='direction-policy-pilot-launch.json'
    if objective_audit:receipt_name='objective-audit-launch.json'
    if advantage_race:receipt_name='advantage-cap-race-launch.json'
    if phase_stability_race:receipt_name='phase-stability-race-launch.json'
    if compact:
        result['input_packaging']='Verified warm model dataset; no prior notebook output mounts. GPU compilation may repeat.'
        prior=OUT/receipt_name
        if prior.exists():
            version=json.loads(prior.read_text()).get('versionNumber','previous')
            shutil.copyfile(prior,OUT/(prior.stem+'-v'+str(version)+'.json'))
    (OUT/receipt_name).write_text(json.dumps(result,indent=2));print(json.dumps(result))


def live_log_tail(events,limit=14):
    nonempty=[e for e in events if str(e.get('data','')).strip()]
    return [str(e.get('time',''))+' '+str(e.get('data','')).rstrip() for e in nonempty[-limit:]]


def live_logs(ref,version=None,seconds=20):
    """Bounded live SSE read, using Kaggle's official kernels/logs/stream route."""
    import time
    owner,slug=ref.split('/');events=[]
    if version is not None and str(version).isdigit():version='v'+str(version)
    if version is None:
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        with token_client() as c:
            q=ApiGetKernelRequest();q.user_name=owner;q.kernel_slug=slug
            info=c.kernels.kernels_api_client.get_kernel(q)
            version='v'+str(info.metadata.current_version_number)
    print('LOG_VERSION',version,flush=True)
    with token_client() as c:
        h=c._http_client;headers=dict(h._session.headers)
        headers['Accept']='text/event-stream, */*';headers.pop('Content-Type',None)
        url=h._endpoint.rstrip('/')+'/api/v1/kernels/logs/stream/'+owner+'/'+slug
        try:
            with h._session.get(url,headers=headers,params={'versionLabel':version},stream=True,timeout=(10,25)) as r:
                r.raise_for_status();start=time.monotonic()
                if not r.headers.get('Content-Type','').startswith('text/event-stream'):
                    events=r.json()
                else:
                    # SSE may contain only a short startup message while pip runs.
                    # requests' default 512-byte buffer can hide it until timeout.
                    for line in r.iter_lines(chunk_size=1,decode_unicode=True):
                        if not line or not line.startswith('data:'):continue
                        value=line[5:].strip()
                        if value=='END_OF_LOG':break
                        events.append(json.loads(value))
                        if time.monotonic()-start>seconds:break
        except Exception as exc:print(type(exc).__name__,str(exc)[:200])
    dest=OUT/(slug+'-live.json')
    # A failed poll is missing evidence, not an empty replacement for earlier logs.
    if events or not dest.exists():
        dest.write_text(json.dumps(events,indent=2),encoding='utf-8')
    if events:
        (OUT/(slug+'-'+version+'-live.json')).write_text(json.dumps(events,indent=2),encoding='utf-8')
    (OUT/(slug+'-last-log-check.json')).write_text(json.dumps(dict(
        ref=ref,version=version,checked_unix=time.time(),received_events=len(events)),indent=2))
    # Never hide an unfamiliar progress marker. The raw tail is evidence;
    # absence from a whitelist must not be mistaken for a stalled worker.
    for line in live_log_tail(events):print(line)
    print('Live events:',len(events))


def fetch_reports(ref):
    """Fetch our reports/logs, without copying the runtime/assets again."""
    import requests
    # Output downloads can silently serve the last completed version while a
    # newer version is RUNNING. Never interpret those as current results.
    state=api().kernels_status(ref)
    if type(state).to_dict(state)['status']!='COMPLETE':
        raise RuntimeError('Current version is not COMPLETE; use version-correct live logs instead of output downloads')
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    owner,slug=ref.split('/')
    with token_client() as client:
        query=ApiGetKernelRequest();query.user_name=owner;query.kernel_slug=slug
        info=client.kernels.kernels_api_client.get_kernel(query)
        output_version=int(info.metadata.current_version_number)
    print('REPORT_VERSION',output_version,flush=True)
    if ref.endswith(('/prophecy-model-rollout-calibration','/prophecy-ppo-short-world-race','/prophecy-rwm-history-calibration','/prophecy-termination-calibration','/prophecy-com2-model-calibration','/prophecy-failure-replay-calibration','/prophecy-smooth-actor-race','/prophecy-native-planning-probe','/prophecy-planning-student-race','/prophecy-colored-ppo-race','/prophecy-target-critic-race','/prophecy-colored-ppo-confirmation','/prophecy-planning-student-fit','/prophecy-frozen-feature-student','/prophecy-uncertain-planner','/prophecy-transfer-head-race','/prophecy-multifidelity-probe','/prophecy-native-fidelity-probe','/prophecy-teacher-consistency')):
        from concurrent.futures import ThreadPoolExecutor
        dest=OUT/(ref.split('/')[1]+'-reports');dest.mkdir(exist_ok=True)
        arms=['ppo','ppo_short'] if ref.endswith('/prophecy-ppo-short-world-race') else ['initial','final']
        if ref.endswith('/prophecy-rwm-history-calibration'):arms=['control','recurrent']
        if ref.endswith('/prophecy-termination-calibration'):arms=['analytic','learned']
        if ref.endswith('/prophecy-com2-model-calibration'):arms=['control','com2']
        if ref.endswith('/prophecy-failure-replay-calibration'):arms=['control','failure_replay']
        if ref.endswith('/prophecy-smooth-actor-race'):arms=['relu','smooth']
        if ref.endswith('/prophecy-native-planning-probe'):arms=['seed_984110','seed_984111']
        if ref.endswith(('/prophecy-planning-student-race','/prophecy-planning-student-fit')):arms=['ppo','student']
        if ref.endswith('/prophecy-colored-ppo-race'):arms=['white','colored']
        if ref.endswith('/prophecy-target-critic-race'):arms=['online','target']
        if ref.endswith('/prophecy-colored-ppo-confirmation'):arms=[a+'_'+str(s) for s in [849150,849151] for a in ['white','colored']]
        if ref.endswith('/prophecy-frozen-feature-student'):arms=['ppo','features']
        if ref.endswith('/prophecy-uncertain-planner'):arms=['seed_984180','seed_984181']
        if ref.endswith('/prophecy-transfer-head-race'):arms=['full','heads']
        if ref.endswith('/prophecy-multifidelity-probe'):arms=['calibration','validation']
        if ref.endswith('/prophecy-native-fidelity-probe'):arms=['original','cap4']
        if ref.endswith('/prophecy-teacher-consistency'):arms=['seed_984220','seed_984221']
        names=[arm+'/result.json' for arm in arms]+[arm+'.log' for arm in arms]
        if ref.endswith('/prophecy-colored-ppo-confirmation'):names+=['confirmation.json']
        if ref.endswith('/prophecy-uncertain-planner'):names+=['calibration.json']
        if ref.endswith('/prophecy-multifidelity-probe'):names+=[arm+'/gradient_sketch.npz' for arm in arms]
        if ref.endswith('/prophecy-teacher-consistency'):names+=[arm+'/teacher_consistency.npz' for arm in arms]
        def download_calibration(name):
            with token_client() as client:
                http=client._http_client
                response=http._session.get(http._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/'+name,params={'versionNumber':output_version},timeout=(10,40))
                if response.status_code==404:return None
                response.raise_for_status()
                if name.endswith('.json'):json.loads(response.content)
                # COM2 is a reserved Windows device name, including COM2.log.
                local_name=name.replace('com2/', 'com2_model/', 1) if name.startswith('com2/') else name
                if local_name=='com2.log':local_name='com2_model.log'
                target=dest/local_name;target.parent.mkdir(exist_ok=True);target.write_bytes(response.content)
                return name
        with ThreadPoolExecutor(max_workers=4) as pool:found=[n for n in pool.map(download_calibration,names) if n]
        print(json.dumps(dict(folder=str(dest),reports=found)));return
    # These names are fixed by our two-arm pilot. Direct downloads avoid paging
    # through hundreds of runtime and compiled-cache files just to find reports.
    if ref.endswith(('/prophecy-supermimic-one-step-pilots','/prophecy-supermimic-noisy-race','/prophecy-supermimic-decoupled-pilots','/prophecy-supermimic-exact-reward-audit','/prophecy-supermimic-exact-reward-pilots','/prophecy-supermimic-short-exact-pilots','/prophecy-supermimic-failure-gradient-pilots','/prophecy-supermimic-frozen-model-pilots','/prophecy-supermimic-phase-gradient-pilots','/prophecy-supermimic-exact-critic-race','/prophecy-supermimic-integration-audit','/prophecy-supermimic-smooth-model-audit','/prophecy-supermimic-value-model-audit','/prophecy-supermimic-direction-model-audit','/prophecy-supermimic-direction-policy-pilot','/prophecy-supermimic-objective-audit','/prophecy-ppo-advantage-cap-race','/prophecy-ppo-phase-stability-race','/prophecy-ppo-phase-confirmation','/prophecy-supermimic-full-imagination','/prophecy-supermimic-heading-audit','/prophecy-supermimic-hard-events','/prophecy-supermimic-heading-policy','/prophecy-supermimic-increment-audit','/prophecy-supermimic-increment-policy','/prophecy-supermimic-critic-horizon','/prophecy-supermimic-critic-context','/prophecy-supermimic-gradient-fidelity','/prophecy-supermimic-fit-dose','/prophecy-supermimic-head-fit','/prophecy-supermimic-stochastic-full','/prophecy-supermimic-full-phase','/prophecy-supermimic-capacity','/prophecy-supermimic-direct-tracking','/prophecy-offpolicy-c51-race','/prophecy-native-awr-race','/prophecy-supermimic-headroom','/prophecy-supermimic-earlier-policy','/prophecy-supermimic-policy-step','/prophecy-ppo-world-race')):
        from concurrent.futures import ThreadPoolExecutor
        owner,slug=ref.split('/');dest=OUT/(slug+'-reports');dest.mkdir(exist_ok=True)
        arms=['ppo','stochastic_model'] if ref.endswith('noisy-race') else ['imagined_critic','real_critic']
        if ref.endswith('decoupled-pilots'):arms=['h4','h16']
        if ref.endswith('exact-reward-audit'):arms=['h1','h4']
        if ref.endswith('exact-reward-pilots'):arms=['small_step','larger_step']
        if ref.endswith('short-exact-pilots'):arms=['h1','h4']
        if ref.endswith('failure-gradient-pilots'):arms=['learned_failure','analytic_failure']
        if ref.endswith('frozen-model-pilots'):arms=['refitted','frozen']
        if ref.endswith('phase-gradient-pilots'):arms=['phase_backprop','phase_detached']
        if ref.endswith('exact-critic-race'):arms=['ppo','exact_critic']
        if ref.endswith('integration-audit'):arms=['residual','integrated']
        if ref.endswith('smooth-model-audit'):arms=['residual','regularized']
        if ref.endswith('value-model-audit'):arms=['residual','value_weighted']
        if ref.endswith('direction-model-audit'):arms=['residual','directional']
        if ref.endswith('direction-policy-pilot'):arms=['ppo','directional_actor']
        if ref.endswith('objective-audit'):arms=['deterministic','noisy']
        if ref.endswith('advantage-cap-race'):arms=['ppo','cap10']
        if ref.endswith('phase-stability-race'):arms=['ppo','frozen_phase']
        if ref.endswith('phase-confirmation'):arms=['ppo_seed92719','frozen_seed92719','ppo_seed38147','frozen_seed38147']
        if ref.endswith('full-imagination'):arms=['ppo','imagined_exact']
        if ref.endswith('heading-audit'):arms=['residual','equivariant']
        if ref.endswith('increment-audit'):arms=['residual','increments']
        if ref.endswith('increment-policy'):arms=['ppo','increments_hard']
        if ref.endswith('critic-horizon'):arms=['critic_h32','no_critic_h32']
        if ref.endswith('critic-context'):arms=['original_critic','context_critic']
        if ref.endswith('gradient-fidelity'):arms=['deterministic','noisy']
        if ref.endswith('fit-dose'):arms=['batch256','batch2048']
        if ref.endswith('head-fit'):arms=['coupled','detached']
        if ref.endswith('stochastic-full'):arms=['ppo','stochastic_h32']
        if ref.endswith('full-phase'):arms=['phase_coupled','phase_detached']
        if ref.endswith('capacity'):arms=['width1024','width2048']
        if ref.endswith('direct-tracking'):arms=['ppo','direct_h32']
        if ref.endswith('offpolicy-c51-race'):arms=['ppo','c51_td3']
        if ref.endswith('native-awr-race'):arms=['ppo','awr']
        if ref.endswith('supermimic-headroom'):arms=['current','early']
        if ref.endswith('supermimic-earlier-policy'):arms=['ppo','stochastic_h32']
        if ref.endswith('supermimic-policy-step'):arms=['ppo','model']
        if ref.endswith('ppo-world-race'):arms=['ppo','ppo_world']
        if ref.endswith('hard-events'):arms=['ppo','hard_events']
        if ref.endswith('heading-policy'):arms=['global_hard','heading_hard']
        names=[arm+'/result.json' for arm in arms]+[arm+'.log' for arm in arms]
        if ref.endswith('gradient-fidelity'):names += [arm+'/provenance.json' for arm in arms]
        def download(name):
            with token_client() as c:
                h=c._http_client
                url=h._endpoint.rstrip('/')+'/api/v1/kernels/output/download/'+ref+'/'+name
                r=h._session.get(url,params={'versionNumber':output_version},timeout=(10,40))
                if r.status_code==404:return None
                r.raise_for_status()
                if name.endswith('.json'):json.loads(r.content)
                f=dest/name;f.parent.mkdir(exist_ok=True);f.write_bytes(r.content)
                return name
        with ThreadPoolExecutor(max_workers=4) as pool:
            found=[n for n in pool.map(download,names) if n]
        print(json.dumps(dict(folder=str(dest),reports=found)))
        return
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    owner,slug=ref.split('/');dest=OUT/(slug+'-reports');dest.mkdir(exist_ok=True)
    wanted={'runtime-preflight.json','runtime_provenance.json','ppo/result.json',
            'world_model/result.json','ppo.log','world_model.log','h8/result.json','h16/result.json','h4/result.json','h4.log','h8.log','h16.log',
            'small_step/result.json','fixed_critic/result.json','small_step.log','fixed_critic.log','h1/result.json','h1.log','h1/provenance.json','h4/provenance.json',
            'imagined_critic/result.json','real_critic/result.json','imagined_critic.log','real_critic.log'}
    names=[];page=None
    while True:
        with token_client() as k:
            q=ApiListKernelSessionOutputRequest();q.user_name=owner;q.kernel_slug=slug
            q.page_size=100
            if page:q.page_token=page
            r=k.kernels.kernels_api_client.list_kernel_session_output(q)
        if r.log and page is None:
            (dest/'session.log').write_text(r.log,encoding='utf-8')
            try:lines=''.join(str(x.get('data','')) for x in json.loads(r.log))
            except (ValueError,AttributeError):lines=r.log
            (dest/'session-readable.log').write_text(lines,encoding='utf-8')
            print(lines[-6500:])
        for f in r.files:
            name=f.file_name.replace('\\','/')
            if name not in wanted:continue
            target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
            response=requests.get(f.url,timeout=60);response.raise_for_status()
            target.write_bytes(response.content);names.append(name)
        page=r.next_page_token
        if not page:break
    print(json.dumps(dict(folder=str(dest),reports=names)))

if __name__=='__main__':
    import sys
    if sys.argv[1]=='preflight':preflight()
    elif sys.argv[1]=='prepare-data':prepare_data()
    elif sys.argv[1]=='runtime-preflight':runtime_preflight()
    elif sys.argv[1]=='race':launch_race(int(sys.argv[2]) if len(sys.argv)>2 else 1800)
    elif sys.argv[1]=='pilots':launch_pilots(int(sys.argv[2]) if len(sys.argv)>2 else 240)
    elif sys.argv[1]=='fast-pilots':launch_pilots(int(sys.argv[2]) if len(sys.argv)>2 else 180,fast=True)
    elif sys.argv[1]=='cautious-pilots':launch_pilots(int(sys.argv[2]) if len(sys.argv)>2 else 180,fast=True,cautious=True)
    elif sys.argv[1]=='gradient-audit':launch_pilots(120,audit=True)
    elif sys.argv[1]=='one-step-pilots':launch_pilots(180,fast=True,one_step=True)
    elif sys.argv[1]=='prepare-warm-data':prepare_warm_data()
    elif sys.argv[1]=='prepare-direction-data':prepare_direction_data()
    elif sys.argv[1]=='prepare-cache-data':prepare_cache_data()
    elif sys.argv[1]=='one-step-retry':launch_pilots(180,fast=True,one_step=True,compact=True)
    elif sys.argv[1]=='noisy-race':launch_pilots(180,fast=True,compact=True,noise_race=True)
    elif sys.argv[1]=='decoupled-pilots':launch_pilots(180,fast=True,compact=True,decoupled=True)
    elif sys.argv[1]=='exact-reward-audit':launch_pilots(120,compact=True,reward_audit=True)
    elif sys.argv[1]=='exact-reward-pilots':launch_pilots(240,fast=True,compact=True,exact_pilots=True)
    elif sys.argv[1]=='short-exact-pilots':launch_pilots(240,fast=True,compact=True,short_exact=True)
    elif sys.argv[1]=='failure-gradient-pilots':launch_pilots(240,fast=True,compact=True,failure_pilots=True)
    elif sys.argv[1]=='frozen-model-pilots':launch_pilots(240,fast=True,compact=True,freeze_pilots=True)
    elif sys.argv[1]=='phase-gradient-pilots':launch_pilots(240,fast=True,compact=True,phase_pilots=True)
    elif sys.argv[1]=='exact-critic-race':launch_pilots(300,fast=True,compact=True,exact_critic_race=True)
    elif sys.argv[1]=='integration-audit':launch_pilots(180,compact=True,integration_audit=True)
    elif sys.argv[1]=='smooth-model-audit':launch_pilots(300,compact=True,smooth_audit=True)
    elif sys.argv[1]=='value-model-audit':launch_pilots(120,compact=True,value_audit=True,value_add_mse='add-mse' in sys.argv[2:])
    elif sys.argv[1]=='direction-model-audit':launch_pilots(180,compact=True,direction_audit=True)
    elif sys.argv[1]=='objective-audit':launch_pilots(480,compact=True,objective_audit=True)
    elif sys.argv[1]=='advantage-cap-race':launch_pilots(300,compact=True,advantage_race=True)
    elif sys.argv[1]=='phase-stability-race':launch_pilots(300,compact=True,phase_stability_race=True)
    elif sys.argv[1]=='direction-policy-pilot':launch_pilots(300,compact=True,direction_policy=True)
    elif sys.argv[1]=='logs':live_logs(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
    elif sys.argv[1]=='fetch':fetch_reports(sys.argv[2])
    elif sys.argv[1]=='status':print(api().kernels_status(sys.argv[2]))
