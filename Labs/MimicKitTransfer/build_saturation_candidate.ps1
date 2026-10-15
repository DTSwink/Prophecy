$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'Saved/MimicKitTransfer/no-armature-3913'
$original = Join-Path $root 'Saved/MimicKitTransfer'
$jolt = Join-Path $root 'Intermediate/JoltMigration/Install/Development'
$cpp = Get-Content -Raw -LiteralPath (Join-Path $out 'motor-comparison.cpp')
$needle = 'joint.SetTargetAngularVelocityCS(PolicyVelocityCS(j.childRotation,local));'
if (-not $cpp.Contains($needle)) { throw 'Unexpected fixture source' }
$cpp = $cpp.Replace($needle, @'
const Vec3 target=PolicyVelocityCS(j.childRotation,local);
                joint.SetTargetAngularVelocityCS(target);
                const Quat frame=bodies[j.child]->GetRotation()*j.childRotation;
                const Vec3 velocity=frame.Conjugated()*(bodies[j.child]->GetAngularVelocity()-bodies[j.parent]->GetAngularVelocity());
                Vec3 explicitTorque=Vec3::sZero();
                for(int axis=0;axis<3;++axis){
                    const float request=j.gains.GetY()*(target[axis]-velocity[axis]);
                    const bool saturated=std::abs(request)>=j.gains.GetZ();
                    joint.SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(axis+3),saturated?EMotorState::Off:EMotorState::PositionAndVelocity);
                    if(saturated){explicitTorque.SetComponent(axis,Clamp(request,-j.gains.GetZ(),j.gains.GetZ()));maxMotorFraction=1;}
                }
                const Vec3 worldTorque=frame*explicitTorque;
                physics.GetBodyInterface().AddTorque(bodies[j.child]->GetID(),worldTorque);
                physics.GetBodyInterface().AddTorque(bodies[j.parent]->GetID(),-worldTorque);
'@)
$cpp = $cpp.Replace('physics.AddConstraint(joint);physics.Update(1.f/240,1,&alloc,&jobs);', @'
    if(std::abs(gain*target)>=cap){
        joint->SetMotorState(SixDOFConstraintSettings::EAxis::RotationX,EMotorState::Off);
        const Vec3 torque=childRotation*Vec3(Clamp(gain*target,-cap,cap),0,0);
        bi.AddTorque(bodies[1]->GetID(),torque);bi.AddTorque(bodies[0]->GetID(),-torque);
    }
    physics.AddConstraint(joint);physics.Update(1.f/240,1,&alloc,&jobs);
'@)
$cpp = $cpp.Replace('std::min(2*gain/240*target/(1+2*gain/240),2*cap/240)', '(std::abs(gain*target)>=cap?2*cap/240:2*gain/240*target/(1+2*gain/240))')
Set-Content -LiteralPath (Join-Path $out 'saturation-candidate.cpp') -Value $cpp
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS "/I$jolt/include" "/I$original" (Join-Path $out 'saturation-candidate.cpp') "/Fo$out/saturation-candidate.obj" "/Fe$out/saturation-candidate.exe" /link (Join-Path $jolt 'lib/ProphecyJolt_5_6_Development.lib')
if ($LASTEXITCODE -ne 0) { throw 'Candidate build failed' }
$env:PATH = (Join-Path $jolt 'bin') + ';' + $env:PATH
& (Join-Path $out 'saturation-candidate.exe') --motor-test | Set-Content -LiteralPath (Join-Path $out 'candidate-motor-response.jsonl')
if ($LASTEXITCODE -ne 0) { throw 'Candidate motor response test failed' }
