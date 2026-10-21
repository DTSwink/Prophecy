#include "ProphecyJoltConstraintRuntime.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UObjectIterator.h"

#if !UE_BUILD_SHIPPING
namespace
{
void ConstraintAudit(const TArray<FString>& Args, UWorld* World)
{
    if (!World || !World->IsGameWorld()) return;
    auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto Root = MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (TObjectIterator<UPhysicsConstraintComponent> It; It; ++It)
    {
        auto* C = *It;
        if (C->GetWorld() != World || (!Args.IsEmpty() && !C->GetPathName().Contains(Args[0]))) continue;
        auto Row = MakeShared<FJsonObject>();
        FProphecyJoltJointHandle Joint; FString Error;
        const bool Live = ProphecyJolt::Constraints::GetJoint(C, Joint, Error);
        Row->SetStringField(TEXT("component"), C->GetPathName());
        Row->SetBoolField(TEXT("jolt"), Live); Row->SetStringField(TEXT("error"), Error);
        Row->SetBoolField(TEXT("chaos"), C->ConstraintInstance.IsValidConstraintInstance());
        Row->SetBoolField(TEXT("broken"), C->IsBroken());
        if (Live && Native)
        {
            FProphecyJoltJointSettings Settings; FProphecyJoltBodyState A,B;
            Native->ReadJoint(Joint, Settings);
            Native->ReadBody(Settings.BodyA,A); Native->ReadBody(Settings.BodyB,B);
            const FTransform FrameA = Settings.FrameA * FTransform(A.Rotation,A.PositionCm);
            const FTransform FrameB = Settings.FrameB * FTransform(B.Rotation,B.PositionCm);
            Row->SetNumberField(TEXT("anchor_gap_cm"), FVector::Distance(FrameA.GetLocation(),FrameB.GetLocation()));
            const FVector Travel = FrameA.InverseTransformPosition(FrameB.GetLocation());
            Row->SetStringField(TEXT("travel_cm"), Travel.ToString());
            TArray<TSharedPtr<FJsonValue>> Limits, Rotation;
            for (int32 Axis = 0; Axis < 3; ++Axis)
            {
                auto Limit = MakeShared<FJsonObject>();
                Limit->SetNumberField(TEXT("motion"), int32(Settings.Translation[Axis].Motion));
                Limit->SetNumberField(TEXT("min"), Settings.Translation[Axis].Minimum);
                Limit->SetNumberField(TEXT("max"), Settings.Translation[Axis].Maximum);
                Limit->SetNumberField(TEXT("damping"), Settings.Drives[Axis].Damping);
                Limit->SetBoolField(TEXT("velocity_drive"), Settings.Drives[Axis].bVelocity);
                Limits.Add(MakeShared<FJsonValueObject>(Limit));
                Rotation.Add(MakeShared<FJsonValueNumber>(int32(Settings.Rotation[Axis].Motion)));
            }
            Row->SetArrayField(TEXT("translation"), Limits);
            Row->SetArrayField(TEXT("rotation_motion"), Rotation);
            FVector Force,Torque; Native->ReadJointReaction(Joint,Force,Torque);
            Row->SetNumberField(TEXT("force"),Force.Size()); Row->SetNumberField(TEXT("torque"),Torque.Size());
        }
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    Root->SetArrayField(TEXT("constraints"),Rows);
    FString Json; FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    const FString Directory = FPaths::ProjectSavedDir()/TEXT("Diagnostics/StandardConstraints");
    IFileManager::Get().MakeDirectory(*Directory,true);
    FFileHelper::SaveStringToFile(Json,*(Directory/TEXT("World.json")));
}
FAutoConsoleCommandWithWorldAndArgs ConstraintAuditCommand(TEXT("Prophecy.Jolt.ConstraintAudit"),
    TEXT("On-demand standard constraint native ownership, anchor and reaction audit."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&ConstraintAudit));
}
#endif
