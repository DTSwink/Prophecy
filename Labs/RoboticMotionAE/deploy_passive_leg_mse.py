"""Exclude passive-leg tracking MSE; resume on the retained slow-loco GPU."""
import json,sys,shutil
import deploy_reference_upper as r
from deploy_saved_sitting import remote
c=r.c;d=r.d;OUT=d.OUT;P=d.P;D=OUT/'passive-leg-mse-deploy-20261101';r.D=D;c.D=D
snapshot=r.snapshot
preflight=c.preflight
stop=c.stop
launch=c.launch
status=c.status
audit=c.audit

def stage():
    old=json.loads((D/'previous-inventory.json').read_text())
    diff={n for n in old if old[n]!=d.sha(P/n)}
    assert diff=={'pipeline/slow_loco_env.py'},diff
    assert json.loads((D/'mask-test.json').read_text())['passed']
    assert json.loads((D/'preflight-verified.json').read_text())['passed']
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',c.REMOTE+'/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    d.write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(diff)))
    print('Passive-leg MSE exclusion staged and SHA verified; trainer unchanged',flush=True)

def verify():
    name=json.loads((OUT/'active_run.json').read_text())['run']
    rows=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{name}/evaluation.json').read_text());print(json.dumps([dict(motion=x['motion_name'],mask=x['disabled_leg_mse'],strength=x['limp_support_strength']) for x in e['replay']['replay_rows']]))"))
    assert len(rows)==8
    expected=json.loads((D/'mask-test.json').read_text())['metadata']
    assert all(x['mask']==expected for x in rows)
    assert all(x['strength']['knee_nm']==300 and x['strength']['ankle_nm']==180 for x in rows)
    d.write(D/'live-mask-metadata.json',rows)
    r.verify()
    print('Passive-leg MSE exclusion live and verified; same GPU retained',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
