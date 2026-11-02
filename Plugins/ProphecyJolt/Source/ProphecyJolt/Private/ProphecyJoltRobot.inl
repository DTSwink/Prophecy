// Included in the native owner TU after FProphecyJoltWorldState.
FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ConfigureRobotRig(const FProphecyJoltRigHandle& Handle,
    TConstArrayView<FProphecyJoltRobotMotor> Motors,TConstArrayView<FProphecyJoltRobotDrag> Drag)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready=ValidateReady();if(!Ready.IsSuccess())return Ready;
    auto* Rig=Native->FindRig(Handle);
    if(!Rig || Motors.Num()!=Rig->Constraints.Num() || Drag.Num()!=Rig->Handles.Num())
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Robot profile dimensions must match its rig."));
    if(ProphecyJolt::WorldPrivate::Robots.Contains(Rig))
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Robot rig is already configured."));
    for(const auto& M:Motors)
        if(M.TorqueLimit.ContainsNaN() || M.TorqueLimit.GetMin()<0 || !FMath::IsFinite(M.Damping) || M.Damping<0)
            return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Invalid robot motor profile."));
    auto State=MakeUnique<ProphecyJolt::WorldPrivate::FRobotRig>();
    for(const auto& H:Rig->Handles)
    {
        const auto ID=Native->Find(H)->Body;State->Bodies.Add(ID);
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(),ID);
        if(Lock.Succeeded()){Lock.GetBody().SetAllowSleeping(false);Lock.GetBody().SetApplyGyroscopicForce(false);}
    }
    State->Drag.Append(Drag);State->Physics=&Native->Physics;
    State->PreviousForce.Init(JPH::Vec3::sZero(),Drag.Num());State->PreviousTorque.Init(JPH::Vec3::sZero(),Drag.Num());
    for(int32 I=0;I<Motors.Num();++I)
    {
        auto* Six=ProphecyJolt::GetSixDOF(Rig->Constraints[I].GetPtr());
        JPH::Ref<JPH::ConstraintSettings> Base=Six->GetConstraintSettings();
        auto* Settings=static_cast<JPH::SixDOFConstraintSettings*>(Base.GetPtr());
        for(int32 Axis=0;Axis<3;++Axis)
        {
            auto A=static_cast<JPH::SixDOFConstraintSettings::EAxis>(Axis+3);
            if(Motors[I].bBall)Settings->MakeFreeAxis(A);
            else Settings->SetLimitedAxis(A,-JPH::JPH_PI,JPH::JPH_PI);
        }
        JPH::Ref<JPH::TwoBodyConstraint> New=Settings->Create(*Six->GetBody1(),*Six->GetBody2());
        Native->Physics.ReplaceConstraint(Rig->Constraints[I].GetPtr(),New.GetPtr());
        Rig->Constraints[I]=New;Six=static_cast<JPH::SixDOFConstraint*>(New.GetPtr());
        const auto& D=Rig->JointDescriptions[I];
        State->ChildFrames.Add(D.Frame1.GetRotation());
        const FVector Bounds(FMath::DegreesToRadians(D.CurrentProfile.TwistLimit.TwistLimitDegrees),
            FMath::DegreesToRadians(D.CurrentProfile.ConeLimit.Swing2LimitDegrees),
            FMath::DegreesToRadians(D.CurrentProfile.ConeLimit.Swing1LimitDegrees));
        State->Bounds.Add(Bounds);
        JPH::Ref<ProphecyJolt::FSphericalLimit> Sphere;
        if(Motors[I].bBall)
        {
            Sphere=new ProphecyJolt::FSphericalLimit(*Six->GetBody1(),*Six->GetBody2(),*Settings,
                ProphecyJolt::Conversions::ToJoltRotation(D.Frame2.GetRotation()),
                ProphecyJolt::Conversions::ToJoltRotation(D.Frame1.GetRotation()),JPH::JPH_PI);
            Sphere->SetNumVelocityStepsOverride(40);Sphere->SetNumPositionStepsOverride(8);
            Native->Physics.AddConstraint(Sphere.GetPtr());
        }
        State->Limits.Add(Sphere);
        Six->SetNumVelocityStepsOverride(40);Six->SetNumPositionStepsOverride(8);
        for(int32 Axis=0;Axis<3;++Axis)
        {
            const auto A=static_cast<JPH::SixDOFConstraintSettings::EAxis>(Axis+3);
            Six->GetMotorSettings(A)=JPH::MotorSettings(JPH::ESpringMode::StiffnessAndDamping,0,Motors[I].Damping);
            Six->GetMotorSettings(A).SetTorqueLimit(Motors[I].TorqueLimit[Axis]);
            Six->SetMotorState(A,(!Motors[I].bBall&&Axis!=2)?JPH::EMotorState::Off:JPH::EMotorState::PositionAndVelocity);
        }
    }
    Rig->Targets.Reset();Rig->PublishedHandles.Reset();
    Native->Physics.AddStepListener(State.Get());
    for(const auto& B:State->Bodies)ProphecyJolt::WorldPrivate::RobotBodies.FindOrAdd(&Native->Physics).Add(B.GetIndexAndSequenceNumber(),Rig);
    ProphecyJolt::WorldPrivate::Robots.Add(Rig,MoveTemp(State));
    ProphecyJolt::ScopedContacts::Refresh(*Native);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::PublishRobotMotors(const FProphecyJoltRigHandle& Handle,
    TConstArrayView<FProphecyJoltRobotMotor> Motors,float LimitAlpha)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready=ValidateReady();if(!Ready.IsSuccess())return Ready;
    auto* Rig=Native->FindRig(Handle);auto* Entry=ProphecyJolt::WorldPrivate::Robots.Find(Rig);
    if(!Rig || !Entry || Motors.Num()!=Rig->Constraints.Num() || !FMath::IsFinite(LimitAlpha))
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Robot motor packet requires its configured rig."));
    for(const auto& M:Motors)if(M.Velocity.ContainsNaN())
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Nonfinite robot velocity."));
    auto& S=**Entry;const float Alpha=FMath::Clamp(LimitAlpha,0.f,1.f);
    for(int32 I=0;I<Motors.Num();++I)
    {
        auto* Six=ProphecyJolt::GetSixDOF(Rig->Constraints[I].GetPtr());
        const FVector Velocity=S.ChildFrames[I].UnrotateVector(Motors[I].Velocity);
        Six->SetTargetAngularVelocityCS(ProphecyJolt::Conversions::ToJoltAngularVelocity(Velocity));
        for(int32 Axis=0;Axis<3;++Axis)
        {
            auto& Motor=Six->GetMotorSettings(static_cast<JPH::SixDOFConstraintSettings::EAxis>(Axis+3));
            Motor.mSpringSettings.mDamping=Motors[I].Damping;Motor.SetTorqueLimit(Motors[I].TorqueLimit[Axis]);
        }
        if(S.Limits[I])S.Limits[I]->SetRadius(FMath::Lerp(float(PI),float(S.Bounds[I].GetMax()),Alpha));
        // Hinge locked axes also close from freedom, avoiding an instantaneous snap on entry.
        else
        {
            auto Min=Six->GetRotationLimitsMin(),Max=Six->GetRotationLimitsMax();
            for(int32 Axis=0;Axis<3;++Axis)
            {float V=FMath::Lerp(float(PI),float(S.Bounds[I][Axis]),Alpha);Min.SetComponent(Axis,-V);Max.SetComponent(Axis,V);}
            Six->SetRotationLimits(Min,Max);
        }
    }
    return {};
}
