#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "ProphecyNNPhysicalTargetPose.h"
#include "ProphecyNNPoseTypes.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ReferenceSkeleton.h"
#include "UObject/Package.h"
#include "UObject/StrongObjectPtr.h"

namespace ProphecyNNPhysicalTargets::Tests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

FTransform RandomTransform(FRandomStream& Random)
{
    const FQuat Rotation = FRotator(Random.FRandRange(-170.f, 170.f),
        Random.FRandRange(-170.f, 170.f), Random.FRandRange(-170.f, 170.f)).Quaternion();
    return FTransform(Rotation, FVector(Random.FRandRange(-200.f, 200.f),
        Random.FRandRange(-200.f, 200.f), Random.FRandRange(-200.f, 200.f)),
        FVector(Random.FRandRange(.6f, 1.5f), Random.FRandRange(.6f, 1.5f), Random.FRandRange(.6f, 1.5f)));
}

FReferenceSkeleton MakeReference(bool bAlternateParent = false)
{
    FReferenceSkeleton Result;
    FRandomStream Random(42117);
    {
        FReferenceSkeletonModifier Modifier(Result, nullptr);
        for (int32 Index = 0; Index < 88; ++Index)
        {
            FName Name(*FString::Printf(TEXT("test_%02d"), Index));
            if (Index == 2) Name = TEXT("lowerarm_l");
            if (Index == 3) Name = TEXT("hand_l");
            if (Index == 5) Name = TEXT("lowerarm_r");
            if (Index == 6) Name = TEXT("hand_r");
            int32 Parent = Index == 0 ? INDEX_NONE : (Index - 1) / 2;
            if (Index == 3) Parent = 2;
            if (Index == 6) Parent = 5;
            if (Index == 8 && bAlternateParent) Parent = 0;
            Modifier.Add(FMeshBoneInfo(Name, Name.ToString(), Parent), RandomTransform(Random));
        }
    }
    return Result;
}

TArray<FName> BodyNames(const FReferenceSkeleton& Reference)
{
    TArray<FName> Result = {TEXT("lowerarm_l"), TEXT("hand_l"), TEXT("lowerarm_r"), TEXT("hand_r")};
    for (int32 Index = 8; Result.Num() < 22; Index += 4) Result.Add(Reference.GetBoneName(Index));
    return Result;
}

FProphecyNNPoseSnapshot MakePose(const FReferenceSkeleton& Reference, int32 Seed, int32 Layout)
{
    FProphecyNNPoseSnapshot Result;
    FRandomStream Random(Seed);
    for (int32 Index = 0; Index < Reference.GetNum(); ++Index)
    {
        if (Layout == 1 && Index % 3 == 0) continue;
        if (Layout == 2) continue; // All reference-local fallback, including the root.
        Result.BoneNames.Add(Reference.GetBoneName(Index));
    }
    if (Layout == 3)
    {
        // A reordered source and duplicate with a different transform exercise first-name semantics.
        for (int32 Index = 0; Index < Result.BoneNames.Num() / 2; ++Index)
            Result.BoneNames.Swap(Index, Result.BoneNames.Num() - 1 - Index);
        Result.BoneNames.Insert(TEXT("hand_l"), 0);
        Result.BoneNames.Add(TEXT("not_in_reference"));
    }
    for (int32 Index = 0; Index < Result.BoneNames.Num(); ++Index)
    {
        Result.LocalTransforms.Add(RandomTransform(Random));
        Result.PreviousComponentTransforms.Add(RandomTransform(Random));
        Result.ComponentTransforms.Add(RandomTransform(Random));
    }
    Result.PreviousComponentWorldTransform = RandomTransform(Random);
    Result.ComponentWorldTransform = RandomTransform(Random);
    if (Seed % 2 == 0)
        Result.ComponentWorldTransform.SetScale3D(FVector(-1.1, .8, 1.3));
    Result.BoneLayoutHash = 17; // Deliberately identical across different layouts; no hash-only validity.
    Result.Revision = 1;
    Result.bHasComponentWorldTransform = true;
    return Result;
}

