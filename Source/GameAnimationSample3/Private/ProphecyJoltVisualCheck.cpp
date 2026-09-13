#include "CoreMinimal.h"
#if !UE_BUILD_SHIPPING
#include "ProphecyAgent.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace ProphecyJolt::VisualCheck
{
bool ValidDestination(const TArray<FString>& Args, int32 Count)
{
    return Args.Num() == Count && !FPaths::IsRelative(Args[0]) && !FPaths::FileExists(Args[0]);
}

void Save(const FString& Path, const TSharedRef<FJsonObject>& Report)
{
    FString Text;
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
    if (!FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text))
        || !FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
            &IFileManager::Get(), FILEWRITE_NoReplaceExisting))
    { UE_LOG(LogTemp, Error, TEXT("Could not save Jolt visual report: %s"), *Path); }
}

void Snapshot(UWorld* World, FJsonObject& Report)
{
    Report.SetBoolField(TEXT("assets_saved"), false);
    Report.SetStringField(TEXT("world"), World ? World->GetPathName() : TEXT("None"));
    if (!World || World->WorldType != EWorldType::PIE) return;
    auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldDiagnostics D;
    if (Native && Native->GetDiagnostics(D).IsSuccess())
    {
        Report.SetBoolField(TEXT("initialized"), D.bInitialized);
        Report.SetBoolField(TEXT("faulted"), D.bFaulted);
        Report.SetStringField(TEXT("world_error"), D.Failure);
        Report.SetNumberField(TEXT("completed_steps"), double(D.CompletedSteps));
        Report.SetNumberField(TEXT("bodies"), D.BodyCount);
        Report.SetNumberField(TEXT("joints"), D.ConstraintCount);
        Report.SetNumberField(TEXT("grip_joints"), D.GenericJointCount);
        Report.SetNumberField(TEXT("owner_exclusions"), D.SuppressedBodyPairCount);
    }
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (TActorIterator<AProphecyAgent> It(World); It; ++It)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("agent"), It->GetName());
        Row->SetBoolField(TEXT("jolt"), It->IsJoltPhysicalAnimationEnabled());
        if (auto* Character = It->GetJoltCharacterComponent())
        {
            Row->SetBoolField(TEXT("stopped"), Character->IsSteppingStopped());
            Row->SetStringField(TEXT("error"), Character->GetLastError());
            Row->SetNumberField(TEXT("revision"), double(Character->GetRevision()));
        }
        if (AActor* Sword = It->GetHeldSword())
        {
            Row->SetStringField(TEXT("sword"), Sword->GetName());
            if (auto* Body = Sword->FindComponentByClass<UProphecyJoltBodyComponent>())
            {
                Row->SetBoolField(TEXT("sword_jolt"), Body->IsJoltBody());
                Row->SetStringField(TEXT("sword_error"), Body->GetLastError());
            }
        }
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    Report.SetArrayField(TEXT("agents"), Rows);
    for (TActorIterator<AActor> It(World); It; ++It)
        if (auto* Scene = It->FindComponentByClass<UProphecyJoltSceneCollisionComponent>())
        {
            Report.SetBoolField(TEXT("scene_enabled"), Scene->IsSceneCollisionEnabled());
            Report.SetNumberField(TEXT("scene_bodies"), Scene->GetImportedBodyCount());
            Report.SetStringField(TEXT("scene_error"), Scene->GetLastError());
        }
}

