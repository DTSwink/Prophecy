"""Restore the protected pre-speed-termination checkpoint with a soft cost."""
import json
import deploy_locomotion_branch as d
import restart_locomotion_ae as r


def launch():
    plan=json.loads((d.OUT/'speed-loss-plan.json').read_text());cp=plan['checkpoint'];source=plan['source']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
for label,item in [('source',SOURCE),('resume',CHECKPOINT)]:
 data=c.get_object(Bucket='aj7d2jzwuq',Key=item['key'])['Body'].read()
 assert hashlib.sha256(data).hexdigest()==item['sha256']
 temp=r/(label+'.download');temp.write_bytes(data);temp.replace(r/(label+'.zip'))
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT
(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Pre-termination checkpoint98733 and soft-loss source verified')
'''.replace('SOURCE',repr(dict(key=source['key'],sha256=source['sha256']))).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code,timeout=90),flush=True)
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    base.update(source=source,checkpoint=cp,run_suffix='uefn_locomotion_speed_loss_1024')
    d.save('getup-success-prepared',base)
    d.save('stale-speed-termination-runs',dict(runs=['20261021_220225_uefn_locomotion_extremity_speed_1024',plan['old_run']],
        reason='User rejected hard extremity-speed termination; both tries stale',restore_checkpoint=cp['key']))
    d.launch()


if __name__=='__main__':launch()
