// Independent physical check: rotated child and rotated child constraint frame.
// Two unit inertias, no gravity/contact/limits/armature, velocity gain10.
static int MotorSelfTest()
{
    Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
    physics.Init(16,0,32,32,layers,broad,pair);physics.SetGravity(Vec3::sZero());
    TempAllocatorImpl alloc(8*1024*1024);JobSystemSingleThreaded jobs(128);
    auto& bi=physics.GetBodyInterface();Body* bodies[2];
    const Quat childRotation=Quat::sRotation(Vec3::sAxisZ(),.5f*JPH_PI);
    const Quat childFrame=Quat::sRotation(Vec3::sAxisZ(),JPH_PI/6);
    for(int i=0;i<2;++i){
        BodyCreationSettings s(new SphereShape(.1f),RVec3(0,0,10+10*i),i?childRotation:Quat::sIdentity(),EMotionType::Dynamic,1);
        s.mLinearDamping=0;s.mAngularDamping=0;s.mAllowSleeping=false;
        s.mOverrideMassProperties=EOverrideMassProperties::MassAndInertiaProvided;
        s.mMassPropertiesOverride.mMass=1;s.mMassPropertiesOverride.mInertia=Mat44::sIdentity();
        bodies[i]=bi.CreateBody(s);bi.AddBody(bodies[i]->GetID(),EActivation::Activate);
    }
    SixDOFConstraintSettings s;s.mSpace=EConstraintSpace::LocalToBodyCOM;
    s.mAxisX2=childFrame*Vec3::sAxisX();s.mAxisY2=childFrame*Vec3::sAxisY();
    for(int i=0;i<6;++i)s.MakeFreeAxis(static_cast<SixDOFConstraintSettings::EAxis>(i));
    for(int i=3;i<6;++i){s.mMotorSettings[i]=MotorSettings(ESpringMode::StiffnessAndDamping,0,10);s.mMotorSettings[i].SetTorqueLimit(100);}
    Ref<SixDOFConstraint> joint=static_cast<SixDOFConstraint*>(s.Create(*bodies[0],*bodies[1]));
    for(int i=3;i<6;++i)joint->SetMotorState(static_cast<SixDOFConstraintSettings::EAxis>(i),EMotorState::PositionAndVelocity);
    joint->SetTargetAngularVelocityCS(PolicyVelocityCS(childFrame,Vec3(1,0,0)));
    physics.AddConstraint(joint);physics.Update(1.f/240,1,&alloc,&jobs);
    const Vec3 measured=bodies[1]->GetAngularVelocity()-bodies[0]->GetAngularVelocity();
    const Vec3 expected=childRotation*Vec3((20.f/240)/(1+20.f/240),0,0);
    const float error=(measured-expected).Length();physics.RemoveConstraint(joint);
    std::cout<<"{\"motor_test_error_rad_s\":"<<error<<",\"measured\":["<<measured.GetX()<<','<<measured.GetY()<<','<<measured.GetZ()<<"]}"<<std::endl;
    return error<1e-5?0:6;
}
