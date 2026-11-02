"""Isolated Jolt candidates for the frozen native pelvismax policy. No installation."""
from pathlib import Path
import subprocess,shutil
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'
OUT=BASE/'jolt-native-candidates';OUT.mkdir(exist_ok=True)
s=(BASE/'fixture.cpp').read_text()
s=s.replace('class Layers final', (ROOT/'Labs/MimicKitTransfer/recovery_spherical_limit.inl').read_text()+'\nclass Layers final',1)
s=s.replace('std::vector<Body*> bodies;', 'std::vector<Ref<TwoBodyConstraint>> extra;std::vector<Body*> bodies;')
s=s.replace('else if(std::getenv("TRANSFER_NO_LIMITS"))', 'else if(std::getenv("TRANSFER_NO_LIMITS")||(std::getenv("CAND_SPHERICAL")&&j.actions[0]>=0&&j.actions[1]>=0&&j.actions[2]>=0))')
s=s.replace('physics.AddConstraint(joint);joints.push_back(joint);','''physics.AddConstraint(joint);joints.push_back(joint);
            if(std::getenv("CAND_SPHERICAL")&&j.actions[0]>=0&&j.actions[1]>=0&&j.actions[2]>=0){
                Ref<TwoBodyConstraint> limit=new RecoverySphericalLimit(*bodies[j.parent],*bodies[j.child],settings,j);
                physics.AddConstraint(limit);extra.push_back(limit);
            }''')
s=s.replace('~Fixture(){','~Fixture(){for(auto& c:extra)physics.RemoveConstraint(c);')
s=s.replace('settings.mAllowSleeping=false;', 'settings.mAllowSleeping=false;settings.mApplyGyroscopicForce=std::getenv("CAND_GYRO")!=nullptr;if(std::getenv("CAND_NO_DAMPING")){settings.mLinearDamping=0;settings.mAngularDamping=0;}')
s=s.replace('0,j.gains.GetY())','0,j.gains.GetY()*(std::getenv("CAND_GAIN")?std::atof(std::getenv("CAND_GAIN")):1.f))')
s=s.replace('std::getenv("TRANSFER_NO_MOTORS")?', '(std::getenv("TRANSFER_NO_MOTORS")||std::getenv("CAND_EXPLICIT"))?')
anchor='joint.SetTargetAngularVelocityCS(PolicyVelocityCS(j.childRotation,local));'
s=s.replace(anchor,'''
                if(std::getenv("CAND_NATIVE_MOTOR")){
                    auto& parent=*bodies[j.parent];auto& child=*bodies[j.child];
                    Vec3 rel=child.GetRotation().Conjugated()*(child.GetAngularVelocity()-parent.GetAngularVelocity());
                    for(int a=0;a<3;++a)if(j.actions[a]>=0){
                        local.SetComponent(a,rel[a]+Clamp(j.gains.GetY()*(local[a]-rel[a]),-kTorqueCaps[i][a],kTorqueCaps[i][a])/j.gains.GetY());
                        joint.GetMotorSettings(static_cast<SixDOFConstraintSettings::EAxis>(a+3)).SetTorqueLimit(1.e10f);
                    }
                }
'''+anchor+'''
                if(std::getenv("CAND_EXPLICIT")){
                    auto& parent=*bodies[j.parent];auto& child=*bodies[j.child];
                    Vec3 rel=child.GetRotation().Conjugated()*(child.GetAngularVelocity()-parent.GetAngularVelocity());
                    Vec3 torque=Vec3::sZero();
                    for(int a=0;a<3;++a)if(j.actions[a]>=0)torque.SetComponent(a,Clamp(j.gains.GetY()*(local[a]-rel[a]),-kTorqueCaps[i][a],kTorqueCaps[i][a]));
                    Vec3 world=child.GetRotation()*torque;
                    physics.GetBodyInterface().AddTorque(child.GetID(),world);
                    physics.GetBodyInterface().AddTorque(parent.GetID(),-world);
                }
''')
anchor='if(physics.Update(1.f/240,1,&allocator,&jobs)'
s=s.replace(anchor,'''{auto ps=physics.GetPhysicsSettings();
            if(std::getenv("CAND_BAUMGARTE"))ps.mBaumgarte=std::atof(std::getenv("CAND_BAUMGARTE"));
            if(std::getenv("CAND_SLOP"))ps.mPenetrationSlop=std::atof(std::getenv("CAND_SLOP"));
            if(std::getenv("CAND_NO_REDUCTION"))ps.mUseManifoldReduction=false;
            physics.SetPhysicsSettings(ps);}
            '''+anchor)
(OUT/'fixture.cpp').write_text(s);shutil.copy2(BASE/'jolt-rig-generated.h',OUT/'jolt-rig-generated.h')
build=(BASE/'build.ps1').read_text().replace(str(BASE/'fixture'),str(OUT/'fixture'))
# Includes keep the unchanged generated rig; the executable loads the installed DLL.
(OUT/'build.ps1').write_text(build)
subprocess.run(['pwsh','-NoProfile','-File',str(OUT/'build.ps1')],check=True)
