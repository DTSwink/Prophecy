#pragma once
#include "CoreMinimal.h"
#include "ProphecyBodyflipOptions.generated.h"

UENUM(BlueprintType)
enum class EProphecyBodyflipAttack : uint8
{
    None,
    Headbutt,
    HookLeft,
    HookRight,
    JabLeft,
    JabRight,
    KickLeft,
    KickRight,
    OverheadLeft,
    OverheadRight,
    Pike,
    SlashLeft,
    SlashLeftDown,
    SlashLeftUp,
    SlashRight,
    SlashRightDown,
    SlashRightUp,
    SweepKick,
    BigThrow,
    SmallThrow
};

UENUM(BlueprintType)
enum class EProphecyBodyflipPush : uint8
{
    Foot,
    NearestHand,
    LeftHand,
    RightHand,
    BothHands
};

UENUM(BlueprintType)
enum class EProphecyBodyflipPose : uint8
{
    None,
    Pose1 UMETA(DisplayName="Lara"),
    Pose2 UMETA(DisplayName="Snatch"),
    Pose3 UMETA(DisplayName="Ball"),
    Pose4 UMETA(DisplayName="Ninja"),
    Keep UMETA(DisplayName="Keep pose")
};

UENUM(BlueprintType)
enum class EProphecyBodyflipSequence : uint8
{
    Idle,
    Walk,
    Run,
    SpaceGym
};

UENUM(BlueprintType)
enum class EProphecyBodyflipFoot : uint8
{
    Auto,
    Left,
    Right
};

UENUM(BlueprintType)
enum class EProphecyBodyflipAxis : uint8
{
    Back,
    BackRight30,
    BackRight60,
    Right,
    FrontRight60,
    FrontRight30,
    Front,
    FrontLeft30,
    FrontLeft60,
    Left,
    BackLeft60,
    BackLeft30
};

