"""Checksum-verified local checkpoint fallback for this run's full cloud store."""
import json,sys,time,subprocess,hashlib,shlex
from pathlib import Path
import launch
cloud=launch.cloud;OUT=launch.OUT

def main():
    active=json.loads((OUT/'active_run.json').read_text());state=cloud.state()
    assert active['pod']==state['pod_id']
    name=active['run'];assert all(c.isalnum() or c=='_' for c in name)
    target=OUT/'local-checkpoints'/name;target.mkdir(parents=True,exist_ok=True)
    receipt=OUT/'local-backup-status.json';deadline=active['hard_stop_unix']
    while True:
        try:
            control=json.loads((OUT/'runtime_control.json').read_text())
            if control['pod_id']==active['pod']:deadline=float(control['hard_stop_unix'])
        except (OSError,ValueError,KeyError):pass
        if time.time()>=deadline+120:break
        try:
            code="""from pathlib import Path
import json,hashlib
d=Path('/workspace/mimickit_trial/runs')/NAME
p=max(d.glob('checkpoint_*.zip'),key=lambda p:p.name)
print(json.dumps({'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
""".replace('NAME',repr(name))
            remote=json.loads(cloud.ssh('python -c '+shlex.quote(code),timeout=15))
            p=target/remote['name'];assert p.name==remote['name']
            if not p.exists():
                temporary=p.with_suffix('.part')
                with temporary.open('wb') as f:
                    ssh=cloud.rp.ssh_base(state['connection']);ssh.insert(1,'-C')
                    result=subprocess.run(ssh+['cat','/workspace/mimickit_trial/runs/'+name+'/'+p.name],
                        stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
                assert result.returncode==0,'Checkpoint transfer failed'
                assert temporary.stat().st_size==remote['bytes'] and hashlib.sha256(temporary.read_bytes()).hexdigest()==remote['sha256']
                temporary.replace(p)
                record=dict(run=name,pod=active['pod'],path=str(p),verified=True,verified_unix=time.time(),**remote)
                temp=receipt.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2));temp.replace(receipt)
                # A separate exit watcher waits for this acknowledgement before
                # stopping a finished trainer; the hard deadline still wins.
                ack=json.dumps(dict(name=p.name,sha256=remote['sha256']))
                cloud.ssh('python -c '+shlex.quote("from pathlib import Path; Path('/workspace/mimickit_trial/runs/"+name+"/local_backup_ack.json').write_text("+repr(ack)+")"),timeout=15)
                print(json.dumps(record),flush=True)
            if '--once' in sys.argv:return
        except Exception as error:
            (OUT/'local-backup-error.json').write_text(json.dumps(dict(run=name,time=time.time(),error=str(error)[-400:])))
            if '--once' in sys.argv:raise
        time.sleep(10)

if __name__=='__main__':main()
