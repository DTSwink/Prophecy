"""Allocate/deploy only the explicitly approved one-hour <=$0.59 L4 trial."""
import argparse,hashlib,json,subprocess,tempfile,time,zipfile
from pathlib import Path
import cloud

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--hard-stop',type=float)
    parser.add_argument('--seconds',type=int,default=3600)
    parser.add_argument('--name',default=None)
    args=parser.parse_args()
    assert cloud.OUT.name in ('MimicKitOmni','MimicKitOmniRun','MimicKitNoArmature')
    seconds=args.seconds if args.hard_stop is None else int(args.hard_stop-time.time())
    assert 300<seconds<=3600
    # Reject stale cached source before spending money. Historical checkpoint
    # archives remain immutable; generate the current package before deploying.
    source=cloud.OUT/'source.zip'
    root=Path(__file__).resolve().parents[2]
    with zipfile.ZipFile(source) as package:
        for entry,local in [('assets/uefn/velocity_motors.py',root/'Labs/MimicKitUEFN/velocity_motors.py'),
                            ('pipeline/uefn_engine.py',Path(__file__).with_name('uefn_engine.py')),
                            ('pipeline/train.py',Path(__file__).with_name('train.py')),
                            ('pipeline/omni_config.py',Path(__file__).with_name('omni_config.py'))]:
            assert package.read(entry)==local.read_bytes(), f'Stale UEFN runtime: rebuild source.zip ({entry})'
    name=args.name or 'mimickit-uefn-runLR-20261015'+('-wrists' if args.hard_stop else '')
    cloud.allocate('NVIDIA L4',.59,'SECURE',seconds,name)
    state=cloud.state();hard=args.hard_stop or state['created_unix']+seconds
    (cloud.OUT/'runtime_control.json').write_text(json.dumps(dict(pod_id=state['pod_id'],hard_stop_unix=hard)))
    with (cloud.OUT/'local-guard.log').open('ab') as log:
        guard=subprocess.Popen([__import__('sys').executable,str(Path(__file__).with_name('local_guard.py'))],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    (cloud.OUT/'guards.json').write_text(json.dumps(dict(local_guard=guard.pid)))
    cloud.connect();state=cloud.state()
    cloud.ssh('mkdir -p /workspace/mimickit_trial')
    source=cloud.OUT/'source.zip'
    cloud.rp.scp(state['connection'],source,'/workspace/mimickit_trial/source.zip',timeout=60)
    cloud.ssh('cd /workspace/mimickit_trial && python -m zipfile -e source.zip .')
    private=dict(pod_id=state['pod_id'],deadline_unix=hard-120,runpod_api_key=cloud.rp.load_api_key(),s3=cloud.credentials())
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'private.json';path.write_text(json.dumps(private))
        cloud.rp.scp(state['connection'],path,'/workspace/mimickit_trial/private.json',timeout=45)
    cloud.rp.scp(state['connection'],cloud.OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=45)
    cloud.ssh('chmod 600 /workspace/mimickit_trial/private.json; cd /workspace/mimickit_trial; nohup python pipeline/guard.py > guard.log 2>&1 < /dev/null &')
    cloud.prepare_runtime_cache()
    cloud.ssh('cd /workspace/mimickit_trial; nohup bash pipeline/setup.sh > setup.log 2>&1 < /dev/null &')
    body=source.read_bytes();sha=hashlib.sha256(body).hexdigest();key='mimickit/pipeline_20261014/uefn-runLR/source_'+sha[:12]+'.zip'
    c=cloud.s3();c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body,Metadata={'sha256':sha})
    assert hashlib.sha256(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
    receipt=dict(pod=state['pod_id'],key=key,bytes=len(body),sha256=sha,verified=True,hard_stop_unix=hard)
    (cloud.OUT/'source-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))

if __name__=='__main__':main()
