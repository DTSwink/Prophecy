param([switch]$ContactOnly)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out=Join-Path $root 'Saved/MimicKitTransfer/no-armature-3913'
$original=Join-Path $root 'Saved/MimicKitTransfer'
$jolt=Join-Path $root 'Intermediate/JoltMigration/Install/Development'
$cpp=Get-Content -Raw -LiteralPath (Join-Path $out 'ablation-saturation.cpp')
$name='rig-contact-filter'
if($ContactOnly){
    $cpp=Get-Content -Raw -LiteralPath (Join-Path $out 'ablation-fixture.cpp')
    $name='contact-fixture'
    if(!$cpp.Contains('getenv("TRANSFER_NO_SPECULATIVE")')){
        $cpp=$cpp.Replace('auto& bi=physics.GetBodyInterface();','auto& bi=physics.GetBodyInterface();if(std::getenv("TRANSFER_NO_SPECULATIVE")){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}')
    }
}
$filter=Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'rig_contact_filter.inl')
$definition=$filter.Substring(0,$filter.IndexOf('static int RigContactSelfTest()'))
$test=$filter.Substring($filter.IndexOf('static int RigContactSelfTest()'))
$cpp=$cpp.Replace('#include <vector>','#include <vector>'+"`n"+'#include <array>')
$cpp=$cpp.Replace('struct Fixture : ContactImpulseListener',$definition+"`n"+'struct Fixture : ContactImpulseListener')
$cpp=$cpp.Replace('Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;', 'RigContactFilter rigContactFilter;Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;')
$cpp=$cpp.Replace('settings.mCollisionGroup=CollisionGroup(filter,0,uint(bodies.size()));','settings.mCollisionGroup=CollisionGroup(filter,0,uint(bodies.size()));settings.mUserData=RigContactFilter::Tag;')
$cpp=$cpp.Replace('physics.SetContactImpulseListener(this);','physics.SetContactImpulseListener(this);if(std::getenv("TRANSFER_RIG_NO_SPECULATIVE"))physics.SetContactListener(&rigContactFilter);')
if($ContactOnly){$cpp=$cpp.Replace('if(std::getenv("TRANSFER_RIG_NO_SPECULATIVE"))physics.SetContactListener(&rigContactFilter);','if(!std::getenv("TRANSFER_RIG_ALLOW_SPECULATIVE"))physics.SetContactListener(&rigContactFilter);')}
$cpp=$cpp.Replace('~Fixture(){physics.SetContactImpulseListener(nullptr);','~Fixture(){physics.SetContactListener(nullptr);physics.SetContactImpulseListener(nullptr);')
$cpp=$cpp.Replace('int main(int argc,char** argv)',$test+"`n"+'int main(int argc,char** argv)')
$cpp=$cpp.Replace('    int result=0;',@'
    if(std::string(argv[1])=="--contact-test"){
        const int result=RigContactSelfTest();UnregisterTypes();delete Factory::sInstance;Factory::sInstance=nullptr;return result;}
    int result=0;
'@)
Set-Content -LiteralPath (Join-Path $out "$name.cpp") -Value $cpp
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" "/I$original" (Join-Path $out "$name.cpp") "/Fo$out/$name.obj" "/Fe$out/$name.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if($LASTEXITCODE -ne 0){throw 'Contact fixture build failed'}
$env:PATH=(Join-Path $jolt 'bin')+';'+$env:PATH
& (Join-Path $out "$name.exe") --contact-test | Tee-Object -FilePath (Join-Path $out "$name-selftest.json")
if($LASTEXITCODE -ne 0){throw 'Contact self-test failed'}
