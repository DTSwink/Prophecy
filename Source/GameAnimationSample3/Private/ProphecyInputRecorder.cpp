#include "ProphecyInputRecorder.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Serialization/Archive.h"
#include "UObject/UnrealType.h"

namespace ProphecyInputRecorder
{
struct FButton { const FKey* Key; bool FProphecyReplayedInput::* Member; };
static const FButton Buttons[] = {
    { &EKeys::A, &FProphecyReplayedInput::bA },
    { &EKeys::B, &FProphecyReplayedInput::bB },
    { &EKeys::C, &FProphecyReplayedInput::bC },
    { &EKeys::D, &FProphecyReplayedInput::bD },
    { &EKeys::E, &FProphecyReplayedInput::bE },
    { &EKeys::F, &FProphecyReplayedInput::bF },
    { &EKeys::G, &FProphecyReplayedInput::bG },
    { &EKeys::H, &FProphecyReplayedInput::bH },
    { &EKeys::I, &FProphecyReplayedInput::bI },
    { &EKeys::J, &FProphecyReplayedInput::bJ },
    { &EKeys::K, &FProphecyReplayedInput::bK },
    { &EKeys::L, &FProphecyReplayedInput::bL },
    { &EKeys::M, &FProphecyReplayedInput::bM },
    { &EKeys::N, &FProphecyReplayedInput::bN },
    { &EKeys::O, &FProphecyReplayedInput::bO },
    { &EKeys::P, &FProphecyReplayedInput::bP },
    { &EKeys::Q, &FProphecyReplayedInput::bQ },
    { &EKeys::R, &FProphecyReplayedInput::bR },
    { &EKeys::S, &FProphecyReplayedInput::bS },
    { &EKeys::T, &FProphecyReplayedInput::bT },
    { &EKeys::U, &FProphecyReplayedInput::bU },
    { &EKeys::V, &FProphecyReplayedInput::bV },
    { &EKeys::W, &FProphecyReplayedInput::bW },
    { &EKeys::X, &FProphecyReplayedInput::bX },
    { &EKeys::Y, &FProphecyReplayedInput::bY },
    { &EKeys::Z, &FProphecyReplayedInput::bZ },
    { &EKeys::Zero, &FProphecyReplayedInput::bZero },
    { &EKeys::One, &FProphecyReplayedInput::bOne },
    { &EKeys::Two, &FProphecyReplayedInput::bTwo },
    { &EKeys::Three, &FProphecyReplayedInput::bThree },
    { &EKeys::Four, &FProphecyReplayedInput::bFour },
    { &EKeys::Five, &FProphecyReplayedInput::bFive },
    { &EKeys::Six, &FProphecyReplayedInput::bSix },
    { &EKeys::Seven, &FProphecyReplayedInput::bSeven },
    { &EKeys::Eight, &FProphecyReplayedInput::bEight },
    { &EKeys::Nine, &FProphecyReplayedInput::bNine },
    { &EKeys::SpaceBar, &FProphecyReplayedInput::bSpaceBar },
    { &EKeys::Enter, &FProphecyReplayedInput::bEnter },
    { &EKeys::Tab, &FProphecyReplayedInput::bTab },
    { &EKeys::BackSpace, &FProphecyReplayedInput::bBackSpace },
    { &EKeys::Escape, &FProphecyReplayedInput::bEscape },
    { &EKeys::LeftShift, &FProphecyReplayedInput::bLeftShift },
    { &EKeys::RightShift, &FProphecyReplayedInput::bRightShift },
    { &EKeys::LeftControl, &FProphecyReplayedInput::bLeftControl },
    { &EKeys::RightControl, &FProphecyReplayedInput::bRightControl },
    { &EKeys::LeftAlt, &FProphecyReplayedInput::bLeftAlt },
    { &EKeys::RightAlt, &FProphecyReplayedInput::bRightAlt },
    { &EKeys::Up, &FProphecyReplayedInput::bUp },
    { &EKeys::Down, &FProphecyReplayedInput::bDown },
    { &EKeys::Left, &FProphecyReplayedInput::bLeft },
    { &EKeys::Right, &FProphecyReplayedInput::bRight },
    { &EKeys::Gamepad_LeftThumbstick, &FProphecyReplayedInput::bGamepad_LeftThumbstick },
    { &EKeys::Gamepad_RightThumbstick, &FProphecyReplayedInput::bGamepad_RightThumbstick },
    { &EKeys::Gamepad_Special_Left, &FProphecyReplayedInput::bGamepad_Special_Left },
    { &EKeys::Gamepad_Special_Right, &FProphecyReplayedInput::bGamepad_Special_Right },
    { &EKeys::Gamepad_Special_Left_Touched, &FProphecyReplayedInput::bGamepad_Special_Left_Touched },
    { &EKeys::Gamepad_FaceButton_Bottom, &FProphecyReplayedInput::bGamepad_FaceButton_Bottom },
    { &EKeys::Gamepad_FaceButton_Right, &FProphecyReplayedInput::bGamepad_FaceButton_Right },
    { &EKeys::Gamepad_FaceButton_Left, &FProphecyReplayedInput::bGamepad_FaceButton_Left },
    { &EKeys::Gamepad_FaceButton_Top, &FProphecyReplayedInput::bGamepad_FaceButton_Top },
    { &EKeys::Gamepad_LeftShoulder, &FProphecyReplayedInput::bGamepad_LeftShoulder },
    { &EKeys::Gamepad_RightShoulder, &FProphecyReplayedInput::bGamepad_RightShoulder },
    { &EKeys::Gamepad_LeftTrigger, &FProphecyReplayedInput::bGamepad_LeftTrigger },
    { &EKeys::Gamepad_RightTrigger, &FProphecyReplayedInput::bGamepad_RightTrigger },
    { &EKeys::Gamepad_DPad_Up, &FProphecyReplayedInput::bGamepad_DPad_Up },
    { &EKeys::Gamepad_DPad_Down, &FProphecyReplayedInput::bGamepad_DPad_Down },
    { &EKeys::Gamepad_DPad_Right, &FProphecyReplayedInput::bGamepad_DPad_Right },
    { &EKeys::Gamepad_DPad_Left, &FProphecyReplayedInput::bGamepad_DPad_Left },
    { &EKeys::Gamepad_LeftStick_Up, &FProphecyReplayedInput::bGamepad_LeftStick_Up },
    { &EKeys::Gamepad_LeftStick_Down, &FProphecyReplayedInput::bGamepad_LeftStick_Down },
    { &EKeys::Gamepad_LeftStick_Right, &FProphecyReplayedInput::bGamepad_LeftStick_Right },
    { &EKeys::Gamepad_LeftStick_Left, &FProphecyReplayedInput::bGamepad_LeftStick_Left },
    { &EKeys::Gamepad_RightStick_Up, &FProphecyReplayedInput::bGamepad_RightStick_Up },
    { &EKeys::Gamepad_RightStick_Down, &FProphecyReplayedInput::bGamepad_RightStick_Down },
    { &EKeys::Gamepad_RightStick_Right, &FProphecyReplayedInput::bGamepad_RightStick_Right },
    { &EKeys::Gamepad_RightStick_Left, &FProphecyReplayedInput::bGamepad_RightStick_Left },
};
static_assert(UE_ARRAY_COUNT(Buttons) <= 128);
constexpr uint32 Magic = 0x50524931, Version = 1;
constexpr int32 MaxFrames = 1000000;
constexpr int64 BytesPerFrame = 16 + 8 * 4 + 12 * 8;
FString SlotPath(int32 Slot)
{ return FPaths::ProjectSavedDir() / TEXT("DebugInputRecordings") / FString::Printf(TEXT("Slot_%d.input"), Slot); }

bool Save(int32 Slot, TArray<FProphecyReplayedInput>& Frames)
{
    const FString Path = SlotPath(Slot), Temporary = Path + TEXT(".tmp");
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
    TUniquePtr<FArchive> File(IFileManager::Get().CreateFileWriter(*Temporary));
    if (!File) return false;
    uint32 Tag = Magic, Format = Version; int32 Count = Frames.Num();
    *File << Tag << Format << Count;
    for (auto& Frame : Frames) Frame.SerializeFrame(*File);
    const bool OK = File->Close() && !File->IsError();
    File.Reset();
    return OK && IFileManager::Get().Move(*Path, *Temporary, true, true);
}
bool Load(int32 Slot, TArray<FProphecyReplayedInput>& Frames)
{
    Frames.Reset();
    TUniquePtr<FArchive> File(IFileManager::Get().CreateFileReader(*SlotPath(Slot)));
    if (!File || File->TotalSize() < 12) return false;
    uint32 Tag = 0, Format = 0; int32 Count = 0;
    *File << Tag << Format << Count;
    if (File->IsError() || Tag != Magic || Format != Version || Count < 0 || Count > MaxFrames
        || File->TotalSize() != 12 + int64(Count) * BytesPerFrame) return false;
    Frames.SetNum(Count);
    for (auto& Frame : Frames) Frame.SerializeFrame(*File);
    if (File->IsError()) { Frames.Reset(); return false; }
    return true;
}
}

