#pragma once
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include "ProphecyJoltGrabPointConstraintPart.h"
#include "ProphecyJoltGrabRotationEulerConstraintPart.h"

namespace ProphecyJolt
{
// A grab-only fixed joint. A is the grabbing hand, B is the target.
// The solver sees scaled inverse mass/inertia for A without changing either body.
class FGrabJoint final : public JPH::TwoBodyConstraint
{
public:
    FGrabJoint(JPH::FixedConstraint& Existing, const JPH::FixedConstraintSettings& Settings, float Independence)
        : TwoBodyConstraint(*Existing.GetBody1(), *Existing.GetBody2(), Settings),
          Native(&Existing), Amount(Independence),
          PointA(JPH::Vec3(Settings.mPoint1)), PointB(JPH::Vec3(Settings.mPoint2)),
          InvOrientation(JPH::RotationEulerConstraintPart::sGetInvInitialOrientationXY(
              Settings.mAxisX1, Settings.mAxisY1, Settings.mAxisX2, Settings.mAxisY2)) {}
    // User3 is scoped by the generic Fixed type; pike's User3 is HardSixDOF.
    virtual JPH::EConstraintSubType GetSubType() const override { return JPH::EConstraintSubType::User3; }
    float GetIndependence() const { return Amount; }
    void SetIndependence(float Value)
    {
        if(Amount==Value)return;
        Amount=Value;ResetWarmStart();
    }
    virtual void NotifyShapeChanged(const JPH::BodyID& ID, JPH::Vec3Arg Delta) override
    {
        Native->NotifyShapeChanged(ID,Delta);
        if(ID==mBody1->GetID()) PointA-=Delta;
        else if(ID==mBody2->GetID()) PointB-=Delta;
    }
    virtual void ResetWarmStart() override { Point.Deactivate(); Rotation.Deactivate(); }
    virtual void SetupVelocityConstraint(float) override
    {
        // Re-evaluate motion type: a target switched to kinematic/static gets normal reactions.
        const float Scale=mBody2->IsDynamic()?1.f-Amount:1.f;
        if(Scale!=HandScale) { ResetWarmStart(); HandScale=Scale; }
        Point.SetHandScale(Scale); Rotation.SetHandScale(Scale);
        Calculate();
    }
    virtual void WarmStartVelocityConstraint(float Ratio) override
    { Rotation.WarmStart(*mBody1,*mBody2,Ratio); Point.WarmStart(*mBody1,*mBody2,Ratio); }
    virtual bool SolveVelocityConstraint(float) override
    {
        const bool R=Rotation.SolveVelocityConstraint(*mBody1,*mBody2);
        return Point.SolveVelocityConstraint(*mBody1,*mBody2)||R;
    }
    virtual bool SolvePositionConstraint(float,float Baumgarte) override
    {
        if(mBody1->HasNumericalFailure()||mBody2->HasNumericalFailure())return false;
        Rotation.CalculateConstraintProperties(*mBody1,JPH::Mat44::sRotation(mBody1->GetRotation()),
            *mBody2,JPH::Mat44::sRotation(mBody2->GetRotation()));
        const bool R=Rotation.SolvePositionConstraint(*mBody1,*mBody2,InvOrientation,Baumgarte);
        if(mBody1->HasNumericalFailure()||mBody2->HasNumericalFailure())return false;
        Point.CalculateConstraintProperties(*mBody1,JPH::Mat44::sRotation(mBody1->GetRotation()),PointA,
            *mBody2,JPH::Mat44::sRotation(mBody2->GetRotation()),PointB);
        return Point.SolvePositionConstraint(*mBody1,*mBody2,Baumgarte)||R;
    }
    JPH::Vec3 GetLinearImpulse() const { return Point.GetTotalLambda(); }
    JPH::Vec3 GetAngularImpulse() const { return Rotation.GetTotalLambda(); }
    virtual JPH::Mat44 GetConstraintToBody1Matrix() const override { return Native->GetConstraintToBody1Matrix(); }
    virtual JPH::Mat44 GetConstraintToBody2Matrix() const override { return Native->GetConstraintToBody2Matrix(); }
    // Generic geometry remains stock; the UE owner preserves Amount when reframing.
    virtual JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override { return Native->GetConstraintSettings(); }
    virtual void SaveState(JPH::StateRecorder& Stream) const override
    { TwoBodyConstraint::SaveState(Stream); Rotation.SaveState(Stream); Point.SaveState(Stream); Stream.Write(HandScale); }
    virtual void RestoreState(JPH::StateRecorder& Stream) override
    {
        TwoBodyConstraint::RestoreState(Stream); Rotation.RestoreState(Stream); Point.RestoreState(Stream);
        Stream.Read(HandScale); Rotation.SetHandScale(HandScale); Point.SetHandScale(HandScale);
    }
#ifdef JPH_DEBUG_RENDERER
    virtual void DrawConstraint(JPH::DebugRenderer* Renderer) const override { Native->DrawConstraint(Renderer); }
#endif
private:
    void Calculate()
    {
        const JPH::Mat44 A=JPH::Mat44::sRotation(mBody1->GetRotation()), B=JPH::Mat44::sRotation(mBody2->GetRotation());
        Rotation.CalculateConstraintProperties(*mBody1,A,*mBody2,B);
        Point.CalculateConstraintProperties(*mBody1,A,PointA,*mBody2,B,PointB);
    }
    JPH::Ref<JPH::FixedConstraint> Native;
    float Amount,HandScale=-1;
    JPH::Vec3 PointA,PointB;
    JPH::Quat InvOrientation;
    FGrabPointConstraintPart Point;
    FGrabRotationEulerConstraintPart Rotation;
};
}
