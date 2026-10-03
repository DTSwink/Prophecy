"""Freeze the existing Final Harness for this bounded, independent experiment."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HARNESS = ROOT.parent
FROZEN = ROOT / 'frozen'

def main():
    FROZEN.mkdir(parents=True, exist_ok=True)
    files = {
        'source.html': HARNESS / 'final_harness_standalone/index.html',
        'settings.json': HARNESS / 'final_harness_standalone/persistent_settings.json',
        'build_info.json': HARNESS / 'final_harness_standalone/build_info.json',
        'renderer.js': HARNESS / 'temp_upper_dataset_viewer/final_harness_webgl_renderer.js',
        'app-icon.ico': HARNESS / 'final_harness_standalone/app-icon.ico',
    }
    receipt = {'schema': 'attack_recovery_source_v1', 'branch': 'standard',
               'difficulty': 'easy', 'variantsPerAttack': 20, 'seed': 1234,
               'files': {}}
    for name, source in files.items():
        target = FROZEN / name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError(f'Frozen input changed; preserve existing data: {name}')
        if not target.exists():
            shutil.copy2(source, target)
        receipt['files'][name] = {'source': str(source), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (FROZEN / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
