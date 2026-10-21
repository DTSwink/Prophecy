"""Resume verified 770.7M checkpoint with approved eight-hour perturbed curriculum."""
import hashlib,json,os,shlex,subprocess,sys,tempfile,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm

def main():
    source=json.loads((OUT/'perturbed-preparation/prepared.json').read_text());source['sha256']=source['source_sha256'];source['resume_checkpoint']=source['checkpoint']
    assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest()==source['sha256']
    cp=source['resume_checkpoint']
    client=cloud.s3()
    # Verify the known latest checkpoint remains readable before renting.
    verified=OUT/'perturbed-source-verified.json'
    reuse='--continue-window' in sys.argv and verified.exists() and json.loads(verified.read_text())['sha256']==source['sha256']
    if not reuse:
        stream=client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=cp['key'])['Body'];digest=hashlib.sha256()
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
        stream.close();assert digest.hexdigest()==cp['sha256']
    # Persist the complete executable source before production starts.
    key='mimickit/pipeline_20261014/equipment/perturbed-motion/source_'+source['sha256'][:12]+'.zip'
    if not reuse:
        body=Path(source['source']).read_bytes();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body)
        assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==source['sha256']
    (OUT/'perturbed-source-verified.json').write_text(json.dumps(dict(key=key,sha256=source['sha256'],verified=True)))
    old=cloud.state();p=cloud.rp.request_json('GET','/pods/'+old['pod_id'])
    adopt='--adopt-running' in sys.argv
    assert p['desiredStatus']==('RUNNING' if adopt else 'EXITED')
    previous=json.loads((OUT/'perturbed-start.json').read_text()) if '--continue-window' in sys.argv else None
    begun=previous['started_unix'] if previous else time.time()
    hard=previous['hard_stop_unix'] if previous else begun+28800
    assert hard-time.time()>600
    launched=False;pod=None
    try:
        try:
            assert float(p['costPerHr'])<=.59
            if '--replace-startup-failure' in sys.argv:
                raise RuntimeError('Replace host that twice failed to boot its container')
            if not adopt:cloud.rp.request_json('POST','/pods/'+old['pod_id']+'/start')
            pod=old['pod_id'];print('Using owned '+old.get('gpu','GPU')+'.',flush=True)
        except Exception as error:
            if '--reuse-only' in sys.argv:
                raise RuntimeError('Retained pod restart rejected; no replacement allocated: '+str(error)) from error
            stop_and_confirm(old['pod_id'],cloud.rp.load_api_key(),OUT/'perturbed-old-pod-stopped.json','native replacement preparation')
            retained=OUT/'retained-pods'/old['pod_id'];retained.mkdir(parents=True,exist_ok=True)
            for name in ('pod.json','runtime_control.json','active_run.json'):
                path=OUT/name
                if path.exists():
                    target=retained/(str(int(time.time()))+'-'+name)
                    path.replace(target)
            centers=['EU-CZ-1','EU-NL-1','EU-SE-1','EU-FR-1','US-IL-1','US-TX-3','US-GA-2'] if '--replace-startup-failure' in sys.argv else None
            cloud.allocate(old.get('gpu','NVIDIA L4'),.59,'SECURE',seconds=int(hard-time.time()),name='mimickit-perturbed-'+str(int(time.time())),data_center_ids=centers)
            pod=cloud.state()['pod_id'];print('Replacement allocated; old disk retained.',flush=True)
        setup_deadline=min(hard,time.time()+600)
        control=dict(pod_id=pod,hard_stop_unix=setup_deadline,updated_unix=time.time(),until_stopped=False)
        active=OUT/'active_run.json'
        if active.exists():active.replace(OUT/('previous-active-'+str(int(time.time()))+'.json'))
        (OUT/'runtime_control.json').write_text(json.dumps(control))
        state=cloud.state();state.update(hard_stop_unix=setup_deadline,until_stopped=False);cloud.save(state)
        with (OUT/'perturbed-local-guard.log').open('ab') as log:
            guard=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],
                stdout=log,stderr=log,creationflags=0x08000000)
        (OUT/'perturbed-start.json').write_text(json.dumps(dict(pod=pod,started_unix=begun,hard_stop_unix=hard,local_guard=guard.pid)))
        connection=cloud.rp.wait_for_connection(pod,timeout_seconds=300)
        state=cloud.state();state['connection']=connection;cloud.save(state)
        remote='/workspace/mimickit_trial'
        cloud.ssh('mkdir -p '+remote)
        # Fetch the verified package cloud-to-cloud; avoid a large SCP upload.
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        from botocore.credentials import Credentials
        credentials=cloud.credentials()
        url=credentials['endpoint_url']+'/'+cloud.rp.VOLUME_ID+'/'+key
        request=AWSRequest(method='GET',url=url,headers={'User-Agent':'MimicKit-runtime-cache/1.0','X-Amz-Content-SHA256':hashlib.sha256(b'').hexdigest()})
        SigV4Auth(Credentials(credentials['aws_access_key_id'],credentials['aws_secret_access_key']),'s3',credentials['region_name']).add_auth(request)
        with tempfile.TemporaryDirectory() as tmp:
            hint=Path(tmp)/'source-download.json'
            hint.write_text(json.dumps(dict(url=url,headers=dict(request.headers),sha256=source['sha256'])))
            cloud.rp.scp(connection,hint,remote+'/source-download.json',timeout=45)
        fetch="import json,hashlib,urllib.request; from pathlib import Path; r=Path('/workspace/mimickit_trial'); p=r/'source-download.json'; c=json.loads(p.read_text()); data=urllib.request.urlopen(urllib.request.Request(c['url'],headers=c['headers']),timeout=60).read(); assert hashlib.sha256(data).hexdigest()==c['sha256']; (r/'source.zip').write_bytes(data); p.unlink(); print('Source download verified')"
        # The source is only ~11 MB. SSH avoids intermittent cross-region S3
        # reads; persistent S3 readback above still proves source durability.
        present=cloud.ssh('sha256sum '+remote+'/source.zip 2>/dev/null || true').split()
        if not present or present[0]!=source['sha256']:
            downloaded=False
            if '--cloud-source' in sys.argv:
                try:
                    cloud.ssh('chmod 600 '+remote+'/source-download.json; python -c '+shlex.quote(fetch.replace('timeout=60','timeout=20')),timeout=30)
                    downloaded=True
                except Exception:
                    print('Cloud source read unavailable; using small SSH source transfer.',flush=True)
            if not downloaded:cloud.rp.scp(connection,Path(source['source']),remote+'/source.zip',timeout=90)
        check="import hashlib;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()=="+repr(source['sha256'])+";(r/'source-download.json').unlink(missing_ok=True)"
        cloud.ssh('python -c '+shlex.quote(check),timeout=20)
        cloud.ssh('cd '+remote+'; python -m zipfile -e source.zip .',timeout=45)
        private=dict(pod_id=pod,deadline_unix=setup_deadline-120,runpod_api_key=cloud.rp.load_api_key(),
                     s3=cloud.credentials(),resume_checkpoint=cp)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private.json';path.write_text(json.dumps(private))
            cloud.rp.scp(connection,path,remote+'/private.json',timeout=30)
        cloud.rp.scp(connection,OUT/'runtime_control.json',remote+'/runtime_control.json',timeout=30)
        cloud.ssh('chmod 600 '+remote+'/private.json; cd '+remote+'; rm -f stop.request; nohup python pipeline/guard.py > perturbed-guard.log 2>&1 < /dev/null &')
        # A stopped pod loses the container-local venv; remove only its broken symlink.
        code="from pathlib import Path; p=Path('/workspace/mimickit_trial/venv'); broken=p.is_symlink() and not p.exists(); p.unlink() if broken else None; print(int((p/'bin/python').exists()))"
        ready=cloud.ssh('python -c '+shlex.quote(code)).strip()=='1'
        if not ready:
            cached=OUT/'startup-diagnosis/runtime-cache.tar.gz'
            if '--local-runtime' in sys.argv:
                manifest=json.loads((OUT/'startup-diagnosis/runtime-local.json').read_text())
                assert hashlib.sha256(cached.read_bytes()).hexdigest()==manifest['sha256']
                present=cloud.ssh('sha256sum '+remote+'/runtime-preload.tar.gz 2>/dev/null || true').split()
                if not present or present[0]!=manifest['sha256']:
                    raise RuntimeError('Verified runtime not present on retained disk; refusing another slow paid upload')
                restore="import hashlib,subprocess,sys;from pathlib import Path;sys.path.insert(0,'pipeline');import runtime_cache as c;p=Path('runtime-preload.tar.gz');assert c.compatibility()=="+repr(manifest['compatibility'])+";assert c.sha256(p)=="+repr(manifest['sha256'])+";t=Path('/opt/mimickit-runtime');t.mkdir();subprocess.run(['tar','-xzf',str(p),'-C',str(t)],check=True);Path('venv').symlink_to(t/'venv',target_is_directory=True);Path('runtime-freeze.txt').write_bytes((t/'runtime-freeze.txt').read_bytes());print('Retained runtime restore verified')"
                log=cloud.ssh('cd '+remote+'; python -c '+shlex.quote(restore),timeout=60)
            else:
                cloud.prepare_runtime_cache()
                log=cloud.ssh('cd '+remote+'; timeout 180 python pipeline/runtime_cache.py restore',timeout=190)
            (OUT/'perturbed-runtime.log').write_text(log)
        if '--local-runtime' in sys.argv:
            local_cp=Path(cp['local']);assert hashlib.sha256(local_cp.read_bytes()).hexdigest()==cp['sha256']
            present=cloud.ssh('sha256sum '+remote+'/resume.zip 2>/dev/null || true').split()
            if not present or present[0]!=cp['sha256']:
                cloud.rp.scp(connection,local_cp,remote+'/resume.zip',timeout=180)
            verify="import hashlib;from pathlib import Path;assert hashlib.sha256(Path('/workspace/mimickit_trial/resume.zip').read_bytes()).hexdigest()=="+repr(cp['sha256'])
            cloud.ssh('python -c '+shlex.quote(verify),timeout=15)
        else:
            cloud.ssh('cd '+remote+'; timeout 90 venv/bin/python pipeline/resume.py',timeout=100)
        print('Runtime and latest checkpoint ready. Checking all 512 rows, COM2 preservation, phase feedback, AE reward and five discarded PPO updates.',flush=True)
        try:
            cloud.ssh('cd '+remote+'; timeout 300 venv/bin/python -u pipeline/preflight_perturbed.py > perturbed-preflight.log 2>&1',timeout=310)
        finally:
            (OUT/'perturbed-preflight.log').write_text(cloud.ssh('tail -c 16000 '+remote+'/perturbed-preflight.log'))
            diagnostic=cloud.ssh('cat '+remote+'/perturbed-diagnostic.json 2>/dev/null || true')
            if diagnostic.strip():(OUT/'perturbed-diagnostic.json').write_text(diagnostic)
        result=json.loads(cloud.ssh('cat '+remote+'/perturbed-preflight.json'))
        assert result['passed']
        (OUT/'perturbed-preflight.json').write_text(json.dumps(result,indent=2))
        # Compare the SAME old workload with the recorded L4 benchmark.
        # The new AE/perturbation workload must not be mistaken for GPU slowdown.
        if 'A40' in cloud.state().get('gpu','') and '--accept-slower-a40' not in sys.argv:
            cloud.ssh('cd '+remote+'; timeout 180 venv/bin/python -u pipeline/preflight_perturbed.py --baseline > baseline-preflight.log 2>&1',timeout=190)
            baseline=json.loads(cloud.ssh('cat '+remote+'/baseline-preflight.json'))
            result['old_workload_baseline']=baseline
            (OUT/'perturbed-preflight.json').write_text(json.dumps(result,indent=2))
            if baseline['transitions_per_second'] < 7620:
                raise RuntimeError('A40 old-workload throughput below comparable-speed threshold: '+str(baseline['transitions_per_second']))
        now=datetime.now().astimezone();name=now.strftime('%Y%m%d_%H%M%S')+'_uefn_perturbed_ae_512'
        remaining=int(hard-time.time());assert remaining>600
        args=['--name',name,'--seconds',str(remaining),'--worlds','512','--control-mode','vel','--absolute-walk',
              '--equipment-omni',remote+'/prepared','--evaluate','--output-interval','100','--replay-rows','20','--resume',remote+'/resume.zip','--resume-perturbed-motion']
        control['hard_stop_unix']=hard;control['updated_unix']=time.time()
        (OUT/'runtime_control.json').write_text(json.dumps(control))
        cloud.rp.scp(connection,OUT/'runtime_control.json',remote+'/runtime_control.json',timeout=30)
        state=cloud.state();state.update(hard_stop_unix=hard,until_stopped=False);cloud.save(state)
        subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds',str(remaining),'--',*args],check=True)
        launched=True
        manifest=json.loads((OUT/'20261018_062758_uefn_getup_frame0_reciprocal_512-dashboard.json').read_text())
        manifest['runtime_control']['pod_id']=pod
        manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_UEFN_Perturbed_AE_512',objective='uefn_omni_absolute_walk',
                              sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
        dest=OUT/(name+'-dashboard.json');dest.write_text(json.dumps(manifest,indent=2));pids={}
        for kind,argv in [('bridge',['--name',name]),('dashboard',[str(dest)])]:
            with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdout=log,stderr=log,creationflags=0x08000000)
            pids[kind]=proc.pid
        (OUT/(name+'-observers.json')).write_text(json.dumps(pids));(OUT/'current-run.txt').write_text(name)
        receipt=dict(run=name,pod=pod,hard_stop_unix=hard,checkpoint=cp,observers=pids,preflight=result)
        (OUT/'perturbed-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
    except Exception:
        if pod is None and (OUT/'pod.json').exists():pod=cloud.state()['pod_id']
        if pod is not None:stop_and_confirm(pod,cloud.rp.load_api_key(),OUT/'perturbed-setup-failed-stop.json','native setup failed')
        raise

if __name__=='__main__':main()
