"""Isolated all-two-dead-leg crawl trial; pinned main checkpoint is rollback-only."""
import sys,json,shutil,time,shlex,zipfile
from pathlib import Path
import deploy_crawl_forward as old
from deploy_saved_sitting import remote
d=old.d;P=old.P;OUT=old.OUT;D=OUT/'crawl-only-experiment-20261102'
c=old.c;c.D=D
def preflight():
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(D/'preflight-resume.json','preflight_resume.json')
        for name in ('slow_loco_disabled.py','disabled_limb_rules.py','slow_loco_env.py','train.py','observe.py','observe_many.py','replay.py'):
            z.write(P/'pipeline'/name,'package/pipeline/'+name)
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml','manifest.json','motions.yaml','disabled_inits.npz'):
            z.write(P/'prepared'/name,'report/prepared/'+name)
        z.write(OUT/'geometry.json','report/geometry.json')
        z.write(d.ROOT/'Labs/RoboticMotionAE/preflight_crawl_only_remote.py','preflight_remote.py')
        z.write(d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    d.cloud.rp.scp(d.cloud.state()['connection'],D/'preflight-input.zip','/workspace/mimickit_trial'+'/disabled-preflight.zip',timeout=60)
    remote("from pathlib import Path;import shutil,zipfile;r=Path('/workspace/mimickit_trial');t=r/'disabled-preflight';(t/'package').mkdir(parents=True,exist_ok=True);shutil.copytree(r/'pipeline',t/'package/pipeline',dirs_exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;z=zipfile.ZipFile(r/'disabled-preflight.zip');z.extractall(t);z.close()")
    command='cd /workspace/mimickit_trial; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1'
    try:d.cloud.ssh(command,timeout=630)
    except Exception:
        print(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/preflight.log').read_text()[-8000:])"));raise
    report=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['replay_rows'] in (8,)
    d.write(D/'preflight-verified.json',report);d.write(OUT/'preflight.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='metadata'}),flush=True)

def stage():
    report=json.loads((D/'preflight-verified.json').read_text())
    assert report['passed'] and report['worlds']==2048 and report['resumed_updates']==3
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip','/workspace/mimickit_trial/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    d.write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip')))

def launch():
    # Both guards must see the same bounded setup phase before any trainer starts.
    control=json.loads((OUT/'runtime_control.json').read_text())
    assert control.get('setup_watchdog') and 360 < control['hard_stop_unix']-time.time() <= 1200
    assert control['pod_id']==d.cloud.state()['pod_id']
    actual=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/runtime_control.json').read_text())"))
    assert actual==control, 'Local and remote setup guards disagree'
    provider=d.cloud.rp.request_json('GET','/pods/'+control['pod_id'])
    assert provider['desiredStatus']=='RUNNING' and 0 < provider['costPerHr'] <= .28
    info=json.loads((D/'main-resume-checkpoint.json').read_text())
    assert info['verified'] and d.sha(info['local'])==info['sha256']
    import yaml
    with zipfile.ZipFile(info['local']) as z:
        for n in ('env_config.yaml','engine_config.yaml','agent_config.yaml'):
            previous=yaml.safe_load(z.read(n));current=yaml.safe_load((P/'prepared'/n).read_text())
            if n=='env_config.yaml':assert current.pop('slow_loco_crawl_only_experiment') is True
            assert previous==current,n
    expected=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import zipfile,hashlib;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(expected)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(info['path'],replay_rows=8,run_kind='disabled_curriculum_crawl_only_signed5');d.observe()
    shutil.copy2(OUT/'active_run.json',D/'launched-run.json')

def audit():return c.audit()

def verify():
    result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['state']=='training' and result['status']['worlds']==2048
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    assert result['resume']['iteration_offset']==20415
    assert result['model']['_obs_norm._mean']==[160]
    name=result['run']
    code=f"""import sys,json,hashlib,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/{name!r};sys.path.insert(0,str(r/'disabled-preflight'))
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
from verify_disabled_replay import verify
result=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['motion_name']=='crawl' and row['disabled_limb_code']==12 and row['cohort_index']==2
  assert row['motion_playback_rate']==.5 and row['loco_failure_penalty']==500.
  assert row['crawl_forward_reward']['form']=='signed_displacement_v1'
  assert row['target_deviation']['world_pelvis']['reset_every_ticks']==130
  assert abs(row['row_target_radii_m']['pelvis']-.8)<1e-5
print(json.dumps(result))
"""
    checked=json.loads(d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=45))
    d.write(D/'live-replay-verified.json',checked)
    d.verify()
    d.write(D/'deployment-verified.json',dict(run=name,status=result['status'],verified=True,source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],rollback_checkpoint=json.loads((D/'main-resume-checkpoint.json').read_text())['local']))

if __name__=='__main__':globals()[sys.argv[1]]()
