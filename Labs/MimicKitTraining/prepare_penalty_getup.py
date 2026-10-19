"""Fresh experiment: freeze previous native setup, add only failure penalty."""
import copy,hashlib,json,zipfile
from pathlib import Path
import yaml
from uefn_package import runtime_files,verify_package
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'

def main():
    saved=json.loads((OUT/'getup-native-stop.json').read_text())
    assert saved['local_verified'] and saved['state']=='EXITED'
    assert hashlib.sha256(Path(saved['local']).read_bytes()).hexdigest()==saved['checkpoint']['sha256']
    replacements={name:path.read_bytes() for name,path in runtime_files(ROOT).items()}
    replacements['pipeline/preflight_penalty_getup.py']=Path(__file__).with_name('preflight_penalty_getup.py').read_bytes()
    destination=OUT/'penalty-getup-source.zip'
    with zipfile.ZipFile(OUT/'native-getup-source.zip') as old:
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'))
        cfg['idle_recovery']['termination_penalty_per_tick']=1.
        replacements['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        for entry,data in replacements.items():
            if entry.startswith('assets/'):
                assert old.read(entry)==data, 'Unexpected asset drift: '+entry
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as new:
            for entry in old.infolist():
                new.writestr(copy.copy(entry),replacements.pop(entry.filename,old.read(entry.filename)))
            for entry,data in replacements.items():new.writestr(entry,data)
        with zipfile.ZipFile(destination) as new:
            verify_package(new,ROOT)
            for entry in old.namelist():
                if entry.startswith(('assets/','motions/','prepared/')) and entry!='prepared/env_config.yaml':
                    assert new.read(entry)==old.read(entry),entry
            restored=yaml.safe_load(new.read('prepared/env_config.yaml'))
            assert restored['idle_recovery'].pop('termination_penalty_per_tick')==1.
            assert restored==yaml.safe_load(old.read('prepared/env_config.yaml'))
    receipt=dict(source=str(destination),sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        bytes=destination.stat().st_size,preserved_checkpoint=saved['checkpoint'],fresh_weights=True,
        change='FAIL reward minus remaining ticks; no other task/agent/engine/asset changes')
    (OUT/'penalty-getup-source.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
