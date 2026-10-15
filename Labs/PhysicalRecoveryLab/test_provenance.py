"""Exercise stale export, edited model and changed source asset rejection."""
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from provenance import digest, verify_export

with TemporaryDirectory() as folder:
    root=Path(folder);out=root/'export';out.mkdir();asset=root/'rig.uasset';asset.write_bytes(b'asset')
    rig=out/'rig.json';rig.write_text(json.dumps({'source_files':{'rig.uasset':{'sha256':digest(asset)}}}))
    xml=out/'uefn.xml';xml.write_text('<mujoco/>')
    (out/'uefn.json').write_text(json.dumps({'rig_sha256':digest(rig),'xml_sha256':digest(xml)}))
    verify_export(out,root)
    for file in (rig,xml,asset):
        original=file.read_bytes();file.write_bytes(original+b'changed')
        try:verify_export(out,root)
        except ValueError:pass
        else:raise AssertionError(f'Stale file accepted: {file.name}')
        file.write_bytes(original)
    verify_export(out,root)
print('PASS: modified rig, model and source asset all rejected; matching export accepted')
