// Included by the module translation unit to avoid regrouping retained unity globals.
#include "ProphecyDebugCameraController.h"
#include "ProphecyAgent.h"
#include "Components/InputComponent.h"
#include "GameFramework/CheatManager.h"
#include "HAL/IConsoleManager.h"

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
static void Configure(UCheatManager* Manager)
{
    if (!IsValid(Manager) || Manager->HasAnyFlags(RF_ClassDefaultObject)) return;
    // Keep any deliberately selected custom debug-camera class untouched.
    if (Manager->DebugCameraControllerClass==ADebugCameraController::StaticClass())
        Manager->DebugCameraControllerClass=AProphecyDebugCameraController::StaticClass();
}
void Startup()
{
    if (!CreatedHandle.IsValid())
        CreatedHandle=UCheatManager::RegisterForOnCheatManagerCreated(
            FOnCheatManagerCreated::FDelegate::CreateStatic(&Configure));
}
void Shutdown()
{
    if (CreatedHandle.IsValid()) UCheatManager::UnregisterFromOnCheatManagerCreated(CreatedHandle);
    CreatedHandle.Reset();
}
// Install the newly compiled hook in an already-running editor. Normal launches
// use StartupModule. No poll, world tick, per-agent tick or packaged-game hook.
static FAutoConsoleCommand InstallCommand(TEXT("Prophecy.DebugCamera.InstallInput"),
    TEXT("Install editor-only agent key forwarding after Live Coding."),FConsoleCommandDelegate::CreateStatic(&Startup));
#endif
}
