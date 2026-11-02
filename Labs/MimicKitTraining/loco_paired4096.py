"""Synchronized2048 production/4096 trial, preserving the latest1024 state."""
import os,sys,json,time,hashlib,zipfile,subprocess,shlex
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/'Saved/MimicKitLocomotion'
PAIR=ROOT/'Saved/MimicKitLocomotionSweeps/20261024_batch4096'
PAIR.mkdir(parents=True,exist_ok=True)
ROLE=sys.argv[1]
assert ROLE in ['main','trial']
OUT=MAIN if ROLE=='main' else PAIR
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
import deploy_locomotion_branch as d
d.OUT=OUT;os.environ['MIMICKIT_STATE_DIR']=str(OUT)
assert cloud.OUT==OUT

def save(name,value): (PAIR/(name+'.json')).write_text(json.dumps(value,indent=2))
def remote(code,timeout=55):return cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=timeout)

def prepare():
    assert ROLE=='main'
    old=json.loads((MAIN/'getup-success-prepared.json').read_text());save('previous-main-plan',old)
    source=PAIR/'paired-source.zip'
    with zipfile.ZipFile(old['source']['local']) as z,zipfile.ZipFile(source,'w') as out:
        for info in z.infolist():
            data=z.read(info.filename)
            if info.filename=='pipeline/train.py':
                before=b'(a.equipment_omni and a.worlds==1024)'
                assert data.count(before)==1
                data=data.replace(before,b'(a.equipment_omni and a.worlds in (1024,2048,4096))')
                line=b"    parser.add_argument('--seconds',type=int,default=6600)"
                assert data.count(line)==1
                data=data.replace(line,line+b"\n    parser.add_argument('--paired-start-file',type=Path)")
                line=b'    start=time.time()'
                assert data.count(line)==1
                gate=b'''    if a.paired_start_file:
        atomic_json(directory/'pair-ready.json',dict(ready_unix=time.time(),worlds=a.worlds))
        gate_deadline=time.time()+300
        while not a.paired_start_file.exists():
            if time.time()>gate_deadline:raise RuntimeError('Paired startup timed out')
            time.sleep(.1)
        gate=json.loads(a.paired_start_file.read_text())
        assert gate['run']==a.name
        while time.time()<gate['start_unix']:time.sleep(.005)
'''
                data=data.replace(line,gate+line);compile(data,'paired-train.py','exec')
                (PAIR/'paired-train.py').write_bytes(data)
            out.writestr(info,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    new=dict(local=str(source),key='mimickit/pipeline_20261014/paired4096/source_'+sha[:12]+'.zip',sha256=sha)
    cloud.rp.scp(cloud.state()['connection'],PAIR/'paired-train.py','/workspace/mimickit_trial/paired-train.py',timeout=30)
    code="""from pathlib import Path
import json,hashlib,zipfile,boto3
r=Path('/workspace/mimickit_trial')
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(r/'source.zip') as src,zipfile.ZipFile(r/'paired-source.zip','w') as dst:
 for info in src.infolist():dst.writestr(info,(r/'paired-train.py').read_bytes() if info.filename=='pipeline/train.py' else src.read(info.filename))
data=(r/'paired-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Paired source persistent readback verified')
""".replace('OLD',repr(old['source']['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(new['key']))
    print(remote(code),flush=True)
    save('source',new)
    active=json.loads((MAIN/'active_run.json').read_text())
    (MAIN/'ae30-switch.json').write_text(json.dumps(dict(old_run=active['run'],pod=active['pod'],source=new),indent=2))
    save('comparison',dict(training_seconds=2100,baseline_worlds=2048,trial_worlds=4096,source=new,
        old_1024_run=active['run'],scope='Equal wall time from synchronized training-loop release; other settings unchanged'))

def restart_trial():
    assert ROLE=='trial' and not (OUT/'pod.json').exists()
    old=ROOT/'Saved/MimicKitLocomotionSweeps/20261024_batch2048'
    state=json.loads((old/'pod.json').read_text());cloud.save(state)
    assert cloud.rp.request_json('GET','/pods/'+state['pod_id'])['desiredStatus']=='EXITED'
    cloud.rp.request_json('POST','/pods/'+state['pod_id']+'/start')
    import loco_sweep_cloud as sweep
    sweep.OUT=OUT;os.environ['MIMICKIT_STATE_DIR']=str(OUT);sweep.protect_setup()
    cloud.connect()
    print('Trial pod restarted; bounded setup guard active',flush=True)
    print(d.remote("""from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'venv'
if p.is_symlink():
 assert str(p.readlink())=='/opt/mimickit-runtime/venv';p.unlink()
(r/'runtime-cache-restored.json').unlink(missing_ok=True)
print('Stale runtime link cleared')
"""),flush=True)
    d.runtime();end=time.time()+240
    while time.time()<end:
        if d.remote("from pathlib import Path;r=Path('/workspace/mimickit_trial');print(int((r/'runtime-cache-restored.json').exists() and (r/'venv/bin/python').exists()))").strip()=='1':
            print('Trial runtime ready',flush=True);return
        time.sleep(5)
    raise RuntimeError('Trial runtime restore timed out')

def stop_main():
    assert ROLE=='main'
    import restart_locomotion_ae as r
    r.stop()

def capture_main():
    assert ROLE=='main'
    import restart_locomotion_ae as r
    r.capture()
    cp=json.loads((MAIN/'ae30-switch.json').read_text())['checkpoint'];save('checkpoint',cp)
    source=json.loads((PAIR/'source.json').read_text())
    stamp=datetime.now().astimezone().strftime('%Y%m%d_%H%M%S');save('pair-id',dict(stamp=stamp))
    for scope,worlds in [(MAIN,2048),(PAIR,4096)]:
        plan=json.loads((PAIR/'previous-main-plan.json').read_text())
        plan.update(checkpoint=cp,source=source,worlds=worlds,until_stopped=worlds==2048,
            run_suffix='uefn_locomotion_paired_'+str(worlds))
        (scope/'getup-success-prepared.json').write_text(json.dumps(plan,indent=2))
        if worlds==2048:(scope/'final-phase-prepared.json').write_text(json.dumps(plan,indent=2))
    print('Latest1024 checkpoint locally preserved and common plans ready',flush=True)

def deploy():
    p=json.loads((OUT/'getup-success-prepared.json').read_text())
    code="""from pathlib import Path
import json,hashlib,zipfile,boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
for item,name in [(SOURCE,'source.zip'),(CP,'resume.zip')]:
 data=c.get_object(Bucket='aj7d2jzwuq',Key=item['key'])['Body'].read();assert hashlib.sha256(data).hexdigest()==item['sha256'];(r/name).write_bytes(data)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p['resume_checkpoint']=CP;(r/'private.json').write_text(json.dumps(p))
for name in ['stop.request','paired-start.json','billing_stopped.json']:(r/name).unlink(missing_ok=True)
print('Same source and same checkpoint verified on GPU')
""".replace('SOURCE',repr(p['source'])).replace('CP',repr({k:p['checkpoint'][k] for k in ['key','sha256']}))
    print(remote(code),flush=True)

def launch():
    p=json.loads((OUT/'getup-success-prepared.json').read_text())
    from extend_runtime import extend
    if ROLE=='main':extend(until_stopped=True)
    else:extend(time.time()+2700)
    stamp=json.loads((PAIR/'pair-id.json').read_text())['stamp'];name=stamp+'_'+p['run_suffix']
    args=['--name',name,'--seconds','86400' if ROLE=='main' else '2100','--worlds',str(p['worlds']),
        '--control-mode','vel','--absolute-walk','--equipment-omni','/workspace/mimickit_trial/prepared',
        '--evaluate','--output-interval','100','--replay-rows','20','--resume','/workspace/mimickit_trial/resume.zip',
        '--actor-lr','1.125e-6','--resume-perturbed-motion','--paired-start-file','/workspace/mimickit_trial/paired-start.json']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds','2700',
        '--source-package',p['source']['local'],'--source-sha256',p['source']['sha256'],'--',*args],check=True)
    save(ROLE+'-active',json.loads((OUT/'active_run.json').read_text()))
    # Independent remote billing fallback, in addition to the exit watcher.
    if ROLE=='trial':
        print(remote("import subprocess;from pathlib import Path;r=Path('/workspace/mimickit_trial');log=(r/'pair-guard.log').open('ab');subprocess.Popen(['python',str(r/'pipeline/guard.py')],stdout=log,stderr=log,start_new_session=True);print('Trial remote deadline guard active')"))

def ready():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    code="""from pathlib import Path
import json
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
ready=p/'pair-ready.json'
print(json.dumps(dict(ready=ready.exists(),failure=json.loads((p/'failure.json').read_text()) if (p/'failure.json').exists() else None,log_tail=(r/(NAME+'.log')).read_text()[-500:] if not ready.exists() else '')))
""".replace('NAME',repr(name))
    x=json.loads(remote(code));save(ROLE+'-ready',x);print(json.dumps(x))

def release():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    timing=json.loads((PAIR/'timing-armed.json').read_text())
    if ROLE=='trial':
        from extend_runtime import extend
        extend(timing['billing_stop'])
    value=dict(start_unix=timing['start'],run=name)
    print(remote("from pathlib import Path;import json;p=Path('/workspace/mimickit_trial/paired-start.json');p.write_text(json.dumps("+repr(value)+"));print('Startup gate armed')"),flush=True)

def observers():
    active=json.loads((OUT/'active_run.json').read_text());name=active['run']
    if ROLE=='trial':(OUT/'geometry.json').write_bytes((MAIN/'geometry.json').read_bytes())
    old=json.loads((PAIR/'comparison.json').read_text())['old_1024_run']
    m=json.loads((MAIN/(old+'-dashboard.json')).read_text())
    m['runtime_control']=dict(path=str(OUT/'runtime_control.json'),pod_id=active['pod'],fallback_unix=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix'])
    stamp=datetime.strptime(name[:15],'%Y%m%d_%H%M%S').strftime('%Y-%m-%d_%H-%M-%S')
    m['runs']=[dict(name=stamp+name[15:],objective='uefn_omni_absolute_walk',training_outcomes=True,sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(m,indent=2));pids={}
    for kind,args in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*args],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000);pids[kind]=proc.pid
    if ROLE=='trial':
        with (OUT/'local-runtime-guard.log').open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000);pids['local_guard']=proc.pid
    (OUT/'current-run.txt').write_text(name);save(ROLE+'-observers',pids);print(json.dumps(pids))

def verify():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    code="""from pathlib import Path
import json,time
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and time.time()-s['updated_unix']<180
assert not (p/'backup_errors.json').exists() and not (p/'finished.json').exists()
print(json.dumps(dict(status=s,backup=b)))
""".replace('NAME',repr(name))
    x=json.loads(remote(code));cp=json.loads((PAIR/'checkpoint.json').read_text())
    assert x['status']['iteration']>cp['finished']['iteration']+1
    save(ROLE+'-verified',x)
    if ROLE=='main':print(remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff guard released')"))
    else:(OUT/'setup-verified').write_text('Advancing with verified backup; bounded trial controls active')
    print(json.dumps({k:x['status'][k] for k in ['iteration','samples','worlds','training_transitions_per_second']}))

def previous_helper(name,**kwargs):
    import ast
    path=Path(__file__).with_name('loco_batch2048_trial.py')
    tree=ast.parse(path.read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope=dict(globals(),OUT=PAIR);d.OUT=PAIR
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    return scope[name](**kwargs)

def fetch():
    previous_helper('fetch',baseline=ROLE=='main')

def collect_finished():
    assert ROLE=='trial'
    previous_helper('collect_finished')

def analyze():
    from analyze_batch2048_trial import summary
    seconds=json.loads((PAIR/'comparison.json').read_text())['training_seconds']
    result={label:summary(json.loads((PAIR/(label+'-data.json')).read_text()),seconds) for label in ['baseline','trial']}
    save('comparison-results',result)
    for label,s in result.items():
        print(label,json.dumps(dict(start_failure=s['first_three_minutes']['percent'],end_failure=s['last_three_minutes']['percent'],samples_per_second=s['measured_samples_per_second'])))

if __name__=='__main__':globals()[sys.argv[2]]()
