"""Replace crawl progress bonus with temporal jiggle cost; same retained GPU."""
import ast,json,shutil,sys,time,shlex,zipfile
import deploy_slow_policy as d
import deploy_contact_cleanup as c
import deploy_crawl_only_experiment as x
from deploy_saved_sitting import remote
D=d.OUT/'crawl-jiggle-20261103';R='/workspace/mimickit_trial';c.D=D;x.D=D

def inventory():
    D.mkdir(exist_ok=True)
    assert not (D/'previous-run.json').exists()
    a=json.loads((d.OUT/'active_run.json').read_text())
    inv=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/source-inventory.json').read_text())"))
    assert all(d.sha(d.P/n)==h for n,h in inv.items())
    d.write(D/'previous-run.json',a);d.write(D/'previous-inventory.json',inv)
    for rel in ('pipeline/slow_loco_disabled.py','pipeline/observe.py','pipeline/replay.py'):
        path=D/'before'/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(d.P/rel,path)
    print(a['run'],flush=True)

def stage():
    calibration=json.loads((D/'calibration.json').read_text());assert calibration['passed'] and calibration['spec']['maximum']==5
    report=json.loads((D/'preflight-verified.json').read_text());assert report['passed']
    report.update(stress_test_penalty_cap=10,final_penalty_cap=5,final_cap_cpu_calibration=True)
    d.write(D/'preflight-verified.json',report)
    d.bundle();shutil.copy2(d.OUT/'source-receipt.json',D/'source-receipt.json');x.stage_from_persistent()