FProphecyReplayedInput FProphecyReplayedInput::Capture(const APlayerController* PC)
{
    FProphecyReplayedInput Out;
    if (!IsValid(PC)) return Out;
    for (const auto& Button : ProphecyInputRecorder::Buttons) Out.*(Button.Member) = PC->IsInputKeyDown(*Button.Key);
    Out.Gamepad_LeftX = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX);
    Out.Gamepad_LeftY = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY);
    Out.Gamepad_RightX = PC->GetInputAnalogKeyState(EKeys::Gamepad_RightX);
    Out.Gamepad_RightY = PC->GetInputAnalogKeyState(EKeys::Gamepad_RightY);
    Out.Gamepad_LeftTriggerAxis = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis);
    Out.Gamepad_RightTriggerAxis = PC->GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis);
    Out.Gamepad_Special_Left_X = PC->GetInputAnalogKeyState(EKeys::Gamepad_Special_Left_X);
    Out.Gamepad_Special_Left_Y = PC->GetInputAnalogKeyState(EKeys::Gamepad_Special_Left_Y);
    PC->GetInputMotionState(Out.Tilt, Out.RotationRate, Out.Gravity, Out.Acceleration);
    return Out;
}

void FProphecyReplayedInput::SerializeFrame(FArchive& Ar)
{
    uint64 Bits[2] = {};
    if (Ar.IsSaving()) for (int32 I=0; I<UE_ARRAY_COUNT(ProphecyInputRecorder::Buttons); ++I)
        if (this->*(ProphecyInputRecorder::Buttons[I].Member)) Bits[I/64] |= uint64(1) << (I%64);
    Ar << Bits[0] << Bits[1];
    if (Ar.IsLoading()) for (int32 I=0; I<UE_ARRAY_COUNT(ProphecyInputRecorder::Buttons); ++I)
        this->*(ProphecyInputRecorder::Buttons[I].Member) = (Bits[I/64] & (uint64(1) << (I%64))) != 0;
    Ar << Gamepad_LeftX;
    Ar << Gamepad_LeftY;
    Ar << Gamepad_RightX;
    Ar << Gamepad_RightY;
    Ar << Gamepad_LeftTriggerAxis;
    Ar << Gamepad_RightTriggerAxis;
    Ar << Gamepad_Special_Left_X;
    Ar << Gamepad_Special_Left_Y;
    Ar << Tilt.X << Tilt.Y << Tilt.Z;
    Ar << RotationRate.X << RotationRate.Y << RotationRate.Z;
    Ar << Gravity.X << Gravity.Y << Gravity.Z;
    Ar << Acceleration.X << Acceleration.Y << Acceleration.Z;
}

