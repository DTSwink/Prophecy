"""Refresh only Parry using the established defense exporter and parity checks."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import sys
from ExportDefenseNetworks import PROJECT, digest
from InstallDefenseCheckpoints import main as stage_defenses


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint',type=Path)
    parser.add_argument('--stage',type=Path,required=True)
    args=parser.parse_args()
    stage=args.stage.resolve()
    stage.mkdir(parents=True,exist_ok=False)
    target=PROJECT/'Content/locomotion/NN/defense'
    before={p.name:digest(p) for p in target.iterdir() if p.is_file()}
    dodge=json.loads((target/'dodge_checkpoint.json').read_text())
    previous=json.loads((target/'parry_checkpoint.json').read_text())
    # Stage and validate through the existing exporter; do not install Dodge.
    original_argv=sys.argv
    try:
        sys.argv=[__file__,dodge['file'],str(args.checkpoint.resolve()),'--stage',str(stage)]
        with (stage/'export.log').open('w') as output,contextlib.redirect_stdout(output):
            stage_defenses()
    finally:
        sys.argv=original_argv
    for name in ('prophecy_dodge_upper.onnx','prophecy_dodge_walk.onnx','prophecy_dodge_run.onnx'):
        assert digest(stage/name)==before[name],('Installed Dodge differs from provenance',name)
    names=('prophecy_parry_upper.onnx','parry_checkpoint.json')
    backup=stage/'backup';backup.mkdir()
    for name in names:shutil.copy2(target/name,backup/name)
    # This existing native test reads a fixed Saved path. Keep its installed-model
    # expectations current while preserving its Dodge and forearm reference cases.
    fixture=PROJECT/'Saved/DefenseIntegration/CheckpointUpdates/Defense20261005/validation.json'
    old=json.loads(fixture.read_text());new=json.loads((stage/'validation.json').read_text())
    old['networks']=[r for r in old['networks'] if r['model']!=names[0]]+[r for r in new['networks'] if r['model']==names[0]]
    shutil.copy2(fixture,backup/'native-validation.json')
    try:
        for name in names:
            temp=target/(name+'.checkpoint-update')
            shutil.copy2(stage/name,temp);os.replace(temp,target/name)
        fixture.write_text(json.dumps(old))
        assert all(digest(target/name)==digest(stage/name) for name in names)
        assert all(digest(target/name)==value for name,value in before.items() if name not in names)
    except BaseException:
        for name in names:shutil.copy2(backup/name,target/name)
        shutil.copy2(backup/'native-validation.json',fixture)
        raise
    report={'previous_step':previous['step'],'installed':json.loads((target/names[1]).read_text()),
            'changed_files':list(names),'other_defense_files_unchanged':True,'native_fixture':str(fixture)}
    (stage/'install.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
