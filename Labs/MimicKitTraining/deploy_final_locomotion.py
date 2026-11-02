"""Guarded final-phase deploy; preserve immutable old source and checkpoint."""
import hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r

def upload():
    plan=json.loads((d.OUT/'final-phase-prepared.json').read_text());cp=plan['checkpoint'];source=plan['source']
    assert hashlib.sha256(Path(cp['local']).read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(cp['local']) as z:assert z.testzip() is None
    data=Path(source['local']).read_bytes();assert hashlib.sha256(data).hexdigest()==source['sha256']
    d.cloud.s3().put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=source['key'],Body=data)
    print('Source uploaded; retained latest checkpoint verified',flush=True)

def start():
    pod=d.cloud.state()['pod_id'];assert pod=='leuh8va7hfcevy'
    state=d.cloud.rp.request_json('GET','/pods/'+pod)
    assert state['desiredStatus']=='EXITED' and 0<float(state['costPerHr'])<=.59
    marker=d.OUT/'final-phase-verified';marker.unlink(missing_ok=True)
    guard=f'''import sys,time
from pathlib import Path
sys.path.insert(0,{str(d.ROOT/'Labs/MimicKitTraining')!r})
import deploy_locomotion_branch as d
from billing_stop import stop_and_confirm
end=time.time()+900
while time.time()<end and not Path({str(marker)!r}).exists():time.sleep(2)
if not Path({str(marker)!r}).exists():stop_and_confirm({pod!r},d.cloud.rp.load_api_key(),Path({str(d.OUT/'final-phase-timeout.json')!r}),'Final phase setup not verified within15minutes')
'''
    with (d.OUT/'final-phase-guard.log').open('ab') as log:
        g=subprocess.Popen([sys.executable,'-c',guard],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
    d.save('final-phase-guard',dict(pid=g.pid,pod=pod,deadline=time.time()+900))
    try:d.cloud.rp.request_json('POST','/pods/'+pod+'/start')
    except Exception:
        marker.touch();raise
    print('Existing L4 start accepted; bounded setup guard active',flush=True);d.cloud.connect()

def deploy():
    plan=json.loads((d.OUT/'final-phase-prepared.json').read_text());cp=plan['checkpoint'];source=plan['source']
    code='''import json,hashlib,zipfile,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
for item,name in [(SOURCE,'source.zip'),(CP,'resume.zip')]:
 data=c.get_object(Bucket='aj7d2jzwuq',Key=item['key'])['Body'].read();assert hashlib.sha256(data).hexdigest()==item['sha256']
 (r/name).write_bytes(data)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p['resume_checkpoint']=CP;(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Source and latest checkpoint persistent readback verified')
'''.replace('SOURCE',repr(source)).replace('CP',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code,timeout=60),flush=True)
    d.cloud.rp.scp(d.cloud.state()['connection'],Path(__file__).with_name('preflight_final_locomotion.py'),'/workspace/mimickit_trial/preflight_final_locomotion.py',timeout=40)
    d.save('getup-success-prepared',plan)

def test():
    print(r.remote("import subprocess;from pathlib import Path;r=Path('/workspace/mimickit_trial');log=(r/'final-phase-preflight.log').open('wb');p=subprocess.Popen(['timeout','240',str(r/'venv/bin/python'),'-u',str(r/'preflight_final_locomotion.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);print(p.pid)"),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='launch':d.launch()
    else:globals()[sys.argv[1]]()
