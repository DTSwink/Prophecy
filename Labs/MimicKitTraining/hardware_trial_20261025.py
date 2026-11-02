"""Prepared hardware comparison; paid actions require a separate human approval receipt.

Every mutation is confined to this trial's state/pod. Preparation reads production
and preserves a checkpoint; it never pauses, stops, or restarts the main trainer.
"""
import ast
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT/'Saved/MimicKitLocomotion'
OUT = MAIN/'perf-lossless-20261024/hardware-options/rtx4090-trial'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['MIMICKIT_STATE_DIR'] = str(OUT)
import cloud
from backup import verified_readback

assert cloud.OUT == OUT.resolve() and cloud.OUT != MAIN.resolve()


def save(name, data):
    (OUT/(name+'.json')).write_text(json.dumps(data, indent=2))


def remote(code, timeout=45):
    owned_pod()
    return cloud.ssh('python -c '+shlex.quote(code), timeout=timeout)


def owned_pod():
    value = cloud.state()
    plan = json.loads((OUT/'plan.json').read_text())
    assert value['pod_id'] not in plan['protected_pods']
    assert value['name'] == plan['pod_name']
    return value


def prepare():
    active = json.loads((MAIN/'active_run.json').read_text())
    main = json.loads((MAIN/'pod.json').read_text())
    prepared = json.loads((MAIN/'getup-success-prepared.json').read_text())
    source = prepared['source']
    assert hashlib.sha256(Path(source['local']).read_bytes()).hexdigest() == source['sha256']
    code = '''from pathlib import Path
import hashlib,json,shutil,time,boto3
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());assert s['state']=='training' and time.time()-s['updated_unix']<180
b=json.loads((p/'backup_status.json').read_text());cp=p/Path(b['key']).name
assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
o=r/'perf-lossless-20261024/hardware-baseline';o.mkdir(exist_ok=True)
shutil.copyfile(cp,o/'checkpoint.zip')
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
key='mimickit/pipeline_20261014/hardware-trial/'+b['sha256']+'.zip'
c.copy_object(Bucket='aj7d2jzwuq',Key=key,CopySource={'Bucket':'aj7d2jzwuq','Key':b['key']})
body=c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'];h=hashlib.sha256()
for block in iter(lambda:body.read(4*1024*1024),b''):h.update(block)
body.close();assert h.hexdigest()==b['sha256']
b.update(preserved_key=key,origin_key=b['key'],key=key)
print(json.dumps(b))
'''.replace('NAME', repr(active['run']))
    command = '/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code)
    result = subprocess.run(cloud.rp.ssh_base(main['connection'])+['bash', '-lc', shlex.quote(command)],
                            capture_output=True, text=True, check=True, timeout=60)
    cp = json.loads(result.stdout)
    protected = [main['pod_id']]
    recovery = ROOT/'Saved/MimicKitEquipment/pod.json'
    if recovery.exists():
        protected.append(json.loads(recovery.read_text())['pod_id'])
    plan = dict(checkpoint=cp, source=source, baseline=active, protected_pods=protected,
                pod_name='mimickit-hardware4090-20261025', gpu='NVIDIA GeForce RTX 4090',
                ceiling=.89, maximum_paid_seconds=1200, maximum_gpu_cost_usd=.30,
                worlds=2048, seed=20261025, warmup_updates=2, measured_updates=8,
                actor_lr=1.125e-6, com2_weight=56.41750205477203,
                precision='FP32 highest; TF32 disabled', authorization='pending',
                promotion='No migration or production changes from this trial',
                measurement='Same pinned checkpoint/source/seed; warm full-update wall time, unchanged optimizer/physics. Not a learning-speed or 10x claim.')
    save('plan', plan); save('getup-success-prepared', plan)
    print(json.dumps(dict(prepared=True, checkpoint=cp['sha256'], source=source['sha256'], paid_actions=False)))


def allocate_approved():
    plan = json.loads((OUT/'plan.json').read_text())
    approval = json.loads((OUT/'human-approval.json').read_text())
    assert approval['approved'] is True
    assert approval['ceiling'] >= plan['ceiling'] and approval['maximum_paid_seconds'] >= 1200
    assert approval['pod_name'] == plan['pod_name']
    assert not (OUT/'pod.json').exists()
    assert not (OUT/'allocation-attempt.json').exists(), 'Reconcile the previous request; never blindly allocate again'
    existing = [v for v in cloud.rp.request_json('GET', '/pods') if v.get('name') == plan['pod_name']]
    assert not existing, 'Named pod already exists; reconcile it without creating another'
    save('allocation-attempt', dict(started_unix=time.time(), name=plan['pod_name'], outcome='pending'))
    try:
        cloud.allocate(plan['gpu'], plan['ceiling'], 'SECURE', seconds=1200, name=plan['pod_name'])
    except Exception:
        # A timed-out POST may still have allocated compute. Recover its unique
        # identity, then the outer failure path stops it; never retry the POST.
        if not (OUT/'pod.json').exists():
            matches = [v for v in cloud.rp.request_json('GET', '/pods') if v.get('name') == plan['pod_name']]
            assert len(matches) <= 1, 'Ambiguous allocation; inspect the exact named pods'
            if matches:
                value = matches[0]
                cloud.save(dict(pod_id=value['id'], name=plan['pod_name'], gpu=plan['gpu'],
                                created_unix=time.time(), cost_per_hour=value.get('costPerHr'),
                                recovered_after_unknown_outcome=True))
        raise
    pod = owned_pod(); end = pod['created_unix']+1180
    save('runtime_control', dict(pod_id=pod['pod_id'], hard_stop_unix=end,
                                 until_stopped=False, updated_unix=time.time()))
    code = ('import sys,time;from pathlib import Path;'
            'sys.path.insert(0,'+repr(str(ROOT/'Labs/MimicKitTraining'))+');'
            'import cloud;from billing_stop import stop_and_confirm;'
            'time.sleep(max(0,'+repr(end)+'-time.time()));'
            'stop_and_confirm('+repr(pod['pod_id'])+',cloud.rp.load_api_key(),'
            'Path('+repr(str(OUT/'hard-stop.json'))+'),"Hardware trial absolute deadline")')
    try:
        with (OUT/'guard.log').open('ab') as log:
            guard = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=log, creationflags=0x08000000)
        save('guard', dict(pid=guard.pid, deadline=end))
        cloud.connect(); cloud.ssh('mkdir -p /workspace/mimickit_trial')
    except Exception:
        stop()
        raise


