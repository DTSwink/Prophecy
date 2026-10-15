"""Independent timestep experiment, linking the unmodified installed Jolt DLL."""
from pathlib import Path
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913/timestep'


def main(output_name='timestep'):
    global OUT
    assert output_name in ('timestep','solver-iterations')
    OUT=OUT.parent/output_name
    OUT.mkdir(exist_ok=True)
    source=OUT.parent/'contact-observation.cpp'
    text=source.read_text(encoding='utf-8')
    begin=text.index('    void Step(const std::vector<float>& actions)')
    end=text.index('    void Print()',begin)
    part=text[begin:end]
    part=part.replace('std::fill(groundImpulse.begin(),groundImpulse.end(),0.0);',
        'const float dt=std::getenv("TRANSFER_DT")?std::stof(std::getenv("TRANSFER_DT")):1.f/240;\n'
        '        if (!(dt>0 && dt<=1.f/30)) throw std::runtime_error("Invalid diagnostic timestep");\n'
        '        std::fill(groundImpulse.begin(),groundImpulse.end(),0.0);')
    part=part.replace('9.81f/240','9.81f*dt').replace('GetLinearDamping()/240','GetLinearDamping()*dt')
    part=part.replace('physics.Update(1.f/240,','physics.Update(dt,').replace('*240.f/kJoints','/dt/kJoints')
    assert 'physics.Update(dt,' in part
    text=text[:begin]+part+text[end:]
    text=text.replace('#include <cmath>','#include <cmath>\n#include <chrono>')
    text=text.replace('struct Fixture : ContactImpulseListener',
        'static uint IterationOverride(const char* name) {const auto value=std::getenv(name); '
        'const int n=value?std::stoi(value):0; if(n<0||n>255)throw std::runtime_error("Invalid iteration count");return uint(n);}\n'
        'struct Fixture : ContactImpulseListener')
    text=text.replace('float maxMotorFraction=0;','double updateSeconds=0;float maxMotorDefect=0,maxAnchorError=0,maxMotorFraction=0;')
    anchor='settings.mCollisionGroup=CollisionGroup(filter,0,uint(bodies.size()));'
    text=text.replace(anchor,
        'settings.mNumVelocityStepsOverride=IterationOverride("TRANSFER_RIG_VELOCITY_STEPS");'
        'settings.mNumPositionStepsOverride=IterationOverride("TRANSFER_RIG_POSITION_STEPS");'+anchor)
    anchor='Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(settings.Create(*bodies[j.parent],*bodies[j.child]));'
    assert text.count(anchor)==1
    text=text.replace(anchor,
        'settings.mNumVelocityStepsOverride=IterationOverride("TRANSFER_RIG_VELOCITY_STEPS");'
        'settings.mNumPositionStepsOverride=IterationOverride("TRANSFER_RIG_POSITION_STEPS");'+anchor)
    text=text.replace('externalVerticalImpulse=0;groundNormalTilt=0;maxMotorFraction=0;',
        'externalVerticalImpulse=0;groundNormalTilt=0;maxMotorFraction=0;updateSeconds=0;maxMotorDefect=0;maxAnchorError=0;')
    anchor='if(physics.Update(dt,1,&allocator,&jobs)!=EPhysicsUpdateError::None)throw std::runtime_error("Native physics failed");'
    assert text.count(anchor)==1
    text=text.replace(anchor,
        'std::vector<Quat> motorFrames;for(const auto& j:kJoints)motorFrames.push_back(bodies[j.child]->GetRotation()*j.childRotation);'
        'auto started=std::chrono::steady_clock::now();'+anchor+
        'updateSeconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();'
        'for(size_t ji=0;ji<joints.size();++ji){const auto& j=kJoints[ji];'
        'const auto& parent=*bodies[j.parent];const auto& child=*bodies[j.child];'
        'const Vec3 relative=motorFrames[ji].Conjugated()*(child.GetAngularVelocity()-parent.GetAngularVelocity());'
        'Vec3 command=Vec3::sZero();for(int a=0;a<3;++a)if(j.actions[a]>=0)command.SetComponent(a,actions[j.actions[a]]);'
        'command=PolicyVelocityCS(j.childRotation,command);'
        'const Vec3 impulse=joints[ji]->GetTotalLambdaMotorRotation();'
        'for(int a=0;a<3;++a)if(j.actions[a]>=0){const float expected=std::clamp(j.gains.GetY()*(command[a]-relative[a]),-j.gains.GetZ(),j.gains.GetZ());'
        'maxMotorDefect=std::max(maxMotorDefect,std::abs(impulse[a]/dt-expected));}'
        'const auto anchor1=parent.GetPosition()+parent.GetRotation()*j.parentPosition;'
        'const auto anchor2=child.GetPosition()+child.GetRotation()*j.childPosition;'
        'maxAnchorError=std::max(maxAnchorError,float((anchor1-anchor2).Length()));}')
    text=text.replace('if(a.GetObjectLayer()==0 || b.GetObjectLayer()==0){',
        'if(!std::getenv("TRANSFER_NO_CONTACT_OBSERVATIONS") && (a.GetObjectLayer()==0 || b.GetObjectLayer()==0)){')
    text=text.replace('<<",\\\"max_motor_fraction\\\":"<<maxMotorFraction',
        '<<",\\\"physics_update_seconds\\\":"<<updateSeconds<<",\\\"motor_defect_nm\\\":"<<maxMotorDefect'
        '<<",\\\"anchor_error_m\\\":"<<maxAnchorError<<",\\\"max_motor_fraction\\\":"<<maxMotorFraction')
    anchor='        if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}'
    assert text.count(anchor)==1
    text=text.replace(anchor,
        '        if(std::getenv("TRANSFER_FRICTIONLESS_SELF") && a.GetUserData()==RigContactFilter::Tag '
        '&& b.GetUserData()==RigContactFilter::Tag '
        '&& a.GetCollisionGroup().GetGroupID()==b.GetCollisionGroup().GetGroupID()) '
        's.mCombinedFriction=0;\n'+anchor)
    (OUT/'fixture.cpp').write_text(text,encoding='utf-8')
    install=ROOT/'Intermediate/JoltMigration/Install/Development'
    script=f"""$ErrorActionPreference='Stop'
& 'C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/Tools/Launch-VsDevShell.ps1' -SkipAutomaticLocation -Arch amd64 -HostArch amd64
& cl.exe /nologo /std:c++20 /O2 /MD /EHsc /GR- /fp:precise /DJPH_SHARED_LIBRARY /DJPH_DOUBLE_PRECISION /DJPH_OBJECT_STREAM /DJPH_ENABLE_ASSERTS '/I{ROOT/'Intermediate/JoltMigration/Upstream'}' '/I{ROOT/'Saved/MimicKitTransfer'}' '{OUT/'fixture.cpp'}' '/Fo{OUT/'fixture.obj'}' '/Fe{OUT/'fixture.exe'}' /link '{install/'lib/ProphecyJolt_5_6_Development.lib'}'
if($LASTEXITCODE -ne 0){{throw 'Timestep fixture build failed'}}
"""
    (OUT/'build.ps1').write_text(script,encoding='utf-8')
    subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                dll_sha256=hashlib.sha256((install/'bin/ProphecyJolt_5_6_Development.dll').read_bytes()).hexdigest(),
                installed_physics_unchanged=True)
    (OUT/'build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    import sys
    main(sys.argv[1] if len(sys.argv)>1 else 'timestep')
