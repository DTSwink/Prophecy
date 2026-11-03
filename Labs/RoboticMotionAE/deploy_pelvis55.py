"""Crawl pelvis radius only; continue latest on the retained pod."""
import ast,json,shutil,sys,time,shlex
from pathlib import Path
import deploy_slow_policy as d
import deploy_contact_cleanup as c
import deploy_crawl_only_experiment as x
from deploy_saved_sitting import remote

D=d.OUT/'pelvis55-20261103';R='/workspace/mimickit_trial'
c.D=D;x.D=D

def prepare():
    old=json.loads((D/'previous-inventory.json').read_text())
    assert all(d.sha(d.P/n)==h for n,h in old.items())
    rel='pipeline/slow_loco_disabled.py';p=d.P/rel;s=p.read_text()
    shutil.copy2(p,D/'slow_loco_disabled.before.py')
    anchor='        self._pelvis_window.radius[self._injured] *= 2.\n'
    assert s.count(anchor)==1
    addition="""        # Explicit moving-crawl pelvis tolerance; all other spheres stay unchanged.
        crawl_pelvis = self._injured & (self._fixed_motion_ids == 0)
        pelvis_column = next(i for i,p in enumerate(self._termination_points) if p['body']=='pelvis')
        self._target_radii_sq[crawl_pelvis, pelvis_column] = .55**2
        self._pelvis_window.radius[crawl_pelvis] = .55
"""
    s=s.replace(anchor,anchor+addition)
    ast.parse(s);p.write_text(s);(d.ROOT/'Labs/RoboticMotionAE/slow_loco_disabled.py').write_text(s)
    diff=[n for n,h in old.items() if d.sha(d.P/n)!=h];assert diff==[rel]
    src=(d.P/'pipeline/slow_loco_env.py').read_text()
    node=next(n for n in ast.parse(src).body if isinstance(n,ast.ClassDef) and n.name=='PeriodicPelvisTarget')
    code='import torch,json;from types import SimpleNamespace\ntorch.set_num_threads(1)\n'+ast.get_source_segment(src,node)+"""
# Exercise the actual added row mask/assignment, including unaffected rows and columns.
w=PeriodicPelvisTarget(torch.tensor([200,200,70,200]),'cpu')
w.radius=torch.tensor([.8,.4,.8,.8]);radii=torch.full((4,3),.54**2);radii[:,-1]=w.radius.square()
self=SimpleNamespace(_injured=torch.tensor([True,False,True,True]),_fixed_motion_ids=torch.tensor([0,0,4,1]),_termination_points=[{'body':'head'},{'body':'left_hand'},{'body':'pelvis'}],_target_radii_sq=radii,_pelvis_window=w)
"""+'\n'.join(line[8:] for line in addition.splitlines())+"""
torch.testing.assert_close(w.radius,torch.tensor([.55,.4,.8,.8]))
torch.testing.assert_close(radii[:,-1],w.radius.square())
assert torch.allclose(radii[:,:2],torch.full((4,2),.54**2))
zero=torch.zeros(4,3);w.reset(torch.arange(4),zero,zero)
for tick in range(1,401):
 ref=zero.clone();ref[:,0]=tick*.003;actual=zero.clone();actual[:,0]=tick*.001
 w.update(actual,ref)
 if tick in (200,400):torch.testing.assert_close(w.target[0],actual[0])
probe=w.target.clone();probe[0,0]+=.549;assert not w.sphere_failed(probe)[0]
probe[0,0]+=.002;assert w.sphere_failed(probe)[0]
print(json.dumps(dict(passed=True,radius_m=.55,reset_ticks=200,unaffected_rows_and_limbs=True)))
"""
    report=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=40))
    d.write(D/'preflight-verified.json',report)
    d.bundle();shutil.copy2(d.OUT/'source-receipt.json',D/'source-receipt.json');x.stage_from_persistent()
    d.write(D/'change.json',dict(changed_files=diff,pelvis_radius_before=.8,pelvis_radius_after=.55,reset_ticks=200,all_configs_unchanged=True))
    print('55cm boundary checks passed; source staged; trainer unchanged',flush=True)

def stop():
    a=json.loads((D/'previous-run.json').read_text())
    d.write(d.OUT/'runtime_control.json',dict(pod_id=a['pod'],hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False))
    c.stop()

def launch():
    cp=c.preserve();digest=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import hashlib,zipfile;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(digest)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(cp['path'],8,'disabled_curriculum_crawl_pelvis55',replay_interval_seconds=300)
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
  assert abs(row['row_target_radii_m']['pelvis']-.55)<1e-6
  assert row['loco_failure_penalty']==500 and row['crawl_forward_reward']['form']=='signed_displacement_v1'
cmd=json.loads((r/(NAME+'-launch.json')).read_text())['command'];assert cmd[cmd.index('--replay-interval-seconds')+1]=='300'
print(json.dumps(checks))
'''.replace('NAME',repr(name))
    checks=json.loads(d.cloud.ssh(R+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
    d.write(D/'replay-verified.json',checks);d.verify()
    d.write(D/'verified.json',dict(passed=True,run=name,status=result['status'],recenter_ticks=200,radius_m=.55))

if __name__=='__main__':globals()[sys.argv[1]]()
