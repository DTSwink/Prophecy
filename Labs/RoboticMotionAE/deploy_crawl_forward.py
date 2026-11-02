"""Scoped additive crawl-speed continuation on the retained GPU."""
import sys,json,shutil,time
import deploy_crawl_legs_only as old
from deploy_saved_sitting import remote
d=old.d;P=old.P;OUT=old.OUT;D=OUT/'crawl-forward-deploy-20261102'
c=old.c;c.D=D;old.D=D

def preflight():
    name=json.loads((D/'previous-run.json').read_text())['run']
    pin=json.loads(remote(f"import json,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/{name}');b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1];assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256'];print(json.dumps(dict(path=str(cp),sha256=b['sha256'])))"))
    d.write(D/'preflight-resume.json',pin)
    x=old.x;x.D=D;x.preflight()

def stage():
    previous=json.loads((D/'previous-inventory.json').read_text())
    changed={n for n,h in previous.items() if d.sha(P/n)!=h}
    assert changed=={'pipeline/slow_loco_disabled.py','pipeline/observe.py','pipeline/replay.py'},changed
    report=json.loads((D/'preflight-verified.json').read_text())
    assert report['passed'] and report['worlds']==2048 and report['resumed_updates']==3
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip','/workspace/mimickit_trial/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    d.write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(changed)))

def stop():c.stop()
def audit():return c.audit()

def launch():
    info=c.preserve();expected=json.loads((D/'staged.json').read_text())['source_sha256']
    remote("import zipfile,hashlib;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(expected)+";zipfile.ZipFile(r/'contact-source.zip').extractall(r)")
    d.launch(info['path'],replay_rows=33,run_kind='disabled_curriculum_crawl_forward5');d.observe()
    shutil.copy2(OUT/'active_run.json',D/'launched-run.json')

def verify():
    name=json.loads((D/'launched-run.json').read_text())['run']
    code=f'''import json,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/{name!r}
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
rows=json.loads((p/'evaluation.json').read_text())['replay']['replay_rows']
eligible=[]
for row in rows:
 spec=row['crawl_forward_reward'];active=row['motion_name']=='crawl' and row['disabled_limb_code']==12 and row['cohort_index']>0
 assert spec['enabled']==active and spec['maximum']==5.
 values=row['frame_crawl_forward_reward']
 assert all(0<=v<=5.00001 for v in values)
 if active:eligible.append(dict(label=row['replay_row_label'],max_bonus=max(values),target=spec['target_velocity_xy_m_s']))
 else:assert not any(values)
assert len(eligible)==1 and eligible[0]['max_bonus']>0
print(json.dumps(dict(passed=True,eligible=eligible,rows=len(rows))))
'''
    d.write(D/'bonus-live-verified.json',json.loads(remote(code)))
    old.verify()
    result=json.loads((D/'live-replay-verified.json').read_text())
    assert result['passed'] and len(result['rows'])==33
    print('Forward speed reward continuation verified',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
