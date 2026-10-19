"""Bounded reuse of the already-owned L4, never allocates or extends its window."""
import os,sys,json,time,subprocess,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_STATE_DIR']=str(ROOT/'Saved/MimicKitEquipment')
sys.path.insert(0,str(ROOT/'Labs/MimicKitTraining'))
import cloud
from billing_stop import stop_and_confirm
OUT=ROOT/'Saved/MimicKitTransfer/vanilla-calibration'
POD='v05mjf1bj17lwa'


def main():
    assert cloud.state()['pod_id']==POD
    hard=json.loads((cloud.OUT/'runtime_control.json').read_text())['hard_stop_unix']
    if len(sys.argv)>1 and sys.argv[1]=='--guard':
        deadline=min(hard,float(sys.argv[2]))
        while time.time()<deadline:time.sleep(min(5,deadline-time.time()))
        stop_and_confirm(POD,cloud.rp.load_api_key(),OUT/'gpu-deadline-stop.json','native calibration deadline')
        return
    assert time.time()+600<hard,'Insufficient existing window; do not extend'
    p=cloud.rp.request_json('GET','/pods/'+POD)
    assert p['desiredStatus']=='EXITED' and float(p['costPerHr'])<=.59
    deadline=min(hard,time.time()+600)
    guard=subprocess.Popen([sys.executable,__file__,'--guard',str(deadline)],creationflags=0x08000000)
    receipt=dict(pod=POD,started_unix=time.time(),deadline_unix=deadline,original_deadline=hard,ceiling=.59,guard_pid=guard.pid)
    (OUT/'gpu-session.json').write_text(json.dumps(receipt,indent=2))
    remote='/workspace/mimickit_trial/native-calibration-20261018'
    try:
        cloud.rp.request_json('POST','/pods/'+POD+'/start')
        cloud.connect();print('Owned L4 restarted; original deadline preserved.',flush=True)
        cloud.ssh('mkdir -p '+remote)
        cloud.rp.scp(cloud.state()['connection'],OUT/'gpu-packet.tar.gz',remote+'/packet.tar.gz',timeout=45)
        cloud.ssh('tar -xzf '+remote+'/packet.tar.gz -C '+remote)
        print('Native-only validation packet uploaded.',flush=True)
        try:
            output=cloud.ssh('timeout 480 /workspace/mimickit_trial/venv/bin/python -u '+remote+'/validate_vanilla_gpu.py '+remote,timeout=500)
            (OUT/'gpu-audit.log').write_text(output)
        except Exception as error:
            (OUT/'gpu-audit-error.txt').write_text(str(error));raise
        result=cloud.ssh('cat '+remote+'/gpu-results.json')
        (OUT/'gpu-results.json').write_text(result)
        receipt['result']=json.loads(result)
        print(json.dumps(receipt['result']),flush=True)
    except Exception as error:
        receipt['failure']=str(error);print('Audit did not complete: '+str(error),flush=True)
    finally:
        receipt['stop']=stop_and_confirm(POD,cloud.rp.load_api_key(),OUT/'gpu-stopped.json','native calibration finished or failed')
        receipt['ended_unix']=time.time();(OUT/'gpu-session.json').write_text(json.dumps(receipt,indent=2))
        if guard.poll() is None:guard.terminate();guard.wait(timeout=10)
        print('Owned L4 confirmed stopped.',flush=True)

if __name__=='__main__':main()
