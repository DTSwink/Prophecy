"""Scoped termination continuation, preserving the retained GPU and latest state."""
import sys,json,shutil,time,shlex
import deploy_disabled_curriculum as x
from deploy_saved_sitting import remote
d=x.d;P=x.P;OUT=x.OUT;D=OUT/'agonising-radii-deploy-20261102'
c=x.s.c;c.D=D
stop=c.stop;audit=c.audit

def stage():
    old=json.loads((D/'previous-inventory.json').read_text())
    diff={n for n,h in old.items() if d.sha(P/n)!=h}
    assert diff=={'pipeline/slow_loco_env.py','pipeline/slow_loco_disabled.py'},diff
    report=json.loads((D/'preflight-verified.json').read_text());assert report['passed'] and report['boundary_cases']==36864
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip','/workspace/mimickit_trial/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    d.write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(diff)))

def launch():
    info=c.preserve();expected=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import zipfile,hashlib;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(expected)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(info['path'],replay_rows=40,run_kind='disabled_curriculum_agonising_free');d.observe()
    shutil.copy2(OUT/'active_run.json',D/'launched-run.json')

def verify():
    result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['state']=='training' and result['status']['worlds']==2048
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    name=result['run']
    code=f'''import sys,json,numpy as np
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/{name!r};sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
result=verify(p/'replay.npz')
with np.load(p/'replay.npz',allow_pickle=False) as z:
 rows=json.loads(str(z['metadata']))['replay_rows']
 for i,row in enumerate(rows):
  suffix='' if i==0 else '_'+str(i);motion=row['motion_name'];inj=row['cohort_index']>0
  exempt=motion in ('agonising','agonising_idle');assert row['failure_termination_enabled']==(not exempt)
  if exempt:assert not row['target_deviation']['points'] and not (z['data'+suffix][:,0]==1).any()
  for b,v in row['row_target_radii_m'].items():
   if v is None:continue
   base=.4 if b=='pelvis' else .2 if motion in ('limpL_idle','limpR_idle') and b in ('left_hand','right_hand') else .54 if motion.startswith('limp') else .27
   assert abs(v-base*(2 if inj else 1))<1e-6,(motion,b,v)
print(json.dumps(result))
'''
    checked=json.loads(d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=45))
    d.write(D/'live-replay-verified.json',checked)
    d.verify();d.write(D/'deployment-verified.json',dict(run=name,status=result['status'],verified=True,source_sha256=json.loads((D/'staged.json').read_text())['source_sha256']))

if __name__=='__main__':globals()[sys.argv[1]]()
