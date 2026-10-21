"""Deploy/start only this new two-hour crawl run; existing loco state is untouched."""
from pathlib import Path
import os,sys,json,time,hashlib,shlex,subprocess,tempfile,zipfile,argparse
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitCrawl';PACKAGE=OUT/'package'
PIPE=ROOT/'Labs/MimicKitTraining'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
sys.path.insert(0,str(PIPE))
import cloud

def write(path,value):path.write_text(json.dumps(value,indent=2))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def bundle(resume_after_wrist_correction=False, resume_after_contact_cleanup=False, updated_references=False):
    from current_phat import verify_current_phat
    verify_current_phat(PACKAGE/'assets/uefn')
    report=json.loads((OUT/'preflight/report.json').read_text())
    assert report['passed'] and report.get('current_phat'), 'Run validation against the current PHAT before deployment'
    assert report['limits_sha256']==sha(PACKAGE/'assets/uefn/limits.json'), 'Preflight uses stale PHAT limits'
    if updated_references:
        imports=json.loads((OUT/'upperbody-limits-20261017/imports.json').read_text())
        for item in imports:assert sha(Path(item['path']))==item['sha256'],'Authored animation changed during preparation'
        validation=json.loads((OUT/'resume-validation.json').read_text())
        checkpoint=json.loads((OUT/'resume-checkpoint.json').read_text())
        reference=json.loads((OUT/'updated-training-20261017/verification.json').read_text())
        assert reference['passed'] and validation['finite_and_solver_checks_passed']
        assert reference['limits_sha256']==validation['limits_sha256']==sha(PACKAGE/'assets/uefn/limits.json')
        assert validation['checkpoint_sha256']==checkpoint['sha256']
        for clip in reference['clips']:
            path=PACKAGE/'motions'/(clip['clip']+'.pkl')
            assert clip['sha256']==sha(path)==validation['motion_sha256'][path.name]
        write(OUT/'resume-contact-acceptance.json',dict(user_request='Finetune latest checkpoint with updated animations and PHAT for 35 minutes',
            reference=reference,validation=validation,dynamic_penetration_validated=False,
            scope='Current reference/contact and checkpoint-rollout validation; no claim of perfect dynamic ground contact'))
    elif resume_after_wrist_correction or resume_after_contact_cleanup:
        # User explicitly requested continuing the saved policy after the wrist
        # correction. Preserve the residual-contact evidence; do not mark it clean.
        validation=json.loads((OUT/'resume-validation.json').read_text())
        checkpoint=json.loads((OUT/'resume-checkpoint.json').read_text())
        assert validation['finite_and_solver_checks_passed']
        assert validation['checkpoint_sha256']==checkpoint['sha256']
        assert validation['limits_sha256']==sha(PACKAGE/'assets/uefn/limits.json')
        if resume_after_contact_cleanup:
            cleanup=json.loads((OUT/'contact-cleanup-validation.json').read_text())
            assert cleanup['passed']
            for clip in cleanup['checks']:
                path=PACKAGE/'motions'/(clip['clip']+'.pkl')
                assert clip['sha256']==sha(path)==validation['motion_sha256'][path.name]
        write(OUT/'resume-contact-acceptance.json',dict(
            user_request='do it and resume for 1h' if resume_after_contact_cleanup else 'okay should be good resume from latest for 2h',
            dynamic_penetration_validated=False,validation=validation,
            scope='Resume with cleaned crawl contacts and corrected wrists; solver unchanged' if resume_after_contact_cleanup else 'Resume with corrected wrists and unchanged solver; residual penetration disclosed'))
    else:
        assert report.get('dynamic_penetration_validated') is True, 'Dynamic ground-contact regression must pass before another paid run'
    assert report['policy_clips']==['crawl','crawl_idle'] and report['termination_regression_passed']
    assert not report['clip_end_reset']
    manifest=json.loads((PACKAGE/'prepared/manifest.json').read_text())
    assert [r['id'] for r in manifest['motions']]==['crawl','crawl_idle']
    assert all(r['loop_mode']=='WRAP' for r in manifest['motions'])
    assert json.loads((OUT/'locked-twist-test.json').read_text())['passed']
    assert json.loads((OUT/'contact-capacity-test.json').read_text())['passed']
    inventory={str(p.relative_to(PACKAGE)).replace('\\','/'):sha(p) for p in PACKAGE.rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='source-inventory.json'}
    write(PACKAGE/'source-inventory.json',inventory)
    with zipfile.ZipFile(OUT/'source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in inventory:z.write(PACKAGE/name,name)
        z.write(PACKAGE/'source-inventory.json','source-inventory.json')
    write(OUT/'package-receipt.json',dict(sha256=sha(OUT/'source.zip'),bytes=(OUT/'source.zip').stat().st_size,files=len(inventory)))

def deploy(resume_after_wrist_correction=False,resume_after_contact_cleanup=False,seconds=7200):
    assert 300<seconds<=7200
    bundle(resume_after_wrist_correction=resume_after_wrist_correction,resume_after_contact_cleanup=resume_after_contact_cleanup)
    assert cloud.OUT==OUT
    assert not (OUT/'pod.json').exists(),'Reconcile existing owned allocation; never allocate a duplicate'
    cloud.allocate('NVIDIA L4',.59,'SECURE',seconds,'prophecy-crawl-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    state=cloud.state();hard=state['created_unix']+seconds
    write(OUT/'runtime_control.json',dict(pod_id=state['pod_id'],hard_stop_unix=hard))
    with (OUT/'local-guard.log').open('ab') as log:
        guard=subprocess.Popen([sys.executable,str(PIPE/'local_guard.py')],stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT/'guards.json',dict(local_guard=guard.pid))
    try:
        cloud.connect();state=cloud.state()
        cloud.ssh('mkdir -p /workspace/mimickit_trial')
        cloud.rp.scp(state['connection'],OUT/'source.zip','/workspace/mimickit_trial/source.zip',timeout=60)
        cloud.ssh('cd /workspace/mimickit_trial && python -m zipfile -e source.zip .')
        private=dict(pod_id=state['pod_id'],deadline_unix=hard-120,runpod_api_key=cloud.rp.load_api_key(),s3=cloud.credentials())
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'private.json';write(p,private)
            cloud.rp.scp(state['connection'],p,'/workspace/mimickit_trial/private.json',timeout=45)
        cloud.rp.scp(state['connection'],OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=45)
        cloud.ssh('chmod 600 /workspace/mimickit_trial/private.json; cd /workspace/mimickit_trial; nohup python pipeline/guard.py > guard.log 2>&1 < /dev/null &')
        cloud.prepare_runtime_cache()
        cloud.ssh('cd /workspace/mimickit_trial; nohup bash pipeline/setup.sh > setup.log 2>&1 < /dev/null &')
        body=(OUT/'source.zip').read_bytes();digest=hashlib.sha256(body).hexdigest()
        key='mimickit/pipeline_20261014/crawl/source_'+digest[:16]+'.zip'
        client=cloud.s3();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body,Metadata={'sha256':digest})
        assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==digest
        receipt=dict(pod=state['pod_id'],hard_stop_unix=hard,key=key,sha256=digest,verified=True)
        write(OUT/'source-receipt.json',receipt);print(json.dumps(receipt),flush=True)
    except BaseException:
        from billing_stop import stop_and_confirm
        stop_and_confirm(state['pod_id'],cloud.rp.load_api_key(),OUT/'deploy-error-stop.json','Crawl deployment failed')
        raise

def start(resume=False):
    from current_phat import verify_current_phat, FILES
    verify_current_phat(PACKAGE/'assets/uefn')
    preflight=json.loads((OUT/'preflight/report.json').read_text())
    assert preflight.get('current_phat') and preflight.get('limits_sha256')==sha(PACKAGE/'assets/uefn/limits.json'), 'Validate current PHAT before starting training'
    current_assets={f'assets/uefn/{name}':sha(PACKAGE/'assets/uefn'/name) for name in FILES}
    state=cloud.state();control=json.loads((OUT/'runtime_control.json').read_text())
    assert state['pod_id']==control['pod_id'] and control['hard_stop_unix']>time.time()+300
    name=datetime.now().strftime('%Y%m%d_%H%M%S')+'_uefn_crawl_velocity_512'
    args=['--name',name,'--worlds','512','--control-mode','vel','--absolute-walk','--evaluate',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--replay-rows','12','--seconds',str(int(state['max_initial_runtime_seconds']))]
    resume_receipt=None
    if resume:
        resume_receipt=json.loads((OUT/'resume-checkpoint.json').read_text())
        checkpoint=Path(resume_receipt['local_path'])
        assert resume_receipt['verified'] and sha(checkpoint)==resume_receipt['sha256']
        remote='/workspace/mimickit_trial/resume.zip'
        fetch="""from pathlib import Path
import json,hashlib,boto3
r=Path('/workspace/mimickit_trial')
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
p=r/'resume-download.zip'
c.download_file(BUCKET,KEY,str(p))
assert hashlib.sha256(p.read_bytes()).hexdigest()==DIGEST
p.replace(r/'resume.zip')
print('Resume checkpoint downloaded and checksum verified')
""".replace('BUCKET',repr(cloud.rp.VOLUME_ID)).replace('KEY',repr(resume_receipt.get('key'))).replace('DIGEST',repr(resume_receipt['sha256']))
        if resume_receipt.get('key'):
            cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(fetch),timeout=60)
        else:
            # Reuse an identical retained archive before attempting a slow upload.
            source_run=resume_receipt.get('source_run','')
            assert not source_run or all(c.isalnum() or c=='_' for c in source_run)
            retained="""from pathlib import Path
import hashlib,shutil,json
r=Path('/workspace/mimickit_trial');p=r/'runs'/RUN/FILE
valid=p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==DIGEST
if valid:shutil.copy2(p,r/'resume.zip')
print(json.dumps(valid))
""".replace('RUN',repr(source_run)).replace('FILE',repr(checkpoint.name)).replace('DIGEST',repr(resume_receipt['sha256']))
            reused=bool(source_run) and json.loads(cloud.ssh('python -c '+shlex.quote(retained),timeout=30))
            if not reused:cloud.rp.scp(state['connection'],checkpoint,remote,timeout=180)
            code="from pathlib import Path; import hashlib; assert hashlib.sha256(Path('/workspace/mimickit_trial/resume.zip').read_bytes()).hexdigest()=="+repr(resume_receipt['sha256'])
            cloud.ssh('python -c '+shlex.quote(code),timeout=20)
        args+=['--resume',remote]
    code="""from pathlib import Path
import json,hashlib,subprocess,time
r=Path('/workspace/mimickit_trial')
assert (r/'runtime-cache-restored.json').exists()
assert not (r/'stop.request').exists()
assert not (r/'runs'/NAME).exists()
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:argv=(p/'cmdline').read_bytes().split(b'\\0')
    except OSError:continue
    assert b'/workspace/mimickit_trial/pipeline/train.py' not in argv
for path,digest in json.loads((r/'source-inventory.json').read_text()).items():
    assert hashlib.sha256((r/path).read_bytes()).hexdigest()==digest,path
for path,digest in CURRENT_PHAT_ASSETS.items():
    assert hashlib.sha256((r/path).read_bytes()).hexdigest()==digest,'Remote PHAT differs from current local PHAT: '+path
command=[str(r/'venv/bin/python'),'-u',str(r/'pipeline/train.py')]+ARGS
with (r/(NAME+'.log')).open('ab',buffering=0) as log:
    p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(run=NAME,name=NAME,pid=p.pid,command=command,launched_unix=time.time())
(r/(NAME+'-launch.json')).write_text(json.dumps(receipt,indent=2))
with (r/(NAME+'-exit-guard.log')).open('ab',buffering=0) as log:
    g=subprocess.Popen([str(r/'venv/bin/python'),str(r/'pipeline/failure_stop.py'),NAME],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt['exit_guard_pid']=g.pid
(r/(NAME+'-launch.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
""".replace('NAME',repr(name)).replace('ARGS',repr(args)).replace('CURRENT_PHAT_ASSETS',repr(current_assets))
    receipt=json.loads(cloud.ssh('python -c '+shlex.quote(code)))
    receipt.update(pod=state['pod_id'],hard_stop_unix=control['hard_stop_unix'])
    if resume_receipt:receipt['resume_checkpoint']=resume_receipt
    write(OUT/(name+'-launch.json'),receipt);write(OUT/'active_run.json',receipt)
    if state.get('local_checkpoint_backup'):
        with (OUT/(name+'-local-backup.log')).open('ab',buffering=0) as log:
            helper=subprocess.Popen([sys.executable,'-u',str(Path(__file__).parent/'local_backup.py')],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        receipt['local_backup_pid']=helper.pid
        write(OUT/'active_run.json',receipt)
    # Existing low-bandwidth bridge/replayer and TensorBoard infrastructure.
    source=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name)
    dashboard=dict(output=str(ROOT/'Saved/MimicKit/TensorBoardRuns'),
        runtime_control=dict(path=str(OUT/'runtime_control.json'),pod_id=state['pod_id']),
        runs=[dict(name=datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'_UEFN_Crawl_velocity_512',
                   objective='uefn_crawl_idle_mse',sources=[str(source)])])
    path=OUT/(name+'-dashboard.json');write(path,dashboard);observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab',buffering=0) as log:
            p=subprocess.Popen([sys.executable,str(PIPE/(kind+'.py'))]+argv,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        observers[kind]=p.pid
    write(OUT/'observers.json',dict(run=name,**observers));print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['bundle','deploy','start'])
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--resume-after-wrist-correction',action='store_true')
    parser.add_argument('--resume-after-contact-cleanup',action='store_true')
    parser.add_argument('--seconds',type=int,default=7200);a=parser.parse_args()
    if a.action=='start':start(resume=a.resume)
    else:
        assert not a.resume,'--resume applies to start'
        kw=dict(resume_after_wrist_correction=a.resume_after_wrist_correction,resume_after_contact_cleanup=a.resume_after_contact_cleanup)
        if a.action=='deploy':kw['seconds']=a.seconds
        dict(bundle=bundle,deploy=deploy)[a.action](**kw)
