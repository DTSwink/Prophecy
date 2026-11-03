"""Half contact friction for disabled bodies; retained GPU/latest continuation."""
import json,sys,shutil,zipfile,shlex,time
from pathlib import Path
import deploy_crawl_jiggle as j
D=j.d.OUT/'dead-friction-half-20261103';R=j.R
j.D=D;j.c.D=D;j.x.D=D

def preflight():
    a=json.loads((D/'previous-run.json').read_text())
    pin=json.loads(j.remote("import json,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1];assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256'];print(json.dumps(dict(path=str(cp),sha256=b['sha256'])))"))
    j.d.write(D/'preflight-resume.json',pin)
    src=(j.d.OUT/'action-jiggle-20261103/preflight_remote.py').read_text()
    src=src.replace("    N=2048;","    ec['uefn_asset_directory']=str(p/'assets/uefn')\n    N=2048;",1)
    extra=(D/'friction_checks.py').read_text()
    src=src.replace("    assert hasattr(env,'_jiggle_termination')",extra+"\n    assert hasattr(env,'_jiggle_termination')",1)
    (D/'preflight_remote.py').write_text(src)
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(D/'preflight-resume.json','preflight_resume.json')
        for path in (j.d.P/'pipeline').glob('*.py'):z.write(path,'package/pipeline/'+path.name)
        for path in (j.d.P/'assets').rglob('*'):
            if path.is_file() and '__pycache__' not in str(path):z.write(path,'package/'+path.relative_to(j.d.P).as_posix())
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml','manifest.json','motions.yaml','disabled_inits.npz'):
            z.write(j.d.P/'prepared'/name,'report/prepared/'+name)
        z.write(j.d.OUT/'geometry.json','report/geometry.json')
        z.write(D/'preflight_remote.py','preflight_remote.py')
        z.write(j.d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    j.d.cloud.rp.scp(j.d.cloud.state()['connection'],D/'preflight-input.zip',R+'/dead-friction-preflight.zip',timeout=90)
    j.remote("from pathlib import Path;import zipfile;r=Path('/workspace/mimickit_trial');zipfile.ZipFile(r/'dead-friction-preflight.zip').extractall(r/'disabled-preflight')")
    try:j.d.cloud.ssh('cd '+R+'; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1',timeout=630)
    except Exception:j.status();raise
    report=json.loads(j.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['resumed_updates']==3
    j.d.write(D/'preflight-verified.json',report);j.d.write(j.d.OUT/'preflight.json',report)
    print('Full 2048-world resumed preflight passed',flush=True)

def stage():
    assert json.loads((D/'preflight-verified.json').read_text())['passed']
    old=json.loads((D/'previous-inventory.json').read_text())
    changed=[n for n,h in old.items() if j.d.sha(j.d.P/n)!=h]
    assert set(changed)==set(json.loads((D/'change.json').read_text())['changed_files']),changed
    with zipfile.ZipFile(D/'preflight-input.zip') as z:
        for n in changed:assert z.read('package/'+n)==(j.d.P/n).read_bytes(),n
    j.d.bundle();shutil.copy2(j.d.OUT/'source-receipt.json',D/'source-receipt.json');j.x.stage_from_persistent()

def stop():j.stop()
def launch():
    original=j.d.launch
    j.d.launch=lambda cp,rows,kind,replay_interval_seconds=300:original(cp,rows,'disabled_curriculum_dead_friction_half',replay_interval_seconds=replay_interval_seconds)
    j.launch()
def audit():return j.audit()
def status():j.status()
def verify():
    result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    name=result['run']
    code="""import json,hashlib,sys,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
sys.path[:0]=[str(r/'pipeline'),str(r/'MimicKit/mimickit'),str(r/'disabled-preflight')]
from verify_disabled_replay import verify
checks=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['disabled_limb_friction']['multiplier']==.5
  assert row['disabled_limb_code']==12 and row['loco_failure_penalty']==500
  assert row['policy_action_jiggle']['enabled'] and row['policy_action_jiggle']['weight']==200
  assert row['crawl_forward_reward']['enabled']
print(json.dumps(checks))
""".replace('NAME',repr(name))
    checks=json.loads(j.d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=50))
    j.d.write(D/'replay-verified.json',checks);j.d.verify()
    j.d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],disabled_friction_multiplier=.5))
if __name__=='__main__':globals()[sys.argv[1]]()
