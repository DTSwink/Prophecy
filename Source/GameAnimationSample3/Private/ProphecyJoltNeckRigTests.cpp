#include "ProphecyJoltPose.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/SkeletalMesh.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPhysicalNeckRigTest,
    "Prophecy.Jolt.Pose.PhysicalNeckChain",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPhysicalNeckRigTest::RunTest(const FString&)
{
    auto* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Mannequin"), Mesh)) return false;
    auto* Asset = Mesh->GetPhysicsAsset();
    if (!TestNotNull(TEXT("Original PHAT"), Asset)) return false;
    const auto& Ref = Mesh->GetRefSkeleton();
    const int32 N1 = Ref.FindBoneIndex(TEXT("neck_01")), N2 = Ref.FindBoneIndex(TEXT("neck_02")), H = Ref.FindBoneIndex(TEXT("head"));
    if (!TestTrue(TEXT("Three physical neck/head bones"), Asset->FindBodyIndex(TEXT("neck_01")) >= 0
        && Asset->FindBodyIndex(TEXT("neck_02")) >= 0 && Asset->FindBodyIndex(TEXT("head")) >= 0)) return false;
    const int32 NeckJoint = Asset->FindConstraintIndex(TEXT("neck_02"), TEXT("neck_01"));
    const int32 HeadJoint = Asset->FindConstraintIndex(TEXT("head"), TEXT("neck_02"));
    if (!TestTrue(TEXT("Joints follow both neck bones"), NeckJoint >= 0 && HeadJoint >= 0)) return false;
    for (FName Neck : {FName(TEXT("neck_01")), FName(TEXT("neck_02"))})
        for (FName Other : {FName(TEXT("head")), FName(TEXT("clavicle_l")), FName(TEXT("clavicle_r")), FName(TEXT("neck_01"))})
            if (Neck != Other) TestTrue(*FString::Printf(TEXT("No collision %s / %s"), *Neck.ToString(), *Other.ToString()),
                Asset->CollisionDisableTable.Contains(FRigidBodyIndexPair(Asset->FindBodyIndex(Neck), Asset->FindBodyIndex(Other))));

    TArray<int32> Parents;
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    for (int32 I = 0; I < Ref.GetNum(); ++I) Parents.Add(Ref.GetParentIndex(I));
    for (const auto& Body : Asset->SkeletalBodySetups)
    {
        auto& M = Mappings.AddDefaulted_GetRef();
        M.BoneIndex = Ref.FindBoneIndex(Body->BoneName);
        M.BodyFromBoneRigid = FTransform::Identity;
        M.VisualScale = FVector::OneVector;
    }
    ProphecyJolt::Pose::FPreparedLayout Layout;
    FString Error;
    if (!Layout.Build(Ref.GetNum(), Parents, Mappings, Error)) { AddError(Error); return false; }
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        TArray<FTransform> Local = Ref.GetRefBonePose(), World, Bodies;
        for (int32 B : {N1, N2, H})
            Local[B].SetRotation((Local[B].GetRotation() * FRotator(Frame * .3, Frame * -.2, Frame * .1).Quaternion()).GetNormalized());
        World.SetNum(Local.Num());
        for (int32 I = 0; I < Local.Num(); ++I) World[I] = Parents[I] < 0 ? Local[I] : Local[I] * World[Parents[I]];
        for (int32 J : {NeckJoint, HeadJoint})
        {
            const auto& C = Asset->ConstraintSetup[J]->DefaultInstance;
            const FVector A = (C.GetRefFrame(EConstraintFrame::Frame1) * World[Ref.FindBoneIndex(C.ConstraintBone1)]).GetTranslation();
            const FVector B = (C.GetRefFrame(EConstraintFrame::Frame2) * World[Ref.FindBoneIndex(C.ConstraintBone2)]).GetTranslation();
            if (!TestTrue(TEXT("Authored bent neck preserves locked joint anchors"), FVector::Distance(A, B) < 1.e-5)) return false;
        }
        for (const auto& M : Mappings) Bodies.Add(World[M.BoneIndex]);
        // Deliberately wrong helper pose: the physical neck must win, including when
        // neck_02 was appended after its head child in the PHAT array.
        Local[N2].SetRotation(FRotator(81, 27, -63).Quaternion());
        FProphecyJoltComposedPose Completed;
        if (!Layout.Compose(Local, Bodies, FTransform::Identity, Completed, Error)) { AddError(Error); return false; }
        for (int32 B : {N1, N2, H})
            if (!TestTrue(TEXT("Completed neck is the exact physical pose"), Completed.WorldTransforms[B].Equals(World[B], 1.e-6))) return false;
    }
    return true;
}
#endif
