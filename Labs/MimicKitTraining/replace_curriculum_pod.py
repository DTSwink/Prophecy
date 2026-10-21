"""Explicitly approved L4 replacement; bounded setup and canonical guard state."""
import hashlib,json,os,shlex,subprocess,sys,tempfile,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm


def main():
    if (OUT/'pod.json').exists():
        old=cloud.state()
    else:
        old=json.loads(sorted((OUT/'retained-pods/f44oylb1xk3y5o').glob('*-pod.json'))[-1].read_text())
    assert old['pod_id']=='f44oylb1xk3y5o'
    status=cloud.rp.request_json('GET','/pods/'+old['pod_id'])
    assert status['desiredStatus']=='EXITED'
    cp=json.loads((OUT/'getup-curriculum-preserved-checkpoint.json').read_text())
    src=json.loads((OUT/'getup-curriculum-source-verified.json').read_text())
    for item in (cp,src):
        assert hashlib.sha256(Path(item['local']).read_bytes()).hexdigest()==item['sha256']
    retained=OUT/'retained-pods'/old['pod_id'];retained.mkdir(parents=True,exist_ok=True)
    for name in ('pod.json','runtime_control.json','active_run.json'):
        path=OUT/name
        if path.exists():path.replace(retained/(str(int(time.time()))+'-'+name))
    pod=None
    try:
        cloud.allocate('NVIDIA L4',.59,'COMMUNITY' if '--community' in sys.argv else 'SECURE',seconds=600,
                       name='mimickit-curriculum-replacement-'+str(int(time.time())),
                       data_center_ids=['US-IL-1','US-TX-3','US-GA-2','EU-RO-1','EU-CZ-1','EU-SE-1','EU-NL-1','EU-FR-1'] if '--regions' in sys.argv else None)
        pod=cloud.state()['pod_id']
        control=dict(pod_id=pod,hard_stop_unix=time.time()+600,until_stopped=False,updated_unix=time.time())
        (OUT/'runtime_control.json').write_text(json.dumps(control))
        with (OUT/'curriculum-replacement-guard.log').open('ab') as log:
            guard=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],
                stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000)
        (OUT/'curriculum-replacement-allocation.json').write_text(json.dumps(dict(pod=pod,guard_pid=guard.pid,setup_deadline=control['hard_stop_unix'])))
        conn=cloud.rp.wait_for_connection(pod,timeout_seconds=180)
        state=cloud.state();state['connection']=conn;cloud.save(state)
        r='/workspace/mimickit_trial'
        cloud.ssh('mkdir -p '+r)
        cloud.rp.scp(conn,Path(src['local']),r+'/source.zip',timeout=90)
        code="import hashlib,zipfile;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()=="+repr(src['sha256'])+";zipfile.ZipFile(r/'source.zip').extractall(r)"
        cloud.ssh('python -c '+shlex.quote(code),timeout=30)
        private=dict(pod_id=pod,deadline_unix=control['hard_stop_unix']-120,
                     runpod_api_key=cloud.rp.load_api_key(),s3=cloud.credentials(),resume_checkpoint=cp)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'private.json';path.write_text(json.dumps(private))
            cloud.rp.scp(conn,path,r+'/private.json',timeout=30)
        cloud.rp.scp(conn,OUT/'runtime_control.json',r+'/runtime_control.json',timeout=30)
        cloud.ssh('chmod 600 '+r+'/private.json; cd '+r+'; nohup python pipeline/guard.py > replacement-guard.log 2>&1 < /dev/null &')
        print('Replacement connected; restoring verified runtime.',flush=True)
        cloud.prepare_runtime_cache()
        log=cloud.ssh('cd '+r+'; timeout 180 python pipeline/runtime_cache.py restore',timeout=190)
        (OUT/'curriculum-replacement-runtime.log').write_text(log)
        cloud.ssh('cd '+r+'; timeout 90 venv/bin/python pipeline/resume.py',timeout=100)
        plan=json.loads((OUT/'getup-curriculum-switch.json').read_text())
        plan.update(pod=pod,replacement_of=old['pod_id'],replacement_authorized=True)
        plan['instructions']=plan['instructions'].replace(old['pod_id'],pod)
        (OUT/'getup-curriculum-switch.json').write_text(json.dumps(plan,indent=2))
        (OUT/'curriculum-replacement-ready.json').write_text(json.dumps(dict(pod=pod,source=src,checkpoint=cp,ready=True)))
        print('Verified source, runtime and latest checkpoint ready on '+pod,flush=True)
    except Exception:
        if pod is None and (OUT/'pod.json').exists():pod=cloud.state()['pod_id']
        if pod:stop_and_confirm(pod,cloud.rp.load_api_key(),OUT/'curriculum-replacement-failed-stop.json','replacement setup failed')
        raise


if __name__=='__main__':main()
