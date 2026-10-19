"""Finish the validated migration, preserving the existing paid stop time."""
import copy,hashlib,json,os,shlex,subprocess,sys,time,zipfile
from pathlib import Path
from datetime import datetime
import yaml
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitEquipment'
os.environ['MIMICKIT_STATE_DIR']=str(OUT)
import cloud
from uefn_package import verify_package,runtime_files


def main():
    report=json.loads(cloud.ssh('cat /workspace/mimickit_trial/adam-velocity-preflight.json'))
    assert report['passed'] and report['receipt']['iteration_offset']==38800
    (OUT/'adam-velocity-preflight.json').write_text(json.dumps(report,indent=2))
    source_path=OUT/'adam-velocity-source.zip'
    with zipfile.ZipFile(source_path) as z:
        entries={n:z.read(n) for n in z.namelist()}
    entries.update({n:p.read_bytes() for n,p in runtime_files(ROOT).items()})
    cfg=yaml.safe_load(entries['prepared/agent_config.yaml'])
    cfg['actor_optimizer']['learning_rate']=report['selected_actor_lr']
    entries['prepared/agent_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    entries['pipeline/preflight_adam_velocity.py']=Path(__file__).with_name('preflight_adam_velocity.py').read_bytes()
    with zipfile.ZipFile(source_path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    with zipfile.ZipFile(source_path) as z:verify_package(z,ROOT)
    data=source_path.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/equipment/adam-velocity/source_'+sha[:12]+'.zip'
    c=cloud.s3();c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
    assert hashlib.sha256(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
    source=dict(key=key,sha256=sha,source=str(source_path),bytes=len(data),allowed_config_changes=['prepared/agent_config.yaml'])
    for name in ['adam-velocity-source.json','adam-velocity-source-verified.json']:(OUT/name).write_text(json.dumps(source,indent=2))
    code="""import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read();assert hashlib.sha256(data).hexdigest()==SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
print('Final source verified and installed')
""".replace('KEY',repr(key)).replace('SHA',repr(sha))
    print(cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=60),flush=True)
    active=json.loads((OUT/'active_run.json').read_text());old=active['run'];pod=active['pod']
    hard=json.loads((OUT/'runtime_control.json').read_text())['hard_stop_unix']
    assert pod=='n5esp2rc3dvxc4' and hard==1792393912.192196
    now=datetime.now().astimezone();suffix='uefn_main_adam_velocity_512';name=now.strftime('%Y%m%d_%H%M%S')+'_'+suffix
    seconds=int(hard-time.time())
    args=['--name',name,'--seconds',str(seconds),'--worlds','512','--control-mode','vel','--absolute-walk',
          '--equipment-omni','/workspace/mimickit_trial/prepared','--evaluate','--output-interval','100','--replay-rows','20',
          '--resume','/workspace/mimickit_trial/resume.zip']
    subprocess.run([sys.executable,str(Path(__file__).with_name('start_training.py')),'--keep-deadline','--seconds',str(seconds),'--',*args],check=True)
    cloud.ssh('touch /workspace/mimickit_trial/adam_handoff_complete')
    manifest=json.loads((OUT/(old+'-dashboard.json')).read_text())
    manifest['runs']=[dict(name=now.strftime('%Y-%m-%d_%H-%M-%S')+'_'+suffix,objective='uefn_omni_absolute_walk',
        sources=[str(Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name))])]
    path=OUT/(name+'-dashboard.json');path.write_text(json.dumps(manifest,indent=2));observers={}
    for kind,argv in [('bridge',['--name',name]),('dashboard',[str(path)])]:
        with (OUT/(name+'-'+kind+'.log')).open('ab') as log:
            p=subprocess.Popen([sys.executable,str(Path(__file__).with_name(kind+'.py')),*argv],stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=0x08000000)
        observers[kind]=p.pid
    receipt=dict(run=name,previous_run=old,pod=pod,hard_stop_unix=hard,
        checkpoint=json.loads((OUT/'pre-collapse-38799.json').read_text()),source=source,observers=observers,
        actor_lr=cfg['actor_optimizer']['learning_rate'],critic_lr=cfg['critic_optimizer']['learning_rate'],kl_limit=cfg['actor_kl_limit'])
    (OUT/'adam-velocity-launch.json').write_text(json.dumps(receipt,indent=2));(OUT/'current-run.txt').write_text(name)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