// Frozen original full-skeleton algorithm, deliberately independent of FLayout and its dependencies.
void Legacy(const FReferenceSkeleton& Reference, TConstArrayView<FName> Bodies,
    const FProphecyNNPoseSnapshot& Pose, TArray<FName>& Names,
    TArray<FTransform>& FutureTargets, TArray<FTransform>& PreviousTargets)
{
    Names.Reset(); FutureTargets.Reset(); PreviousTargets.Reset();
    TArray<FTransform> Previous, Future;
    Previous.SetNumUninitialized(Reference.GetNum()); Future.SetNumUninitialized(Reference.GetNum());
    auto Expand = [&](const TArray<FTransform>& Source, const FTransform& World, TArray<FTransform>& Out)
    {
        for (int32 Bone = 0; Bone < Reference.GetNum(); ++Bone)
        {
            const int32 SourceIndex = Pose.BoneNames.IndexOfByKey(Reference.GetBoneName(Bone));
            if (Source.IsValidIndex(SourceIndex)) { Out[Bone] = Source[SourceIndex] * World; continue; }
            const int32 Parent = Reference.GetParentIndex(Bone);
            Out[Bone] = Parent != INDEX_NONE ? Reference.GetRefBonePose()[Bone] * Out[Parent]
                : Reference.GetRefBonePose()[Bone] * World;
        }
    };
    Expand(Pose.PreviousComponentTransforms, Pose.PreviousComponentWorldTransform, Previous);
    Expand(Pose.ComponentTransforms, Pose.ComponentWorldTransform, Future);
    for (const FName Name : Bodies)
    {
        const int32 Bone = Reference.FindBoneIndex(Name);
        if (!Previous.IsValidIndex(Bone) || !Future.IsValidIndex(Bone)) continue;
        Names.Add(Name); FutureTargets.Add(Future[Bone]); PreviousTargets.Add(Previous[Bone]);
    }
}

bool ExactlySame(const FTransform& A, const FTransform& B)
{
    const FQuat X = A.GetRotation(), Y = B.GetRotation();
    return X.X == Y.X && X.Y == Y.Y && X.Z == Y.Z && X.W == Y.W
        && A.GetTranslation() == B.GetTranslation() && A.GetScale3D() == B.GetScale3D();
}

// Frozen Agent interpolation; production keeps using the existing Agent implementation.
FTransform Blend(const FTransform& A, const FTransform& B, float Alpha)
{
    FQuat Start = A.GetRotation().GetNormalized(), End = B.GetRotation().GetNormalized();
    float CosHalfAngle = Start | End;
    if (CosHalfAngle < 0.f) { End = End * -1.f; CosHalfAngle = -CosHalfAngle; }
    CosHalfAngle = FMath::Clamp(CosHalfAngle, 0.f, 1.f);
    const float Angle = 2.f * FMath::Acos(CosHalfAngle);
    FQuat Rotation = Start;
    if (Angle > 1.e-6f)
    {
        const float WeightedAngle = FMath::Atan2(Alpha * FMath::Sin(Angle),
            (1.f - Alpha) + Alpha * FMath::Cos(Angle));
        Rotation = FQuat::Slerp(Start, End, WeightedAngle / Angle);
        Rotation.Normalize();
    }
    return FTransform(Rotation, FMath::Lerp(A.GetLocation(), B.GetLocation(), Alpha), FVector::OneVector);
}

bool Compare(FAutomationTestBase& Test, FLayout& Layout, const FReferenceSkeleton& Reference,
    TConstArrayView<FName> Bodies, const FProphecyNNPoseSnapshot& Pose)
{
    Layout.Update(Reference, Bodies, Pose.BoneNames);
    TArray<FName> ActualNames, ExpectedNames;
    TArray<FTransform> ActualFuture, ActualPrevious, ExpectedFuture, ExpectedPrevious;
    const bool Result = Layout.Evaluate(Reference, Pose, ActualNames, ActualFuture, ActualPrevious);
    Legacy(Reference, Bodies, Pose, ExpectedNames, ExpectedFuture, ExpectedPrevious);
    if (!Test.TestEqual(TEXT("Same success and complete target names"), Result, ExpectedNames.Num() > 0)
        || !Test.TestTrue(TEXT("Exact target order and duplicate names"), ActualNames == ExpectedNames)) return false;
    for (int32 Index = 0; Index < ActualNames.Num(); ++Index)
        if (!Test.TestTrue(TEXT("Exact previous target components"), ExactlySame(ActualPrevious[Index], ExpectedPrevious[Index]))
            || !Test.TestTrue(TEXT("Exact future target components"), ExactlySame(ActualFuture[Index], ExpectedFuture[Index]))) return false;
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySparseTargetsOracle,
    "Prophecy.NN.PhysicalTargets.SparseMatchesFullTraversal", ProphecyNNPhysicalTargets::Tests::Flags)
