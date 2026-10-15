"""Reject stale exported models before allocating a physics simulation."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Robotics'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_export(out=OUT,root=ROOT):
    meta=json.loads((out/'uefn.json').read_text())
    if digest(out/'rig.json')!=meta['rig_sha256']:
        raise ValueError('Rig export changed; regenerate the model and its validation receipts')
    if digest(out/'uefn.xml')!=meta['xml_sha256']:
        raise ValueError('Converted model changed outside its recorded export')
    rig=json.loads((out/'rig.json').read_text())
    sources=rig.get('source_files',{})
    if not sources:raise ValueError('Export lacks source asset fingerprints')
    for relative,expected in sources.items():
        source=(root/relative).resolve()
        if not source.is_relative_to(root.resolve()):raise ValueError('Source asset outside project')
        if digest(source)!=expected['sha256']:
            raise ValueError(f'Source asset changed; export and validate it before training: {relative}')
    return {'rig_sha256':meta['rig_sha256'],'xml_sha256':meta['xml_sha256']}


if __name__=='__main__':print(json.dumps({'passed':True,**verify_export()},indent=2))
