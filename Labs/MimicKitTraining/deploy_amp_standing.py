"""Install the prepared standing experiment on the already-owned bounded pod."""
import hashlib,json,subprocess,tempfile,time,zipfile
from pathlib import Path
import cloud

def main():
    s=cloud.state();assert s['name']=='mimickit-standing-20261014'
    base=cloud.OUT/'timed-tail-source.zip';target=cloud.OUT/'amp-standing-source.zip'
    with zipfile.ZipFile(base) as src,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            if not name.startswith('pipeline/'):
                dst.writestr(name,src.read(name))
        for p in Path(__file__).parent.iterdir():
            if p.suffix in ('.py','.yaml','.sh','.patch') or p.name in ('amp_standing_target.pkl','amp_standing_target.json'):
                dst.write(p,'pipeline/'+p.name)
    cloud.ssh('mkdir -p /workspace/mimickit_trial')
    cloud.rp.scp(s['connection'],target,'/workspace/mimickit_trial/source.zip',timeout=60)
    cloud.ssh("cd /workspace/mimickit_trial && python -m zipfile -e source.zip .")
    hard=s['created_unix']+3600
    private=dict(pod_id=s['pod_id'],deadline_unix=hard-120,runpod_api_key=cloud.rp.load_api_key(),s3=cloud.credentials())
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'private.json';p.write_text(json.dumps(private))
        cloud.rp.scp(s['connection'],p,'/workspace/mimickit_trial/private.json',timeout=45)
    cloud.rp.scp(s['connection'],cloud.OUT/'runtime_control.json','/workspace/mimickit_trial/runtime_control.json',timeout=45)
    cloud.ssh('chmod 600 /workspace/mimickit_trial/private.json; cd /workspace/mimickit_trial; nohup python pipeline/guard.py > guard.log 2>&1 < /dev/null &')
    cloud.prepare_runtime_cache()
    cloud.ssh('cd /workspace/mimickit_trial; nohup bash pipeline/setup.sh > setup.log 2>&1 < /dev/null &')
    # The source backup is tiny; one verified copy, not repeated checkpoint downloads.
    c=cloud.s3();key='mimickit/pipeline_20261014/amp-standing/source.zip';body=target.read_bytes();sha=hashlib.sha256(body).hexdigest()
    c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body,Metadata={'sha256':sha})
    assert hashlib.sha256(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
    receipt=dict(pod=s['pod_id'],key=key,bytes=len(body),sha256=sha,verified=True)
    (cloud.OUT/'amp-standing-source-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))

if __name__=='__main__':main()
