#pragma once
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>

namespace ProphecyJolt::FootExtension
{
// Independent translation frame: rotating the original SixDOF frame would also
// rotate its authored swing/twist limits. Keep that joint for angular rows only.
inline JPH::SixDOFConstraintSettings Settings(const JPH::SixDOFConstraint& Joint,
    JPH::Vec3Arg ParentAxis, float Metres)
{
    using Axis=JPH::SixDOFConstraintSettings::EAxis;
    JPH::SixDOFConstraintSettings S;
    S.mSpace=JPH::EConstraintSpace::LocalToBodyCOM;
    S.mPosition1=JPH::RVec3(Joint.GetConstraintToBody1Matrix().GetTranslation());
    S.mPosition2=JPH::RVec3(Joint.GetConstraintToBody2Matrix().GetTranslation());
    S.mAxisX1=ParentAxis.Normalized();
    S.mAxisY1=S.mAxisX1.GetNormalizedPerpendicular();
    S.mAxisX2=JPH::Vec3::sAxisX(); S.mAxisY2=JPH::Vec3::sAxisY();
    S.SetLimitedAxis(Axis::TranslationX,0,Metres);
    S.MakeFixedAxis(Axis::TranslationY); S.MakeFixedAxis(Axis::TranslationZ);
    for (int I=3;I<6;++I) S.MakeFreeAxis(Axis(I));
    S.mNumVelocityStepsOverride=Joint.GetNumVelocityStepsOverride();
    S.mNumPositionStepsOverride=Joint.GetNumPositionStepsOverride();
    S.mConstraintPriority=Joint.GetConstraintPriority();
    return S;
}
struct FJoint
{
    JPH::Ref<JPH::SixDOFConstraint> Original, Translation;
    JPH::Vec3 Minimum,Maximum;
};
}
