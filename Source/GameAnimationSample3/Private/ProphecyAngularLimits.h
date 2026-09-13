#pragma once

#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"

namespace ProphecyAngularLimits
{
inline bool Equal(const FConstraintProfileProperties& A, const FConstraintProfileProperties& B)
{
    return A.ConeLimit.Swing1Motion == B.ConeLimit.Swing1Motion
        && A.ConeLimit.Swing2Motion == B.ConeLimit.Swing2Motion
        && A.TwistLimit.TwistMotion == B.TwistLimit.TwistMotion
        && A.ConeLimit.Swing1LimitDegrees == B.ConeLimit.Swing1LimitDegrees
        && A.ConeLimit.Swing2LimitDegrees == B.ConeLimit.Swing2LimitDegrees
        && A.TwistLimit.TwistLimitDegrees == B.TwistLimit.TwistLimitDegrees;
}

inline void Copy(FConstraintProfileProperties& To, const FConstraintProfileProperties& From)
{
    To.ConeLimit.Swing1Motion = From.ConeLimit.Swing1Motion;
    To.ConeLimit.Swing2Motion = From.ConeLimit.Swing2Motion;
    To.TwistLimit.TwistMotion = From.TwistLimit.TwistMotion;
    To.ConeLimit.Swing1LimitDegrees = From.ConeLimit.Swing1LimitDegrees;
    To.ConeLimit.Swing2LimitDegrees = From.ConeLimit.Swing2LimitDegrees;
    To.TwistLimit.TwistLimitDegrees = From.TwistLimit.TwistLimitDegrees;
}

inline void Apply(FConstraintInstance& Joint, const FConstraintProfileProperties& Profile)
{
    Joint.SetAngularSwing1Limit(Profile.ConeLimit.Swing1Motion.GetValue(), Profile.ConeLimit.Swing1LimitDegrees);
    Joint.SetAngularSwing2Limit(Profile.ConeLimit.Swing2Motion.GetValue(), Profile.ConeLimit.Swing2LimitDegrees);
    Joint.SetAngularTwistLimit(Profile.TwistLimit.TwistMotion.GetValue(), Profile.TwistLimit.TwistLimitDegrees);
}

// Build the complete request before touching any live constraint.
inline bool Prepare(USkeletalMeshComponent& Mesh, bool bUseAuthored,
    TArray<FConstraintProfileProperties>& Out, FString& Error)
{
    const UPhysicsAsset* Asset = Mesh.GetPhysicsAsset();
    if (!Asset || Mesh.Constraints.IsEmpty() || Mesh.Constraints.Num() != Asset->ConstraintSetup.Num())
    { Error = TEXT("Angular-limit selection requires an initialized PhysicalMesh with its complete PHAT joints."); return false; }
    Out.Reset(Mesh.Constraints.Num());
    for (int32 Index = 0; Index < Mesh.Constraints.Num(); ++Index)
    {
        const FConstraintInstance* Joint = Mesh.Constraints[Index];
        const UPhysicsConstraintTemplate* Template = Asset->ConstraintSetup[Index];
        if (!Joint || !Template || Joint->JointName != Template->DefaultInstance.JointName
            || Joint->ConstraintBone1 != Template->DefaultInstance.ConstraintBone1
            || Joint->ConstraintBone2 != Template->DefaultInstance.ConstraintBone2)
        { Error = TEXT("Angular-limit selection found a missing or replaced PHAT joint."); return false; }
        auto& Profile = Out.Add_GetRef(Joint->ProfileInstance);
        if (bUseAuthored) Copy(Profile, Template->DefaultInstance.ProfileInstance);
        else
        {
            Profile.ConeLimit.Swing1Motion = ACM_Free;
            Profile.ConeLimit.Swing2Motion = ACM_Free;
            Profile.TwistLimit.TwistMotion = ACM_Free;
        }
    }
    return true;
}

// Select connectivity, never JointName or an array index inferred from a bone index.
inline bool PrepareParentJoint(USkeletalMeshComponent& Mesh, FName ChildBone,
    TArray<FConstraintProfileProperties>& Out, int32& OutIndex, FString& Error)
{
    Error.Reset();
    OutIndex = INDEX_NONE;
    if (ChildBone.IsNone() || Mesh.GetBoneIndex(ChildBone) == INDEX_NONE)
    { Error = TEXT("Child Bone must name an actual skeletal bone."); return false; }
    if (!Prepare(Mesh, true, Out, Error)) return false;
    for (int32 Index = 0; Index < Out.Num(); ++Index)
        Out[Index] = Mesh.Constraints[Index]->ProfileInstance;
    for (FName Parent = Mesh.GetParentBone(ChildBone); !Parent.IsNone(); Parent = Mesh.GetParentBone(Parent))
    {
        for (int32 Index = 0; Index < Mesh.Constraints.Num(); ++Index)
        {
            const auto& Joint = *Mesh.Constraints[Index];
            if ((Joint.ConstraintBone1 == ChildBone && Joint.ConstraintBone2 == Parent)
                || (Joint.ConstraintBone2 == ChildBone && Joint.ConstraintBone1 == Parent))
            {
                if (OutIndex != INDEX_NONE)
                { Error = TEXT("More than one PHAT joint connects this child to the same parent."); return false; }
                OutIndex = Index;
            }
        }
        if (OutIndex != INDEX_NONE) return true;
    }
    Error = FString::Printf(TEXT("Bone '%s' has no PHAT joint to a skeletal ancestor."), *ChildBone.ToString());
    return false;
}
}
