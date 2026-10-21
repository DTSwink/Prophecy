"""Isolated L4 experiments: no writes to production run state/checkpoints."""
import ast,hashlib,json,os,shlex,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'Saved/MimicKitLocomotion'
OUT=ROOT/'Saved/MimicKitLocomotionSweeps/20261021'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from backup import verified_readback

def remote(code,timeout=50):return cloud.ssh('python -c '+shlex.quote(code),timeout=timeout)
def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(value,indent=2))

def prepare():
    cp=json.loads((MAIN/'user-stop-checkpoint.json').read_text())
    source=json.loads((MAIN/'getup-success-prepared.json').read_text())['source']
    for item in [cp,source]:assert hashlib.sha256(Path(item['local']).read_bytes()).hexdigest()==item['sha256']
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
       [Path(cp['local']),Path(source['local']),*(MAIN/n for n in ['active_run.json','pod.json','runtime_control.json','getup-success-prepared.json','user-stop-checkpoint.json'])]}
    save('protected-main-files',protected)
    cp['preserved_key']=cp['key']
    save('getup-success-prepared',dict(checkpoint=cp,source=source))
    configs=OUT/'base_config';configs.mkdir(exist_ok=True)
    with zipfile.ZipFile(cp['local']) as z:
        assert z.testzip() is None
        for name in ['env_config.yaml','engine_config.yaml','agent_config.yaml']:(configs/name).write_bytes(z.read(name))
    seeds=[83191+i for i in range(8)]
    variants={
       'baseline':{},
       'lr2':dict(actor_lr=2.25e-6),
       'lr4':dict(actor_lr=4.5e-6),
       'critic3':dict(critic_lr=3e-4),
       'batch8_lr2':dict(actor_batch_size=8,actor_lr=2.25e-6),
       'roll64_lr2':dict(steps_per_iter=64,actor_lr=2.25e-6),
       'adaptive_kl':dict(adaptive_actor_kl_target=.015,actor_lr_min=1.125e-6,actor_lr_max=9e-6),
    }
    for v in variants.values():v.update(equivalent_updates=256,seed=13579,evaluate_at_updates=[128,256])
    plan=dict(sha256=cp['sha256'],checkpoint=cp['key'],worlds=512,variants=variants,
              evaluation_seeds=seeds,variant_timeout_seconds=1800,stage='screen',
              authorization='User: no time limit; minimize cost/time; L4 ceiling0.59/hour; main remains stopped',
              preserved_main=protected,source=source)
    save('plan',plan)
    print('Prepared isolated experiment configuration; protected production checkpoint91895',flush=True)

def allocate():
    cloud.allocate(sys.argv[3] if len(sys.argv)>3 else 'NVIDIA L4',.59,sys.argv[2] if len(sys.argv)>2 else 'SECURE',seconds=600,name='mimickit-loco-sweeps-'+str(int(time.time())),
        data_center_ids=['EU-CZ-1','EU-NL-1','EU-SE-1','EU-FR-1','US-IL-1','US-TX-3','US-GA-2'] if '--regions' in sys.argv else None)
    protect_setup()
    print(cloud.connect(),flush=True);cloud.ssh('mkdir -p /workspace/mimickit_trial')

def protect_setup():
    pod=cloud.state()['pod_id'];end=time.time()+600
    save('runtime_control',dict(pod_id=pod,hard_stop_unix=end,until_stopped=False,updated_unix=time.time()))
    marker=OUT/'setup-verified';marker.unlink(missing_ok=True)
    code=f"""import sys,time
from pathlib import Path
sys.path.insert(0,{str(ROOT/'Labs/MimicKitTraining')!r})
import cloud
from billing_stop import stop_and_confirm
while time.time()<{end!r} and not Path({str(marker)!r}).exists():time.sleep(2)
if not Path({str(marker)!r}).exists():stop_and_confirm({pod!r},cloud.rp.load_api_key(),Path({str(OUT/'setup-timeout.json')!r}),'Sweep setup not verified within10minutes')
"""
    with (OUT/'setup-watchdog.log').open('ab') as log:
        p=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    save('setup-watchdog',dict(pid=p.pid,deadline=end))

