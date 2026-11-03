"""User-authorized grip/elbow update; retains GPU and immutable main rollback."""
import sys,json,time,shlex,zipfile,shutil
from pathlib import Path
import deploy_slow_policy as d
from deploy_saved_sitting import remote
D=d.OUT/'grip3-elbow150-20261102';R='/workspace/mimickit_trial'
def stage():
 d.bundle();shutil.copy2(d.OUT/'source-receipt.json',D/'source-receipt.json')
 import deploy_crawl_only_experiment as x
 x.D=D
 # Source staging requires the prior full production preflight, plus new smoke below.
 shutil.copy2(d.OUT/'preflight.json',D/'preflight-verified.json')
 x.stage_from_persistent()
 print(remote("import zipfile;from pathlib import Path;r=Path('/workspace/mimickit_trial');zipfile.ZipFile(r/'contact-source.zip').extractall(r/'grip-preflight');print('scratch source ready')"))
def smoke():
 d.cloud.rp.scp(d.cloud.state()['connection'],d.ROOT/'Labs/RoboticMotionAE/smoke_grip_remote.py',R+'/grip-preflight/smoke.py',timeout=30)
 print(d.cloud.ssh('cd /workspace/mimickit_trial; timeout 150s venv/bin/python -u grip-preflight/smoke.py > grip-preflight/smoke.log 2>&1',timeout=170))
 result=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/grip-preflight/smoke.json').read_text())"));assert result['passed'];d.write(D/'smoke.json',result);print(json.dumps(result))
def stop():
 assert json.loads((D/'smoke.json').read_text())['passed']
 old=json.loads((D/'previous-run.json').read_text());control=dict(pod_id=old['pod'],hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False)
 d.write(d.OUT/'runtime_control.json',control)
 print(remote(f'''import json,os,signal
from pathlib import Path
r=Path({R!r});x={old!r}
assert x['run'].encode() in (Path('/proc')/str(x['pid'])/'cmdline').read_bytes()
g=Path('/proc')/str(x['exit_guard_pid'])/'cmdline'
if g.exists() and x['run'].encode() in g.read_bytes():os.kill(x['exit_guard_pid'],signal.SIGTERM)
(r/'runtime_control.json').write_text(json.dumps({control!r}))
(r/'runs'/x['run']/'stop.request').write_text('Authorized grip3 elbow150 update; preserve latest and retain GPU')
print('graceful checkpoint handoff requested; GPU retained')'''))
def launch():
 old=json.loads((D/'previous-run.json').read_text())
 info=json.loads(remote(f'''import json,hashlib
from pathlib import Path
r=Path({R!r});x={old!r};p=r/'runs'/x['run']
proc=Path('/proc')/str(x['pid'])/'cmdline'
assert not proc.exists() or x['run'].encode() not in proc.read_bytes(),'Waiting for old trainer'
assert (p/'finished.json').exists()
b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1]
assert cp.name.endswith('_final.zip') and hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
print(json.dumps(dict(backup=b,path=str(cp),finished=json.loads((p/'finished.json').read_text()))))'''))
 b=info['backup'];folder=d.OUT/'preserved-latest'/old['run'];folder.mkdir(parents=True,exist_ok=True);cp=folder/b['key'].split('/')[-1]
 stream=d.cloud.s3().get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=b['key'])['Body'];tmp=cp.with_suffix('.part')
 with tmp.open('wb') as f:
  for chunk in iter(lambda:stream.read(1024*1024),b''):f.write(chunk)
 stream.close();assert d.sha(tmp)==b['sha256'];tmp.replace(cp)
 import yaml
 with zipfile.ZipFile(cp) as z:
  assert z.testzip() is None
  for n in ('env_config.yaml','agent_config.yaml'):assert yaml.safe_load(z.read(n))==yaml.safe_load((d.P/'prepared'/n).read_text())
  assert yaml.safe_load(z.read('engine_config.yaml'))==yaml.safe_load((D/'before/prepared/engine_config.yaml').read_text())
 d.write(D/'resume-checkpoint.json',dict(**info,local=str(cp),verified=True))
 expected=json.loads((D/'staged.json').read_text())['source_sha256']
 print(remote(f"import zipfile,hashlib;from pathlib import Path;r=Path({R!r});assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=={expected!r};zipfile.ZipFile(r/'contact-source.zip').extractall(r);print('verified source installed')"))
 d.launch(info['path'],8,'disabled_curriculum_crawl_grip3_elbow150',replay_interval_seconds=300);d.observe();shutil.copy2(d.OUT/'active_run.json',D/'launched-run.json')
def status():
 a=json.loads((d.OUT/'active_run.json').read_text())
 print(remote(f"from pathlib import Path;import json,time;r=Path({R!r});p=r/'runs'/{a['run']!r};z=json.loads((p/'status.json').read_text()) if (p/'status.json').exists() else {{}};print(json.dumps({{k:z.get(k) for k in ['state','iteration','samples','updated_unix','worlds']}}));print((r/({a['run']!r}+'.log')).read_text()[-1700:])"))
def audit():
 import deploy_contact_cleanup as c
 c.D=D
 return c.audit()
def verify():
 result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
 assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
 assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
 assert result['model']['_obs_norm._mean']==[160]
 name=result['run']
 code="""import json,hashlib,sys,numpy as np,yaml
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
for n,h in json.loads((r/'source-inventory.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
checks=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['motion_name']=='crawl' and row['disabled_limb_code']==12 and row['motion_playback_rate']==.5
  assert row['loco_failure_penalty']==500 and row['crawl_forward_reward']['form']=='signed_displacement_v1'
cfg=yaml.safe_load((p/'selected_engine.yaml').read_text())
assert cfg['uefn_motor_torque_caps_nm']=={'right_lower_arm':150.,'left_lower_arm':150.}
assert cfg['transfer_ground_friction_multipliers']=={n:3. for n in ('right_hand','left_hand','right_lower_arm','left_lower_arm')}
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(checks))
""".replace('NAME',repr(name))
 checked=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45));d.write(D/'replay-verified.json',checked)
 d.verify();d.write(D/'verified.json',dict(run=name,source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],status=result['status'],passed=True))
def postcheck():
 a=json.loads((d.OUT/'active_run.json').read_text());name=a['run']
 code=f"""import json,time
from pathlib import Path
r=Path({R!r});p=r/'runs'/{name!r};s=json.loads((p/'status.json').read_text());c=json.loads((r/'runtime_control.json').read_text())
assert c['until_stopped'] and not c['setup_watchdog']
assert not (p/'finished.json').exists() and not (p/'failure.json').exists()
assert s['state']=='training' and time.time()-s['updated_unix']<300
assert {name!r}.encode() in (Path('/proc')/{str(a['pid'])!r}/'cmdline').read_bytes()
e=json.loads((p/'evaluation.json').read_text())
print(json.dumps(dict(status={{k:s[k] for k in ('iteration','samples','updated_unix')}},replay_iteration=e['iteration'],replay_generated=e['replay']['generated_unix'],checked_unix=time.time())))
"""
 result=json.loads(remote(code));f=D/'post-release-statuses.json';h=json.loads(f.read_text()) if f.exists() else [];h.append(result);d.write(f,h);print(json.dumps(result))
if __name__=='__main__':globals()[sys.argv[1]]()
