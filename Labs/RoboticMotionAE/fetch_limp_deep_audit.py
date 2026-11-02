"""Read-only capture of current slow-loco checkpoint and training telemetry."""
import json,zipfile
import deploy_slow_policy as d
from deploy_saved_sitting import remote
out=d.OUT/'limp-deep-audit-20261101';out.mkdir(exist_ok=True)
a=json.loads((d.OUT/'active_run.json').read_text());client=d.cloud.s3();bucket=d.cloud.rp.VOLUME_ID
r=json.loads(client.get_object(Bucket=bucket,Key='mimickit/pipeline_20261014/runs/'+a['run']+'/latest_verified.json')['Body'].read())
cp=out/'latest.zip';client.download_file(bucket,r['key'],str(cp));assert d.sha(cp)==r['sha256']
with zipfile.ZipFile(cp) as z:z.extract('model.pt',out)
(out/'checkpoint.json').write_text(json.dumps(r,indent=2))
for name in ['status.json','evaluation.json','log.txt','provenance.json']:
    text=remote('from pathlib import Path;print(Path('+repr('/workspace/mimickit_trial/runs/'+a['run']+'/'+name)+').read_text())')
    (out/name).write_text(text)
print(json.dumps(dict(run=a['run'],checkpoint=r,out=str(out))),flush=True)
