"""Sustained jiggle termination experiment, retained GPU/latest checkpoint."""
import json,sys,shutil,zipfile,shlex,time,ast
from pathlib import Path
import deploy_crawl_jiggle as j
D=j.d.OUT/'body-jiggle-audit-20261103'
j.D=D;j.c.D=D;j.x.D=D
R=j.R

def preflight():
    a=json.loads((D/'previous-run.json').read_text())
    pin=json.loads(j.remote("import json,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1];assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256'];print(json.dumps(dict(path=str(cp),sha256=b['sha256'])))"))
    j.d.write(D/'preflight-resume.json',pin)
    src=(j.d.OUT/'crawl-jiggle-20261103/preflight_remote.py').read_text()
    src=src.replace("    names=env._kin_char_model.get_body_names();", "    assert hasattr(env,'_jiggle_termination')\n    names=env._kin_char_model.get_body_names();")
    src=src.replace("    env.reset();max_torque=0.", "    env.reset();env._time_buf.fill_(.1);env._reward_buf.fill_(1.);env._jiggle_termination.failed.fill_(True)\n    env._update_done();assert (env._done_buf==1).all();torch.testing.assert_close(env._reward_buf,torch.full_like(env._reward_buf,-499.))\n    env.reset();assert not env._jiggle_termination.failed.any() and not env._jiggle_termination.streak.any()\n    max_torque=0.")
    src=src.replace("        m=row['evaluation'];", "        assert row['evaluation']['crawl_jiggle_termination']['persistence_ticks']==6\n        m=row['evaluation'];")
    src=src.replace("    assert refcost.max()<.01,refcost.max()", "    assert refcost.max()<.01,refcost.max()\n    from crawl_jiggle_termination import recorded_detection\n    assert not recorded_detection(pose,env._jiggle_hand_ids,env._pelvis_id,30.,env._jiggle_angular_ids)[0].any()")
    src=src.replace('assert not env._crawl_forward_values.any()', 'assert not env._crawl_jiggle_values.any()')
    src=src.replace('bonus=-env._crawl_jiggle_values','bonus=env._crawl_forward_values')
    old=(j.d.ROOT/'Labs/RoboticMotionAE/preflight_crawl_only_remote.py').read_text()
    test=old[old.index('    from slow_loco_disabled import signed_crawl_progress'):old.index('    def check():')]
    src=src.replace('    def check():',test+'    def check():',1)
    # Full termination/replay preflight already passed. This second bounded check
    # changes only restoration of the exact previous forward reward and zero jiggle cost.
    start=src.index('    from observe_many import MultiRecorder')
    end=src.index("if __name__=='__main__':main()",start)
    src=src[:start]+"    (out/'preflight.json').write_text(json.dumps(dict(passed=True,worlds=N,observations=160,boundary_cases=cases,resumed_updates=3,resumed_checkpoint=restored['iteration_offset']-1,forward_reward_restored=True,jiggle_cost_zero=True,independent_live_replay_required=True,seconds=time.time()-started),indent=2))\n    print('PASS restored forward reward',flush=True)\n"+src[end:]
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
        z.write(j.d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    j.d.cloud.rp.scp(j.d.cloud.state()['connection'],D/'preflight-input.zip',R+'/jiggle-termination-preflight.zip',timeout=90)
    j.remote("from pathlib import Path;import zipfile;r=Path('/workspace/mimickit_trial');t=r/'disabled-preflight';(t/'package').mkdir(parents=True,exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;zipfile.ZipFile(r/'jiggle-termination-preflight.zip').extractall(t)")
    try:j.d.cloud.ssh('cd '+R+'; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1',timeout=630)
    except Exception:j.status();raise
    report=json.loads(j.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['resumed_updates']==3
    j.d.write(D/'preflight-verified.json',report);j.d.write(j.d.OUT/'preflight.json',report)
    print('Full resumed 2048-world termination preflight passed',flush=True)

def stage():
    assert json.loads((D/'preflight-verified.json').read_text())['passed']
    calibration=json.loads((D/'termination-calibration.json').read_text());assert calibration['passed']
    assert all(calibration['counts'][k]['terminated']==0 for k in ('normal','one_leg','reference'))
    with zipfile.ZipFile(D/'preflight-input.zip') as z:
        for name in z.namelist():
            if name.startswith('package/'):
                assert z.read(name)==(j.d.P/name[len('package/'):]).read_bytes(),name

    old=json.loads((D/'previous-inventory.json').read_text())
    changed=[n for n,h in old.items() if j.d.sha(j.d.P/n)!=h]
    assert set(changed)=={'pipeline/slow_loco_disabled.py','pipeline/observe.py','pipeline/crawl_jiggle_termination.py'},changed
    j.d.bundle();shutil.copy2(j.d.OUT/'source-receipt.json',D/'source-receipt.json');j.x.stage_from_persistent()
    shutil.copy2(j.d.OUT/'crawl-jiggle-episode500-20261103/calibration.json',D/'calibration.json')

def stop():j.stop()
def launch():
    # Same safe latest-save/download/install sequence, distinct experiment name.
    original=j.d.launch
    def launch_named(cp,rows,kind,replay_interval_seconds=300):
        return original(cp,rows,'disabled_curriculum_body_jiggle_termination',replay_interval_seconds=replay_interval_seconds)
    j.d.launch=launch_named
    j.launch()
def audit():return j.audit()
def status():j.status()
def verify():
    result=j.audit();name=result['run']
    history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['state']=='training' and result['status']['worlds']==2048
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    assert result['status']['iteration']>=result['resume']['iteration_offset']+3
    code="""import json,numpy as np,sys,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
sys.path[:0]=[str(r/'pipeline'),str(r/'MimicKit/mimickit'),str(r/'disabled-preflight')]
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
from verify_disabled_replay import verify
check=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['crawl_jiggle_termination']['enabled'] and row['crawl_jiggle_termination']['persistence_ticks']==6
  assert row['crawl_jiggle_termination']['version']==2 and len(row['crawl_jiggle_termination']['angular_bodies'])==9
  assert not row['crawl_jiggle_penalty']['enabled'] and not any(row['frame_crawl_jiggle_penalty'])
  assert row['crawl_forward_reward']['enabled'] and row['crawl_forward_reward']['form']=='signed_displacement_v1'
  assert row['crawl_forward_reward']['maximum']==5
  assert row['loco_failure_penalty']==500 and row['disabled_limb_code']==12
  assert row['pelvis_reset_every_ticks']==200 and abs(row['row_target_radii_m']['pelvis']-.55)<1e-6
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(dict(independent=check,rows=[dict(frames=len(x['frame_crawl_jiggle_streak']),peak_streak=max(x['frame_crawl_jiggle_streak']),jiggle_terminated=any(x['frame_crawl_jiggle_terminated'])) for x in rows])))
""".replace('NAME',repr(name))
    meta=json.loads(j.d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
    j.d.write(D/'live-termination-metadata.json',meta)
    j.d.verify()
    j.d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],resume=result['resume'],forward_reward_restored=True,jiggle_cost_zero=True))
if __name__=='__main__':globals()[sys.argv[1]]()
