"""Combine existing isolated point-contact DLL with measured rig settings.

Uses a local header overlay; never patches installed/source Jolt or Unreal.
The DLL was already built/tested by build_point_contact.py.
"""
from pathlib import Path
import hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
POINT=BASE/'point-contact'
OUT=POINT/'profile'


def main():
    OUT.mkdir(exist_ok=True)
    upstream=ROOT/'Intermediate/JoltMigration/Upstream'
    dll=POINT/'ProphecyJolt_5_6_Development.dll'
    receipt=json.loads((POINT/'build.json').read_text())
    assert hashlib.sha256(dll.read_bytes()).hexdigest()==receipt['isolated_dll_sha256']
    header=(upstream/'Jolt/Physics/Collision/ContactListener.h').read_text()
    anchor='class ContactSettings\n{\npublic:'
    assert header.count(anchor)==1
    header=header.replace(anchor,anchor+'\n\tbool mEnableSpeculativeContacts = true;\n')
    overlay=OUT/'include/Jolt/Physics/Collision/ContactListener.h'
    overlay.parent.mkdir(parents=True,exist_ok=True);overlay.write_text(header)
    source=(BASE/'solver-iterations/fixture.cpp').read_text()
    anchor='if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}'
    assert source.count(anchor)==1
    source=source.replace(anchor,'s.mEnableSpeculativeContacts=false;\n        if(m.mPenetrationDepth<0){++suppressed;}')
    (OUT/'fixture.cpp').write_text(source)
    shutil.copy2(dll,OUT/dll.name)
    script=f"""$ErrorActionPreference='Stop'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS '/I{OUT/'include'}' '/I{upstream}' '/I{ROOT/'Saved/MimicKitTransfer'}' '{OUT/'fixture.cpp'}' '/Fo{OUT/'fixture.obj'}' '/Fe{OUT/'fixture.exe'}' /link '{POINT/'ProphecyJolt_5_6_Development.lib'}'
if($LASTEXITCODE -ne 0){{throw 'Point-profile build failed'}}
"""
    (OUT/'build.ps1').write_text(script)
    subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
    (OUT/'build.json').write_text(json.dumps(dict(dll_sha256=receipt['isolated_dll_sha256'],
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),installed_source_unchanged=True),indent=2))


if __name__=='__main__':main()