void Begin(const TArray<FString>& Args, UWorld* World)
{
    if (!ValidDestination(Args, 2))
    { UE_LOG(LogTemp, Error, TEXT("VisualBegin requires a new absolute report path and exact existing agent name.")); return; }
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    AProphecyAgent* Agent = nullptr;
    AActor* Owner = nullptr;
    bool bChangedAgent = false;
    bool bPreviousMACD = false;
    EProphecyAgentSimulationMode PreviousMode = EProphecyAgentSimulationMode::Kinematic;
    const auto Run = [&]() -> bool
    {
        if (!World || World->WorldType != EWorldType::PIE)
        { Error = TEXT("Visual startup is restricted to an existing PIE world."); return false; }
        if (World->bInTick)
        { Error = TEXT("Run visual startup between PIE world ticks, for example through the editor Python bridge."); return false; }
        for (TActorIterator<AProphecyAgent> It(World); It; ++It)
            if (It->GetName() == Args[1]) { Agent = *It; break; }
        if (!Agent || !Agent->bManualNNPoseApplication || !Agent->HasActorBegunPlay()
            || Agent->IsJoltPhysicalAnimationEnabled() || Agent->GetHeldSword()
            || Agent->GetSimulationMode() == EProphecyAgentSimulationMode::HalfSim)
        { Error = TEXT("Choose an initialized manual agent in Kinematic/Physical mode without an existing Jolt binding or held sword."); return false; }
        if (auto* Existing = Agent->GetJoltCharacterComponent())
            if (Existing->IsEnablePending() || Existing->IsKinematicRestorePending())
            { Error = TEXT("The selected character has a pending admission or restoration."); return false; }
        for (TActorIterator<AActor> It(World); It; ++It)
            if (It->FindComponentByClass<UProphecyJoltSceneCollisionComponent>())
            { Error = TEXT("A scene owner already exists; use the ordinary gameplay controls."); return false; }
        if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(World, Error)) return false;
        Owner = World->SpawnActor<AActor>();
        if (!Owner) { Error = TEXT("Could not create the temporary PIE scene owner."); return false; }
        auto* Scene = NewObject<UProphecyJoltSceneCollisionComponent>(Owner);
        Owner->AddInstanceComponent(Scene);
        Scene->RegisterComponent();
        if (!Scene->EnableSceneCollision(Error)) return false;
        if (!Scene->IsSceneCollisionEnabled() || Scene->IsEnablePending())
        { Error = TEXT("Scene admission was deferred; retry visual startup between PIE world ticks."); return false; }
        PreviousMode = Agent->GetSimulationMode();
        bPreviousMACD = Agent->IsMACDEnabled();
        bChangedAgent = true;
        Agent->SetMACDEnabled(false);
        if (!Agent->EnableJoltPhysicalAnimation())
        {
            auto* Character = Agent->GetJoltCharacterComponent();
            Error = Character ? Character->GetLastError() : TEXT("Character admission failed.");
            return false;
        }
        if (!Agent->IsJoltPhysicalAnimationEnabled() || Agent->GetJoltCharacterComponent()->IsEnablePending())
        { Error = TEXT("Character admission did not finish synchronously."); return false; }
        if (!Agent->EquipSword(true)) { Error = TEXT("Actual sword equip failed; inspect the native log."); return false; }
        AActor* Sword = Agent->GetHeldSword();
        auto* Body = Sword ? Sword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
        if (!Body || !Body->IsJoltBody() || Body->IsEnablePending())
        { Error = TEXT("Sword admission did not finish synchronously."); return false; }
        return true;
    };
    const bool bSuccess = Run();
    if (!bSuccess)
    {
        if (bChangedAgent && IsValid(Agent))
        {
            Agent->HideSword();
            Agent->DisableJoltPhysicalAnimation();
            Agent->SetMACDEnabled(bPreviousMACD);
            Agent->SetSimulationMode(PreviousMode);
        }
        if (IsValid(Owner)) Owner->Destroy();
        UE_LOG(LogTemp, Error, TEXT("Jolt visual startup failed: %s"), *Error);
    }
    Snapshot(World, *Report);
    Report->SetBoolField(TEXT("startup_success"), bSuccess);
    Report->SetStringField(TEXT("startup_error"), Error);
    Save(Args[0], Report);
}

void Status(const TArray<FString>& Args, UWorld* World)
{
    if (!ValidDestination(Args, 1)) return;
    auto Report = MakeShared<FJsonObject>();
    Snapshot(World, *Report);
    Save(Args[0], Report);
}
FAutoConsoleCommandWithWorldAndArgs BeginCommand(TEXT("Prophecy.Jolt.VisualBegin"),
    TEXT("PIE only: initialize scene + exact existing manual fighter + sword; new absolute report path, agent name. Saves no assets."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&Begin));
FAutoConsoleCommandWithWorldAndArgs StatusCommand(TEXT("Prophecy.Jolt.VisualStatus"),
    TEXT("Read current PIE Jolt scene/agent/sword state into a new absolute JSON report."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&Status));
}
#endif
