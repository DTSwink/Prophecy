#pragma once
#include <Jolt/Physics/Constraints/TwoBodyConstraint.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/Constraints/ConstraintPart/AngleConstraintPart.h>

namespace ProphecyJolt
{
/** Canonical PHAT-centred total-angle limit. Matches accepted recovery sphere32. */
class FSphericalLimit final : public JPH::TwoBodyConstraint
{
    JPH::Quat Frame1,Frame2;
    float Radius;
    JPH::Vec3 Axis=JPH::Vec3::sAxisX();
    JPH::AngleConstraintPart Part;
public:
    FSphericalLimit(JPH::Body& A,JPH::Body& B,const JPH::SixDOFConstraintSettings& Settings,
        JPH::QuatArg InFrame1,JPH::QuatArg InFrame2,float InRadius)
        :TwoBodyConstraint(A,B,Settings),Frame1(InFrame1),Frame2(InFrame2),Radius(InRadius){}
    void SetRadius(float Value){if(Value!=Radius){Radius=Value;Part.Deactivate();}}
    JPH::EConstraintSubType GetSubType()const override{return JPH::EConstraintSubType::Cone;}
    void NotifyShapeChanged(const JPH::BodyID&,JPH::Vec3Arg)override{}
    JPH::Mat44 GetConstraintToBody1Matrix()const override{return JPH::Mat44::sRotation(Frame1);}
    JPH::Mat44 GetConstraintToBody2Matrix()const override{return JPH::Mat44::sRotation(Frame2);}
    JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings()const override{return new JPH::SixDOFConstraintSettings;}
    void SetupVelocityConstraint(float Dt)override
    {
        const JPH::Quat World=mBody1->GetRotation()*Frame1;
        const JPH::Quat Q=(World.Conjugated()*mBody2->GetRotation()*Frame2).EnsureWPositive();
        float Angle;JPH::Vec3 Local;Q.GetAxisAngle(Local,Angle);
        const float Error=Angle-Radius;
        if(Error<=0){Part.Deactivate();return;}
        Axis=World*Local;
        Part.CalculateConstraintPropertiesWithSettingsForLimit(Dt,*mBody1,*mBody2,Axis,0,Error,
            JPH::SpringSettings(JPH::ESpringMode::FrequencyAndDamping,32.f,1.f));
    }
    void ResetWarmStart()override{Part.Deactivate();}
    void WarmStartVelocityConstraint(float Ratio)override{if(Part.IsActive())Part.WarmStart(*mBody1,*mBody2,Ratio);}
    bool SolveVelocityConstraint(float)override{return Part.IsActive()&&Part.SolveVelocityConstraint(*mBody1,*mBody2,Axis,-1.e10f,0);}
    bool SolvePositionConstraint(float,float)override{return false;}
};
}
