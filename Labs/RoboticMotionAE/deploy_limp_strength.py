"""Targeted limp support strength continuation on the retained GPU."""
import json,sys,shutil
import deploy_reference_upper as r
from deploy_saved_sitting import remote
c=r.c;d=r.d;OUT=d.OUT;P=d.P;D=OUT/'limp-strength-deploy-20261101';r.D=D;c.D=D
write=d.write
snapshot=r.snapshot
preflight=c.preflight
stop=c.stop
launch=c.launch
status=c.status
audit=c.audit

def stage():
 old=json.loads((D/'previous-inventory.json').read_text());new={n:d.sha(P/n) for n in old}
 assert {n for n in old if old[n]!=new[n]}=={'pipeline/slow_loco_env.py'}
 assert json.loads((D/'strength-test.json').read_text())['passed']
 assert json.loads((D/'preflight-verified.json').read_text())['passed']
 d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
 d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',c.REMOTE+'/contact-source.zip',timeout=90)
 assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
 write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=['pipeline/slow_loco_env.py']))
 print('Limp support strength source staged and verified',flush=True)

def verify():
 name=json.loads((OUT/'active_run.json').read_text())['run']
 rows=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{name}/evaluation.json').read_text());print(json.dumps([dict(motion=x['motion_name'],strength=x['limp_support_strength']) for x in e['replay']['replay_rows']]))"))
 expected=json.loads((D/'strength-test.json').read_text())['metadata']
 assert len(rows)==8 and all(row['strength']==expected for row in rows)
 write(D/'live-strength-metadata.json',rows)
 r.verify()
 print('Targeted limp strength verified; GPU retained',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
