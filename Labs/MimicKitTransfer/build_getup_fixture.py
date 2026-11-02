"""Current recovery rig/caps in a separate fixture, using the installed Jolt DLL."""
import json, hashlib, subprocess, argparse, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--point-profile',action='store_true');args=parser.parse_args()
    # Reuse the established PHAT-to-fixture conversion, without its old output paths.
    generate=(ROOT/'Labs/MimicKitTransfer/generate.py').read_text()
    generate=generate[:generate.index("cpp=(ROOT/")]
    generate=generate.replace("OUT=ROOT/'Saved/MimicKitTransfer'", "OUT=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'")
    scope={'__file__':str(ROOT/'Labs/MimicKitTransfer/generate.py')};exec(compile(generate,'frozen_rig_generator','exec'),scope)
    import yaml
    caps=yaml.safe_load((OUT/'native/engine_config.yaml').read_text())['uefn_motor_torque_caps_nm']
    values=[]
    for node in scope['nodes'][1:]:
        n=node.get('name');default=max(abs(scope['vals'](node.find('joint').get('actuatorfrcrange'))))
        ball=len(node.findall('joint'))==3
        values.append([caps.get(f'{n}:{a}' if ball else n,default) for a in range(3)])
    header=OUT/'jolt-rig-generated.h'
    header.write_text(header.read_text()+'\nstatic const float kTorqueCaps[][3]={'+','.join('{'+','.join(scope['num'](v) for v in row)+'}' for row in values)+'};\n')
    cpp=(ROOT/'Saved/MimicKitTransfer/no-armature-3913/contact-observation.cpp').read_text()
    cpp=cpp.replace('SetTorqueLimit(j.gains.GetZ())','SetTorqueLimit(kTorqueCaps[&j-kJoints][axis])')
    cpp=cpp.replace('/kJoints[ji].gains.GetZ()','/kTorqueCaps[ji][axis]')
    cpp=cpp.replace('a=Clamp(a,-2.f*JPH_PI,2.f*JPH_PI);','/* Caller applies exact saved per-axis action bounds. */')
    cpp=cpp.replace('(a==1||b==1);', '(a==1||b==1) && !(std::getenv("TRANSFER_NO_SELF") && a==1 && b==1);')
    overrides='settings.mNumVelocityStepsOverride=std::getenv("TRANSFER_RIG_VELOCITY_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_VELOCITY_STEPS")):0; settings.mNumPositionStepsOverride=std::getenv("TRANSFER_RIG_POSITION_STEPS")?std::atoi(std::getenv("TRANSFER_RIG_POSITION_STEPS")):0;'
    cpp=cpp.replace('settings.mCollisionGroup=',overrides+'settings.mCollisionGroup=')
    cpp=cpp.replace('Ref<SixDOFConstraint> joint=static_cast',overrides+'Ref<SixDOFConstraint> joint=static_cast',1)
    cpp=cpp.replace('if(!enabled || (a.GetUserData()!=Tag',
        'if(std::getenv("TRANSFER_FRICTIONLESS_SELF") && a.GetObjectLayer()==1 && b.GetObjectLayer()==1)s.mCombinedFriction=0;\n        if(!enabled || (a.GetUserData()!=Tag')
    install=ROOT/'Intermediate/JoltMigration/Install/Development'
    includes='';library=install/'lib/ProphecyJolt_5_6_Development.lib'
    if args.point_profile:
        base=ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact'
        cpp=cpp.replace('if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}', 's.mEnableSpeculativeContacts=false; if(m.mPenetrationDepth<0){++suppressed;}')
        old=OUT;OUT=OUT/'point-profile';OUT.mkdir(exist_ok=True)
        shutil.copy2(header,OUT/header.name)
        shutil.copy2(base/'ProphecyJolt_5_6_Development.dll',OUT/'ProphecyJolt_5_6_Development.dll')
        includes=f"'/I{base/'profile/include'}'";library=base/'ProphecyJolt_5_6_Development.lib'
    (OUT/'fixture.cpp').write_text(cpp)
    build=f"""$ErrorActionPreference='Stop'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS {includes} '/I{ROOT/'Intermediate/JoltMigration/Upstream'}' '/I{OUT}' '{OUT/'fixture.cpp'}' '/Fo{OUT/'fixture.obj'}' '/Fe{OUT/'fixture.exe'}' /link '{library}'
if($LASTEXITCODE -ne 0){{throw 'Recovery fixture build failed'}}
"""
    (OUT/'build.ps1').write_text(build)
    subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
    used_dll=(OUT/'ProphecyJolt_5_6_Development.dll') if args.point_profile else (install/'bin/ProphecyJolt_5_6_Development.dll')
    report={'dll_sha256':hashlib.sha256(used_dll.read_bytes()).hexdigest(),'dll_path':str(used_dll),
            'rig_sha256':scope['meta']['source_sha256'],'physics_hz':240,'policy_hz':30,'torque_caps':values,
            'project_dll_changed':False,'old_runlr_fixture_changed':False}
    (OUT/'fixture-build.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
