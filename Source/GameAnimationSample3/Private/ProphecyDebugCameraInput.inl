// Included by the module translation unit to avoid regrouping retained unity globals.
#include "ProphecyDebugCameraController.h"
#include "ProphecyAgent.h"
#include "Components/InputComponent.h"
#include "GameFramework/CheatManager.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/PlayerInput.h"
#if WITH_EDITOR
#include "Editor.h"
#include "UObject/UObjectIterator.h"
#endif

void AProphecyDebugCameraController::ClearForwardedInput()
{
#if WITH_EDITOR
    if (ForwardedInput)
    {
        PopInputComponent(ForwardedInput);
        ForwardedInput->DestroyComponent();
        ForwardedInput=nullptr;
    }
#endif
}

void AProphecyDebugCameraController::OnActivate(APlayerController* OriginalPC)
{
    Super::OnActivate(OriginalPC);
#if WITH_EDITOR
    ClearForwardedInput();
    AProphecyAgent* Agent=OriginalPC ? Cast<AProphecyAgent>(OriginalPC->GetPawn()) : nullptr;
    if (!Agent || !Agent->InputEnabled() || !Agent->InputComponent) return;
    const UInputComponent* Source=Agent->InputComponent;
    // Copy delegates, not gameplay state. They still execute on the original Pawn.
    // Leave axis/look input to the free camera. Non-consuming key/action bindings
    // let overlapping shortcuts (movement keys, mouse buttons, etc.) reach it too.
    ForwardedInput=NewObject<UInputComponent>(this,NAME_None,RF_Transient);
    ForwardedInput->bBlockInput=false;
    ForwardedInput->Priority=Source->Priority;
    ForwardedInput->KeyBindings=Source->KeyBindings;
    for (auto& Binding:ForwardedInput->KeyBindings) Binding.bConsumeInput=false;
    for (int32 I=0;I<Source->GetNumActionBindings();++I)
    {
        FInputActionBinding Binding=Source->GetActionBinding(I);
        Binding.bConsumeInput=false;
        ForwardedInput->AddActionBinding(Binding);
    }
    ForwardedInput->RegisterComponent();
    PushInputComponent(ForwardedInput);
#endif
}

void AProphecyDebugCameraController::OnDeactivate(APlayerController* RestoredPC)
{
    ClearForwardedInput();
    Super::OnDeactivate(RestoredPC);
}

void AProphecyDebugCameraController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ClearForwardedInput();
    Super::EndPlay(EndPlayReason);
}

namespace ProphecyDebugCameraInput
{
#if WITH_EDITOR
static FDelegateHandle CreatedHandle;
static FDelegateHandle CameraKeysHandle;
static void ConfigureCameraKeys(bool = false)
{
    // DefaultPawn/SpectatorPawn bindings are engine-defined, not project input
    // mappings. There is no public remove/rebind API; the backing array itself
    // is mutable. Restrict this edit to three known camera mappings.
    auto& Mappings=const_cast<TArray<FInputAxisKeyMapping>&>(UPlayerInput::GetEngineDefinedAxisMappings());
    int32 Changed=0;
    for(auto& Mapping:Mappings)
    {
        if(Mapping.AxisName==TEXT("DefaultPawn_MoveForward")&&Mapping.Key==EKeys::W)
        { Mapping.Key=EKeys::Z;++Changed; }
        else if(Mapping.AxisName==TEXT("DefaultPawn_MoveRight")&&Mapping.Key==EKeys::A)
        { Mapping.Key=EKeys::Q;++Changed; }
        else if(Mapping.AxisName==TEXT("DefaultPawn_MoveUp")&&Mapping.Key==EKeys::Q)
        { Mapping.Key=EKeys::A;++Changed; }
    }
    if(Changed)for(TObjectIterator<UPlayerInput> It;It;++It)
        if(!It->HasAnyFlags(RF_ClassDefaultObject))It->ForceRebuildingKeyMaps(false);
    bool Forward=false,Left=false,Right=false,Back=false,QDown=false;
    for(const auto& M:Mappings)
    {
        Forward|=M.AxisName==TEXT("DefaultPawn_MoveForward")&&M.Key==EKeys::Z&&M.Scale==1.f;
        Back|=M.AxisName==TEXT("DefaultPawn_MoveForward")&&M.Key==EKeys::S&&M.Scale==-1.f;
        Left|=M.AxisName==TEXT("DefaultPawn_MoveRight")&&M.Key==EKeys::Q&&M.Scale==-1.f;
        Right|=M.AxisName==TEXT("DefaultPawn_MoveRight")&&M.Key==EKeys::D&&M.Scale==1.f;
        QDown|=M.AxisName==TEXT("DefaultPawn_MoveUp")&&M.Key==EKeys::Q;
    }
    UE_LOG(LogTemp,Display,TEXT("Prophecy camera keys: changed=%d ZQSD=%d QDescends=%d (A/E vertical; Ctrl/C/Space retained)"),Changed,Forward&&Back&&Left&&Right,QDown);
}
static void Configure(UCheatManager* Manager)
{
    if (!IsValid(Manager) || Manager->HasAnyFlags(RF_ClassDefaultObject)) return;
    // Keep any deliberately selected custom debug-camera class untouched.
    if (Manager->DebugCameraControllerClass==ADebugCameraController::StaticClass())
        Manager->DebugCameraControllerClass=AProphecyDebugCameraController::StaticClass();
}
void Startup()
{
    if(!CameraKeysHandle.IsValid())CameraKeysHandle=FEditorDelegates::PostPIEStarted.AddStatic(&ConfigureCameraKeys);
    ConfigureCameraKeys();
    if (!CreatedHandle.IsValid())
        CreatedHandle=UCheatManager::RegisterForOnCheatManagerCreated(
            FOnCheatManagerCreated::FDelegate::CreateStatic(&Configure));
}
void Shutdown()
{
    if(CameraKeysHandle.IsValid())FEditorDelegates::PostPIEStarted.Remove(CameraKeysHandle);
    CameraKeysHandle.Reset();
    if (CreatedHandle.IsValid()) UCheatManager::UnregisterFromOnCheatManagerCreated(CreatedHandle);
    CreatedHandle.Reset();
}
// Install the newly compiled hook in an already-running editor. Normal launches
// use StartupModule. No poll, world tick, per-agent tick or packaged-game hook.
static FAutoConsoleCommand InstallCommand(TEXT("Prophecy.DebugCamera.InstallInput"),
    TEXT("Install editor-only agent key forwarding after Live Coding."),FConsoleCommandDelegate::CreateStatic(&Startup));
#endif
}
