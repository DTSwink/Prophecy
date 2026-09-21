#include "ProphecyPhysicalProfileLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyJointDampingPolicy.h"
#include "ProphecyClampProfiles.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Kismet/KismetSystemLibrary.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

FString UProphecyPhysicalProfileLibrary::PrintPhysicalBoneProfiles(
    AProphecyAgent* Agent, float Duration, FLinearColor TextColor)
{
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
    if (!IsValid(Agent)) return {};
    const USkeletalMeshComponent* Mesh = Agent->GetPoseReferenceMesh();
    const UPhysicsAsset* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
    const USkeletalMesh* Skeleton = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
    if (!Asset || !Skeleton) return {};

    // Reference height gives a stable anatomical order even while kicking or falling.
    const FReferenceSkeleton& Ref = Skeleton->GetRefSkeleton();
    TArray<FTransform> ReferencePose = Ref.GetRefBonePose();
    for (int32 Index = 0; Index < ReferencePose.Num(); ++Index)
    {
        const int32 Parent = Ref.GetParentIndex(Index);
        if (Parent != INDEX_NONE) ReferencePose[Index] *= ReferencePose[Parent];
    }
    struct FRow { FName Bone; double Height; };
    TArray<FRow> Rows;
    TSet<FName> Seen;
    for (const USkeletalBodySetup* Body : Asset->SkeletalBodySetups)
    {
        if (!Body || Body->BoneName.IsNone() || Seen.Contains(Body->BoneName)) continue;
        const int32 Index = Ref.FindBoneIndex(Body->BoneName);
        if (Index == INDEX_NONE) continue;
        Seen.Add(Body->BoneName);
        Rows.Add({Body->BoneName, ReferencePose[Index].GetTranslation().Z});
    }
    Rows.Sort([](const FRow& A, const FRow& B)
    {
        return A.Height == B.Height ? A.Bone.LexicalLess(B.Bone) : A.Height > B.Height;
    });

    FString Text;
    for (const FRow& Row : Rows)
    {
        FProphecyBodyMagnetizationSettings Magnet;
        Agent->GetBodyMagnetizationSettings(Row.Bone, Magnet);
        const bool Enabled = Agent->bWorldMagnetizationEnabled &&
            Magnet.bSimulateBody && Magnet.bMagnetizationEnabled;
        const float Linear = Enabled ? FMath::Max(0.f, Agent->WorldMagnetizationLinearStrengthScale * Magnet.LinearStrengthScale) : 0.f;
        const float Angular = Enabled ? FMath::Max(0.f, Agent->WorldMagnetizationAngularStrengthScale * Magnet.AngularStrengthScale) : 0.f;
        FProphecyPhysicalFeedbackToleranceSettings Tolerance;
        const FString ToleranceText = Agent->GetPhysicalFeedbackTolerance(Row.Bone, Tolerance)
            ? FString::Printf(TEXT("L=%.2f A=%.2f"), Tolerance.LinearToleranceCm, Tolerance.AngularToleranceDegrees)
            : TEXT("n/a");
        if (!Text.IsEmpty()) Text += TEXT("\n");
        float Damping;
        const FString DampingText=ProphecyJointDamping::Get(Agent,Row.Bone,Damping)
            ? FString::Printf(TEXT("%.2f"),Damping) : TEXT("n/a");
        Text += FString::Printf(TEXT("%s : L=%.2f A=%.2f / %s / D=%s"), *Row.Bone.ToString(), Linear, Angular, *ToleranceText,*DampingText);
        Text += ProphecyClampProfiles::Debug(Agent,Row.Bone);
    }
    if (!Text.IsEmpty())
    {
        // A single keyed block preserves head-to-feet order and cannot pile up on Tick.
        const FName Key(*FString::Printf(TEXT("ProphecyPhysicalProfiles_%u"), Agent->GetUniqueID()));
        UKismetSystemLibrary::PrintString(Agent, Text, true, false, TextColor,
            FMath::IsFinite(Duration) ? FMath::Max(0.f, Duration) : 0.f, Key);
    }
    return Text;
#else
    return {};
#endif
}
