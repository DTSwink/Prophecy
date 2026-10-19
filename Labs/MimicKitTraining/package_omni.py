"""Small isolated source bundle. Runtime/kernel caches stay cloud-to-cloud."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from uefn_package import CONTACT_FILES,verify_package
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--equipment',action='store_true');args=parser.parse_args()
out=ROOT/('Saved/MimicKitEquipment' if args.equipment else 'Saved/MimicKitOmni');out.mkdir(exist_ok=True)
package=out/'package';package.mkdir(exist_ok=True)
asset=package/'assets/uefn';asset.mkdir(parents=True,exist_ok=True)
for name in ('humanoid_uefn.xml','limits.json','runtime.py','velocity_motors.py','body_velocity.py','physics.json'):
    shutil.copy2(ROOT/'Labs/MimicKitUEFN'/name,asset/name)
# The adapter imports its established sibling module by path.
dep=package/'assets/PhysicalRecoveryLab';dep.mkdir(exist_ok=True)
shutil.copy2(ROOT/'Labs/PhysicalRecoveryLab/phat_constraints.py',dep/'phat_constraints.py')
contact=package/'assets/MimicKitTransfer';contact.mkdir(exist_ok=True)
for name in CONTACT_FILES:shutil.copy2(ROOT/'Labs/MimicKitTransfer'/name,contact/name)
motions=package/'motions';motions.mkdir(exist_ok=True)
for name in ('M_Neutral_Run_Loop_LR.pkl','manifest.json'):
    shutil.copy2(ROOT/'Saved/MimicKitUEFN/omni'/name,motions/name)
if args.equipment:
    import yaml
    from prepare_equipment import prepare
    prepared=prepare(out/'prepared');remote=Path('/workspace/mimickit_trial')
    rows=json.loads((prepared/'manifest.json').read_text())
    for row in rows['motions']:
        dest=motions/(row['id']+'.pkl');shutil.copy2(row['file'],dest)
        row['file']=(remote/'motions'/dest.name).as_posix()
    target=package/'prepared';target.mkdir(exist_ok=True)
    (target/'manifest.json').write_text(json.dumps(rows,indent=2))
    (target/'motions.yaml').write_text(yaml.safe_dump(dict(motions=[dict(file=r['file'],weight=1.) for r in rows['motions']])))
    for n in ('env','engine','agent'):
        config=yaml.safe_load((prepared/(n+'_config.yaml')).read_text())
        if n=='env':config.update(char_file=(remote/'assets/uefn/humanoid_uefn.xml').as_posix(),
            motion_file=(remote/'prepared/motions.yaml').as_posix(),omni_manifest=(remote/'prepared/manifest.json').as_posix())
        if n=='engine':config['uefn_asset_directory']=(remote/'assets/uefn').as_posix()
        (target/(n+'_config.yaml')).write_text(yaml.safe_dump(config,sort_keys=False))
    shutil.copy2(prepared/'auto-phase-calibration.json',target/'auto-phase-calibration.json')
archive=out/'source.zip'
base=ROOT/'Saved/MimicKitTorque/absolute-balanced-source.zip'
if not base.exists():base=ROOT/'Saved/MimicKitTorque/source.zip'
with zipfile.ZipFile(base) as old,zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as new:
    for name in old.namelist():
        if name.startswith('MimicKit/') and '/.git/' not in name:new.writestr(name,old.read(name))
    for path in Path(__file__).parent.iterdir():
        if path.suffix in ('.py','.sh','.yaml'):
            new.write(path,'pipeline/'+path.name)
    for directory in (('assets','motions','prepared') if args.equipment else ('assets','motions')):
        for path in (package/directory).rglob('*'):
            if path.is_file():new.write(path,str(path.relative_to(package)).replace('\\','/'))
    for name in ('MimicKitTraining.md','MimicKitUEFNBodyMatching.md'):
        new.write(ROOT/'Docs'/name,'docs/'+name)
with zipfile.ZipFile(archive) as check:verify_package(check,ROOT)
receipt=dict(bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(out/'package-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
