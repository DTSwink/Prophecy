"""Restore pre-grip checkpoint/physics, retaining the accepted wall-clock replay cadence."""
import sys,json,time,shutil,zipfile,shlex
from pathlib import Path
import deploy_slow_policy as d
from deploy_saved_sitting import remote
import deploy_grip_update as g
D=d.OUT/'restore-crawl-baseline-20261102';OLD=d.OUT/'grip3-elbow150-20261102';R='/workspace/mimickit_trial'
def prepare():
 D.mkdir(exist_ok=True);assert not (D/'previous-run.json').exists()
 a=json.loads((d.OUT/'active_run.json').read_text());assert a['run']==json.loads((OLD/'launched-run.json').read_text())['run']
 pod=d.cloud.rp.request_json('GET','/pods/'+a['pod']);assert pod['desiredStatus']=='RUNNING' and pod['costPerHr']<=.28
 inv=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/source-inventory.json').read_text())"))
 assert all(d.sha(d.P/n)==h for n,h in inv.items())
 d.write(D/'previous-run.json',a);d.write(D/'cancelled-source-inventory.json',inv)
 cp=json.loads((OLD/'resume-checkpoint.json').read_text());assert d.sha(cp['local'])==cp['backup']['sha256'];d.write(D/'resume-checkpoint.json',cp)
 for rel in ['prepared/engine_config.yaml','assets/MimicKitTransfer/contact_engine.py','assets/MimicKitTransfer/sequential_contact_adapter.py']:
  shutil.copy2(OLD/'before'/rel,d.P/rel)
 shutil.copy2(d.P/'prepared/engine_config.yaml',d.OUT/'prepared/engine_config.yaml')
 s=(OLD/'before/pipeline/train.py').read_text()
 i=s.index("    parser.add_argument('--output-interval'")
 s=s[:i]+"    parser.add_argument('--replay-interval-seconds',type=float,default=None,help='Wall-clock evaluation/checkpoint cadence; overrides iteration cadence')\n"+s[i:]
 needle="    agent._output_train_model=lambda it,*unused:snapshot(it,'upstream output interval')"
 assert needle in s
 s=s.replace(needle,needle+'''
    if a.replay_interval_seconds is not None:
        assert a.evaluate and a.replay_interval_seconds > 0
        next_output=[0.0]
        def output_due():
            now=time.monotonic()
            if now < next_output[0]:return False
            next_output[0]=now+a.replay_interval_seconds
            return True
        agent._output_due=output_due
''')
 (d.P/'pipeline/train.py').write_text(s)
 baseline=json.loads((OLD/'previous-inventory.json').read_text());diff=[n for n,h in baseline.items() if d.sha(d.P/n)!=h]
 assert set(diff)=={'pipeline/train.py','MimicKit/mimickit/learning/base_agent.py'},diff
 import yaml
 with zipfile.ZipFile(cp['local']) as z:
  assert z.testzip() is None
  for n in ('engine_config.yaml','env_config.yaml','agent_config.yaml'):assert yaml.safe_load(z.read(n))==yaml.safe_load((d.P/'prepared'/n).read_text()),n
 d.write(D/'baseline-verified.json',dict(passed=True,checkpoint=20726,sha256=cp['backup']['sha256'],only_changed_files=diff,physics_exact_previous=True,configs_exact_checkpoint=True))
 d.bundle();shutil.copy2(d.OUT/'source-receipt.json',D/'source-receipt.json')
 import deploy_crawl_only_experiment as x
 x.D=D;shutil.copy2(d.OUT/'preflight.json',D/'preflight-verified.json');x.stage_from_persistent()
 print('Previous physics/config/source restored; only replay cadence code differs')
def stop():
 assert json.loads((D/'baseline-verified.json').read_text())['passed']
 a=json.loads((D/'previous-run.json').read_text());c=dict(pod_id=a['pod'],hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False)
 d.write(d.OUT/'runtime_control.json',c)
 print(remote(f'''import json,os,signal
from pathlib import Path
r=Path({R!r});a={a!r}
assert a['run'].encode() in (Path('/proc')/str(a['pid'])/'cmdline').read_bytes()
p=Path('/proc')/str(a['exit_guard_pid'])/'cmdline'
if p.exists() and a['run'].encode() in p.read_bytes():os.kill(a['exit_guard_pid'],signal.SIGTERM)
(r/'runtime_control.json').write_text(json.dumps({c!r}))
(r/'runs'/a['run']/'stop.request').write_text('User cancelled grip/elbow experiment; restore pre-change checkpoint20726, retain GPU')
print('Graceful cancellation requested; GPU retained')'''))
def launch():
 a=json.loads((D/'previous-run.json').read_text());cp=json.loads((D/'resume-checkpoint.json').read_text());digest=json.loads((D/'staged.json').read_text())['source_sha256']
 result=json.loads(remote(f'''import json,hashlib,zipfile
from pathlib import Path
r=Path({R!r});a={a!r};p=r/'runs'/a['run'];proc=Path('/proc')/str(a['pid'])/'cmdline'
assert not proc.exists() or a['run'].encode() not in proc.read_bytes(),'Waiting for cancelled trainer final save'
assert (p/'finished.json').exists()
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
assert hashlib.sha256(Path({cp['path']!r}).read_bytes()).hexdigest()=={cp['backup']['sha256']!r}
assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=={digest!r}
zipfile.ZipFile(r/'contact-source.zip').extractall(r)
print(json.dumps(dict(cancelled_run=a['run'],retained_final=b)))'''))
 d.write(D/'cancelled-experiment.json',result)
 d.launch(cp['path'],8,'disabled_curriculum_crawl_signed5_restored',replay_interval_seconds=300);d.observe();shutil.copy2(d.OUT/'active_run.json',D/'launched-run.json')
def audit():
 import deploy_contact_cleanup as c
 c.D=D;return c.audit()
def verify():
 result=audit();history=json.loads((D/'advancing-statuses.json').read_text());assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
 assert result['resume']['iteration_offset']==20727 and result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
 assert result['model']['_obs_norm._mean']==[160]
 name=result['run'];code="""import json,sys,hashlib,yaml,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
for n,h in json.loads((r/'source-inventory.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
cfg=yaml.safe_load((p/'selected_engine.yaml').read_text());assert 'uefn_motor_torque_caps_nm' not in cfg and 'transfer_ground_friction_multipliers' not in cfg
sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
v=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for x in rows:assert x['motion_name']=='crawl' and x['disabled_limb_code']==12 and x['motion_playback_rate']==.5 and x['loco_failure_penalty']==500 and x['crawl_forward_reward']['form']=='signed_displacement_v1'
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(v))
""".replace('NAME',repr(name))
 v=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45));d.write(D/'replay-verified.json',v)
 d.verify();d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],source_sha256=json.loads((D/'staged.json').read_text())['source_sha256']))
def postcheck():
 g.D=D;g.postcheck()
def status():g.status()
if __name__=='__main__':globals()[sys.argv[1]]()
