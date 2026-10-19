"""Preserve the stopped get-up task; replace only its physics backend."""
import hashlib,json,zipfile
from pathlib import Path
import yaml
from uefn_package import runtime_files,verify_package
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment'

def main():
    checkpoint=OUT/'getup-reciprocal-stopped-latest.zip'
    expected=json.loads((OUT/'getup-reciprocal-stop.json').read_text())['checkpoint']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==expected['sha256']
    replacements={n:p.read_bytes() for n,p in runtime_files(ROOT).items()}
    for name in ('preflight_native_getup.py','telemetry.py'):
        replacements['pipeline/'+name]=(ROOT/'Labs/MimicKitTraining'/name).read_bytes()
    with zipfile.ZipFile(checkpoint) as cp:
        configs={n:yaml.safe_load(cp.read(n+'_config.yaml')) for n in ('env','engine','agent')}
    engine=configs['engine']
    engine.update(uefn_native_profile='native_runlr_soft_contact_20261018',
                  uefn_bounded_velocity_motors=False,uefn_jolt_contact_profile=False,
                  transfer_floor_aware_projection=False)
    replacements['prepared/engine_config.yaml']=yaml.safe_dump(engine,sort_keys=False).encode()
    destination=OUT/'native-getup-source.zip'
    with zipfile.ZipFile(OUT/'reciprocal-source.zip') as old,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as new:
        for n in ('env','agent'):
            assert yaml.safe_load(old.read('prepared/'+n+'_config.yaml'))==configs[n]
        for entry in old.infolist():
            new.writestr(entry,replacements.pop(entry.filename,old.read(entry.filename)))
        for name,data in replacements.items():new.writestr(name,data)
    with zipfile.ZipFile(destination) as z:
        verify_package(z,ROOT)
        with zipfile.ZipFile(OUT/'reciprocal-source.zip') as old:
            # No body, limits, motion, reward, reset or network drift on this resume.
            for name in old.namelist():
                if name.startswith(('motions/','assets/uefn/','prepared/')) and name!='prepared/engine_config.yaml':
                    assert z.read(name)==old.read(name),name
    receipt=dict(source=str(destination),sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                 bytes=destination.stat().st_size,resume_checkpoint=expected,physics_only=True)
    (OUT/'native-getup-source.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
