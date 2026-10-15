"""Small isolated source bundle. Runtime/kernel caches stay cloud-to-cloud."""
import hashlib,json,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'Saved/MimicKitOmni';out.mkdir(exist_ok=True)
package=out/'package';package.mkdir(exist_ok=True)
asset=package/'assets/uefn';asset.mkdir(parents=True,exist_ok=True)
for name in ('humanoid_uefn.xml','limits.json','runtime.py','velocity_motors.py','body_velocity.py','physics.json'):
    shutil.copy2(ROOT/'Labs/MimicKitUEFN'/name,asset/name)
# The adapter imports its established sibling module by path.
dep=package/'assets/PhysicalRecoveryLab';dep.mkdir(exist_ok=True)
shutil.copy2(ROOT/'Labs/PhysicalRecoveryLab/phat_constraints.py',dep/'phat_constraints.py')
motions=package/'motions';motions.mkdir(exist_ok=True)
for name in ('M_Neutral_Run_Loop_LR.pkl','manifest.json'):
    shutil.copy2(ROOT/'Saved/MimicKitUEFN/omni'/name,motions/name)
archive=out/'source.zip'
base=ROOT/'Saved/MimicKitTorque/absolute-balanced-source.zip'
if not base.exists():base=ROOT/'Saved/MimicKitTorque/source.zip'
with zipfile.ZipFile(base) as old,zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as new:
    for name in old.namelist():
        if name.startswith('MimicKit/') and '/.git/' not in name:new.writestr(name,old.read(name))
    for path in Path(__file__).parent.iterdir():
        if path.suffix in ('.py','.sh','.yaml'):
            new.write(path,'pipeline/'+path.name)
    for directory in ('assets','motions'):
        for path in (package/directory).rglob('*'):
            if path.is_file():new.write(path,str(path.relative_to(package)).replace('\\','/'))
    for name in ('MimicKitTraining.md','MimicKitUEFNBodyMatching.md'):
        new.write(ROOT/'Docs'/name,'docs/'+name)
receipt=dict(bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(out/'package-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
