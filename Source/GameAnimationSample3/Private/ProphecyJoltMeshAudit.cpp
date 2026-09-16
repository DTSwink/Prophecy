#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltBodyComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "PhysicsEngine/BodyInstance.h"
#include "UObject/UObjectIterator.h"

namespace
{
void Audit(const TArray<FString>& Args, UWorld* World)
{
    if (!World || !World->IsGameWorld()) return;
    auto* Scene = UProphecyJoltSceneCollisionComponent::FindForWorld(World);
    auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("world"), World->GetPathName());
    Root->SetStringField(TEXT("scene_error"), Scene ? Scene->GetLastError() : TEXT("No Jolt scene owner"));
    auto* Coordinator = World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    Root->SetBoolField(TEXT("shared_stopped"), Coordinator && Coordinator->IsSteppingStopped());
    Root->SetStringField(TEXT("shared_error"), Coordinator ? Coordinator->GetLastError() : TEXT("No coordinator"));
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (Native && Native->GetDiagnostics(Diagnostics).IsSuccess()) Root->SetNumberField(TEXT("completed_steps"), double(Diagnostics.CompletedSteps));
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (TObjectIterator<UStaticMeshComponent> It; It; ++It)
    {
        auto* Mesh = *It;
        if (Mesh->GetWorld() != World || !Mesh->IsRegistered() || (!Args.IsEmpty() && !Mesh->GetPathName().Contains(Args[0]))) continue;
        auto Row = MakeShared<FJsonObject>();
        FProphecyJoltBodyHandle Body; FProphecyJoltBodyState State;
        const bool bNative = Scene && Scene->GetBodyHandle(*Mesh, INDEX_NONE, Body)
            && Native && Native->ReadBody(Body, State).IsSuccess();
        Row->SetStringField(TEXT("component"), Mesh->GetPathName());
        TInlineComponentArray<UProphecyJoltBodyComponent*> Adapters(Mesh->GetOwner());
        int32 ActiveOwners=0, PendingOwners=0;
        for (const auto* Adapter : Adapters) if (Adapter->GetSourceComponent() == Mesh)
        { ActiveOwners += Adapter->IsJoltBody() ? 1 : 0; PendingOwners += Adapter->IsEnablePending() ? 1 : 0; }
        Row->SetNumberField(TEXT("active_owners"), ActiveOwners);
        Row->SetNumberField(TEXT("pending_owners"), PendingOwners);
        Row->SetBoolField(TEXT("jolt"), bNative);
        Row->SetBoolField(TEXT("jolt_dynamic"), bNative && State.bDynamic);
        Row->SetBoolField(TEXT("chaos_simulating"), Mesh->IsSimulatingPhysics());
        Row->SetNumberField(TEXT("collision_enabled"), int32(Mesh->GetCollisionEnabled()));
        Row->SetNumberField(TEXT("mobility"), int32(Mesh->Mobility));
        Row->SetStringField(TEXT("component_position"), Mesh->GetComponentLocation().ToString());
        if (bNative) Row->SetStringField(TEXT("body_position"), State.PositionCm.ToString());
        if (const auto* BI = Mesh->GetBodyInstance(NAME_None, false)) Row->SetBoolField(TEXT("welded_in_chaos"), BI->WeldParent != nullptr);
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    Root->SetArrayField(TEXT("meshes"), Rows);
    FString Json; FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Json));
    const FString Directory = FPaths::ProjectSavedDir() / TEXT("Diagnostics/DefaultJoltMeshes");
    IFileManager::Get().MakeDirectory(*Directory, true);
    FFileHelper::SaveStringToFile(Json, *(Directory / TEXT("World.json")));
    UE_LOG(LogTemp, Display, TEXT("Jolt mesh audit: %d components, scene error '%s'. Saved Diagnostics/DefaultJoltMeshes/World.json"), Rows.Num(), *Root->GetStringField(TEXT("scene_error")));
}
FAutoConsoleCommandWithWorldAndArgs AuditCommand(TEXT("Prophecy.Jolt.MeshAudit"),
    TEXT("On-demand mesh backend audit; optional component path substring. No tick work."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&Audit));
#if !UE_BUILD_SHIPPING
FAutoConsoleCommandWithWorldAndArgs DropKeyCommand(TEXT("Prophecy.Sword.DebugDropKey"),
    TEXT("Inject Right Shift through the player input path. Argument: press or release. Development audit only."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    {
        if (!World || !World->IsGameWorld() || Args.Num()!=1) return;
        auto* Controller=World->GetFirstPlayerController();
        if (!Controller || (Args[0]!=TEXT("press") && Args[0]!=TEXT("release"))) return;
        const bool Pressed=Args[0]==TEXT("press");
        Controller->InputKey(FInputKeyEventArgs(nullptr, INPUTDEVICEID_NONE, EKeys::RightShift,
            Pressed ? IE_Pressed : IE_Released, Pressed ? 1.f : 0.f, false, FPlatformTime::Cycles64()));
    }));
#endif
}
