"""Preserve the current wrist preparation, observer UI and verification receipts."""
import hashlib,json,zipfile
from pathlib import Path
import cloud

root=cloud.ROOT;out=cloud.OUT;archive=out/'wrist-review.zip'
files=[root/'Docs/MimicKitTraining.md',root/'Docs/MimicKitUEFNBodyMatching.md',
       root/'Tools/Locomotion/PrepareMimicKitOmni.py',root/'Tools/Locomotion/RetargetFootLift.py',
       root/'Content/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.uasset',
       root/'Saved/MimicKitUEFN/source-rig.json']
files+=list((root/'Labs/MimicKitUEFN').glob('*.py'))
files+=list((root/'Saved/MimicKitUEFN/omni').glob('*.pkl'))
files+=[root/'Labs/MimicKitTraining'/n for n in ('observe_omni.py','verify_omni_replay.py','backup_omni_review.py')]
files+=[out/n for n in ('omni-calibration.json','preflight-report.json','replay-numerical-verification.json','verified-checkpoint-receipt.json','observers.json')]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for f in files:z.write(f,str(f.relative_to(root)).replace('\\','/'))
    z.write(Path('C:/Users/singerie/Documents/Cursor/stepper/training/rollout_debug_viewer/viewer.html'),'replayer/viewer.html')
body=archive.read_bytes();sha=hashlib.sha256(body).hexdigest()
key='mimickit/pipeline_20261014/uefn-runLR/review_'+sha[:12]+'.zip'
c=cloud.s3();c.put_object(Bucket=cloud.rp.VOLUME_ID,Key=key,Body=body,Metadata={'sha256':sha})
assert hashlib.sha256(c.get_object(Bucket=cloud.rp.VOLUME_ID,Key=key)['Body'].read()).hexdigest()==sha
r=dict(key=key,bytes=len(body),sha256=sha,verified=True)
(out/'review-backup-receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
