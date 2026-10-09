"""Freeze the requested defense picker models without replacing project defaults."""
import argparse
import contextlib
import json
from pathlib import Path
import shutil
import sys
from ExportDefenseNetworks import PROJECT, digest
from InstallDefenseCheckpoints import main as export_defenses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parry-1178405', type=Path, required=True)
    parser.add_argument('--parry-1216457', type=Path, required=True)
    parser.add_argument('--dodge-151341', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve(); stage.mkdir(parents=True, exist_ok=False)
    base = PROJECT/'Content/locomotion/NN/defense'
    before = {p.name:digest(p) for p in base.iterdir() if p.is_file()}
    current = {k:json.loads((base/f'{k}_checkpoint.json').read_text()) for k in ('parry','dodge')}
    assert current['parry']['step'] == 1149700 and current['dodge']['step'] == 322925
    for kind in current:
        assert digest(Path(current[kind]['file'])) == current[kind]['sha256']
    for folder, dodge, parry in (
        ('first', Path(current['dodge']['file']), args.parry_1178405),
        ('second', args.dodge_151341, args.parry_1216457)):
        old = sys.argv
        try:
            sys.argv = [__file__,str(dodge.resolve()),str(parry.resolve()),'--stage',str(stage/folder)]
            with (stage/(folder+'.log')).open('w') as output, contextlib.redirect_stdout(output):
                export_defenses()
        finally:
            sys.argv = old
        # The requested Dodge changes learned upper weights only: prove the
        # frozen lower policies/settings/bank capacities remain identical.
        for name in ('prophecy_dodge_walk.onnx','prophecy_dodge_run.onnx'):
            assert digest(stage/folder/name) == before[name], ('lower policy differs', name)
        for name in ('dodge_lower_settings.json','dodge_banks.json'):
            assert json.loads((stage/folder/name).read_text()) == json.loads((base/name).read_text()), name
    target = base/'pickers'; target.mkdir(exist_ok=True)
    report = []
    for kind, step, source in (
        ('parry',1149700,base), ('parry',1178405,stage/'first'),
        ('parry',1216457,stage/'second'), ('dodge',322925,base), ('dodge',151341,stage/'second')):
        dest = target/f'{kind.capitalize()}{step}'; dest.mkdir(exist_ok=True)
        meta = json.loads((source/f'{kind}_checkpoint.json').read_text())
        assert meta['step'] == step
        model = f'prophecy_{kind}_upper.onnx'
        assert digest(source/model) == meta['models'][model]['sha256']
        for name in (model,):
            if (dest/name).exists():
                assert (dest/name).read_bytes() == (source/name).read_bytes(), ('frozen selection changed',dest/name)
            else:
                shutil.copy2(source/name,dest/name)
        meta.pop('backup_folder',None)  # An export staging directory is not part of the frozen identity.
        metadata=dest/f'{kind}_checkpoint.json'
        if metadata.exists():
            existing=json.loads(metadata.read_text());existing.pop('backup_folder',None)
            assert existing==meta, ('frozen checkpoint metadata changed',metadata)
        metadata.write_text(json.dumps(meta,indent=2)+'\n')
        report.append({'kind':kind,'step':step,'model_sha256':digest(dest/model),'checkpoint_sha256':meta['sha256']})
    # Keep native test input/output oracles separate from shipped runtime models.
    oracle = []
    for folder in ('first','second'):
        for row in json.loads((stage/folder/'validation.json').read_text())['networks']:
            kind = 'parry' if 'parry' in row['model'] else 'dodge'
            if row['model'] != f'prophecy_{kind}_upper.onnx': continue
            step = json.loads((stage/folder/f'{kind}_checkpoint.json').read_text())['step']
            oracle.append({**row,'folder':f'{kind.capitalize()}{step}'})
    # Installed parry1149700 oracle was preserved by the October6 installer.
    old = json.loads((PROJECT/'Saved/DefenseIntegration/CheckpointUpdates/Defense20261005/validation.json').read_text())
    oracle += [{**r,'folder':'Parry1149700'} for r in old['networks'] if r['model']=='prophecy_parry_upper.onnx']
    (stage/'validation.json').write_text(json.dumps({'networks':oracle}))
    assert all(digest(base/name)==value for name,value in before.items())
    (stage/'report.json').write_text(json.dumps({'defaults_unchanged':True,'dodge_lower_and_settings_identical':True,'models':report},indent=2)+'\n')
    print((stage/'report.json').read_text())


if __name__ == '__main__': main()
