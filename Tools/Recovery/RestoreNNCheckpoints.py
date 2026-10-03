"""Verify backed-up checkpoint bytes; optionally recreate original relative paths.

  python Tools/Recovery/RestoreNNCheckpoints.py
  python Tools/Recovery/RestoreNNCheckpoints.py --restore --stepper-root C:/work/stepper

No PyTorch import or pickle execution. Existing differing files are never overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def contained(base, relative):
    result = (base / relative).resolve()
    if not result.is_relative_to(base.resolve()):
        raise ValueError('Path escapes restore root: ' + relative)
    if os.name == 'nt':
        # Training-run names can exceed MAX_PATH beneath a replacement checkout.
        name = str(result)
        result = Path('\\\\?\\UNC\\' + name[2:] if name.startswith('\\\\') else '\\\\?\\' + name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--stepper-root', type=Path)
    args = parser.parse_args()
    records = json.loads((ROOT / 'Tools/Recovery/NNCheckpoints20261003.json').read_text())['checkpoints']
    if args.restore and args.stepper_root is None:
        parser.error('--restore requires --stepper-root')
    copies = []
    for record in records:
        source = contained(ROOT, record['path'])
        if source.stat().st_size != record['bytes'] or digest(source) != record['sha256']:
            raise ValueError('Checkpoint verification failed: ' + str(source))
        if args.restore:
            for origin in record['sources']:
                base = args.project_root if origin['restore_root'] == 'project' else args.stepper_root
                dest = contained(base, origin['restore_path'])
                if dest.exists():
                    if digest(dest) != record['sha256']:
                        raise ValueError('Refusing to overwrite differing checkpoint: ' + str(dest))
                else:
                    copies.append((source, dest, record['sha256']))
    # Validate all inputs and destinations before copying anything.
    for source, dest, sha in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as src, dest.open('xb') as dst:
            shutil.copyfileobj(src, dst)
        if digest(dest) != sha:
            raise ValueError('Restored checkpoint verification failed: ' + str(dest))
    print(f'Verified {len(records)} checkpoints ({sum(r["bytes"] for r in records):,} bytes); restored {len(copies)} files.')


if __name__ == '__main__':
    main()