bool FProphecySparseTargetsOracle::RunTest(const FString&)
{
    using namespace ProphecyNNPhysicalTargets;
    using namespace ProphecyNNPhysicalTargets::Tests;
    FReferenceSkeleton Reference = MakeReference();
    TArray<FName> Bodies = BodyNames(Reference);
    FLayout Layout;
    for (int32 Seed = 1; Seed <= 32; ++Seed)
        for (int32 Variant = 0; Variant < 4; ++Variant)
        {
            const FProphecyNNPoseSnapshot Pose = MakePose(Reference, Seed, Variant);
            if (!Compare(*this, Layout, Reference, Bodies, Pose)) return false;
            if (Variant == 0) TestEqual(TEXT("22 supplied body bones need only 22 world multiplications per endpoint"),
                Layout.GetEvaluatedBoneCount(), 22);
            TestFalse(TEXT("Unchanged layout reuses indices"), Layout.Update(Reference, Bodies, Pose.BoneNames));
        }
    // Preserve missing-body skips, PHAT order and duplicate outputs.
    Bodies.Insert(TEXT("missing_phat_bone"), 2);
    const FName DuplicateBody = Bodies[0];
    Bodies.Add(DuplicateBody); Bodies.Swap(0, 8);
    return Compare(*this, Layout, Reference, Bodies, MakePose(Reference, 95, 1));
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySparseTargetsEdits,
    "Prophecy.NN.PhysicalTargets.SourceReferenceAndAssetChanges", ProphecyNNPhysicalTargets::Tests::Flags)
bool FProphecySparseTargetsEdits::RunTest(const FString&)
{
    using namespace ProphecyNNPhysicalTargets;
    using namespace ProphecyNNPhysicalTargets::Tests;
    FReferenceSkeleton Reference = MakeReference();
    TArray<FName> Bodies = BodyNames(Reference);
    FProphecyNNPoseSnapshot Pose = MakePose(Reference, 41, 2);
    FLayout Layout;
    if (!Compare(*this, Layout, Reference, Bodies, Pose)) return false;
    {
        FReferenceSkeletonModifier Modifier(Reference, nullptr);
        Modifier.UpdateRefPoseTransform(0, FTransform(FRotator(21, 33, 7), FVector(101, -55, 9), FVector(.7, 1.1, 1.4)));
    }
    TestFalse(TEXT("Ref values do not rebuild indices"), Layout.Update(Reference, Bodies, Pose.BoneNames));
    if (!Compare(*this, Layout, Reference, Bodies, Pose)) return false;
    Reference = MakeReference(true);
    TestTrue(TEXT("Changed parent invalidates cached topology"), Layout.Update(Reference, Bodies, Pose.BoneNames));
    if (!Compare(*this, Layout, Reference, Bodies, Pose)) return false;

    TStrongObjectPtr<USkeletalMesh> Mesh(NewObject<USkeletalMesh>(GetTransientPackage()));
    TStrongObjectPtr<USkeletalMesh> OtherMesh(NewObject<USkeletalMesh>(GetTransientPackage()));
    TStrongObjectPtr<UPhysicsAsset> Asset(NewObject<UPhysicsAsset>(GetTransientPackage()));
    TStrongObjectPtr<UPhysicsAsset> OtherAsset(NewObject<UPhysicsAsset>(GetTransientPackage()));
    Mesh->SetRefSkeleton(Reference); OtherMesh->SetRefSkeleton(MakeReference());
    for (const FName Name : Bodies)
    {
        USkeletalBodySetup* Body = NewObject<USkeletalBodySetup>(Asset.Get());
        Body->BoneName = Name; Asset->SkeletalBodySetups.Add(Body);
    }
    Asset->SkeletalBodySetups.Insert(nullptr, 3);
    USkeletalBodySetup* OtherBody = NewObject<USkeletalBodySetup>(OtherAsset.Get());
    OtherBody->BoneName = Bodies[4]; OtherAsset->SkeletalBodySetups.Add(OtherBody);
    auto CheckAssets = [&](const USkeletalMesh& CurrentMesh, const UPhysicsAsset& CurrentAsset)
    {
        TArray<FName> CurrentBodies, ActualNames, ExpectedNames;
        TArray<FTransform> AF, AP, EF, EP;
        for (const USkeletalBodySetup* Body : CurrentAsset.SkeletalBodySetups)
            if (Body) CurrentBodies.Add(Body->BoneName);
        BuildWorldPoses(CurrentMesh, CurrentAsset, Pose, ActualNames, AF, AP);
        Legacy(CurrentMesh.GetRefSkeleton(), CurrentBodies, Pose, ExpectedNames, EF, EP);
        if (!TestTrue(TEXT("Weak asset identity and null body rows preserve names"), ActualNames == ExpectedNames)) return false;
        for (int32 Index = 0; Index < AF.Num(); ++Index)
            if (!TestTrue(TEXT("Each asset uses its own live reference values"), ExactlySame(AF[Index], EF[Index]) && ExactlySame(AP[Index], EP[Index]))) return false;
        return true;
    };
    if (!CheckAssets(*Mesh, *Asset) || !CheckAssets(*OtherMesh, *Asset) || !CheckAssets(*Mesh, *OtherAsset)) return false;
    Asset->SkeletalBodySetups[0]->BoneName = Reference.GetBoneName(87);
    Asset->SkeletalBodySetups.Swap(0, 7);
    Mesh->SetRefSkeleton(MakeReference());
    return CheckAssets(*Mesh, *Asset);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySparseTargetsForearms,
    "Prophecy.NN.PhysicalTargets.InterpolationAndRigidForearms", ProphecyNNPhysicalTargets::Tests::Flags)
