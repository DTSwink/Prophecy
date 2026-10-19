"""Resume verified 337.74M main checkpoint with approved eight-hour curriculum."""
import hashlib,json,os,shlex,subprocess,sys,tempfile,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm

def main():
    source=json.loads((OUT/'main337-native-source.json').read_text())
    assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest()==source['sha256']
    cp=source['resume_checkpoint']
    client=cloud.s3()
    # Verify the known latest checkpoint remains readable before renting.
    stream=client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=cp['key'])['Body'];digest=hashlib.sha256()
    for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    stream.close();assert digest.hexdigest()==cp['sha256']
    # Persist the complete executable source before production starts.
    key='mimickit/pipeline_20261014/equipment/main337-getup/source_'+source['sha256'][:12]+'.zip'
    body=Path(source['source']).read_bytes();client.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body)
    assert hashlib.sha256(client.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==source['sha256']
    (OUT/'main337-source-verified.json').write_text(json.dumps(dict(key=key,sha256=source['sha256'],verified=True)))
    old=cloud.state();p=cloud.rp.request_json('GET','/pods/'+old['pod_id'])
    assert p['desiredStatus']=='EXITED'
    previous=json.loads((OUT/'main337-start.json').read_text()) if '--continue-window' in sys.argv else None
    begun=previous['started_unix'] if previous else time.time()
    hard=previous['hard_stop_unix'] if previous else begun+28800
    assert hard-time.time()>600
    launched=False;pod=None
    try:
        try:
            assert float(p['costPerHr'])<=.59
            cloud.rp.request_json('POST','/pods/'+old['pod_id']+'/start')
            pod=old['pod_id'];print('Reusing retained L4.',flush=True)
        except Exception as error:
            stop_and_confirm(old['pod_id'],cloud.rp.load_api_key(),OUT/'main337-old-pod-stopped.json','native replacement preparation')
            retained=OUT/'retained-pods'/old['pod_id'];retained.mkdir(parents=True,exist_ok=True)
            for name in ('pod.json','runtime_control.json','active_run.json'):
                path=OUT/name
                if path.exists():
                    target=retained/(str(int(time.time()))+'-'+name)
                    path.replace(target)
            cloud.allocate('NVIDIA L4',.59,'SECURE',seconds=int(hard-time.time()),name='mimickit-main337-'+str(int(time.time())))
            pod=cloud.state()['pod_id'];print('Replacement allocated; old disk retained.',flush=True)
        control=dict(pod_id=pod,hard_stop_unix=hard,updated_unix=time.time(),until_stopped=False)
        (OUT/'runtime_control.json').write_text(json.dumps(control))
        state=cloud.state();state.update(hard_stop_unix=hard,until_stopped=False);cloud.save(state)
        with (OUT/'main337-local-guard.log').open('ab') as log:
            guard=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],
                stdout=log,stderr=log,creationflags=0x08000000)
        (OUT/'main337-start.json').write_text(json.dumps(dict(pod=pod,started_unix=begun,hard_stop_unix=hard,local_guard=guard.pid)))
        cloud.connect();connection=cloud.state()['connection'];remote='/workspace/mimickit_trial'
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
        cloud.ssh('chmod 600 '+remote+'/source-download.json; python -c '+shlex.quote(fetch),timeout=75)
        cloud.ssh('cd '+remote+'; python -m zipfile -e source.zip .',timeout=45)
        private=dict(pod_id=pod,deadline_unix=hard-120,runpod_api_key=cloud.rp.load_api_key(),
                     s3=cloud.credentials(),resume_checkpoint=cp)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private.json';path.write_text(json.dumps(private))
            cloud.rp.scp(connection,path,remote+'/private.json',timeout=30)
        cloud.rp.scp(connection,OUT/'runtime_control.json',remote+'/runtime_control.json',timeout=30)
        cloud.ssh('chmod 600 '+remote+'/private.json; cd '+remote+'; rm -f stop.request; nohup python pipeline/guard.py > main337-guard.log 2>&1 < /dev/null &')
        # A stopped pod loses the container-local venv; remove only its broken symlink.
        code="from pathlib import Path; p=Path('/workspace/mimickit_trial/venv'); broken=p.is_symlink() and not p.exists(); p.unlink() if broken else None; print(int((p/'bin/python').exists()))"
        ready=cloud.ssh('python -c '+shlex.quote(code)).strip()=='1'
        if not ready:
            cloud.prepare_runtime_cache()
            log=cloud.ssh('cd '+remote+'; timeout 180 python pipeline/runtime_cache.py restore',timeout=190)
            (OUT/'main337-runtime.log').write_text(log)
        cloud.ssh('cd '+remote+'; timeout 90 venv/bin/python pipeline/resume.py',timeout=100)
        print('Runtime and latest checkpoint ready. Checking native engine and five PPO updates with critic cap10.',flush=True)
        try:
            cloud.ssh('cd '+remote+'; timeout 180 venv/bin/python -u pipeline/preflight_main337.py > main337-preflight.log 2>&1',timeout=190)
        finally:
            (OUT/'main337-preflight.log').write_text(cloud.ssh('tail -c 16000 '+remote+'/main337-preflight.log'))
            diagnostic=cloud.ssh('cat '+remote+'/main337-diagnostic.json 2>/dev/null || true')
            if diagnostic.strip():(OUT/'main337-diagnostic.json').write_text(diagnostic)
        result=json.loads(cloud.ssh('cat '+remote+'/main337-preflight.json'))
        assert result['passed']
        (OUT/'main337-preflight.json').write_text(json.dumps(result,indent=2))
        now=datetime.now().astimezone();name=now.strftime('%Y%m%d_%H%M%S')+'_uefn_main337_native_mj_512'
        remaining=int(hard-time.time());assert remaining>600
        args=['--name',name,'--seconds',str(remaining),'--worlds','512','--control-mode','vel','--absolute-walk',
              '--equipment-omni',remote+'/prepared','--evaluate','--output-interval','100','--replay-rows','20','--resume',remote+'/resume.zip']
        subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds',str(remaining),'--',*args],check=True)
        launched=True
        manifest=json.loads((OUT/'20261018_062758_uefn_getup_frame0_reciprocal_512-dashboard.json').read_text())
        manifest['runtime_control']['pod_id']=pod
        manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_UEFN_Main337_native_MJ_512',objective='uefn_omni_absolute_walk',
                              sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
        dest=OUT/(name+'-dashboard.json');dest.write_text(json.dumps(manifest,indent=2));pids={}
        for kind,argv in [('bridge',['--name',name]),('dashboard',[str(dest)])]:
            with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdout=log,stderr=log,creationflags=0x08000000)
            pids[kind]=proc.pid
        (OUT/(name+'-observers.json')).write_text(json.dumps(pids));(OUT/'current-run.txt').write_text(name)
        receipt=dict(run=name,pod=pod,hard_stop_unix=hard,checkpoint=cp,observers=pids,preflight=result)
        (OUT/'main337-launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
    except Exception:
        if pod is None and (OUT/'pod.json').exists():pod=cloud.state()['pod_id']
        if pod is not None:stop_and_confirm(pod,cloud.rp.load_api_key(),OUT/'main337-setup-failed-stop.json','native setup failed')
        raise

if __name__=='__main__':main()
