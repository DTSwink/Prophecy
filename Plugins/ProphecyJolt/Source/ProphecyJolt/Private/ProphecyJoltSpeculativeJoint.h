#pragma once

#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/Constraints/ConstraintPart/AngleConstraintPart.h>

namespace ProphecyJolt
{
inline bool NeedsSpeculativeSwing(const JPH::SixDOFConstraint& Native)
{
    using Axis = JPH::SixDOFConstraintSettings::EAxis;
    return !Native.IsFixedAxis(Axis::RotationY) && !Native.IsFixedAxis(Axis::RotationZ)
        && !(Native.IsFreeAxis(Axis::RotationY) && Native.IsFreeAxis(Axis::RotationZ));
}
// Preserve SixDOF's frames, anchors, hard limits and position solver. Its cone
// velocity row is inactive inside the range, so a velocity servo can cross the
// boundary in one step. Add the interior inequality dC/dt <= -C/dt, allowing
// remaining clearance and inward/tangential motion without damping the joint.
class FSpeculativeJoint final : public JPH::TwoBodyConstraint
{
public:
    FSpeculativeJoint(JPH::SixDOFConstraint& Existing, const JPH::SixDOFConstraintSettings& Settings)
        : JPH::TwoBodyConstraint(*Existing.GetBody1(), *Existing.GetBody2(), Settings), Native(&Existing) { RefreshLimits(); }
    JPH::SixDOFConstraint& GetNative() const { return *Native; }
    void SetRotationLimits(JPH::Vec3Arg Minimum, JPH::Vec3Arg Maximum)
    {
        Native->SetRotationLimits(Minimum, Maximum);
        RefreshLimits();
    }
    virtual JPH::EConstraintSubType GetSubType() const override { return JPH::EConstraintSubType::User1; }
    virtual void NotifyShapeChanged(const JPH::BodyID& ID, JPH::Vec3Arg Delta) override { Native->NotifyShapeChanged(ID, Delta); }
    virtual void ResetWarmStart() override { Native->ResetWarmStart(); Swing.Deactivate(); }
    virtual void SetupVelocityConstraint(float Dt) override
    {
        Native->SetupVelocityConstraint(Dt);
        if (!bSpeculativeSwing || Dt <= 0.0f)
        { Swing.Deactivate(); return; }
        JPH::Quat S, T;
        Native->GetRotationInConstraintSpace().GetSwingTwist(S, T);
        const float C = JPH::Square(S.GetY()) / A2 + JPH::Square(S.GetZ()) / B2 - 1.0f;
        if (C > 0.0f) { Swing.Deactivate(); return; }
        const JPH::Vec3 V = S.RotateAxisX();
        const float D = 1.0f + V.GetX();
        if (D <= 1.0e-6f) { Swing.Deactivate(); return; }
        // C(v) = (vz^2/a^2 + vy^2/b^2)/(2*(1+vx)) - 1.
        // dC/dt = (v cross grad(C)) dot relative angular velocity.
        const float N = JPH::Square(V.GetZ()) / A2 + JPH::Square(V.GetY()) / B2;
        const JPH::Vec3 Gradient(-N / (2.0f * D * D), V.GetY() / (B2 * D), V.GetZ() / (A2 * D));
        const JPH::Vec3 Jacobian = V.Cross(Gradient);
        const float Length = Jacobian.Length();
        if (Length <= 1.0e-6f) { Swing.Deactivate(); return; }
        const JPH::Quat Frame = mBody1->GetRotation() * Native->GetConstraintToBody1Matrix().GetQuaternion();
        SwingAxis = Frame * (Jacobian / Length);
        Swing.CalculateConstraintProperties(*mBody1, *mBody2, SwingAxis, C / (Length * Dt));
    }
    virtual void WarmStartVelocityConstraint(float Ratio) override
    {
        Native->WarmStartVelocityConstraint(Ratio);
        if (Swing.IsActive()) Swing.WarmStart(*mBody1, *mBody2, Ratio);
    }
    virtual bool SolveVelocityConstraint(float Dt) override
    {
        bool Changed = Native->SolveVelocityConstraint(Dt);
        if (Swing.IsActive()) Changed |= Swing.SolveVelocityConstraint(*mBody1, *mBody2, SwingAxis, -FLT_MAX, 0.0f);
        return Changed;
    }
    virtual bool SolvePositionConstraint(float Dt, float Baumgarte) override { return Native->SolvePositionConstraint(Dt, Baumgarte); }
    virtual JPH::Mat44 GetConstraintToBody1Matrix() const override { return Native->GetConstraintToBody1Matrix(); }
    virtual JPH::Mat44 GetConstraintToBody2Matrix() const override { return Native->GetConstraintToBody2Matrix(); }
    virtual JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override { return Native->GetConstraintSettings(); }
    virtual void SaveState(JPH::StateRecorder& Stream) const override { TwoBodyConstraint::SaveState(Stream); Native->SaveState(Stream); Swing.SaveState(Stream); }
    virtual void RestoreState(JPH::StateRecorder& Stream) override { TwoBodyConstraint::RestoreState(Stream); Native->RestoreState(Stream); Swing.RestoreState(Stream); }
#ifdef JPH_DEBUG_RENDERER
    virtual void DrawConstraint(JPH::DebugRenderer* Renderer) const override { Native->DrawConstraint(Renderer); }
#endif
private:
    void RefreshLimits()
    {
        bSpeculativeSwing = NeedsSpeculativeSwing(*Native);
        const auto Hi = Native->GetRotationLimitsMax();
        A2 = JPH::Square(JPH::Sin(Hi.GetY() * 0.5f));
        B2 = JPH::Square(JPH::Sin(Hi.GetZ() * 0.5f));
        Swing.Deactivate(); // A runtime range change must not reuse its old boundary impulse.
    }
    JPH::Ref<JPH::SixDOFConstraint> Native;
    JPH::AngleConstraintPart Swing;
    JPH::Vec3 SwingAxis = JPH::Vec3::sAxisY();
    float A2 = 1.0f, B2 = 1.0f;
    bool bSpeculativeSwing = false;
};

inline JPH::SixDOFConstraint* GetSixDOF(JPH::TwoBodyConstraint* C)
{
    if (C->GetSubType() == JPH::EConstraintSubType::User1) return &static_cast<FSpeculativeJoint*>(C)->GetNative();
    return C->GetSubType() == JPH::EConstraintSubType::SixDOF ? static_cast<JPH::SixDOFConstraint*>(C) : nullptr;
}
}
