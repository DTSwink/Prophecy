"""In-place continuation on the retained pod, without stopping/reallocating it."""
import json,sys,shlex,time,hashlib,zipfile
from pathlib import Path
import deploy_slow_policy as d
OUT=d.OUT; receipt=OUT/'user-pose-20261031'
OLD='20261031_175934_uefn_slowloco_unperturbed_2048'
CP=OUT/'preserved-latest/20261031_171941_uefn_slowloco_unperturbed_2048/checkpoint_0001436_final.zip'
REMOTE='/workspace/mimickit_trial'
def remote(code):return d.cloud.ssh('python -c '+shlex.quote(code),timeout=45)
def stage():
    assert d.sha(CP)=='e0a48a00df0be0a18b4e53a5fb4795c25eebdd6fcff0e8f1908cc6176c635e24'
    with zipfile.ZipFile(CP) as z:assert z.testzip() is None
    d.bundle();s=d.cloud.state();assert s['pod_id']=='5xs589fdlcb7nr'
    for local,name in [(OUT/'source.zip','user-pose-source.zip'),(CP,'user-pose-resume.zip')]:
        d.cloud.rp.scp(s['connection'],local,REMOTE+'/'+name,timeout=90)
        assert remote(f"import hashlib;print(hashlib.sha256(open('{REMOTE}/{name}','rb').read()).hexdigest())").strip()==d.sha(local)
    print('source and safe checkpoint staged and verified')
def stop_trainer():
    # Remove only the old process-exit guard before graceful trainer replacement.
    code=f'''import json,os,signal,time
from pathlib import Path
r=Path('{REMOTE}');name='{OLD}'
x=json.loads((r/(name+'-launch.json')).read_text())
assert name.encode() in (Path('/proc')/str(x['pid'])/'cmdline').read_bytes()
g=Path('/proc')/str(x['exit_guard_pid'])/'cmdline'
if g.exists() and name.encode() in g.read_bytes():os.kill(x['exit_guard_pid'],signal.SIGTERM)
c=json.loads((r/'runtime_control.json').read_text());c.update(hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False)
(r/'runtime_control.json').write_text(json.dumps(c))
(r/'runs'/name/'stop.request').write_text('User approved saved sitting pose continuation; retain GPU')
print(json.dumps(dict(trainer=x['pid'],old_guard=x['exit_guard_pid'],graceful_stop_requested=True)))
'''
    print(remote(code))
def status():
    a=json.loads((OUT/'active_run.json').read_text());name=a['run']
    print(remote(f'''import json,time
from pathlib import Path
r=Path('{REMOTE}');p=r/'runs'/'{name}'
f=p/'status.json';s=json.loads(f.read_text()) if f.exists() else {{}}
print(json.dumps(dict(run='{name}',status={{k:s.get(k) for k in ['state','iteration','samples','updated_unix']}},finished=(p/'finished.json').exists(),failure=(p/'failure.json').exists(),backup_errors=(p/'backup_errors.json').exists(),trainer_alive=(Path('/proc')/'{a['pid']}'/'cmdline').exists())))
'''))
def launch():
    print(remote(f'''import json,zipfile,hashlib
from pathlib import Path
r=Path('{REMOTE}');name='{OLD}'
x=json.loads((r/(name+'-launch.json')).read_text())
p=Path('/proc')/str(x['pid'])/'cmdline'
assert not p.exists() or name.encode() not in p.read_bytes(),'Old trainer still running'
assert (r/'runs'/name/'finished.json').exists()
with zipfile.ZipFile(r/'user-pose-source.zip') as z:z.extractall(r)
for n,h in json.loads((r/'source-inventory.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
print('Updated targets installed, source verified')
'''))
    d.launch(REMOTE+'/user-pose-resume.zip');d.observe()
if __name__=='__main__':globals()[sys.argv[1]]()
