"""Same-GPU isolated checks and guarded checkpoint handoff."""
import json,sys,hashlib
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
OUT=d.OUT/'idle-recovery-20261028'

def upload():
 plan=json.loads((OUT/'prepared.json').read_text());old=json.loads((OUT/'previous-plan.json').read_text())
 d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'overlay.zip','/workspace/mimickit_trial/idle-recovery-overlay.zip',timeout=40)
 code="""from pathlib import Path
import zipfile,hashlib,pickle,json,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
out=r/'idle-recovery-check';out.mkdir(exist_ok=True)
for name in ['complete.json','failure.txt']:(out/name).unlink(missing_ok=True)
with zipfile.ZipFile(r/'source.zip') as src,zipfile.ZipFile(r/'idle-recovery-overlay.zip') as delta,zipfile.ZipFile(r/'idle-recovery-source.zip','w') as dst:
 for info in pickle.loads(delta.read('infos.pkl')):dst.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else src.read(info.filename))
 for name in delta.namelist():
  if name!='infos.pkl':
   p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(delta.read(name))
data=(r/'idle-recovery-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
assert (r/'runtime-freeze.txt').exists()
print('Candidate and persistent readback verified')
""".replace('OLD',repr(old['source']['sha256'])).replace('SHA',repr(plan['source']['sha256'])).replace('KEY',repr(plan['source']['key']))
 print(r.remote(code,timeout=60),flush=True)
 d.cloud.rp.scp(d.cloud.state()['connection'],Path(__file__).with_name('preflight_idle_recovery_20261028.py'),'/workspace/mimickit_trial/preflight_idle_recovery_20261028.py',timeout=30)
 print(r.remote("import subprocess;from pathlib import Path;r=Path('/workspace/mimickit_trial');log=(r/'idle-recovery-check/preflight.log').open('wb');p=subprocess.Popen(['timeout','180',str(r/'venv/bin/python'),'-u',str(r/'preflight_idle_recovery_20261028.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);print(p.pid)",timeout=20),flush=True)

def status():
 print(r.remote("from pathlib import Path;r=Path('/workspace/mimickit_trial/idle-recovery-check');print((r/'complete.json').read_text() if (r/'complete.json').exists() else (r/'failure.txt').read_text() if (r/'failure.txt').exists() else (r/'preflight.log').read_text()[-2000:])",timeout=20),flush=True)

def stop():
 plan=json.loads((OUT/'prepared.json').read_text());active=json.loads((d.OUT/'active_run.json').read_text())
 result=json.loads(r.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/idle-recovery-check/complete.json').read_text())",timeout=20))
 assert result['passed'] and result['source_sha256']==plan['source']['sha256']
 (OUT/'preflight.json').write_text(json.dumps(result,indent=2))
 assert active['run']=='20261028_181302_uefn_locomotion_leg7_idle3_2048' and active['pod']=='dt94w83iq0waci'
 d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
 r.stop()

def capture():
 r.capture()
 p=json.loads((OUT/'prepared.json').read_text());p['checkpoint']=json.loads((d.OUT/'ae30-switch.json').read_text())['checkpoint']
 (OUT/'prepared.json').write_text(json.dumps(p,indent=2))

def launch():
 plan=json.loads((OUT/'prepared.json').read_text());cp=plan['checkpoint'];src=plan['source']
 assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==cp['sha256']
 code="""from pathlib import Path
import hashlib,json,shutil,zipfile
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'idle-recovery-source.zip').read_bytes()).hexdigest()==SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CPSHA
assert (r/'runtime-freeze.txt').exists()
shutil.copyfile(r/'idle-recovery-source.zip',r/'source.zip')
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p=json.loads((r/'private.json').read_text());p['resume_checkpoint']=CP;(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Candidate promoted; latest checkpoint/runtime verified')
""".replace('CPSHA',repr(cp['sha256'])).replace('SHA',repr(src['sha256'])).replace('CP',repr(dict(key=cp['key'],sha256=cp['sha256'])))
 print(r.remote(code,timeout=30),flush=True);d.save('getup-success-prepared',plan);d.launch()

if __name__=='__main__':globals()[sys.argv[1]]()
