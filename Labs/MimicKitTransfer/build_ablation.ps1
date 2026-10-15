param([switch]$Saturation)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out=Join-Path $root 'Saved/MimicKitTransfer/no-armature-3913'
$original=Join-Path $root 'Saved/MimicKitTransfer'
$jolt=Join-Path $root 'Intermediate/JoltMigration/Install/Development'
$cpp=Get-Content -Raw -LiteralPath $(if($Saturation){Join-Path $out 'saturation-candidate.cpp'}else{Join-Path $original 'fixture.cpp'})
$cpp=$cpp.Replace('return a==1||b==1;','return !std::getenv("TRANSFER_NO_CONTACT") && (a==1||b==1);')
$cpp=$cpp.Replace('physics.SetGravity(Vec3(0,0,-9.81f));','physics.SetGravity(std::getenv("TRANSFER_NO_GRAVITY")?Vec3::sZero():Vec3(0,0,-9.81f));')
$cpp=$cpp.Replace('else settings.SetLimitedAxis(angular,-j.limits[axis],j.limits[axis]);','else if(std::getenv("TRANSFER_NO_LIMITS"))settings.MakeFreeAxis(angular);else settings.SetLimitedAxis(angular,-j.limits[axis],j.limits[axis]);')
$cpp=$cpp.Replace('EMotorState::PositionAndVelocity);','std::getenv("TRANSFER_NO_MOTORS")?EMotorState::Off:EMotorState::PositionAndVelocity);')
$cpp=$cpp.Replace('for(int substep=0;substep<8;++substep)','for(int substep=0;substep<(std::getenv("TRANSFER_SUBSTEPS")?std::atoi(std::getenv("TRANSFER_SUBSTEPS")):8);++substep)')
$cpp=$cpp.Replace('bi.AddForceAndTorque(b.GetID(),','if(!std::getenv("TRANSFER_NO_DRAG"))bi.AddForceAndTorque(b.GetID(),')
$cpp=$cpp.Replace('auto& bi=physics.GetBodyInterface();',@'
auto& bi=physics.GetBodyInterface();
        if(std::getenv("TRANSFER_HIGH_ITERATIONS")) {auto ps=physics.GetPhysicsSettings();ps.mNumVelocitySteps=100;ps.mNumPositionSteps=20;physics.SetPhysicsSettings(ps);}
        if(std::getenv("TRANSFER_NO_SPECULATIVE")) {auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
'@)
$stem=if($Saturation){'ablation-saturation'}else{'ablation-fixture'}
Set-Content -LiteralPath (Join-Path $out "$stem.cpp") -Value $cpp
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" "/I$original" (Join-Path $out "$stem.cpp") "/Fo$out/$stem.obj" "/Fe$out/$stem.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if($LASTEXITCODE -ne 0){throw 'Ablation fixture build failed'}
