#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyInputRecorder.generated.h"

class APlayerController;
class FArchive;

/** Debug input values from one actor tick. Reading this does not inject engine input events. */
USTRUCT(BlueprintType, meta=(DisplayName="Replayed Input"))
struct GAMEANIMATIONSAMPLE3_API FProphecyReplayedInput
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="A"))
    bool bA = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="B"))
    bool bB = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="C"))
    bool bC = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="D"))
    bool bD = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="E"))
    bool bE = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="F"))
    bool bF = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="G"))
    bool bG = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="H"))
    bool bH = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="I"))
    bool bI = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="J"))
    bool bJ = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="K"))
    bool bK = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="L"))
    bool bL = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="M"))
    bool bM = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="N"))
    bool bN = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="O"))
    bool bO = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="P"))
    bool bP = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Q"))
    bool bQ = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="R"))
    bool bR = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="S"))
    bool bS = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="T"))
    bool bT = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="U"))
    bool bU = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="V"))
    bool bV = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="W"))
    bool bW = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="X"))
    bool bX = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Y"))
    bool bY = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Z"))
    bool bZ = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Zero"))
    bool bZero = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="One"))
    bool bOne = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Two"))
    bool bTwo = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Three"))
    bool bThree = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Four"))
    bool bFour = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Five"))
    bool bFive = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Six"))
    bool bSix = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Seven"))
    bool bSeven = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Eight"))
    bool bEight = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Nine"))
    bool bNine = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="SpaceBar"))
    bool bSpaceBar = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Enter"))
    bool bEnter = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Tab"))
    bool bTab = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="BackSpace"))
    bool bBackSpace = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Escape"))
    bool bEscape = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="LeftShift"))
    bool bLeftShift = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="RightShift"))
    bool bRightShift = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="LeftControl"))
    bool bLeftControl = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="RightControl"))
    bool bRightControl = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="LeftAlt"))
    bool bLeftAlt = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="RightAlt"))
    bool bRightAlt = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Up"))
    bool bUp = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Down"))
    bool bDown = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Left"))
    bool bLeft = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Right"))
    bool bRight = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftThumbstick"))
    bool bGamepad_LeftThumbstick = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightThumbstick"))
    bool bGamepad_RightThumbstick = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad Special Left"))
    bool bGamepad_Special_Left = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad Special Right"))
    bool bGamepad_Special_Right = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad Special Left Touched"))
    bool bGamepad_Special_Left_Touched = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad FaceButton Bottom"))
    bool bGamepad_FaceButton_Bottom = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad FaceButton Right"))
    bool bGamepad_FaceButton_Right = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad FaceButton Left"))
    bool bGamepad_FaceButton_Left = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad FaceButton Top"))
    bool bGamepad_FaceButton_Top = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftShoulder"))
    bool bGamepad_LeftShoulder = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightShoulder"))
    bool bGamepad_RightShoulder = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftTrigger"))
    bool bGamepad_LeftTrigger = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightTrigger"))
    bool bGamepad_RightTrigger = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad DPad Up"))
    bool bGamepad_DPad_Up = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad DPad Down"))
    bool bGamepad_DPad_Down = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad DPad Right"))
    bool bGamepad_DPad_Right = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad DPad Left"))
    bool bGamepad_DPad_Left = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftStick Up"))
    bool bGamepad_LeftStick_Up = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftStick Down"))
    bool bGamepad_LeftStick_Down = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftStick Right"))
    bool bGamepad_LeftStick_Right = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad LeftStick Left"))
    bool bGamepad_LeftStick_Left = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightStick Up"))
    bool bGamepad_RightStick_Up = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightStick Down"))
    bool bGamepad_RightStick_Down = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightStick Right"))
    bool bGamepad_RightStick_Right = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Input", meta=(DisplayName="Gamepad RightStick Left"))
    bool bGamepad_RightStick_Left = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_LeftX = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_LeftY = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_RightX = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_RightY = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_LeftTriggerAxis = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_RightTriggerAxis = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_Special_Left_X = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Gamepad")
    float Gamepad_Special_Left_Y = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Motion Controller")
    FVector Tilt = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Motion Controller")
    FVector RotationRate = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Motion Controller")
    FVector Gravity = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Motion Controller")
    FVector Acceleration = FVector::ZeroVector;

    static FProphecyReplayedInput Capture(const APlayerController* Controller);
    void SerializeFrame(FArchive& Archive);
};

/** Created only by Initialize Input Recorder on the manual debug Blueprint. */
UCLASS(Transient, NotBlueprintable)
class GAMEANIMATIONSAMPLE3_API UProphecyInputRecorderComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyInputRecorderComponent();
    virtual ~UProphecyInputRecorderComponent() override;
    bool Initialize(FString& Error);
    virtual void TickComponent(float DeltaSeconds, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    struct FState;
    struct FStateDeleter { void operator()(FState* Value) const; };
    TUniquePtr<FState, FStateDeleter> State;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyInputRecorderLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** ManualPoseAgent debug only. Call once from its initialization function.
     * No component or ticking exists before this is called. Idempotent. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Debug|Input Recorder", meta=(DefaultToSelf="Agent"))
    static bool InitializeInputRecorder(AActor* Agent, FString& OutError);
};
