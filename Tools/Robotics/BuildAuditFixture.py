"""Compile a small isolated contact probe; never replace any installed DLL."""
from pathlib import Path
import subprocess, shutil
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/jolt-native-candidates'
OUT=ROOT/'Saved/Diagnostics/RobotLocomotion20261026/transfer-audit/point'
PROFILE=ROOT/'Saved/MimicKitTransfer/no-armature-3913/point-contact'
OUT.mkdir(parents=True,exist_ok=True)
text=(SOURCE/'fixture.cpp').read_text(encoding='utf-8')
old='if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}'
assert text.count(old)==1
text=text.replace(old,'if(!std::getenv("AUDIT_MANIFOLD"))s.mEnableSpeculativeContacts=false; if(m.mPenetrationDepth<0){if(std::getenv("AUDIT_MANIFOLD"))s.mIsSensor=true;++suppressed;}')
text=text.replace('physics.AddConstraint(limit);extra.push_back(limit);',
    'if(!std::getenv("AUDIT_GROUP_LIMITS"))physics.AddConstraint(limit);extra.push_back(limit);')
text=text.replace('groundImpulse.resize(bodies.size(),0.0);',
    'if(std::getenv("AUDIT_GROUP_LIMITS"))for(auto& limit:extra)physics.AddConstraint(limit); groundImpulse.resize(bodies.size(),0.0);')
(OUT/'fixture.cpp').write_text(text,encoding='utf-8')
shutil.copyfile(SOURCE/'jolt-rig-generated.h',OUT/'jolt-rig-generated.h')
def quote(s): return "'"+str(s).replace("'","''")+"'"
args=['/nologo','/std:c++20','/O2','/MD','/EHsc','/GR-','/fp:precise','/DJPH_SHARED_LIBRARY',
      '/DJPH_DOUBLE_PRECISION','/DJPH_OBJECT_STREAM','/DJPH_ENABLE_ASSERTS',
      '/I'+str(PROFILE/'profile/include'),'/I'+str(ROOT/'Intermediate/JoltMigration/Upstream'),
      str(OUT/'fixture.cpp'),'/Fo'+str(OUT/'fixture.obj'),'/Fe'+str(OUT/'fixture.exe'),
      '/link',str(PROFILE/'ProphecyJolt_5_6_Development.lib')]
script="$ErrorActionPreference='Stop'\n& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64\n"
script+='& cl.exe '+' '.join(map(quote,args))+"\nif($LASTEXITCODE -ne 0){throw 'Audit fixture failed'}\n"
(OUT/'build.ps1').write_text(script,encoding='utf-8')
subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