def preflight():
    a=json.loads((D/'previous-run.json').read_text())
    pin=json.loads(remote("import json,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1];assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256'];print(json.dumps(dict(path=str(cp),sha256=b['sha256'])))"))
    d.write(D/'preflight-resume.json',pin)
    src=(d.ROOT/'Labs/RoboticMotionAE/preflight_crawl_only_remote.py').read_text()
    start=src.index('    from slow_loco_disabled import signed_crawl_progress')
    end=src.index('    def check():',start)
    src=src[:start]+'''    assert hasattr(env,'_hand_jiggle')
    assert not env._crawl_forward_values.any()
    # Complete twice-looped reference at the actual slowed playback rate.
    from crawl_jiggle import recorded_cost
    length=float(env._motion_lib.get_motion_length(0))
    times=torch.arange(int(length*120)+1,device='cuda:0')/60
    mids=torch.zeros_like(times,dtype=torch.long)
    vals=env._motion_lib.calc_motion_frame(mids,times)
    reference_pos,reference_rot=env._kin_char_model.forward_kinematics(vals[0],vals[1],vals[4])
    pose=torch.cat((reference_pos,reference_rot),-1).cpu().numpy()
    refcost=recorded_cost(pose,env._jiggle_hand_ids,env._pelvis_id,30.)
    assert refcost.max()<.01,refcost.max()
    (out/'reference-jiggle.json').write_text(json.dumps(dict(max_cost=float(refcost.max()),frames=len(pose))))
    env.reset();assert not env._hand_jiggle.count.any()
''' +src[end:]
    src=src.replace('env._pelvis_window.windows==130','env._pelvis_window.windows==200')
    src=src.replace("-.40*multiplier)","-.55)")
    src=src.replace("bonus=getattr(env,'_crawl_forward_values',torch.zeros_like(env._reward_buf))","assert not env._crawl_forward_values.any()\n        bonus=-env._crawl_jiggle_values")
    (D/'preflight_remote.py').write_text(src);ast.parse(src)
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(D/'preflight-resume.json','preflight_resume.json')
        for name in ('slow_loco_disabled.py','crawl_jiggle.py','disabled_limb_rules.py','slow_loco_env.py','train.py','observe.py','observe_many.py','replay.py'):
            z.write(d.P/'pipeline'/name,'package/pipeline/'+name)
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml','manifest.json','motions.yaml','disabled_inits.npz'):
            z.write(d.P/'prepared'/name,'report/prepared/'+name)
        z.write(d.OUT/'geometry.json','report/geometry.json')
        z.write(D/'preflight_remote.py','preflight_remote.py')
        z.write(d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    d.cloud.rp.scp(d.cloud.state()['connection'],D/'preflight-input.zip',R+'/disabled-preflight.zip',timeout=60)
    remote("from pathlib import Path;import shutil,zipfile;r=Path('/workspace/mimickit_trial');t=r/'disabled-preflight';(t/'package').mkdir(parents=True,exist_ok=True);shutil.copytree(r/'pipeline',t/'package/pipeline',dirs_exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;zipfile.ZipFile(r/'disabled-preflight.zip').extractall(t)")
    try:d.cloud.ssh('cd '+R+'; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1',timeout=630)
    except Exception:
        print(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/preflight.log').read_text()[-6500:])"));raise
    report=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['worlds']==2048 and report['resumed_updates']==3
    d.write(D/'preflight-verified.json',report);d.write(d.OUT/'preflight.json',report)
    print('Full resumed preflight passed',flush=True)

def stop():
    a=json.loads((D/'previous-run.json').read_text())
    d.write(d.OUT/'runtime_control.json',dict(pod_id=a['pod'],hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False))
    c.stop()

def launch():
    old=json.loads((D/'previous-run.json').read_text())['run']
    for attempt in range(24):
        ready=remote("import json;from pathlib import Path;r=Path('/workspace/mimickit_trial');name="+repr(old)+";x=json.loads((r/(name+'-launch.json')).read_text());cmd=Path('/proc')/str(x['pid'])/'cmdline';print(int((r/'runs'/name/'finished.json').exists() and (not cmd.exists() or name.encode() not in cmd.read_bytes())))").strip()=='1'
        if ready:break
        time.sleep(5)
    assert ready,'Graceful save still pending; retain GPU and reconcile before launch'
    cp=c.preserve();expected=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import zipfile,hashlib;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(expected)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(cp['path'],8,'disabled_curriculum_crawl_jiggle',replay_interval_seconds=300)
    d.observe();shutil.copy2(d.OUT/'active_run.json',D/'launched-run.json')

def audit():return c.audit()

def status():
    print(remote("from pathlib import Path;p=Path('/workspace/mimickit_trial/disabled-preflight/preflight.log');print(p.read_text()[-2500:])"))

def health():
    a=json.loads((d.OUT/'active_run.json').read_text())
    print(remote("import json,time,subprocess;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');s=json.loads((p/'status.json').read_text());print({k:s.get(k) for k in ['state','iteration','updated_unix']});print(subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader'],text=True));print(subprocess.check_output(['ps','-eo','pid,etime,pcpu,pmem,comm'],text=True)[-2500:])"))

def stopped():
    a=json.loads((D/'previous-run.json').read_text())
    print(remote("import json;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/"+a['run']+"');print('finished', (p/'finished.json').exists());print((p/'backup_status.json').read_text())"))

def verify():
    result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['state']=='training' and result['status']['worlds']==2048
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    assert result['status']['iteration']>=result['resume']['iteration_offset']+3
    name=result['run']
    code='''import json,hashlib,sys,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
sys.path[:0]=[str(r/'pipeline'),str(r/'MimicKit/mimickit'),str(r/'disabled-preflight')]
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
from verify_disabled_replay import verify
checked=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['crawl_jiggle_penalty']['enabled'] and not row['crawl_forward_reward']['enabled']
  assert row['crawl_jiggle_penalty']['window_ticks']==6
  assert row['crawl_jiggle_penalty']['maximum']==5
  assert row['crawl_jiggle_penalty']['coefficient']==COEFFICIENT
  assert row['loco_failure_penalty']==500 and row['disabled_limb_code']==12
  assert row['pelvis_reset_every_ticks']==200 and abs(row['row_target_radii_m']['pelvis']-.55)<1e-6
  assert not any(row['frame_crawl_forward_reward'])
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(checked))
'''.replace('NAME',repr(name)).replace('COEFFICIENT',str(json.loads((D/'calibration.json').read_text())['spec']['coefficient']))
    check=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
    d.write(D/'replay-verified.json',check)
    d.verify()
    d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],resume=result['resume'],no_forward_bonus=True))

if __name__=='__main__':globals()[sys.argv[1]]()
