"""User-requested limp support knee 500 Nm, retained GPU continuation."""
import json,sys
import deploy_limp_strength as s
from deploy_saved_sitting import remote
D=s.OUT/'knee500-deploy-20261101';s.D=D;s.r.D=D;s.c.D=D
snapshot=s.snapshot
preflight=s.preflight
stop=s.stop
launch=s.launch
status=s.status
audit=s.audit

def stage():
    before=(D/'before-package/pipeline/slow_loco_env.py').read_text()
    after=(s.P/'pipeline/slow_loco_env.py').read_text()
    assert before.count('dict(knee_nm=300., ankle_nm=180.,')==1
    assert after==before.replace('dict(knee_nm=300., ankle_nm=180.,','dict(knee_nm=500., ankle_nm=180.,')
    s.stage()

def verify():
    name=json.loads((s.OUT/'active_run.json').read_text())['run']
    data=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{name}/evaluation.json').read_text());print(json.dumps([x['disabled_leg_mse'] for x in e['replay']['replay_rows']]))"))
    prior=json.loads((s.OUT/'passive-leg-mse-deploy-20261101/mask-test.json').read_text())['metadata']
    assert len(data)==8 and all(x==prior for x in data)
    s.write(D/'live-mask-metadata.json',data)
    s.verify()

if __name__=='__main__':globals()[sys.argv[1]]()