/** Typed Bodyflip controls. Distances are centimetres; durations are seconds. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyflipAttackOptions
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="Attack."))
    EProphecyBodyflipAttack Attack = EProphecyBodyflipAttack::None;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="DelaySeconds."))
    float DelaySeconds = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="BlendInSeconds."))
    float BlendInSeconds = 0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="BlendOutSeconds."))
    float BlendOutSeconds = 0.25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="ThrowChargePercent."))
    float ThrowChargePercent = 100;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(ToolTip="ThrowSpeedMultiplier."))
    float ThrowSpeedMultiplier = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions")
    bool bUseWorldThrowDirection = false;
    /** Optional fixed world direction. Otherwise spear aims at the target point and bomb retains its arc. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|AttackOptions", meta=(EditCondition="bUseWorldThrowDirection"))
    FVector WorldThrowDirection = FVector::ForwardVector;
};

/** Typed Bodyflip controls. Distances are centimetres; durations are seconds. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyflipSpinOptions
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="bInheritFlipSpeed. A true inherit flag keeps the preceding command; explicit zero stops rotation."))
    bool bInheritFlipSpeed = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="FlipDegreesPerSecond."))
    float FlipDegreesPerSecond = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="bInheritTwistSpeed. A true inherit flag keeps the preceding command; explicit zero stops rotation."))
    bool bInheritTwistSpeed = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="TwistDegreesPerSecond."))
    float TwistDegreesPerSecond = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="bInheritAxis. A true inherit flag keeps the preceding command; explicit zero stops rotation."))
    bool bInheritAxis = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="Axis."))
    EProphecyBodyflipAxis Axis = EProphecyBodyflipAxis::Back;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="DelaySeconds."))
    float DelaySeconds = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="AccelerateSeconds."))
    float AccelerateSeconds = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="DecelerateSeconds."))
    float DecelerateSeconds = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|SpinOptions", meta=(ToolTip="bInstantSpin."))
    bool bInstantSpin = false;
};

/** Typed Bodyflip controls. Distances are centimetres; durations are seconds. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyflipPoseOptions
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|PoseOptions", meta=(ToolTip="Pose."))
    EProphecyBodyflipPose Pose = EProphecyBodyflipPose::None;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|PoseOptions", meta=(ToolTip="BlendInSeconds."))
    float BlendInSeconds = 0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|PoseOptions", meta=(ToolTip="HoldSeconds."))
    float HoldSeconds = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|PoseOptions", meta=(ToolTip="BlendOutSeconds."))
    float BlendOutSeconds = 0.25f;
};

USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyflipPoseTuning
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose", meta=(ClampMin="0", ClampMax="4"))
    double WobbleSpeed = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose", meta=(ClampMin="0", ClampMax="1"))
    double WobbleAmplitude = 0.1;
    FProphecyBodyflipPoseTuning() = default;
    FProphecyBodyflipPoseTuning(double Speed, double Amplitude) : WobbleSpeed(Speed), WobbleAmplitude(Amplitude) {}
};

/** Typed Bodyflip controls. Defaults carry the November 2 lab tuning; no scene events are queued automatically. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyflipSettings
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="Sequence."))
    EProphecyBodyflipSequence Sequence = EProphecyBodyflipSequence::Idle;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="PrepareSeconds."))
    float PrepareSeconds = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="StartYawDegrees."))
    float StartYawDegrees = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="RunSeconds."))
    float RunSeconds = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="GaitPhase."))
    float GaitPhase = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="BodyBlendSeconds."))
    float BodyBlendSeconds = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="LegBlendSeconds."))
    float LegBlendSeconds = 0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="LegFollowSeconds."))
    float LegFollowSeconds = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="HandFollowSeconds."))
    float HandFollowSeconds = 0.05f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="HandReturnSeconds."))
    float HandReturnSeconds = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="HandBendSeconds."))
    float HandBendSeconds = 0.35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="FallCapCmPerSecond."))
    float FallCapCmPerSecond = 2000;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SupportingFoot."))
    EProphecyBodyflipFoot SupportingFoot = EProphecyBodyflipFoot::Auto;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="ReachRatio."))
    float ReachRatio = 0.99f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="ContactDistanceCm."))
    float ContactDistanceCm = 5;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SupportLeadAlpha."))
    float SupportLeadAlpha = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="FootSpeedCmPerSecond."))
    float FootSpeedCmPerSecond = 800;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="FootConeDegrees."))
    float FootConeDegrees = 40;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="HandConeDegrees."))
    float HandConeDegrees = 45;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="JumpVerticalSkew."))
    float JumpVerticalSkew = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SmallJumpThresholdPercent."))
    float SmallJumpThresholdPercent = 35;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="MediumJumpThresholdPercent."))
    float MediumJumpThresholdPercent = 70;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SmallLoadSeconds."))
    float SmallLoadSeconds = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="MediumLoadSeconds."))
    float MediumLoadSeconds = 0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="FullLoadSeconds."))
    float FullLoadSeconds = 0.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="LoadDepthCm."))
    float LoadDepthCm = 15;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="Rebound."))
    float Rebound = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SpinLag."))
    float SpinLag = 0.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="SpinInertia."))
    float SpinInertia = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="InitialFlipSpeed."))
    float InitialFlipSpeed = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="InitialTwistSpeed."))
    float InitialTwistSpeed = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="InitialFlipAxis."))
    EProphecyBodyflipAxis InitialFlipAxis = EProphecyBodyflipAxis::Back;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bAim."))
    bool bAim = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="AimWeight."))
    float AimWeight = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bDirectToArmed."))
    bool bDirectToArmed = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bUndoAttackRotation."))
    bool bUndoAttackRotation = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="PelvisAttackCompensation."))
    float PelvisAttackCompensation = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bSoftAttackLegs."))
    bool bSoftAttackLegs = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bSurfaceIK."))
    bool bSurfaceIK = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bMatchJumpPose."))
    bool bMatchJumpPose = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bAirFlip."))
    bool bAirFlip = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="StandingJumpSpeedRatio."))
    float StandingJumpSpeedRatio = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="PlantPitchDegrees."))
    float PlantPitchDegrees = 10;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="ToeOffPitchDegrees."))
    float ToeOffPitchDegrees = 35;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="FootRollDegreesPerSecond."))
    float FootRollDegreesPerSecond = 720;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Settings", meta=(ToolTip="bWeaponDrawn."))
    bool bWeaponDrawn = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    bool bMotionCompensation = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    bool bDistributePelvisTurn = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack", meta=(DisplayName="Pike: Steer Through Thrust", ToolTip="Use the lab's continuous Pike thrust steering during flips. Unsupported fits retain standard aim."))
    bool bPikeThrustSteering = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Spin")
    bool bMomentum3D = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    bool bSpaceFallingAnimation = true;
    /** Negative uses each jump's Blend Out; otherwise shared duration before distance weighting. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    double AttackReturnSeconds = 0.247086720867209;
    /** 0 preserves the base duration; 1 scales linearly with angular distance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    double AttackReturnDistanceWeight = 0.4;
    /** Source frames after release when no attack end override is set. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    int32 BigThrowReturnFrames = 16;
    /** Source frames after release when no attack end override is set. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    int32 SmallThrowReturnFrames = 34;
    /** Shared pose entry duration before distance weighting. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseBlendSeconds = 0.260907859078591;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseBlendDistanceWeight = 0.45;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseEaseIn = 0.15;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseExponent = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseEaseOut = 0.5;
    /** Angular velocity along pelvis up that selects the full authored variant. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseFullResponseDegreesPerSecond = 45;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    double PoseSpinResponseSeconds = 0.17;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    bool bInvertPoseVariants = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Support")
    bool bFootTargets = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Support")
    bool bHandTargets = true;
    /** Source-frame cuts, clamped to Hit/Release through the authored last frame. Remove an entry to use the clip default. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Attack")
    TMap<EProphecyBodyflipAttack, int32> AttackEndFrames = {
        {EProphecyBodyflipAttack::SweepKick,26}, {EProphecyBodyflipAttack::SlashRightUp,23},
        {EProphecyBodyflipAttack::SlashRightDown,22}, {EProphecyBodyflipAttack::SlashRight,25},
        {EProphecyBodyflipAttack::SlashLeftUp,21}, {EProphecyBodyflipAttack::SlashLeftDown,24},
        {EProphecyBodyflipAttack::Pike,16},
        {EProphecyBodyflipAttack::JabLeft,11}, {EProphecyBodyflipAttack::JabRight,11},
        {EProphecyBodyflipAttack::HookLeft,13}, {EProphecyBodyflipAttack::HookRight,13}};
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Bodyflip|Pose")
    TMap<EProphecyBodyflipPose, FProphecyBodyflipPoseTuning> PoseTuning = {
        {EProphecyBodyflipPose::Pose1,{0.3,0.04}}, {EProphecyBodyflipPose::Pose2,{0.2,0.09}},
        {EProphecyBodyflipPose::Pose3,{0.2,0.02}}, {EProphecyBodyflipPose::Pose4,{0.25,0.07}}};
};
