"""Resume the owned stopped crawl pod for the authorized 35-minute window."""
import argparse,json,shlex,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
import launch
from billing_stop import stop_and_confirm
c=launch.cloud;OUT=launch.OUT;PACKAGE=launch.PACKAGE

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--retry',action='store_true');parser.add_argument('--continue-latest',action='store_true');parser.add_argument('--seconds',type=int,default=2100);args=parser.parse_args()
    assert 300<=args.seconds<=7200
    state=c.state();pod=state['pod_id'];assert pod=='o6qhah385ykhhx'
    live=c.rp.request_json('GET','/pods/'+pod)
    assert live['desiredStatus']=='EXITED' and 0<float(live['costPerHr'])<=.59
    retry=args.retry
    archive=OUT/'updated-training-20261017'/('continuation-control-'+str(int(time.time())) if args.continue_latest else 'retry-control-'+str(int(time.time())) if retry else 'prior-run-control');archive.mkdir(exist_ok=False)
    for name in ('pod.json','active_run.json','runtime_control.json','guards.json','observers.json','local-backup-status.json'):
        p=OUT/name
        if p.exists():shutil.copy2(p,archive/name)
    # Keep the existing backup uploader; its quota errors remain visible. The
    # exit watcher waits for independently verified local checkpoint copies.
    shutil.copy2(Path(__file__).parent/'local_backup_exit.py',PACKAGE/'pipeline/failure_stop.py')
    if args.continue_latest:
        previous=json.loads((OUT/'active_run.json').read_text())
        receipt=json.loads((OUT/'local-backup-status.json').read_text())
        checkpoint=Path(receipt['path'])
        previous_run=previous['run'] or (json.loads((OUT/'resume-checkpoint.json').read_text())['source_run'] if retry else '')
        assert receipt['verified'] and receipt['run']==previous_run and checkpoint.name.endswith('_final.zip')
        assert launch.sha(checkpoint)==receipt['sha256']
        evidence=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+previous_run)
        assert (evidence/'finished.json').exists() and not (evidence/'failure.json').exists()
        with zipfile.ZipFile(checkpoint) as z:
            assert {'model.pt','resume_state.pt','provenance.json'}<=set(z.namelist())
            provenance=json.loads(z.read('provenance.json'))
            assert provenance['wrapper_sha256']==launch.sha(PACKAGE/'pipeline/train.py')
        assert launch.sha(OUT/'source.zip')==json.loads((OUT/'package-receipt.json').read_text())['sha256']
        receipt.update(local_path=str(checkpoint),source_run=receipt['run'],backup_mode='local_checksum_verified')
        launch.write(OUT/'resume-checkpoint.json',receipt)
    else:launch.bundle(updated_references=True)
    expected=json.loads((OUT/'resume-checkpoint.json').read_text())
    started=state['created_unix'] if retry else time.time();hard=started+args.seconds+(765 if args.continue_latest else 0)
    assert hard>time.time()+300,'Insufficient time remains in the authorized window'
    state.update(created_unix=started,max_initial_runtime_seconds=hard-started,local_checkpoint_backup=True,previous_allocation=str(archive/'pod.json'))
    c.save(state)
    launch.write(OUT/'runtime_control.json',dict(pod_id=pod,hard_stop_unix=hard))
    # Prevent old failure evidence from ending this new explicitly authorized run.
    launch.write(OUT/'active_run.json',dict(pod=pod,status='preparing',run=''))
    with (OUT/'updated-window-local-guard.log').open('ab') as log:
        guard=subprocess.Popen([sys.executable,str(launch.PIPE/'local_guard.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    launch.write(OUT/'guards.json',dict(local_guard=guard.pid))
    try:
        c.rp.request_json('POST','/pods/'+pod+'/start')
        state['connection']=c.rp.wait_for_connection(pod,timeout_seconds=120);c.save(state)
        info=c.rp.request_json('GET','/pods/'+pod);assert 0<float(info['costPerHr'])<=.59
        # Inspect final remote checkpoint identity before any training launch.
        inspect="""from pathlib import Path
import json,hashlib
r=Path('/workspace/mimickit_trial')
d=r/'runs'/SOURCE_RUN
p=max(d.glob('checkpoint_*.zip'),key=lambda p:p.name)
print(json.dumps(dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),runtime_exists=(r/'venv/bin/python').exists())))
""".replace('SOURCE_RUN',repr(expected['source_run']))
        latest=json.loads(c.ssh('python -c '+shlex.quote(inspect),timeout=30))
        expected=json.loads((OUT/'resume-checkpoint.json').read_text())
        assert latest['sha256']==expected['sha256'],('A newer remote checkpoint requires local validation',latest)
        c.rp.scp(state['connection'],OUT/'source.zip','/workspace/mimickit_trial/updated-source.zip',timeout=60)
        private=dict(pod_id=pod,deadline_unix=hard-120,runpod_api_key=c.rp.load_api_key(),s3=c.credentials())
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'private.json';launch.write(p,private)
            c.rp.scp(state['connection'],p,'/workspace/mimickit_trial/private.json',timeout=30)
        c.rp.scp(state['connection'],OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=30)
        deploy="""from pathlib import Path
import zipfile,hashlib,subprocess,json,time
r=Path('/workspace/mimickit_trial');p=r/'updated-source.zip'
assert hashlib.sha256(p.read_bytes()).hexdigest()==DIGEST
for n in ('stop.request','billing_stopped.json'):
    old=r/n
    if old.exists():old.rename(r/(n+'.previous-'+str(int(time.time()))))
with zipfile.ZipFile(p) as z:z.extractall(r)
(r/'private.json').chmod(0o600)
with (r/'updated-window-guard.log').open('ab') as log:
    g=subprocess.Popen(['python',str(r/'pipeline/guard.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print(json.dumps(dict(remote_guard=g.pid)))
""".replace('DIGEST',repr(launch.sha(OUT/'source.zip')))
        guards=json.loads(c.ssh('python -c '+shlex.quote(deploy),timeout=45));guards['local_guard']=guard.pid
        launch.write(OUT/'guards.json',guards)
        if not latest['runtime_exists']:
            print('Restoring verified runtime cache on the restarted container',flush=True)
            c.prepare_runtime_cache()
            restore="""from pathlib import Path
import subprocess,time
r=Path('/workspace/mimickit_trial');v=r/'venv'
assert not (v/'bin/python').exists()
if v.is_symlink():v.rename(r/('venv-broken-link-'+str(int(time.time()))))
subprocess.run(['python',str(r/'pipeline/runtime_cache.py'),'restore'],check=True)
"""
            print(c.ssh('python -c '+shlex.quote(restore),timeout=240),flush=True)
        else:
            c.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote('import newton,mujoco,mujoco_warp,torch; assert torch.cuda.is_available()'),timeout=45)
        # Source has verified copies on this PC and the retained pod volume.
        launch.write(OUT/'source-receipt.json',dict(pod=pod,hard_stop_unix=hard,sha256=launch.sha(OUT/'source.zip'),verified_local_and_remote=True,cloud_upload_not_attempted_known_quota=True))
        launch.start(resume=True)
        if args.continue_latest:
            active=json.loads((OUT/'active_run.json').read_text())
            for attempt in range(60):
                probe="from pathlib import Path; import json; p=Path('/workspace/mimickit_trial/runs')/"+repr(active['run'])+"/'status.json'; print(p.read_text() if p.exists() else 'null')"
                status=json.loads(c.ssh('python -c '+shlex.quote(probe),timeout=20))
                if status:break
                time.sleep(10)
            assert status and status['state']=='training','Learner did not begin within setup allowance'
            training_start=status['updated_unix']-status['elapsed_seconds'];training_stop=training_start+args.seconds;hard=training_stop+165
            control=dict(pod_id=pod,hard_stop_unix=hard,training_start_unix=training_start,training_stop_unix=training_stop,training_seconds=args.seconds,reason='User requested one additional hour from latest completed checkpoint')
            update="from pathlib import Path; p=Path('/workspace/mimickit_trial/runtime_control.json'); t=p.with_suffix('.tmp'); t.write_text("+repr(json.dumps(control))+"); t.replace(p); print(p.read_text())"
            assert json.loads(c.ssh('python -c '+shlex.quote(update),timeout=20))==control
            launch.write(OUT/'runtime_control.json',control)
            active.update(hard_stop_unix=hard,training_start_unix=training_start,training_stop_unix=training_stop)
            launch.write(OUT/'active_run.json',active)
            state=c.state();state['max_initial_runtime_seconds']=hard-state['created_unix'];c.save(state)
            launch.write(archive/'continuation-receipt.json',dict(run=active['run'],resume_checkpoint=expected['name'],control=control,first_iteration=status['iteration']))
            print(json.dumps(dict(stage='training_started',run=active['run'],control=control)),flush=True)
    except BaseException:
        stop_and_confirm(pod,c.rp.load_api_key(),OUT/'updated-window-start-error-stop.json','Updated crawl start failed')
        raise

if __name__=='__main__':main()
