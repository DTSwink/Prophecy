"""Export one compatible frozen Dodge choice without replacing project defaults.

The matching enum, runtime path and build staging list must also be added in C++.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

from ExportDefenseNetworks import PROJECT, digest
from InstallDefenseCheckpoints import main as export_defenses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--step', type=int, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    base = PROJECT / 'Content/locomotion/NN/defense'
    stage = args.stage.resolve()
    source = args.checkpoint.resolve()
    source_hash = digest(source)
    before = {p.name: digest(p) for p in base.iterdir() if p.is_file()}
    parry = json.loads((base / 'parry_checkpoint.json').read_text(encoding='utf-8'))
    previous_argv = sys.argv
    try:
        sys.argv = [__file__, str(source), parry['file'], '--stage', str(stage)]
        export_defenses()  # No --install: export and validate in staging only.
    finally:
        sys.argv = previous_argv
    for name in ('prophecy_dodge_walk.onnx', 'prophecy_dodge_run.onnx'):
        assert digest(stage / name) == before[name], ('lower model differs', name)
    for name in ('dodge_lower_settings.json', 'dodge_banks.json'):
        assert json.loads((stage / name).read_text(encoding='utf-8')) == json.loads((base / name).read_text(encoding='utf-8')), name
    meta = json.loads((stage / 'dodge_checkpoint.json').read_text(encoding='utf-8'))
    assert meta['step'] == args.step and meta['sha256'] == source_hash == digest(source)
    meta.pop('backup_folder', None)
    name = 'prophecy_dodge_upper.onnx'
    assert digest(stage / name) == meta['models'][name]['sha256']
    target = base / 'pickers' / f'Dodge{args.step}'
    target.mkdir(parents=True, exist_ok=True)
    if (target / name).exists():
        assert digest(target / name) == digest(stage / name), 'Cannot replace a frozen choice'
    else:
        shutil.copy2(stage / name, target / name)
    metadata = target / 'dodge_checkpoint.json'
    if metadata.exists():
        assert json.loads(metadata.read_text(encoding='utf-8')) == meta, 'Frozen provenance changed'
    metadata.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    validation = json.loads((stage / 'validation.json').read_text(encoding='utf-8'))
    oracle = [dict(row, folder=target.name) for row in validation['networks'] if row['model'] == name]
    (stage / 'picker-validation.json').write_text(json.dumps(dict(networks=oracle)), encoding='utf-8')
    assert all(digest(base / name) == value for name, value in before.items())
    receipt = dict(step=args.step, checkpoint_sha256=source_hash, model_sha256=digest(target / name),
                   defaults_unchanged=True, lower_models_settings_banks_identical=True,
                   parity=meta['models'][name], target=str(target))
    (stage / 'picker-report.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
