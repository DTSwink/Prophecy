"""Upper-body implicit passive damping experiment, retained GPU/latest checkpoint."""
import json,sys,shutil,zipfile,shlex,time,ast
from pathlib import Path
import deploy_crawl_jiggle as j
D=j.d.OUT/'upperbody-damping-20261103'
j.D=D;j.c.D=D;j.x.D=D
R=j.R

def preflight():
    a=json.loads((D/'previous-run.json').read_text())
    pin=json.loads(j.remote("import json,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1];assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256'];print(json.dumps(dict(path=str(cp),sha256=b['sha256'])))"))
    j.d.write(D/'preflight-resume.json',pin)
    src=(j.d.OUT/'crawl-jiggle-20261103/preflight_remote.py').read_text()
    src=src.replace("    N=2048;", "    ec['uefn_asset_directory']=str(p/'assets/uefn')\n    N=2048;")
    src=src.replace("    names=env._kin_char_model.get_body_names();", "    from damping_selftest import check_damping\n    check_damping(env,out)\n    names=env._kin_char_model.get_body_names();")
    src=src.replace("        m=row['evaluation'];", "        assert row['evaluation']['passive_upperbody_damping']['bodies']['head']['coefficient_nm_s_per_rad']==5.\n        m=row['evaluation'];")
    ast.parse(src);(D/'preflight_remote.py').write_text(src)
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(D/'preflight-resume.json','preflight_resume.json')
        for path in (j.d.P/'pipeline').glob('*.py'):z.write(path,'package/pipeline/'+path.name)
        for path in (j.d.P/'assets').rglob('*'):
            if path.is_file() and '__pycache__' not in str(path):z.write(path,'package/'+path.relative_to(j.d.P).as_posix())
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml','manifest.json','motions.yaml','disabled_inits.npz'):
            z.write(j.d.P/'prepared'/name,'report/prepared/'+name)
        z.write(j.d.OUT/'geometry.json','report/geometry.json')
        z.write(D/'preflight_remote.py','preflight_remote.py')
        z.write(j.d.ROOT/'Labs/RoboticMotionAE/test_passive_joint_damping.py','damping_selftest.py')
        z.write(j.d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    j.d.cloud.rp.scp(j.d.cloud.state()['connection'],D/'preflight-input.zip',R+'/upper-damping-preflight.zip',timeout=90)
    j.remote("from pathlib import Path;import zipfile;r=Path('/workspace/mimickit_trial');t=r/'disabled-preflight';(t/'package').mkdir(parents=True,exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;zipfile.ZipFile(r/'upper-damping-preflight.zip').extractall(t)")
    try:j.d.cloud.ssh('cd '+R+'; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1',timeout=630)
    except Exception:j.status();raise
    report=json.loads(j.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['resumed_updates']==3
    j.d.write(D/'preflight-verified.json',report);j.d.write(j.d.OUT/'preflight.json',report)
    check=json.loads(j.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/damping-check.json').read_text())"))
    assert check['passed'];j.d.write(D/'damping-check.json',check)
    print('Full resumed 2048-world damping preflight passed',flush=True)

def stage():
    assert json.loads((D/'preflight-verified.json').read_text())['passed']
    old=json.loads((D/'previous-inventory.json').read_text())
    changed=[n for n,h in old.items() if j.d.sha(j.d.P/n)!=h]
    assert set(changed)=={'assets/MimicKitTransfer/contact_engine.py','assets/MimicKitTransfer/sequential_contact_adapter.py','pipeline/observe.py'},changed
    j.d.bundle();shutil.copy2(j.d.OUT/'source-receipt.json',D/'source-receipt.json');j.x.stage_from_persistent()
    shutil.copy2(j.d.OUT/'crawl-jiggle-episode500-20261103/calibration.json',D/'calibration.json')

def stop():j.stop()
def launch():
    # Same safe latest-save/download/install sequence, distinct experiment name.
    original=j.d.launch
    def launch_named(cp,rows,kind,replay_interval_seconds=300):
        return original(cp,rows,'disabled_curriculum_upper_damping',replay_interval_seconds=replay_interval_seconds)
    j.d.launch=launch_named
    j.launch()
def audit():return j.audit()
def status():j.status()
def verify():
    result=j.audit();name=result['run']
    code="import json,numpy as np;from pathlib import Path;z=np.load('/workspace/mimickit_trial/runs/"+name+"/replay.npz',allow_pickle=False);rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8;assert all(r['passive_upperbody_damping']['bodies']['head']['coefficient_nm_s_per_rad']==5. and len(r['passive_upperbody_damping']['bodies'])==8 for r in rows);print(json.dumps(rows[0]['passive_upperbody_damping']))"
    meta=json.loads(j.d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
    j.d.write(D/'live-damping-metadata.json',meta)
    j.verify()
if __name__=='__main__':globals()[sys.argv[1]]()