def retained():
    # Reuse compute only; production run directories/config pointers stay intact.
    previous=json.loads((MAIN/'pod.json').read_text())
    assert previous.get('user_stopped') and previous['cost_per_hour']<=.59
    cloud.save(previous);protect_setup()
    try:cloud.rp.request_json('POST','/pods/'+previous['pod_id']+'/start')
    except Exception:
        (OUT/'pod.json').rename(OUT/'retained-start-failed.json');raise
    print(cloud.connect(),flush=True)
    print(cloud.ssh('test -x /workspace/mimickit_trial/venv/bin/python && echo RUNTIME_RETAINED'),flush=True)

def reuse(name):
    path=ROOT/'Labs/MimicKitTraining/resume_getup_success.py';source=path.read_text();tree=ast.parse(source)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope=dict(globals());exec(ast.get_source_segment(source,fn),scope);scope[name]()
def provision():reuse('provision')
def runtime():reuse('runtime')

def start():
    plan=json.loads((OUT/'plan.json').read_text());con=cloud.state()['connection']
    for name in ['loco_learning_sweep.py','loco_sweep_queue.py','loco_privileged_critic.py']:
        cloud.rp.scp(con,ROOT/'Labs/MimicKitTraining'/name,'/workspace/mimickit_trial/pipeline/'+name,timeout=45)
    cloud.ssh('mkdir -p /workspace/mimickit_trial/loco-sweeps/base_config')
    cloud.rp.scp(con,OUT/'plan.json','/workspace/mimickit_trial/loco-sweeps/plan.json',timeout=45)
    for p in (OUT/'base_config').glob('*.yaml'):cloud.rp.scp(con,p,'/workspace/mimickit_trial/loco-sweeps/base_config/'+p.name,timeout=45)
    from extend_runtime import extend
    extend(time.time()+7200)
    print(remote('''from pathlib import Path
import subprocess,shutil,json
r=Path('/workspace/mimickit_trial');o=r/'loco-sweeps'
assert (r/'runtime-cache-restored.json').exists()
shutil.copyfile(r/'resume.zip',o/'checkpoint.zip')
with (o/'queue.log').open('ab') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/loco_sweep_queue.py'),str(o)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(pid=p.pid)))
'''),flush=True)
    (OUT/'setup-verified').write_text('Queue launched; remote deadline and idle watchdog active')

def inspect():
    raw=remote('''from pathlib import Path
import json
o=Path('/workspace/mimickit_trial/loco-sweeps');s=json.loads((o/'queue_status.json').read_text());data={}
for p in o.glob('result_*.json'):
 v=json.loads(p.read_text());v['updates_count']=len(v.get('updates',[]));v.pop('updates',None);v.pop('evaluations',None);data[p.stem]=v
active=s.get('active');log=o/(active+'.log') if active else o/'queue.log'
print(json.dumps(dict(queue=s,results=data,log_tail=log.read_text()[-1800:] if log.exists() else '')))
''')
    value=json.loads(raw);save('inspection',value);print(json.dumps(value,indent=2))

def fetch():
    # Compact result files only; no model/replay streams or credentials.
    raw=remote('''from pathlib import Path
import json
o=Path('/workspace/mimickit_trial/loco-sweeps')
print(json.dumps({p.name:json.loads(p.read_text()) for p in [o/'queue_status.json',*o.glob('result_*.json')]}))
''')
    values=json.loads(raw)
    for name,value in values.items():(OUT/name).write_text(json.dumps(value,separators=(',',':')))
    print(json.dumps(values['queue_status.json']))
    for name,value in values.items():
        if name.startswith('result_'):
            print(name,value.get('phase'),len(value.get('updates',[])),len(value.get('evaluations',[])))

if __name__=='__main__':globals()[sys.argv[1]]()
