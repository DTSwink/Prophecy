"""Crawl pelvis recenter interval only; continue latest on the retained pod."""
import ast,json,shutil,sys,time,shlex
from pathlib import Path
import deploy_slow_policy as d
import deploy_contact_cleanup as c
import deploy_crawl_only_experiment as x
from deploy_saved_sitting import remote

D=d.OUT/'pelvis200-20261103';R='/workspace/mimickit_trial'
c.D=D;x.D=D

def prepare():
    old=json.loads((D/'previous-inventory.json').read_text())
    assert all(d.sha(d.P/n)==h for n,h in old.items())
    rel='pipeline/slow_loco_env.py';p=d.P/rel;s=p.read_text()
    shutil.copy2(p,D/'slow_loco_env.before.py')
    assert s.count('self._pelvis_window_steps[:2] = 130')==1
    s=s.replace('self._pelvis_window_steps[:2] = 130','self._pelvis_window_steps[:2] = 200')
    s=s.replace('refreshed every70 ticks; absolute reference Z','refreshed at the per-motion interval; absolute reference Z')
    p.write_text(s);(d.ROOT/'Labs/RoboticMotionAE/slow_loco_env.py').write_text(s)
    diff=[n for n,h in old.items() if d.sha(d.P/n)!=h];assert diff==[rel]
    node=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='PeriodicPelvisTarget')
    code='import torch,json\ntorch.set_num_threads(1)\n'+ast.get_source_segment(s,node)+'''
w=PeriodicPelvisTarget(torch.tensor([200,70]),'cpu');ids=torch.arange(2);zero=torch.zeros(2,3)
w.reset(ids,zero,zero);w.radius.fill_(.8)
for tick in range(1,401):
 ref=zero.clone();ref[:,0]=tick*.003;ref[:,2]=.4
 actual=zero.clone();actual[:,0]=tick*.001;actual[:,2]=.4
 w.update(actual,ref)
 anchor=(tick//w.windows)*w.windows
 expected=anchor*.001+(tick-anchor)*.003
 torch.testing.assert_close(w.target[:,0],expected)
 if tick in (130,150,199):assert abs(float(w.target[0,0]-actual[0,0]))>.1
 if tick in (200,400):torch.testing.assert_close(w.target[0,:2],actual[0,:2])
probe=w.target.clone();probe[:,0]+=.799;assert not w.sphere_failed(probe).any()
probe[:,0]+=.002;assert w.sphere_failed(probe).all()
age=w.age.clone();w.reset(torch.tensor([0]),zero[:1],zero[:1]);assert w.age.tolist()==[0,int(age[1])]
print(json.dumps(dict(passed=True,reset_ticks=200,other_motions_ticks=70,radius_m=.8,checked_ticks=400)))
'''
    report=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=40))
    d.write(D/'preflight-verified.json',report)
    d.bundle();shutil.copy2(d.OUT/'source-receipt.json',D/'source-receipt.json');x.stage_from_persistent()
    d.write(D/'change.json',dict(changed_files=diff,crawl_interval_before=130,crawl_interval_after=200,all_configs_unchanged=True))
    print('200-tick boundary checks passed; source staged; running trainer unchanged',flush=True)

def stop():
    a=json.loads((D/'previous-run.json').read_text())
    d.write(d.OUT/'runtime_control.json',dict(pod_id=a['pod'],hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False))
    c.stop()

def launch():
    cp=c.preserve();digest=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import hashlib,zipfile;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(digest)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(cp['path'],8,'disabled_curriculum_crawl_pelvis200',replay_interval_seconds=300)
    d.observe();shutil.copy2(d.OUT/'active_run.json',D/'launched-run.json')

def audit():return c.audit()

def verify():
    result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    name=result['run']
    code='''import sys,json,hashlib,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
checks=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows'];assert len(rows)==8
 for row in rows:
  assert row['motion_name']=='crawl' and row['disabled_limb_code']==12
  assert row['target_deviation']['world_pelvis']['reset_every_ticks']==200
  assert abs(row['row_target_radii_m']['pelvis']-.8)<1e-6
  assert row['loco_failure_penalty']==500 and row['crawl_forward_reward']['form']=='signed_displacement_v1'
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(checks))
'''.replace('NAME',repr(name))
    checks=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
    d.write(D/'replay-verified.json',checks);d.verify()
    d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],recenter_ticks=200,radius_m=.8))

if __name__=='__main__':globals()[sys.argv[1]]()
