"""Build an isolated crawl fixture against the installed project Jolt DLL."""
from pathlib import Path
import json, hashlib, subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103'
PACKAGE=ROOT/'Saved/MimicKitSlowLoco/package'

def main():
    OUT.mkdir(exist_ok=True)
    src=(ROOT/'Labs/MimicKitTransfer/generate.py').read_text()
    src=src[:src.index('cpp=(ROOT/')]
    src=src.replace("OUT=ROOT/'Saved/MimicKitTransfer'",'OUT=Path('+repr(str(OUT))+')')
    src=src.replace("ASSET=OUT/'source/assets/uefn'",'ASSET=Path('+repr(str(PACKAGE/'assets/uefn'))+')')
    scope={'__file__':str(ROOT/'Labs/MimicKitTransfer/generate.py')}
    exec(compile(src,'isolated_crawl_rig','exec'),scope)
    caps=[]
    for node in scope['nodes'][1:]:
        joints=node.findall('joint')
        v=max(abs(scope['vals'](joints[0].get('actuatorfrcrange'))))
        caps.append([v]*3)
    header=OUT/'jolt-rig-generated.h'
    header.write_text(header.read_text()+'\nstatic const float kTorqueCaps[][3]={'+','.join('{'+','.join(scope['num'](v) for v in row)+'}' for row in caps)+'};\n')
    cpp=(ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/fixture.cpp').read_text()
    # Both legs are physically passive, not zero-velocity servos.
    cpp=cpp.replace('std::getenv("TRANSFER_NO_MOTORS")?EMotorState::Off:EMotorState::PositionAndVelocity',
                    '(std::getenv("TRANSFER_NO_MOTORS") || j.child>=9)?EMotorState::Off:EMotorState::PositionAndVelocity',1)
    cpp=cpp.replace('groundImpulse.resize(bodies.size(),0.0);',
                    'rigContactFilter.enabled=!std::getenv("CRAWL_STOCK_CONTACT");groundImpulse.resize(bodies.size(),0.0);',1)
    # Avoid zero caps in the passive limbs' diagnostic division; active motors unchanged.
    (OUT/'fixture.cpp').write_text(cpp)
    install=ROOT/'Intermediate/JoltMigration/Install/Development'
    build=f"""$ErrorActionPreference='Stop'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS '/I{ROOT/'Intermediate/JoltMigration/Upstream'}' '/I{OUT}' '{OUT/'fixture.cpp'}' '/Fo{OUT/'fixture.obj'}' '/Fe{OUT/'fixture.exe'}' /link '{install/'lib/ProphecyJolt_5_6_Development.lib'}'
if($LASTEXITCODE -ne 0){{throw 'Isolated crawl fixture build failed'}}
"""
    (OUT/'build.ps1').write_text(build)
    subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
    paths=[install/'bin/ProphecyJolt_5_6_Development.dll',OUT/'fixture.cpp',header]
    report=dict(sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                body_names=scope['names'],torque_caps_nm=caps,disabled_motor_bodies=scope['names'][9:],
                physics_hz=240,policy_hz=30,production_unchanged=True)
    (OUT/'build.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
