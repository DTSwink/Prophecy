namespace ProphecyJolt::ArmMotors
{
static TMap<JPH::PhysicsSystem*, FDrives> Worlds;
FDrives* Find(JPH::PhysicsSystem& Physics) { return Worlds.IsEmpty() ? nullptr : Worlds.Find(&Physics); }

void Set(JPH::PhysicsSystem& Physics, JPH::BodyID ID, bool Enabled)
{
    check(IsInGameThread());
    auto* Drives = Find(Physics);
    const uint32 Key = ID.GetIndexAndSequenceNumber();
    if (!Enabled)
    {
        if (Drives) if (auto* Drive = Drives->Find(Key))
        {
            Physics.RemoveConstraint(Drive->Motor.GetPtr());
            Drives->Remove(Key);
            if (Drives->IsEmpty()) Worlds.Remove(&Physics);
        }
        return;
    }
    if (Drives && Drives->Contains(Key)) return;
    JPH::Ref<JPH::SixDOFConstraint> Drive;
    {
        JPH::BodyLockWrite Lock(Physics.GetBodyLockInterface(), ID);
        if (!Lock.Succeeded() || Lock.GetBody().IsStatic()) return;
        auto& Body = Lock.GetBody();
        JPH::SixDOFConstraintSettings Settings;
        Settings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
        Settings.mPosition1 = Body.GetCenterOfMassPosition();
        Settings.mPosition2 = JPH::RVec3::sZero();
        Drive = static_cast<JPH::SixDOFConstraint*>(Settings.Create(JPH::Body::sFixedToWorld, Body));
        for (int Axis = 0; Axis < 6; ++Axis)
        {
            auto& Motor = Drive->GetMotorSettings(JPH::SixDOFConstraint::EAxis(Axis));
            Motor.SetForceLimit(3000.f);
            Motor.SetTorqueLimit(500.f);
        }
    }
    Physics.AddConstraint(Drive.GetPtr());
    Worlds.FindOrAdd(&Physics).Add(Key, {Drive, false});
    Physics.GetBodyInterface().ActivateBody(ID);
}

void Clear(JPH::PhysicsSystem& Physics)
{
    if (auto* Drives = Find(Physics))
        for (auto& Pair : *Drives) Physics.RemoveConstraint(Pair.Value.Motor.GetPtr());
    Worlds.Remove(&Physics);
}

void Prepare(JPH::PhysicsSystem& Physics, TConstArrayView<FVelocityServo::FTarget> Targets)
{
    auto* Drives = Find(Physics);
    if (!Drives) return;
    for (auto& Pair : *Drives) Pair.Value.Published = false;
    for (const auto& Target : Targets)
        if (auto* Drive = Drives->Find(Target.Body.GetIndexAndSequenceNumber())) Drive->Published = true;
    for (auto& Pair : *Drives)
    {
        if (Pair.Value.Published) continue;
        for (int Axis = 0; Axis < 6; ++Axis)
            Pair.Value.Motor->SetMotorState(JPH::SixDOFConstraint::EAxis(Axis), JPH::EMotorState::Off);
    }
}

bool Apply(FDrives* Drives, JPH::Body& Body, const FVelocityServo::FTarget& Target,
    float DeltaSeconds, JPH::Vec3Arg Linear, JPH::Vec3Arg Angular,
    const FVector& LinearFollow, const FVector& AngularFollow)
{
    if (!Drives) return false;
    auto* Entry = Drives->Find(Body.GetID().GetIndexAndSequenceNumber());
    if (!Entry) return false;
    auto& Drive = *Entry->Motor;
    // Off channels must remain physically free; a velocity motor at current velocity would brake them.
    for (int Axis = 0; Axis < 6; ++Axis)
    {
        const bool Enabled = Axis < 3 ? Target.LinearStrength > 0 && LinearFollow[Axis] > 0
            : Target.AngularStrength > 0 && !AngularFollow.IsNearlyZero();
        Drive.SetMotorState(JPH::SixDOFConstraint::EAxis(Axis), Enabled ? JPH::EMotorState::Velocity : JPH::EMotorState::Off);
    }
    const auto Gravity = Conversions::ToJoltLinearVelocity(FVector(0, 0,
        Target.GravityCompensationCmPerSecondSquared * DeltaSeconds * Target.LinearStrength));
    const auto* Motion = Body.GetMotionProperties();
    auto LimitedLinear = Linear - Gravity;
    if (LimitedLinear.LengthSq() > FMath::Square(Motion->GetMaxLinearVelocity()))
        LimitedLinear *= Motion->GetMaxLinearVelocity() / LimitedLinear.Length();
    auto LimitedAngular = Angular;
    if (LimitedAngular.LengthSq() > FMath::Square(Motion->GetMaxAngularVelocity()))
        LimitedAngular *= Motion->GetMaxAngularVelocity() / LimitedAngular.Length();
    Drive.SetTargetVelocityCS(LimitedLinear);
    Drive.SetTargetAngularVelocityCS(Body.GetRotation().Conjugated() * LimitedAngular);
    if (Target.LinearStrength > 0 && !Gravity.IsNearZero())
        Body.SetLinearVelocity(Body.GetLinearVelocity() + Gravity);
    return true;
}
}