struct UProphecyInputRecorderComponent::FState
{
    FBoolProperty* Recording = nullptr;
    FBoolProperty* Playing = nullptr;
    FIntProperty* Slot = nullptr;
    FStructProperty* Output = nullptr;
    TWeakObjectPtr<UClass> BoundClass;
    TWeakObjectPtr<APlayerController> Controller;
    TArray<FProphecyReplayedInput> Frames;
    int32 ActiveSlot = INDEX_NONE, PlaybackIndex = 0;
    bool bRecording = false, bPlaying = false;

    bool Flush()
    {
        if (!bRecording) return true;
        const bool OK = ProphecyInputRecorder::Save(ActiveSlot, Frames);
        if (!OK) UE_LOG(LogTemp, Error, TEXT("Input recorder could not save slot %d. Existing slot was retained."), ActiveSlot);
        bRecording = false;
        return OK;
    }
};

UProphecyInputRecorderComponent::UProphecyInputRecorderComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}
UProphecyInputRecorderComponent::~UProphecyInputRecorderComponent() = default;
void UProphecyInputRecorderComponent::FStateDeleter::operator()(FState* Value) const { delete Value; }

bool UProphecyInputRecorderComponent::Initialize(FString& Error)
{
    auto* Owner = GetOwner();
    if (!IsValid(Owner) || !Owner->GetWorld() || !Owner->GetWorld()->IsGameWorld())
    { Error = TEXT("Initialize the debug recorder on a live manual pose agent."); return false; }
    bool Manual = false;
    for (auto* Class = Owner->GetClass(); Class; Class = Class->GetSuperClass())
        Manual |= Class->GetPathName() == TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C");
    if (!Manual) { Error = TEXT("The input recorder is restricted to BP_ProphecyManualPoseAgent and its children."); return false; }
    if (State && State->BoundClass == Owner->GetClass()) return true;
    if (State) State->Flush();
    TUniquePtr<FState, FStateDeleter> Next(new FState());
    auto* Class = Owner->GetClass();
    Next->Recording = FindFProperty<FBoolProperty>(Class, TEXT("RecordingInput"));
    Next->Playing = FindFProperty<FBoolProperty>(Class, TEXT("PlayingInput"));
    Next->Slot = FindFProperty<FIntProperty>(Class, TEXT("RecordingSlot"));
    Next->Output = FindFProperty<FStructProperty>(Class, TEXT("ReplayedInput"));
    if (!Next->Recording || !Next->Playing || !Next->Slot || !Next->Output || Next->Output->Struct != FProphecyReplayedInput::StaticStruct())
    { Error = TEXT("The manual Blueprint needs Recording Input, Playing Input, Recording Slot and Replayed Input variables."); return false; }
    Next->BoundClass = Class;
    State = MoveTemp(Next);
    auto* Pawn = Cast<APawn>(Owner);
    auto* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!Controller) Controller = UGameplayStatics::GetPlayerController(Owner, 0);
    State->Controller = Controller;
    if (Controller) AddTickPrerequisiteActor(Controller);
    SetComponentTickInterval(Owner->GetActorTickInterval());
    Owner->AddTickPrerequisiteComponent(this);
    SetComponentTickEnabled(true);
    Error.Reset();
    return true;
}

