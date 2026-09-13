#pragma once

// Optional read-only snapshot outside the timed world tick. The surrounding
// frame interval can include audit cost, as it already does for the base audit.
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "UObject/UnrealType.h"

namespace ProphecySterileBench::RigAudit
{
inline TArray<TSharedPtr<FJsonValue>> Vector(const FVector& V)
{
    return { MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z) };
}

inline TSharedPtr<FJsonObject> Transform(const FTransform& T)
{
    auto O = MakeShared<FJsonObject>();
    O->SetArrayField(TEXT("position_cm"), Vector(T.GetLocation()));
    const FQuat Q = T.GetRotation();
    O->SetArrayField(TEXT("quaternion_xyzw"), { MakeShared<FJsonValueNumber>(Q.X), MakeShared<FJsonValueNumber>(Q.Y),
        MakeShared<FJsonValueNumber>(Q.Z), MakeShared<FJsonValueNumber>(Q.W) });
    O->SetArrayField(TEXT("scale"), Vector(T.GetScale3D()));
    return O;
}

inline const TCHAR* AngularMotion(EAngularConstraintMotion Motion)
{
    switch (Motion)
    {
    case ACM_Free: return TEXT("Free");
    case ACM_Limited: return TEXT("Limited");
    case ACM_Locked: return TEXT("Locked");
    default: return TEXT("Unknown");
    }
}

inline TSharedPtr<FJsonObject> Capture(USkeletalMeshComponent* Mesh)
{
    auto O = MakeShared<FJsonObject>();
    O->SetStringField(TEXT("scope"), TEXT("First live mesh of this synthetic benchmark case; not placed Blueprint overrides or an immutable input recording"));
    O->SetStringField(TEXT("component"), Mesh->GetPathName());
    O->SetStringField(TEXT("physics_asset"), GetPathNameSafe(Mesh->GetPhysicsAsset()));
    O->SetObjectField(TEXT("component_world"), Transform(Mesh->GetComponentTransform()));
    O->SetBoolField(TEXT("update_joints_from_animation"), Mesh->bUpdateJointsFromAnimation);
    auto Scales = MakeShared<FJsonObject>();
    for (const TCHAR* Name : { TEXT("p.Chaos.JointConstraint.SoftAngularStiffnessScale"), TEXT("p.Chaos.JointConstraint.SoftAngularDampingScale") })
    {
        if (const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name))
            Scales->SetNumberField(Name, Variable->GetFloat());
        else
            Scales->SetField(Name, MakeShared<FJsonValueNull>());
    }
    O->SetObjectField(TEXT("chaos_console_scales"), Scales);
    TArray<TSharedPtr<FJsonValue>> Bodies;
    for (const FBodyInstance* B : Mesh->Bodies)
    {
        if (!B || !B->IsValidBodyInstance()) continue;
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("bone"), B->BodySetup.IsValid() ? B->BodySetup->BoneName.ToString() : TEXT(""));
        Row->SetNumberField(TEXT("bone_index"), B->InstanceBoneIndex);
        Row->SetArrayField(TEXT("body_scale"), Vector(B->Scale3D));
        Row->SetBoolField(TEXT("dynamic"), B->IsInstanceSimulatingPhysics());
        Row->SetBoolField(TEXT("awake"), B->IsInstanceAwake());
        Row->SetBoolField(TEXT("gravity"), B->bEnableGravity);
        Row->SetNumberField(TEXT("mass_kg"), B->GetBodyMass());
        Row->SetArrayField(TEXT("principal_inertia_kg_cm2"), Vector(B->GetBodyInertiaTensor()));
        Row->SetObjectField(TEXT("body_world"), Transform(B->GetUnrealWorldTransform()));
        Row->SetObjectField(TEXT("mass_frame_world"), Transform(B->GetMassSpaceToWorldSpace()));
        Row->SetObjectField(TEXT("mass_frame_body"), Transform(B->GetMassSpaceLocal()));
        Row->SetArrayField(TEXT("linear_velocity_cm_s"), Vector(B->GetUnrealWorldVelocity()));
        Row->SetArrayField(TEXT("angular_velocity_rad_s"), Vector(B->GetUnrealWorldAngularVelocityInRadians()));
        Row->SetNumberField(TEXT("collision_enabled"), static_cast<uint8>(B->GetCollisionEnabled()));
        Row->SetNumberField(TEXT("object_channel"), static_cast<uint8>(B->GetObjectType()));
        TArray<TSharedPtr<FJsonValue>> Responses;
        // ECC_MAX also includes an obsolete sentinel outside the 32 response slots.
        for (int32 Channel = 0; Channel < static_cast<int32>(ECC_OverlapAll_Deprecated); ++Channel)
            Responses.Add(MakeShared<FJsonValueNumber>(static_cast<uint8>(B->GetResponseToChannel(static_cast<ECollisionChannel>(Channel)))));
        Row->SetArrayField(TEXT("channel_responses"), Responses);
        Row->SetBoolField(TEXT("body_instance_ccd"), B->bUseCCD);
        Row->SetBoolField(TEXT("body_instance_macd"), B->IsUsingMACD());
        Bodies.Add(MakeShared<FJsonValueObject>(Row));
    }
    TArray<TSharedPtr<FJsonValue>> Constraints;
    for (const FConstraintInstance* C : Mesh->Constraints)
    {
        if (!C) continue;
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("joint"), C->JointName.ToString());
        Row->SetStringField(TEXT("child"), C->ConstraintBone1.ToString());
        Row->SetStringField(TEXT("parent"), C->ConstraintBone2.ToString());
        Row->SetBoolField(TEXT("valid"), C->IsValidConstraintInstance());
        Row->SetStringField(TEXT("swing1_motion"), AngularMotion(C->GetAngularSwing1Motion()));
        Row->SetStringField(TEXT("swing2_motion"), AngularMotion(C->GetAngularSwing2Motion()));
        Row->SetStringField(TEXT("twist_motion"), AngularMotion(C->GetAngularTwistMotion()));
        Row->SetNumberField(TEXT("swing1_limit_deg"), C->GetAngularSwing1Limit());
        Row->SetNumberField(TEXT("swing2_limit_deg"), C->GetAngularSwing2Limit());
        Row->SetNumberField(TEXT("twist_limit_deg"), C->GetAngularTwistLimit());
        Row->SetBoolField(TEXT("soft_swing"), C->ProfileInstance.ConeLimit.bSoftConstraint);
        Row->SetBoolField(TEXT("soft_twist"), C->ProfileInstance.TwistLimit.bSoftConstraint);
        Row->SetObjectField(TEXT("child_frame"), Transform(C->GetRefFrame(EConstraintFrame::Frame1)));
        Row->SetObjectField(TEXT("parent_frame"), Transform(C->GetRefFrame(EConstraintFrame::Frame2)));
        FString Profile;
        FConstraintProfileProperties::StaticStruct()->ExportText(Profile, &C->ProfileInstance, nullptr, nullptr, PPF_None, nullptr);
        Row->SetStringField(TEXT("live_profile_reflected"), Profile);
        Constraints.Add(MakeShared<FJsonValueObject>(Row));
    }
    O->SetArrayField(TEXT("bodies"), Bodies);
    O->SetArrayField(TEXT("constraints"), Constraints);
    return O;
}
}
