"""Owned-pod continuation for the approved sitting hip range correction."""
import json,sys,shlex,hashlib,zipfile
from pathlib import Path
import deploy_slow_policy as d
import deploy_saved_sitting as prior
OUT=d.OUT;D=OUT/'hip-limits-20261031';REMOTE='/workspace/mimickit_trial'
def remote(code):return prior.remote(code)
def stage():
    a=json.loads((OUT/'active_run.json').read_text());assert a['pod']=='5xs589fdlcb7nr'
    (D/'previous-run.json').write_text(json.dumps(a));d.bundle()
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',REMOTE+'/hip-source.zip',timeout=90)
    assert remote(f"import hashlib;print(hashlib.sha256(open('{REMOTE}/hip-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    print('hip source staged and verified')
def stop():
    prior.OLD=json.loads((D/'previous-run.json').read_text())['run'];prior.stop_trainer()
def status():prior.status()
def launch():
    old=json.loads((D/'previous-run.json').read_text())['run']
    code=f'''import json,hashlib,zipfile
from pathlib import Path
r=Path('{REMOTE}');name='{old}';p=r/'runs'/name
x=json.loads((r/(name+'-launch.json')).read_text());cmd=Path('/proc')/str(x['pid'])/'cmdline'
assert not cmd.exists() or name.encode() not in cmd.read_bytes()
assert (p/'finished.json').exists()
b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1]
assert cp.name.endswith('_final.zip'),cp
assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
print(json.dumps(dict(backup=b,path=str(cp))))
'''
    info=json.loads(remote(code));b=info['backup'];folder=OUT/'preserved-latest'/old;folder.mkdir(parents=True,exist_ok=True)
    cp=folder/b['key'].split('/')[-1];stream=d.cloud.s3().get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=b['key'])['Body']
    cp.write_bytes(stream.read());stream.close();assert d.sha(cp)==b['sha256']
    with zipfile.ZipFile(cp) as z:assert z.testzip() is None
    (D/'resume-checkpoint.json').write_text(json.dumps(dict(**info,local=str(cp),verified=True),indent=2))
    print(remote(f'''import json,zipfile,hashlib
from pathlib import Path
r=Path('{REMOTE}')
with zipfile.ZipFile(r/'hip-source.zip') as z:z.extractall(r)
for n,h in json.loads((r/'source-inventory.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
print('Updated source and limits verified')
'''))
    d.launch(info['path']);d.observe()
if __name__=='__main__':globals()[sys.argv[1]]()