void UProphecyInputRecorderComponent::TickComponent(float DeltaSeconds, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaSeconds, TickType, TickFunction);
    auto* Owner = GetOwner();
    if (!State || !IsValid(Owner) || !Owner->IsActorTickEnabled()) return;
    if (State->BoundClass != Owner->GetClass())
    {
        FString Error;
        if (!Initialize(Error)) { SetComponentTickEnabled(false); UE_LOG(LogTemp, Error, TEXT("Input recorder: %s"), *Error); }
        return;
    }
    // Capture follows the local controller's input tick and precedes this pawn's
    // Blueprint tick. The recorder is opt-in; no core agent knows about it.
    auto* Pawn = Cast<APawn>(Owner);
    auto* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    if (!PC) PC = UGameplayStatics::GetPlayerController(Owner, 0);
    if (PC != State->Controller.Get())
    {
        if (auto* Old = State->Controller.Get()) RemoveTickPrerequisiteActor(Old);
        State->Controller = PC;
        if (PC) AddTickPrerequisiteActor(PC);
    }
    auto& S = *State;
    bool Record = S.Recording->GetPropertyValue_InContainer(Owner);
    bool Play = S.Playing->GetPropertyValue_InContainer(Owner);
    const int32 Slot = S.Slot->GetPropertyValue_InContainer(Owner);
    if (Slot < 0 && (Record || Play))
    {
        UE_LOG(LogTemp, Warning, TEXT("Input recorder: Recording Slot must be nonnegative."));
        S.Recording->SetPropertyValue_InContainer(Owner, false); S.Playing->SetPropertyValue_InContainer(Owner, false);
        Record = Play = false;
    }
    if (S.bRecording && (!Record || Slot != S.ActiveSlot))
    {
        if (!S.Flush()) { S.Recording->SetPropertyValue_InContainer(Owner,false); Record = false; }
    }
    if (Record)
    {
        if (!S.bRecording) { S.Frames.Reset(); S.Frames.Reserve(3600); S.ActiveSlot = Slot; S.bRecording = true; }
        S.bPlaying = false; S.PlaybackIndex = 0;
        if (Play) { S.Playing->SetPropertyValue_InContainer(Owner, false); Play = false; }
    }
    else if (Play && (!S.bPlaying || Slot != S.ActiveSlot))
    {
        S.ActiveSlot = Slot; S.PlaybackIndex = 0;
        S.bPlaying = ProphecyInputRecorder::Load(Slot, S.Frames) && !S.Frames.IsEmpty();
        if (!S.bPlaying)
        {
            S.Playing->SetPropertyValue_InContainer(Owner, false); Play = false;
            UE_LOG(LogTemp, Warning, TEXT("Input recorder: slot %d is missing, empty or invalid."), Slot);
        }
    }
    else if (!Play) S.bPlaying = false;

    auto* Output = S.Output->ContainerPtrToValuePtr<FProphecyReplayedInput>(Owner);
    if (S.bPlaying && S.Frames.IsValidIndex(S.PlaybackIndex)) *Output = S.Frames[S.PlaybackIndex++];
    else
    {
        if (S.bPlaying) { S.bPlaying = false; S.Playing->SetPropertyValue_InContainer(Owner, false); }
        *Output = FProphecyReplayedInput::Capture(PC);
        if (S.bRecording)
        {
            S.Frames.Add(*Output);
            if (S.Frames.Num() >= ProphecyInputRecorder::MaxFrames)
            {
                S.Flush(); S.Recording->SetPropertyValue_InContainer(Owner, false);
                UE_LOG(LogTemp, Warning, TEXT("Input recording stopped at its one-million-tick safety limit."));
            }
        }
    }
}
void UProphecyInputRecorderComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (State) State->Flush();
    if (auto* Owner = GetOwner()) Owner->RemoveTickPrerequisiteComponent(this);
    if (State && State->Controller.IsValid()) RemoveTickPrerequisiteActor(State->Controller.Get());
    State.Reset();
    Super::EndPlay(Reason);
}

bool UProphecyInputRecorderLibrary::InitializeInputRecorder(AActor* Agent, FString& Error)
{
    Error.Reset();
    if (!IsInGameThread() || !IsValid(Agent)) { Error = TEXT("A live manual pose agent on the game thread is required."); return false; }
    if (auto* Existing = Agent->FindComponentByClass<UProphecyInputRecorderComponent>()) return Existing->Initialize(Error);
    auto* Recorder = NewObject<UProphecyInputRecorderComponent>(Agent, NAME_None, RF_Transient);
    Agent->AddInstanceComponent(Recorder); Recorder->RegisterComponent();
    if (Recorder->Initialize(Error)) return true;
    Recorder->DestroyComponent();
    return false;
}
