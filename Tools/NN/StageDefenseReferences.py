"""Copy the exact supplied inference source snapshots into Saved for port/parity work."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(r'C:\Users\singerie\Documents\Cursor\stepper\training\slashes2\saved_defense_checkpoints')
DEST = ROOT / 'Saved/DefenseIntegration/ReferenceSources'
REFERENCES = {
    'dodge': ('dodge_unreal_reference/reference', 'dodge_step_198044.pt',
              '2a433552043490f7172e2df2aa5d007b4afbbf3f4f51a8e77d94cb120b5c8c4b'),
    'parry': ('parry_unreal_reference_770015', 'parry_step_770015.pt',
              'f4ee679611e1013d72b5587e95c87798f92be58b0dfe2826ade6944b31107e3e'),
}

def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def main():
    report = {}
    for name, (relative, checkpoint, expected) in REFERENCES.items():
        actual = sha(SOURCE / checkpoint)
        if actual != expected:
            raise RuntimeError(f'{name}: supplied checkpoint does not match its handoff: {actual}')
        folder = SOURCE / relative
        destination = (DEST / name).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(folder / 'reference_source.zip') as archive:
            for member in archive.infolist():
                target = (destination / member.filename).resolve()
                if not target.is_relative_to(destination):
                    raise RuntimeError(f'Unsafe archive path: {member.filename}')
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
        report[name] = {'checkpoint': str(SOURCE / checkpoint), 'checkpoint_sha256': actual,
            'reference': str(folder), 'source_snapshot': str(destination),
            'archive_sha256': sha(folder / 'reference_source.zip')}
    (DEST / 'staging.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
