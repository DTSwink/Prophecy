#pragma once

#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/Constraints/ConstraintPart/AxisConstraintPart.h>

namespace ProphecyJolt
{
// UE's shared linear limit is a radius in the subspace of Limited axes.
// Keep stock SixDOF for locks, angular limits and motors; one native solver row
// replaces its independent Limited translation rows. Free axes are projected out.
class FRadialJoint final : public JPH::TwoBodyConstraint
{
public:
    FRadialJoint(JPH::SixDOFConstraint& Existing, const JPH::SixDOFConstraintSettings& Settings,
        JPH::Vec3Arg LimitedMask, float RadiusMetres, const JPH::SpringSettings& SpringSettings)
        : JPH::TwoBodyConstraint(*Existing.GetBody1(), *Existing.GetBody2(), Settings),
          Native(&Existing), Mask(LimitedMask), Radius(RadiusMetres), Spring(SpringSettings) {}

    JPH::SixDOFConstraint& GetNative() const { return *Native; }
    JPH::Vec3 GetLinearImpulse() const { return Native->GetTotalWorldSpaceLinearImpulse() + VelocityAxis * Radial.GetTotalLambda(); }
    JPH::Vec3 GetAngularImpulse() const { return Native->GetTotalWorldSpaceAngularImpulse(); }
    virtual JPH::EConstraintSubType GetSubType() const override { return JPH::EConstraintSubType::User2; }
    virtual void NotifyShapeChanged(const JPH::BodyID& ID, JPH::Vec3Arg Delta) override { Native->NotifyShapeChanged(ID, Delta); }
    virtual void ResetWarmStart() override { Native->ResetWarmStart(); Radial.Deactivate(); }
    virtual void SetupVelocityConstraint(float Dt) override
    {
        Native->SetupVelocityConstraint(Dt);
        JPH::Vec3 R1U, R2, Axis;
        const float Error = Geometry(R1U, R2, Axis);
        if (Error < 0) { Radial.Deactivate(); return; }
        VelocityAxis = Axis;
        Radial.CalculateConstraintPropertiesWithSettingsForLimit(Dt, *mBody1, R1U, *mBody2, R2, Axis, 0.f, Error, Spring);
    }
    virtual void WarmStartVelocityConstraint(float Ratio) override
    {
        Native->WarmStartVelocityConstraint(Ratio);
        if (Radial.IsActive()) Radial.WarmStart(*mBody1, *mBody2, VelocityAxis, Ratio);
    }
    virtual bool SolveVelocityConstraint(float Dt) override
    {
        bool Changed = Native->SolveVelocityConstraint(Dt);
        if (Radial.IsActive()) Changed |= Radial.SolveVelocityConstraint(*mBody1, *mBody2, VelocityAxis, -FLT_MAX, 0.f);
        return Changed;
    }
    virtual bool SolvePositionConstraint(float Dt, float Baumgarte) override
    {
        bool Changed = Native->SolvePositionConstraint(Dt, Baumgarte);
        if (Spring.mFrequency > 0.f) return Changed;
        JPH::Vec3 R1U, R2, Axis;
        const float Error = Geometry(R1U, R2, Axis);
        if (Error > 0.f)
        {
            Radial.CalculateConstraintProperties(*mBody1, R1U, *mBody2, R2, Axis);
            Changed |= Radial.SolvePositionConstraint(*mBody1, *mBody2, Axis, Error, Baumgarte);
        }
        return Changed;
    }
    virtual JPH::Mat44 GetConstraintToBody1Matrix() const override { return Native->GetConstraintToBody1Matrix(); }
    virtual JPH::Mat44 GetConstraintToBody2Matrix() const override { return Native->GetConstraintToBody2Matrix(); }
    // Generic joint settings are persisted by the UE owner, not Jolt object-stream serialization.
    virtual JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override { return Native->GetConstraintSettings(); }
    virtual void SaveState(JPH::StateRecorder& Stream) const override
    { TwoBodyConstraint::SaveState(Stream); Native->SaveState(Stream); Radial.SaveState(Stream); Stream.Write(VelocityAxis); }
    virtual void RestoreState(JPH::StateRecorder& Stream) override
    { TwoBodyConstraint::RestoreState(Stream); Native->RestoreState(Stream); Radial.RestoreState(Stream); Stream.Read(VelocityAxis); }
#ifdef JPH_DEBUG_RENDERER
    virtual void DrawConstraint(JPH::DebugRenderer* Renderer) const override { Native->DrawConstraint(Renderer); }
#endif
private:
    float Geometry(JPH::Vec3& R1U, JPH::Vec3& R2, JPH::Vec3& Axis) const
    {
        const auto LocalA = Native->GetConstraintToBody1Matrix();
        const auto LocalB = Native->GetConstraintToBody2Matrix();
        const auto PointA = mBody1->GetCenterOfMassTransform() * LocalA.GetTranslation();
        const auto PointB = mBody2->GetCenterOfMassTransform() * LocalB.GetTranslation();
        const JPH::Quat Frame = mBody1->GetRotation() * LocalA.GetQuaternion();
        const JPH::Vec3 Projected = (Frame.Conjugated() * JPH::Vec3(PointB - PointA)) * Mask;
        const float Length = Projected.Length();
        // Radius is strictly positive. A zero projection is strictly inside,
        // so the fallback normal cannot reach a solver row.
        Axis = Length > 0.f ? Frame * (Projected / Length) : JPH::Vec3::sAxisX();
        R1U = JPH::Vec3(PointB - mBody1->GetCenterOfMassPosition());
        R2 = JPH::Vec3(PointB - mBody2->GetCenterOfMassPosition());
        return Length - Radius;
    }
    JPH::Ref<JPH::SixDOFConstraint> Native;
    JPH::AxisConstraintPart Radial;
    JPH::Vec3 Mask, VelocityAxis = JPH::Vec3::sAxisX();
    float Radius;
    JPH::SpringSettings Spring;
};
inline JPH::SixDOFConstraint& GenericSixDOF(JPH::TwoBodyConstraint& Constraint)
{
    return Constraint.GetSubType() == JPH::EConstraintSubType::User2
        ? static_cast<FRadialJoint&>(Constraint).GetNative() : static_cast<JPH::SixDOFConstraint&>(Constraint);
}
}
