$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'Saved/MimicKitTransfer/no-armature-3913'
$original = Join-Path $root 'Saved/MimicKitTransfer'
$jolt = Join-Path $root 'Intermediate/JoltMigration/Install/Development'
$cpp = Get-Content -Raw -LiteralPath (Join-Path $original 'fixture.cpp')
$cpp = $cpp.Replace('static int MotorSelfTest()', 'static int MotorSample(float gain,float cap,float target)')
$cpp = $cpp.Replace('JPH_PI/6','0.f')
$cpp = $cpp.Replace('StiffnessAndDamping,0,10','StiffnessAndDamping,0,gain').Replace('SetTorqueLimit(100)','SetTorqueLimit(cap)')
$cpp = $cpp.Replace('childFrame,Vec3(1,0,0)','childFrame,Vec3(target,0,0)')
$cpp = $cpp.Replace('const Vec3 expected=childRotation*Vec3((20.f/240)/(1+20.f/240),0,0);','const Vec3 expected=childRotation*Vec3(std::min(2*gain/240*target/(1+2*gain/240),2*cap/240),0,0);')
$cpp = $cpp.Replace('int main(int argc,char** argv)', @'
static int MotorSelfTest(){
    const float cases[][3]={{10,100,1},{100,400,6},{100,300,6},{100,200,6},{100,5,6},{10,1,6},{100,.1f,6}};
    int failures=0;for(const auto& c:cases)failures+=MotorSample(c[0],c[1],c[2]);return failures;
}
int main(int argc,char** argv)
'@)
Set-Content -LiteralPath (Join-Path $out 'motor-comparison.cpp') -Value $cpp
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" "/I$original" (Join-Path $out 'motor-comparison.cpp') "/Fo$out/motor-comparison.obj" "/Fe$out/motor-comparison.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if ($LASTEXITCODE -ne 0) { throw 'Motor comparison build failed' }
$env:PATH = (Join-Path $jolt 'bin') + ';' + $env:PATH
& (Join-Path $out 'motor-comparison.exe') --motor-test | Set-Content -LiteralPath (Join-Path $out 'native-motor-response.jsonl')
if ($LASTEXITCODE -ne 0) { throw 'Native motor response test failed' }
