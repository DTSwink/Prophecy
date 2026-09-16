#pragma once
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>

namespace ProphecyJolt
{
// Native implicit viscous damping of relative angular velocity. No pose spring.
// Zero restores the importer's motors-off default and removes all motor rows.
inline bool SetJointDamping(JPH::SixDOFConstraint& Joint,float Damping)
{
    bool Changed=false;
    for (int32 I=0; I<3; ++I)
    {
        const auto Axis=JPH::SixDOFConstraintSettings::EAxis(JPH::SixDOFConstraintSettings::RotationX+I);
        auto& Motor=Joint.GetMotorSettings(Axis);
        const auto State=Damping>0 ? JPH::EMotorState::PositionAndVelocity : JPH::EMotorState::Off;
        if (Joint.GetMotorState(Axis)==State && (Damping==0 ||
            (Motor.mSpringSettings.mMode==JPH::ESpringMode::MassNormalizedStiffnessAndDamping
            && Motor.mSpringSettings.mStiffness==0 && Motor.mSpringSettings.mDamping==Damping))) continue;
        Joint.SetMotorState(Axis,JPH::EMotorState::Off); // Retuning clears only this motor's old impulse.
        Motor=JPH::MotorSettings();
        if (Damping>0)
        {
            Motor.mSpringSettings=JPH::SpringSettings(JPH::ESpringMode::MassNormalizedStiffnessAndDamping,0,Damping);
            Joint.SetTargetAngularVelocityCS(JPH::Vec3::sZero());
            Joint.SetMotorState(Axis,State);
        }
        Changed=true;
    }
    return Changed;
}
}
