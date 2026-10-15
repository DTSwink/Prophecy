"""Archive completed diagnostic evidence to existing storage, with readback verification."""
from pathlib import Path
import hashlib, json, zipfile
from backup import Backups
ROOT=Path('/workspace/mimickit_trial')
OUT=ROOT/'causal_regression'
assert (OUT/'queue_complete.json').exists()
assert (OUT/'analysis.json').exists()
source=ROOT/'runs'/json.loads((ROOT/'sweep.json').read_text())['trials'][1]['name']
archive=ROOT/'causal_regression_complete.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for f in sorted(OUT.rglob('*')):
        if f.is_file(): z.write(f,str(f.relative_to(ROOT)))
    for name in ['causal_regression.py','causal_regression_queue.py','analyze_causal_regression.py',
                 'audit_heading_singularity.py','analyze_first_update.py','preserve_causal_evidence.py','recovery_pose.py',
                 'neutral_pose.py','health.py','resume.py']:
        f=ROOT/'pipeline'/name;z.write(f,'source/'+name)
    for name in ['agent_config.yaml','env_config.yaml','engine_config.yaml','provenance.json',
                 'finished.json','backup_status.json']:
        z.write(source/name,'production/'+name)
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
prefix='mimickit/pipeline_20261014/causal_regression/'+sha[:12]
backups=Backups(OUT,json.loads((ROOT/'private.json').read_text())['s3'],prefix)
backups.submit(archive);backups.wait()
print((OUT/'backup_status.json').read_text(),flush=True)
