"""One bounded startup attempt with preserved platform evidence, no training."""
import json, os, shlex, subprocess, sys, time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from billing_stop import stop_and_confirm

def main():
    evidence=OUT/'startup-diagnosis';evidence.mkdir(exist_ok=True)
    original=json.loads((OUT/'perturbed-start.json').read_text())
    hard=min(original['hard_stop_unix'],time.time()+900)
    if '--existing-pod' in sys.argv:
        selected=sys.argv[sys.argv.index('--existing-pod')+1]
        p=cloud.rp.request_json('GET','/pods/'+selected+'?includeMachine=true')
        assert p['name'].startswith('mimickit-') and p['desiredStatus']=='EXITED'
        assert p['machine']['gpuTypeId']=='NVIDIA L4' and float(p['costPerHr'])<=.59
        cloud.save(dict(pod_id=selected,name=p['name'],gpu='NVIDIA L4',cost_per_hour=p['costPerHr'],
                        created_unix=time.time(),max_initial_runtime_seconds=900,cloud_type='SECURE'))
    old=cloud.state();pod=None;ready=False
    try:
        p=cloud.rp.request_json('GET','/pods/'+old['pod_id'])
        assert p['desiredStatus']=='EXITED' and float(p['costPerHr'])<=.59
        try:
            if '--gpu' in sys.argv:
                raise RuntimeError('Controlled same-image startup on alternative GPU')
            cloud.rp.request_json('POST','/pods/'+old['pod_id']+'/start')
            pod=old['pod_id']
        except Exception as error:
            (evidence/'retained-start-error.txt').write_text(str(error))
            print('Retained start rejected: '+str(error),flush=True)
            if '--existing-pod' in sys.argv:
                assert cloud.rp.request_json('GET','/pods/'+old['pod_id'])['desiredStatus']=='EXITED'
                raise
            archive=OUT/'retained-pods'/old['pod_id'];archive.mkdir(exist_ok=True,parents=True)
            for name in ('pod.json','runtime_control.json','active_run.json'):
                path=OUT/name
                if path.exists():path.replace(archive/(str(int(time.time()))+'-'+name))
            gpu=sys.argv[sys.argv.index('--gpu')+1] if '--gpu' in sys.argv else 'NVIDIA L4'
            assert gpu in ('NVIDIA L4','NVIDIA A40')
            centers=sys.argv[sys.argv.index('--centers')+1].split(',') if '--centers' in sys.argv else None
            cloud.allocate(gpu,.59,'SECURE',seconds=int(hard-time.time()),name='mimickit-startup-diagnosis-'+str(int(time.time())),data_center_ids=centers)
            pod=cloud.state()['pod_id']
        state=cloud.state();state.update(hard_stop_unix=hard,until_stopped=False);cloud.save(state)
        (OUT/'runtime_control.json').write_text(json.dumps(dict(pod_id=pod,hard_stop_unix=hard,updated_unix=time.time(),until_stopped=False)))
        with (evidence/'guard.log').open('ab') as log:
            guard=subprocess.Popen([sys.executable,str(Path(__file__).with_name('local_guard.py'))],stdout=log,stderr=log,creationflags=0x08000000)
        start=time.time()
        (evidence/'attempt.json').write_text(json.dumps(dict(pod=pod,started_unix=start,setup_stop_unix=hard,guard_pid=guard.pid)))
        key=cloud.rp.load_api_key()
        while time.time()<hard-60:
            p=cloud.rp.request_json('GET','/pods/'+pod+'?includeMachine=true')
            g=cloud.graphql('query { pod(input: {podId: "'+pod+'"}) { id dockerId desiredStatus uptimeSeconds runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort } } } }')['pod']
            row=dict(elapsed=round(time.time()-start,1),time=time.time(),pod=pod,status=p.get('desiredStatus'),docker=g.get('dockerId'),uptime=g.get('uptimeSeconds'),public_ip=p.get('publicIp'),ports=p.get('portMappings'),machine=p.get('machineId'),runtime=g.get('runtime'))
            with (evidence/'timeline.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            try:
                r=requests.get('https://hapi.runpod.net/v1/pod/'+pod+'/logs',headers={'Authorization':'Bearer '+key},timeout=8)
                if r.ok:
                    logs=r.json();(evidence/(pod+'-platform-logs.json')).write_text(json.dumps(logs,indent=2))
                    row['system_log_count']=len(logs.get('system') or [])
            except requests.RequestException:row['log_read']='unavailable'
            print(json.dumps(row),flush=True)
            if p.get('publicIp') and p.get('portMappings'):
                state=cloud.state();state['connection']=cloud.rp.connection_from_pod(p);cloud.save(state)
                try:
                    result=cloud.ssh('python -c '+shlex.quote("import sys,subprocess;print(sys.version);print(subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True))"),timeout=20)
                    (evidence/'ssh-ready.txt').write_text(result)
                    (evidence/'ready.json').write_text(json.dumps(dict(pod=pod,elapsed=time.time()-start,hard_stop_unix=hard,guard_pid=guard.pid)))
                    ready=True;print('SSH AND GPU READY: '+result,flush=True);return
                except Exception as error:print('SSH not ready: '+type(error).__name__,flush=True)
            time.sleep(20)
        raise TimeoutError('Bounded startup attempt did not reach SSH')
    finally:
        if pod and not ready:
            stop_and_confirm(pod,cloud.rp.load_api_key(),evidence/'stopped.json','bounded startup diagnosis ended without ready SSH')

if __name__=='__main__':main()