def reuse(name):
    owned_pod()
    source = (ROOT/'Labs/MimicKitTraining/resume_getup_success.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(globals()); exec(ast.get_source_segment(source, node), scope); scope[name]()


def provision():
    reuse('provision')


def runtime():
    # Source download must have finished before invoking this stage.
    reuse('runtime')


def launch():
    pod = owned_pod(); plan = json.loads((OUT/'plan.json').read_text())
    assert time.time() < pod['created_unix']+900, 'Insufficient time left; stop trial'
    con = pod['connection']; directory = '/workspace/mimickit_trial'
    cloud.rp.scp(con, Path(__file__).with_name('benchmark_hardware_20261025.py'), directory+'/hardware_benchmark.py', timeout=30)
    cloud.rp.scp(con, OUT/'plan.json', directory+'/hardware-plan.json', timeout=30)
    # Preserve compact evidence before stopping billing on either success/failure.
    runner = '''import json,subprocess,sys,hashlib
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');sys.path.insert(0,str(r/'pipeline'))
from billing_stop import stop_and_confirm
private=json.loads((r/'private.json').read_text());plan=json.loads((r/'hardware-plan.json').read_text())
assert private['pod_id'] not in plan['protected_pods']
evidence={'pod_id':private['pod_id'],'checkpoint_sha256':plan['checkpoint']['sha256']}
try:
 p=subprocess.run(['timeout','240',str(r/'venv/bin/python'),'-u',str(r/'hardware_benchmark.py'),'--plan',str(r/'hardware-plan.json'),'--checkpoint',str(r/'resume.zip'),'--output',str(r/'hardware-result')],cwd=r)
 evidence['exit_code']=p.returncode
 path=r/'hardware-result/complete.json'
 if path.exists():evidence['result']=json.loads(path.read_text())
 data=json.dumps(evidence).encode();digest=hashlib.sha256(data).hexdigest()
 c=boto3.client('s3',**private['s3']);key='mimickit/pipeline_20261014/hardware-trial/'+plan['pod_name']+'/result.json'
 c.put_object(Bucket='aj7d2jzwuq',Key=key,Body=data,Metadata={'sha256':digest})
 assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read()).hexdigest()==digest
finally:
 stop_and_confirm(private['pod_id'],private['runpod_api_key'],r/'hardware-stopped.json','Hardware benchmark finished or failed')
'''
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)/'runner.py'; path.write_text(runner)
        cloud.rp.scp(con, path, directory+'/hardware_runner.py', timeout=30)
    print(remote('''import subprocess,json
from pathlib import Path
r=Path('/workspace/mimickit_trial');assert (r/'runtime-cache-restored.json').exists()
with (r/'hardware-guard.log').open('ab') as log:
 g=subprocess.Popen(['python','pipeline/guard.py'],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
with (r/'hardware-benchmark.log').open('ab') as log:
 p=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'hardware_runner.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(pid=p.pid,guard=g.pid)))
'''))


def collect():
    pod = owned_pod(); plan = json.loads((OUT/'plan.json').read_text())
    state = cloud.rp.request_json('GET', '/pods/'+pod['pod_id'])
    assert state['id'] == pod['pod_id'] and state['desiredStatus'] == 'EXITED', 'Trial still live; inspect its existing process'
    key = 'mimickit/pipeline_20261014/hardware-trial/'+plan['pod_name']+'/result.json'
    obj = cloud.s3().get_object(Bucket=cloud.rp.VOLUME_ID, Key=key)
    raw = obj['Body'].read()
    assert hashlib.sha256(raw).hexdigest() == obj['Metadata']['sha256']
    result = json.loads(raw)
    assert result['pod_id'] == pod['pod_id'] and result['checkpoint_sha256'] == plan['checkpoint']['sha256']
    save('result', result); save('stopped', dict(pod=pod['pod_id'], confirmed=True, state='EXITED', checked_unix=time.time()))
    print(json.dumps(dict(complete=result.get('exit_code') == 0, billing_stopped=True)))


def stop():
    from billing_stop import stop_and_confirm
    pod = owned_pod()
    stop_and_confirm(pod['pod_id'], cloud.rp.load_api_key(), OUT/'stopped.json', 'Hardware comparison completed or failed')
    print('Trial billing stopped; main pod untouched')


if __name__ == '__main__':
    action = sys.argv[1]
    assert action in ['prepare', 'allocate_approved', 'provision', 'runtime', 'launch', 'collect', 'stop']
    try:
        globals()[action]()
    except Exception:
        if action not in ['prepare', 'collect'] and (OUT/'pod.json').exists():
            stop()
        raise
