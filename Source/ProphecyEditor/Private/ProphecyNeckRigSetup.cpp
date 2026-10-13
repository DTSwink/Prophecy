#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/SkeletalMesh.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ScopedTransaction.h"
#include "Serialization/JsonSerializer.h"

// One-time, explicit PHAT authoring. No runtime substitutes for the missing neck bone.
namespace ProphecyNeckRigSetup
{
constexpr TCHAR AssetPath[] = TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin");
constexpr TCHAR MeshPath[] = TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin");

void Run(const TArray<FString>& Args)
{
    const bool Apply = Args.Num() == 1 && Args[0] == TEXT("Apply");
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const auto Work = [&]() -> bool
    {
        if (!GEditor || GEditor->PlayWorld || !IsInGameThread())
        { Error = TEXT("Stop Play before inspecting or editing the neck PHAT."); return false; }
        auto* Asset = LoadObject<UPhysicsAsset>(nullptr, AssetPath);
        auto* Mesh = LoadObject<USkeletalMesh>(nullptr, MeshPath);
        if (!Asset || !Mesh) { Error = TEXT("Original PHAT or mannequin missing."); return false; }
        const auto& Skeleton = Mesh->GetRefSkeleton();
        const int32 N1 = Skeleton.FindBoneIndex(TEXT("neck_01"));
        const int32 N2 = Skeleton.FindBoneIndex(TEXT("neck_02"));
        const int32 H = Skeleton.FindBoneIndex(TEXT("head"));
        const int32 LowerBody = Asset->FindBodyIndex(TEXT("neck_01"));
        const int32 UpperBody = Asset->FindBodyIndex(TEXT("neck_02"));
        const int32 HeadJoint = Asset->FindConstraintIndex(TEXT("UserConstraint_10"));
        if (N1 < 0 || N2 < 0 || H < 0 || Skeleton.GetParentIndex(N2) != N1 || Skeleton.GetParentIndex(H) != N2
            || LowerBody < 0 || HeadJoint < 0 || Asset->FindBodyIndex(TEXT("head")) < 0
            || Asset->FindBodyIndex(TEXT("clavicle_l")) < 0 || Asset->FindBodyIndex(TEXT("clavicle_r")) < 0)
        { Error = TEXT("Expected mannequin neck hierarchy or existing PHAT identities missing."); return false; }
        auto* Lower = Asset->SkeletalBodySetups[LowerBody].Get();
        auto* Head = Asset->ConstraintSetup[HeadJoint].Get();
        const bool Already = UpperBody != INDEX_NONE;
        if (Head->DefaultInstance.ConstraintBone1 != TEXT("head")
            || Head->DefaultInstance.ConstraintBone2 != (Already ? TEXT("neck_02") : TEXT("neck_01"))
            || (Already && Asset->FindConstraintIndex(TEXT("neck_02"), TEXT("neck_01")) == INDEX_NONE))
        { Error = TEXT("Unexpected neck joints; refusing a partial or unrelated migration."); return false; }

        Report->SetNumberField(TEXT("bodies_before"), Asset->SkeletalBodySetups.Num());
        Report->SetNumberField(TEXT("joints_before"), Asset->ConstraintSetup.Num());
        Report->SetBoolField(TEXT("already_has_neck_02"), Already);
        Report->SetStringField(TEXT("neck_02_reference_local"), Skeleton.GetRefBonePose()[N2].ToString());
        Report->SetStringField(TEXT("head_reference_local"), Skeleton.GetRefBonePose()[H].ToString());
        Report->SetNumberField(TEXT("neck_01_mass_kg"), Lower->CalculateMass());

        USkeletalBodySetup* Candidate = nullptr;
        const float OriginalNeckMass = Lower->CalculateMass();
        if (!Already)
        {
            if (Lower->AggGeom.GetElementCount() != 1 || Lower->AggGeom.SphylElems.Num() != 1
                || !FMath::IsFinite(OriginalNeckMass) || OriginalNeckMass <= 0)
            { Error = TEXT("Expected the original single neck capsule with positive mass."); return false; }
            Candidate = DuplicateObject<USkeletalBodySetup>(Lower, GetTransientPackage());
            Candidate->BoneName = TEXT("neck_02");
            auto& Shape = Candidate->AggGeom.SphylElems[0];
            const FVector HeadOffset = Skeleton.GetRefBonePose()[H].GetTranslation();
            Shape.Center = HeadOffset * .5;
            Shape.Rotation = FQuat::FindBetweenNormals(FVector::UpVector, HeadOffset.GetSafeNormal()).Rotator();
            Shape.SetName(TEXT("neck_02_capsule"));
            // User-approved fit: existing capsule size, half the original neck mass each.
            Candidate->DefaultInstance.SetMassOverride(OriginalNeckMass * .5f);
            Report->SetNumberField(TEXT("capsule_radius_cm"), Shape.Radius);
            Report->SetNumberField(TEXT("capsule_length_cm"), Shape.Length);
            Report->SetStringField(TEXT("capsule_transform"), Shape.GetTransform().ToString());
            Report->SetNumberField(TEXT("neck_02_mass_kg"), Candidate->CalculateMass());
        }
        if (!Apply) return true;

        const FScopedTransaction Transaction(NSLOCTEXT("Prophecy", "NeckRig", "Match physical neck to skeleton"));
        Asset->Modify();
        if (!Already)
        {
            Lower->Modify();
            Lower->DefaultInstance.SetMassOverride(OriginalNeckMass * .5f);
            // Append: all pre-existing body/joint indices and user profiles keep their identities.
            auto* Upper = DuplicateObject<USkeletalBodySetup>(Candidate, Asset, TEXT("Neck02Body"));
            Upper->SetFlags(RF_Transactional);
            const int32 NewIndex = Asset->SkeletalBodySetups.Add(Upper);
            auto* Joint = DuplicateObject<UPhysicsConstraintTemplate>(Head, Asset, TEXT("Neck02Constraint"));
            Joint->SetFlags(RF_Transactional);
            auto& CI = Joint->DefaultInstance;
            CI.JointName = TEXT("neck_02");
            CI.ConstraintBone1 = TEXT("neck_02");
            CI.ConstraintBone2 = TEXT("neck_01");
            CI.SetRefFrame(EConstraintFrame::Frame1, FTransform::Identity);
            CI.SetRefFrame(EConstraintFrame::Frame2, Skeleton.GetRefBonePose()[N2]);
            Joint->SetDefaultProfile(CI);
            Asset->ConstraintSetup.Add(Joint);
            Head->Modify();
            Head->DefaultInstance.ConstraintBone2 = TEXT("neck_02");
            // Preserve the head-side frame and express that same joint in its actual parent bone.
            Head->DefaultInstance.SetRefFrame(EConstraintFrame::Frame2,
                Head->DefaultInstance.GetRefFrame(EConstraintFrame::Frame1) * Skeleton.GetRefBonePose()[H]);
            // Keep the old neck's self-collision exclusions for the new neck section.
            const auto Disabled = Asset->CollisionDisableTable;
            for (const auto& Pair : Disabled)
            {
                if (Pair.Key.Indices[0] == LowerBody) Asset->DisableCollision(NewIndex, Pair.Key.Indices[1]);
                if (Pair.Key.Indices[1] == LowerBody) Asset->DisableCollision(NewIndex, Pair.Key.Indices[0]);
            }
            Asset->UpdateBodySetupIndexMap();
            Upper->InvalidatePhysicsData();
            Upper->CreatePhysicsMeshes();
        }
        // User-requested permanent neck exclusions; shared by Chaos and the Jolt importer.
        for (FName Neck : {FName(TEXT("neck_01")), FName(TEXT("neck_02"))})
            for (FName Other : {FName(TEXT("head")), FName(TEXT("clavicle_l")), FName(TEXT("clavicle_r")), FName(TEXT("neck_01"))})
                if (Neck != Other) Asset->DisableCollision(Asset->FindBodyIndex(Neck), Asset->FindBodyIndex(Other));
        Asset->UpdateBoundsBodiesArray();
        Asset->MarkPackageDirty();
        Asset->RefreshPhysicsAssetChange();
        Report->SetNumberField(TEXT("bodies_after"), Asset->SkeletalBodySetups.Num());
        Report->SetNumberField(TEXT("joints_after"), Asset->ConstraintSetup.Num());
        return true;
    };
    Report->SetBoolField(TEXT("success"), Work());
    Report->SetBoolField(TEXT("applied"), Apply && Error.IsEmpty());
    Report->SetStringField(TEXT("error"), Error);
    FString Json;
    FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
    const FString Path = FPaths::ProjectSavedDir() / TEXT("Diagnostics/NeckRig20261013/asset-report.json");
    FFileHelper::SaveStringToFile(Json, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    UE_LOG(LogTemp, Display, TEXT("Neck rig: %s"), *Json);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.NeckRig"), TEXT("Inspect or Apply the physical neck chain; does not save assets."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Run));
}
