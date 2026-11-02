"""User-requested limp support hip 400 Nm, retained GPU continuation."""
import json,sys
import deploy_limp_strength as s
from deploy_saved_sitting import remote
D=s.OUT/'hip400-deploy-20261101';s.D=D;s.r.D=D;s.c.D=D
snapshot=s.snapshot
preflight=s.preflight
stop=s.stop
launch=s.launch
status=s.status
audit=s.audit

def stage():
    before=(D/'before-package/pipeline/slow_loco_env.py').read_text()
    after=(s.P/'pipeline/slow_loco_env.py').read_text()
    expected=before.replace('dict(knee_nm=500., ankle_nm=180.,', 'dict(hip_nm=400., knee_nm=500., ankle_nm=180.,').replace('hip_and_other_motions_unchanged=True', 'other_motions_unchanged=True').replace("for part, cap in [('shin', self.limp_support_strength['knee_nm']),", "for part, cap in [('thigh', self.limp_support_strength['hip_nm']),\n                              ('shin', self.limp_support_strength['knee_nm']),")
    assert after == expected and after != before
    s.stage()

def verify():
    name=json.loads((s.OUT/'active_run.json').read_text())['run']
    data=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{name}/evaluation.json').read_text());print(json.dumps([x['disabled_leg_mse'] for x in e['replay']['replay_rows']]))"))
    prior=json.loads((s.OUT/'passive-leg-mse-deploy-20261101/mask-test.json').read_text())['metadata']
    assert len(data)==8 and all(x==prior for x in data)
    s.write(D/'live-mask-metadata.json',data)
    s.verify()

if __name__=='__main__':globals()[sys.argv[1]]()
