"""Build a separate diagnostic DLL with a per-contact speculative-response flag.

Never installs/replaces the DLL used by Unreal. Temporarily applies a small patch
to the existing dependency source, builds its existing intermediate target, copies
the diagnostic binary, and restores the exact source bytes in finally.
"""
from pathlib import Path
import difflib, hashlib, json, shutil, subprocess

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Intermediate/JoltMigration/Upstream'
OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact'
OUT.mkdir(exist_ok=True)
HEADER=SOURCE/'Jolt/Physics/Collision/ContactListener.h'
CPP=SOURCE/'Jolt/Physics/Constraints/ContactConstraintManager.cpp'


def replace_once(text, old, new):
    assert text.count(old)==1, (old,text.count(old))
    return text.replace(old,new)


def patch(header,cpp):
    header=replace_once(header,'class ContactSettings\n{\npublic:',
        'class ContactSettings\n{\npublic:\n'
        '\t/// Opt out per pair; separated points keep their cache but exert no impulse.\n'
        '\tbool mEnableSpeculativeContacts = true;\n')
    anchor='\tmNonPenetrationConstraint.CalculateConstraintProperties(inInvM1, inInvI1, r1, inInvM2, inInvI2, r2, inWorldSpaceNormal, normal_velocity_bias);'
    cpp=replace_once(cpp,anchor,anchor+'\n\tif (!inSettings.mEnableSpeculativeContacts && penetration < 0.0f)\n\t\tmNonPenetrationConstraint.Deactivate();')
    anchor='\t// Calculate friction part\n\tif (inSettings.mCombinedFriction > 0.0f)'
    cpp=replace_once(cpp,anchor,
        '\tuint active_points = mNumContactPoints;\n'
        '\tif (!inSettings.mEnableSpeculativeContacts)\n'
        '\t{\n\t\tactive_points = 0;\n'
        '\t\tfor (uint i = 0; i < mNumContactPoints; ++i)\n'
        '\t\t\tif (mContactPoints[i].mNonPenetrationConstraint.IsActive()) ++active_points;\n\t}\n'
        '\t// Calculate friction from responding points only.\n'
        '\tif (inSettings.mCombinedFriction > 0.0f && active_points > 0)')
    cpp=replace_once(cpp,'\t\t\tfriction_point += inWorldSpaceContacts[i];\n\t\tfriction_point /= Real(mNumContactPoints);',
        '\t\t\tif (inSettings.mEnableSpeculativeContacts || mContactPoints[i].mNonPenetrationConstraint.IsActive())\n'
        '\t\t\t\tfriction_point += inWorldSpaceContacts[i];\n\t\tfriction_point /= Real(active_points);')
    cpp=replace_once(cpp,'mContactPoints[i].mDistanceToFrictionCenter = (delta - delta.Dot(inWorldSpaceNormal) * inWorldSpaceNormal).Length();',
        'mContactPoints[i].mDistanceToFrictionCenter = (inSettings.mEnableSpeculativeContacts || mContactPoints[i].mNonPenetrationConstraint.IsActive()) ? (delta - delta.Dot(inWorldSpaceNormal) * inWorldSpaceNormal).Length() : 0.0f;')
    cpp=replace_once(cpp,'\t\tif (mNumContactPoints > 1)\n\t\t\tmAngularFrictionConstraint.CalculateConstraintProperties',
        '\t\tif (active_points > 1)\n\t\t\tmAngularFrictionConstraint.CalculateConstraintProperties')
    # Cache and contact ordering are unchanged. Inactive points carry zero warm
    # impulse and get recalculated normally on the next added/persisted callback.
    anchor='\t\tWorldContactPoint<Type1, Type2> &wcp = constraint.mContactPoints[i];\n\t\tconst CachedContactPoint &ccp = cached_manifold.mContactPoints[i];'
    cpp=replace_once(cpp,anchor,
        '\t\tWorldContactPoint<Type1, Type2> &wcp = constraint.mContactPoints[i];\n'
        '\t\tif (!wcp.mNonPenetrationConstraint.IsActive()) continue;\n'
        '\t\tconst CachedContactPoint &ccp = cached_manifold.mContactPoints[i];')
    return header,cpp


def main():
    files=[HEADER,CPP]; originals=[p.read_bytes() for p in files]
    text=[b.decode('utf-8').replace('\r\n','\n') for b in originals]
    modified=patch(*text)
    patchtext=''.join(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),
        fromfile='a/'+p.relative_to(SOURCE).as_posix(),tofile='b/'+p.relative_to(SOURCE).as_posix())) for p,a,b in zip(files,text,modified))
    (ROOT/'Labs/MimicKitTransfer/rig_point_contact.patch').write_text(patchtext,encoding='utf-8')
    for p,b in zip(files,originals): (OUT/(p.name+'.original')).write_bytes(b)
    installed=ROOT/'Intermediate/JoltMigration/Install/Development/bin/ProphecyJolt_5_6_Development.dll'
    original_dll_hash=hashlib.sha256(installed.read_bytes()).hexdigest()
    try:
        for p,s in zip(files,modified): p.write_text(s,encoding='utf-8',newline='\n')
        cmake=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe')
        subprocess.run([str(cmake),'--build',str(ROOT/'Intermediate/JoltMigration/Build/Development'),'--config','Release','--target','Jolt','--parallel','4'],check=True)
        build=ROOT/'Intermediate/JoltMigration/Build/Development/JoltBuild/Release'
        for ext in ['dll','lib']: shutil.copy2(build/f'ProphecyJolt_5_6_Development.{ext}',OUT)
        fixture=(OUT.parent/'contact-observation.cpp').read_text(encoding='utf-8')
        fixture=replace_once(fixture,'if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}',
            's.mEnableSpeculativeContacts=false;\n        if(m.mPenetrationDepth<0){++suppressed;}')
        (OUT/'fixture.cpp').write_text(fixture,encoding='utf-8')
        shell=f'''$ErrorActionPreference='Stop'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS '/I{SOURCE}' '/I{ROOT / 'Saved/MimicKitTransfer'}' '{OUT/'fixture.cpp'}' '/Fo{OUT/'fixture.obj'}' '/Fe{OUT/'fixture.exe'}' /link '{OUT/'ProphecyJolt_5_6_Development.lib'}'
if($LASTEXITCODE -ne 0){{throw 'Fixture compilation failed'}}
& '{OUT/'fixture.exe'}' --contact-test
if($LASTEXITCODE -ne 0){{throw 'Contact regression failed'}}
'''
        (OUT/'build-fixture.ps1').write_text(shell,encoding='utf-8')
        subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build-fixture.ps1')],check=True)
    finally:
        for p,b in zip(files,originals): p.write_bytes(b)
        assert hashlib.sha256(installed.read_bytes()).hexdigest()==original_dll_hash
        assert all(p.read_bytes()==b for p,b in zip(files,originals))
    receipt=dict(installed_dll_unchanged_sha256=original_dll_hash,
        isolated_dll_sha256=hashlib.sha256((OUT/'ProphecyJolt_5_6_Development.dll').read_bytes()).hexdigest(),
        dependency_source_restored=True,patch=str(ROOT/'Labs/MimicKitTransfer/rig_point_contact.patch'))
    (OUT/'build.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__': main()
