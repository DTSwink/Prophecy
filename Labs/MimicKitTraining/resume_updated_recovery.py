"""Stage verified motion-only update, then hand off to the latest checkpoint."""
import argparse,hashlib,json,os,shlex,subprocess,sys,tempfile,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-stem',default='updated-recovery')
    parser.add_argument('--seconds',type=int)
    parser.add_argument('--suffix',default='uefn_main_updated_getups_512')
    args=parser.parse_args()
    stem=args.source_stem
    source=json.loads((OUT/(stem+'-source.json')).read_text())
    data=Path(source['source']).read_bytes();assert hashlib.sha256(data).hexdigest()==source['sha256']
    active=json.loads((OUT/'active_run.json').read_text());old=active['run'];pod=cloud.state()['pod_id']
    assert active['pod']==pod
    hard=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix']
    assert hard-time.time()>600
    client=cloud.s3();key='mimickit/pipeline_20261014/equipment/updated-recovery/source_'+source['sha256'][:12]+'.zip'
    client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data)
    assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==source['sha256']
    (OUT/(stem+'-source-verified.json')).write_text(json.dumps(dict(key=key,sha256=source['sha256'])))
    # The live trainer keeps its original files throughout preparation.
    remote='/workspace/mimickit_trial';connection=cloud.state()['connection']
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'source-fetch.json';path.write_text(json.dumps(dict(key=key,sha256=source['sha256'])))
        cloud.rp.scp(connection,path,remote+'/source-fetch.json',timeout=40)
    fetch="""import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial'); cfg=json.loads((r/'source-fetch.json').read_text())
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
data=c.get_object(Bucket='aj7d2jzwuq',Key=cfg['key'])['Body'].read()
assert hashlib.sha256(data).hexdigest()==cfg['sha256']
p=r/STAGE_NAME;p.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(data)) as z:
 for n in z.namelist():
  if n.startswith(('prepared/','assets/')) and n not in ALLOWED_CHANGES:assert z.read(n)==(r/n).read_bytes(),n
 z.extractall(p)
(p/'source.zip').write_bytes(data)
print('Motion update staged; live trainer untouched')
"""
    fetch=fetch.replace('STAGE_NAME',repr(stem+'_stage')).replace('ALLOWED_CHANGES',repr(source.get('allowed_config_changes',[])))
    print(cloud.ssh('cd '+remote+'; venv/bin/python -c '+shlex.quote(fetch),timeout=60),flush=True)
    begun=False
    try:
        # Independent bounded handoff guard covers controller/network failure.
        handoff="""import json,time,subprocess,os,signal
from pathlib import Path
r=Path('/workspace/mimickit_trial'); name=OLD
receipt=json.loads((r/(name+'-launch.json')).read_text());guard=receipt['exit_guard_pid']
args=(Path('/proc')/str(guard)/'cmdline').read_bytes()
assert b'failure_stop.py' in args and name.encode() in args
watch="import sys,time,json; from pathlib import Path; sys.path.insert(0,'/workspace/mimickit_trial/pipeline'); from billing_stop import stop_and_confirm; r=Path('/workspace/mimickit_trial'); end=time.time()+300; p=r/'recovery_handoff_complete'; c=json.loads((r/'private.json').read_text()); \\nwhile time.time()<end and not p.exists():time.sleep(2)\\nif not p.exists():stop_and_confirm(c['pod_id'],c['runpod_api_key'],r/'handoff_billing_stop.json','recovery handoff timed out')"
(r/'recovery_handoff_complete').unlink(missing_ok=True)
with (r/'recovery-handoff-guard.log').open('ab') as log:
 w=subprocess.Popen([str(r/'venv/bin/python'),'-c',watch],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
os.kill(guard,signal.SIGTERM)
(r/'runs'/name/'stop.request').touch()
print(json.dumps(dict(watchdog=w.pid,old_run=name)))
""".replace('OLD',repr(old))
        begun=True;print(cloud.ssh('python -c '+shlex.quote(handoff)),flush=True)
        stop=time.time()+150
        while time.time()<stop:
            probe="import json; from pathlib import Path; r=Path('/workspace/mimickit_trial'); name="+repr(old)+"; p=r/'runs'/name; f=p/'finished.json'; b=p/'backup_status.json'; pid=json.loads((r/(name+'-launch.json')).read_text())['pid']; proc=Path('/proc')/str(pid)/'cmdline'; exited=not proc.exists() or name.encode() not in proc.read_bytes(); print(json.dumps(dict(exited=exited,finished=json.loads(f.read_text()) if f.exists() else None,backup=json.loads(b.read_text()) if b.exists() else None)))"
            result=json.loads(cloud.ssh('python -c '+shlex.quote(probe)))
            if result['exited'] and result['finished'] and result['backup'] and result['backup']['key'].endswith('_final.zip'):break
            time.sleep(5)
        else:raise TimeoutError('Final checkpoint did not finish in handoff window')
        cp=result['backup'];verified=json.loads(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=cp['key'].rsplit('/',1)[0]+'/latest_verified.json')['Body'].read())
        assert verified==cp
        switch="""import json,hashlib,shutil
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial'); cp=CHECKPOINT; private=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**private['s3']);data=c.get_object(Bucket='aj7d2jzwuq',Key=cp['key'])['Body'].read()
assert hashlib.sha256(data).hexdigest()==cp['sha256']
(r/'resume.zip').write_bytes(data);private['resume_checkpoint']=cp
(r/'private.json').write_text(json.dumps(private))
stage=r/STAGE_NAME
for p in stage.rglob('*'):
 if p.is_file():
  dest=r/p.relative_to(stage);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
(r/'stop.request').unlink(missing_ok=True)
print('Latest final checkpoint verified; updated motions installed')
""".replace('CHECKPOINT',repr(cp)).replace('STAGE_NAME',repr(stem+'_stage'))
        print(cloud.ssh('cd '+remote+'; venv/bin/python -c '+shlex.quote(switch),timeout=60),flush=True)
        now=datetime.now().astimezone();name=now.strftime('%Y%m%d_%H%M%S')+'_'+args.suffix
        remaining=args.seconds or int(hard-time.time())
        training_args=['--name',name,'--seconds',str(remaining),'--worlds','512','--control-mode','vel','--absolute-walk',
            '--equipment-omni',remote+'/prepared','--evaluate','--output-interval','100','--replay-rows','20','--resume',remote+'/resume.zip']
        subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),*(['--keep-deadline'] if args.seconds is None else []),'--seconds',str(remaining),'--',*training_args],check=True)
        hard=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix']
        # New trainer now has its own exit guard; retain original deadline guards.
        cloud.ssh('touch '+remote+'/recovery_handoff_complete')
        manifest=json.loads((OUT/(old+'-dashboard.json')).read_text())
        manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+args.suffix,objective='uefn_omni_absolute_walk',
            sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
        dest=OUT/(name+'-dashboard.json');dest.write_text(json.dumps(manifest,indent=2));pids={}
        for kind,argv in [('bridge',['--name',name]),('dashboard',[str(dest)])]:
            with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=0x08000000)
            pids[kind]=proc.pid
        receipt=dict(run=name,previous_run=old,pod=pod,hard_stop_unix=hard,checkpoint=cp,source_sha256=source['sha256'],observers=pids)
        (OUT/(stem+'-launch.json')).write_text(json.dumps(receipt,indent=2))
        (OUT/'current-run.txt').write_text(name);print(json.dumps(receipt),flush=True)
    except Exception:
        if begun:stop_and_confirm(pod,cloud.rp.load_api_key(),OUT/'updated-recovery-failed-stop.json','recovery update handoff failed')
        raise

if __name__=='__main__':main()