bool FProphecySparseTargetsForearms::RunTest(const FString&)
{
    using namespace ProphecyNNPhysicalTargets;
    using namespace ProphecyNNPhysicalTargets::Tests;
    constexpr int32 AgentId = 1900000027;
    struct FClearPose { int32 Id; ~FClearPose() { FProphecyNNPoseStore::ClearAgentPose(Id); } } ClearPose{AgentId};
    const FReferenceSkeleton Reference = MakeReference();
    const TArray<FName> Bodies = BodyNames(Reference);
    FLayout Layout;
    for (const bool bRigid : {false, true})
        for (const float Alpha : {0.f, .001f, .25f, .5f, .999f, 1.f})
        {
            const FProphecyNNPoseSnapshot Input = MakePose(Reference, 28, 0);
            FProphecyNNPoseStore::SetAgentLocalPose(AgentId, Input.BoneNames, Input.LocalTransforms,
                Input.PreviousComponentTransforms, Input.ComponentTransforms,
                Input.PreviousComponentWorldTransform, Input.ComponentWorldTransform, 1.0, bRigid);
            FProphecyNNPoseSnapshot Pose;
            if (!TestTrue(TEXT("Published oracle snapshot"), FProphecyNNPoseStore::GetAgentLocalPose(AgentId, Pose))) return false;
            Layout.Update(Reference, Bodies, Pose.BoneNames);
            TArray<FName> AN, EN;
            TArray<FTransform> AF, AP, EF, EP;
            Layout.Evaluate(Reference, Pose, AN, AF, AP); Legacy(Reference, Bodies, Pose, EN, EF, EP);
            for (int32 Index = 0; Index < AP.Num(); ++Index)
            {
                AP[Index] = Blend(AP[Index], AF[Index], Alpha);
                EP[Index] = Blend(EP[Index], EF[Index], Alpha);
            }
            FProphecyNNPoseStore::ApplyRigidForearms(AgentId, Pose, AN, AP);
            FProphecyNNPoseStore::ApplyRigidForearms(AgentId, Pose, EN, EP);
            for (int32 Index = 0; Index < AP.Num(); ++Index)
                if (!TestTrue(TEXT("Complete interpolated targets after actual rigid forearms"), ExactlySame(AP[Index], EP[Index]))) return false;
        }
    return true;
}

#endif
