#include "ProphecyNNPhysicalTargetPose.h"

#include "ProphecyNNPoseTypes.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ReferenceSkeleton.h"

namespace ProphecyNNPhysicalTargets
{
namespace
{
bool SameNames(TConstArrayView<FName> A, TConstArrayView<FName> B)
{
    if (A.Num() != B.Num()) return false;
    for (int32 Index = 0; Index < A.Num(); ++Index)
        if (A[Index] != B[Index]) return false;
    return true;
}

struct FCacheEntry
{
    TWeakObjectPtr<const USkeletalMesh> Mesh;
    TWeakObjectPtr<const UPhysicsAsset> PhysicsAsset;
    FLayout Layout;
    uint64 LastUse = 0;
};

// Shared layouts amortize construction across a crowd. Weak identities cannot extend asset lifetime;
// a bounded cache needs no UObject delegates or module shutdown callback. Live values are read below.
TArray<FCacheEntry> GLayouts;
uint64 GLayoutUse = 0;
constexpr int32 MaxCachedLayouts = 64;
}

bool FLayout::HasSourceLayout(TConstArrayView<FName> Names) const
{
    return bInitialized && SameNames(InputSourceNames, Names);
}

bool FLayout::Update(const FReferenceSkeleton& Reference, TConstArrayView<FName> BodyNames,
    TConstArrayView<FName> SourceNames)
{
    bool bMatches = HasSourceLayout(SourceNames) && SameNames(InputBodyNames, BodyNames)
        && ReferenceNames.Num() == Reference.GetNum();
    for (int32 Index = 0; bMatches && Index < Reference.GetNum(); ++Index)
        bMatches = ReferenceNames[Index] == Reference.GetBoneName(Index)
            && Parents[Index] == Reference.GetParentIndex(Index);
    if (bMatches) return false;

    InputSourceNames.Reset(SourceNames.Num());
    InputSourceNames.Append(SourceNames.GetData(), SourceNames.Num());
    InputBodyNames.Reset(BodyNames.Num());
    InputBodyNames.Append(BodyNames.GetData(), BodyNames.Num());
    ReferenceNames.SetNum(Reference.GetNum());
    Parents.SetNum(Reference.GetNum());
    SourceIndices.SetNum(Reference.GetNum());
    for (int32 Index = 0; Index < Reference.GetNum(); ++Index)
    {
        ReferenceNames[Index] = Reference.GetBoneName(Index);
        Parents[Index] = Reference.GetParentIndex(Index);
        // Retain IndexOfByKey's first-match behavior for duplicate NN names.
        SourceIndices[Index] = InputSourceNames.IndexOfByKey(ReferenceNames[Index]);
    }

    TArray<bool, TInlineAllocator<128>> Needed;
    Needed.Init(false, Reference.GetNum());
    TargetNames.Reset(BodyNames.Num());
    TargetIndices.Reset(BodyNames.Num());
    for (const FName Name : BodyNames)
    {
        const int32 Bone = Reference.FindBoneIndex(Name);
        if (Bone == INDEX_NONE) continue;
        TargetNames.Add(Name);
        TargetIndices.Add(Bone);
        // A supplied NN pose is already component-space. Its ancestors are irrelevant unless
        // separately required by another target. Missing bones retain every local*parent step.
        for (int32 Required = Bone; Required != INDEX_NONE && !Needed[Required]; Required = Parents[Required])
        {
            Needed[Required] = true;
            if (SourceIndices[Required] != INDEX_NONE) break;
        }
    }
    NeededBones.Reset(Reference.GetNum());
    for (int32 Index = 0; Index < Reference.GetNum(); ++Index)
        if (Needed[Index]) NeededBones.Add(Index);
    bInitialized = true;
    return true;
}

bool FLayout::Evaluate(const FReferenceSkeleton& Reference, const FProphecyNNPoseSnapshot& Pose,
    TArray<FName>& OutNames, TArray<FTransform>& OutFuture, TArray<FTransform>& OutPrevious) const
{
    ProphecyJolt::CharacterProfiling::FScope EndpointTiming(ProphecyJolt::CharacterProfiling::EPhase::TargetEndpointExpand);
    OutNames.Reset(); OutFuture.Reset(); OutPrevious.Reset();
    if (!bInitialized || Pose.PreviousComponentTransforms.Num() != InputSourceNames.Num()
        || Pose.ComponentTransforms.Num() != InputSourceNames.Num()
        || Reference.GetRefBonePose().Num() != ReferenceNames.Num()) return false;

    TArray<FTransform, TInlineAllocator<128>> PreviousWorld, FutureWorld;
    PreviousWorld.SetNumUninitialized(ReferenceNames.Num());
    FutureWorld.SetNumUninitialized(ReferenceNames.Num());
    const TArray<FTransform>& LocalPose = Reference.GetRefBonePose();
    auto Expand = [&](const TArray<FTransform>& Source, const FTransform& ComponentWorld,
        TArray<FTransform, TInlineAllocator<128>>& Out)
    {
        // Keep the original ascending traversal and literal multiply order, including scale.
        for (const int32 Bone : NeededBones)
        {
            const int32 SourceIndex = SourceIndices[Bone];
            if (Source.IsValidIndex(SourceIndex))
                Out[Bone] = Source[SourceIndex] * ComponentWorld;
            else
                Out[Bone] = Parents[Bone] != INDEX_NONE
                    ? LocalPose[Bone] * Out[Parents[Bone]] : LocalPose[Bone] * ComponentWorld;
        }
    };
    Expand(Pose.PreviousComponentTransforms, Pose.PreviousComponentWorldTransform, PreviousWorld);
    Expand(Pose.ComponentTransforms, Pose.ComponentWorldTransform, FutureWorld);
    OutNames.Append(TargetNames);
    OutFuture.Reserve(TargetIndices.Num()); OutPrevious.Reserve(TargetIndices.Num());
    for (const int32 Bone : TargetIndices)
    {
        OutFuture.Add(FutureWorld[Bone]);
        OutPrevious.Add(PreviousWorld[Bone]);
    }
    return OutNames.Num() > 0;
}

bool BuildWorldPoses(const USkeletalMesh& Mesh, const UPhysicsAsset& PhysicsAsset,
    const FProphecyNNPoseSnapshot& Pose, TArray<FName>& OutNames,
    TArray<FTransform>& OutFuture, TArray<FTransform>& OutPrevious)
{
    check(IsInGameThread());
    TArray<FName, TInlineAllocator<32>> BodyNames;
    BodyNames.Reserve(PhysicsAsset.SkeletalBodySetups.Num());
    for (const USkeletalBodySetup* Body : PhysicsAsset.SkeletalBodySetups)
        if (Body) BodyNames.Add(Body->BoneName);

    FCacheEntry* Entry = GLayouts.FindByPredicate([&](const FCacheEntry& Candidate)
    {
        return Candidate.Mesh.Get() == &Mesh && Candidate.PhysicsAsset.Get() == &PhysicsAsset
            && Candidate.Layout.HasSourceLayout(Pose.BoneNames);
    });
    if (!Entry)
    {
        for (int32 Index = GLayouts.Num() - 1; Index >= 0; --Index)
            if (!GLayouts[Index].Mesh.IsValid() || !GLayouts[Index].PhysicsAsset.IsValid())
                GLayouts.RemoveAtSwap(Index, 1, EAllowShrinking::No);
        if (GLayouts.Num() == MaxCachedLayouts)
        {
            int32 Oldest = 0;
            for (int32 Index = 1; Index < GLayouts.Num(); ++Index)
                if (GLayouts[Index].LastUse < GLayouts[Oldest].LastUse) Oldest = Index;
            GLayouts.RemoveAtSwap(Oldest, 1, EAllowShrinking::No);
        }
        Entry = &GLayouts.AddDefaulted_GetRef();
        Entry->Mesh = &Mesh;
        Entry->PhysicsAsset = &PhysicsAsset;
    }
    Entry->LastUse = ++GLayoutUse;
    Entry->Layout.Update(Mesh.GetRefSkeleton(), BodyNames, Pose.BoneNames);
    return Entry->Layout.Evaluate(Mesh.GetRefSkeleton(), Pose, OutNames, OutFuture, OutPrevious);
}
}
