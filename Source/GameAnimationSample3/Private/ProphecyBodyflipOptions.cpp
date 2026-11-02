#include "ProphecyBodyflipOptions.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProphecyBodyflipLibrary.h"
namespace ProphecyBodyflipOptions
{
static const TCHAR* Key(EProphecyBodyflipAttack Value)
{
    switch(Value)
    {
    case EProphecyBodyflipAttack::None: return TEXT("none");
    case EProphecyBodyflipAttack::Headbutt: return TEXT("headbutt");
    case EProphecyBodyflipAttack::HookLeft: return TEXT("hookL");
    case EProphecyBodyflipAttack::HookRight: return TEXT("hookR");
    case EProphecyBodyflipAttack::JabLeft: return TEXT("jabL");
    case EProphecyBodyflipAttack::JabRight: return TEXT("jabR");
    case EProphecyBodyflipAttack::KickLeft: return TEXT("KickL");
    case EProphecyBodyflipAttack::KickRight: return TEXT("KickR");
    case EProphecyBodyflipAttack::OverheadLeft: return TEXT("overL");
    case EProphecyBodyflipAttack::OverheadRight: return TEXT("overR");
    case EProphecyBodyflipAttack::Pike: return TEXT("pike");
    case EProphecyBodyflipAttack::SlashLeft: return TEXT("slashL");
    case EProphecyBodyflipAttack::SlashLeftDown: return TEXT("slashLD");
    case EProphecyBodyflipAttack::SlashLeftUp: return TEXT("slashLU");
    case EProphecyBodyflipAttack::SlashRight: return TEXT("slashR");
    case EProphecyBodyflipAttack::SlashRightDown: return TEXT("slashRD");
    case EProphecyBodyflipAttack::SlashRightUp: return TEXT("slashRU");
    case EProphecyBodyflipAttack::SweepKick: return TEXT("sweepKick");
    case EProphecyBodyflipAttack::BigThrow: return TEXT("big-throw");
    case EProphecyBodyflipAttack::SmallThrow: return TEXT("small-throw");
    default: return TEXT("none");
    }
}
static const TCHAR* Key(EProphecyBodyflipPush Value)
{
    switch(Value)
    {
    case EProphecyBodyflipPush::Foot: return TEXT("foot");
    case EProphecyBodyflipPush::NearestHand: return TEXT("hand");
    case EProphecyBodyflipPush::LeftHand: return TEXT("handL");
    case EProphecyBodyflipPush::RightHand: return TEXT("handR");
    case EProphecyBodyflipPush::BothHands: return TEXT("handBoth");
    default: return TEXT("foot");
    }
}
static const TCHAR* Key(EProphecyBodyflipPose Value)
{
    switch(Value)
    {
    case EProphecyBodyflipPose::Keep: return TEXT("keep");
    case EProphecyBodyflipPose::None: return TEXT("none");
    case EProphecyBodyflipPose::Pose1: return TEXT("pose1");
    case EProphecyBodyflipPose::Pose2: return TEXT("pose2");
    case EProphecyBodyflipPose::Pose3: return TEXT("pose3");
    case EProphecyBodyflipPose::Pose4: return TEXT("pose4");
    default: return TEXT("none");
    }
}
static const TCHAR* Key(EProphecyBodyflipSequence Value)
{
    switch(Value)
    {
    case EProphecyBodyflipSequence::Idle: return TEXT("idle");
    case EProphecyBodyflipSequence::Walk: return TEXT("walk");
    case EProphecyBodyflipSequence::Run: return TEXT("jump");
    case EProphecyBodyflipSequence::SpaceGym: return TEXT("spaceGym");
    default: return TEXT("idle");
    }
}
static const TCHAR* Key(EProphecyBodyflipFoot Value)
{
    switch(Value)
    {
    case EProphecyBodyflipFoot::Auto: return TEXT("Auto");
    case EProphecyBodyflipFoot::Left: return TEXT("L");
    case EProphecyBodyflipFoot::Right: return TEXT("R");
    default: return TEXT("Auto");
    }
}
static void Encode(const FProphecyBodyflipAttackOptions& V, FJsonObject& O)
{
    O.SetStringField(TEXT("attack"), Key(V.Attack));
    O.SetNumberField(TEXT("attackDelay"), double(V.DelaySeconds));
    O.SetNumberField(TEXT("attackIn"), double(V.BlendInSeconds));
    O.SetNumberField(TEXT("attackOut"), double(V.BlendOutSeconds));
    O.SetNumberField(TEXT("throwCharge"), double(V.ThrowChargePercent));
    O.SetNumberField(TEXT("throwSpeed"), double(V.ThrowSpeedMultiplier));
    if(V.bUseWorldThrowDirection) O.SetArrayField(TEXT("worldThrowDirection"), {MakeShared<FJsonValueNumber>(V.WorldThrowDirection.X),MakeShared<FJsonValueNumber>(V.WorldThrowDirection.Y),MakeShared<FJsonValueNumber>(V.WorldThrowDirection.Z)});
}
static void Encode(const FProphecyBodyflipSpinOptions& V, FJsonObject& O)
{
    if(V.bInheritFlipSpeed) O.SetField(TEXT("flip"), MakeShared<FJsonValueNull>()); else O.SetNumberField(TEXT("flip"), double(V.FlipDegreesPerSecond));
    if(V.bInheritTwistSpeed) O.SetField(TEXT("twist"), MakeShared<FJsonValueNull>()); else O.SetNumberField(TEXT("twist"), double(V.TwistDegreesPerSecond));
    if(V.bInheritAxis) O.SetField(TEXT("turnAxis"), MakeShared<FJsonValueNull>()); else O.SetNumberField(TEXT("turnAxis"), int32(V.Axis));
    O.SetNumberField(TEXT("turnDelay"), double(V.DelaySeconds));
    O.SetNumberField(TEXT("turnIn"), double(V.AccelerateSeconds));
    O.SetNumberField(TEXT("turnOut"), double(V.DecelerateSeconds));
    O.SetBoolField(TEXT("instantSpin"), V.bInstantSpin);
}
static void Encode(const FProphecyBodyflipPoseOptions& V, FJsonObject& O)
{
    O.SetStringField(TEXT("pose"), Key(V.Pose));
    O.SetNumberField(TEXT("poseIn"), double(V.BlendInSeconds));
    O.SetNumberField(TEXT("poseHold"), double(V.HoldSeconds));
    O.SetNumberField(TEXT("poseOut"), double(V.BlendOutSeconds));
}
static void Encode(const FProphecyBodyflipSettings& V, FJsonObject& O)
{
    O.SetStringField(TEXT("mode"), Key(V.Sequence));
    O.SetNumberField(TEXT("trimOut"), double(V.PrepareSeconds));
    O.SetNumberField(TEXT("startYaw"), double(V.StartYawDegrees));
    O.SetNumberField(TEXT("runSeconds"), double(V.RunSeconds));
    O.SetNumberField(TEXT("runPhase"), double(V.GaitPhase));
    O.SetNumberField(TEXT("jumpBlend"), double(V.BodyBlendSeconds));
    O.SetNumberField(TEXT("legBlend"), double(V.LegBlendSeconds));
    O.SetNumberField(TEXT("legFollow"), double(V.LegFollowSeconds));
    O.SetNumberField(TEXT("handFollow"), double(V.HandFollowSeconds));
    O.SetNumberField(TEXT("handReturn"), double(V.HandReturnSeconds));
    O.SetNumberField(TEXT("handBend"), double(V.HandBendSeconds));
    O.SetNumberField(TEXT("fallCap"), double(V.FallCapCmPerSecond)*0.01);
    O.SetStringField(TEXT("jumpFoot"), Key(V.SupportingFoot));
    O.SetNumberField(TEXT("supportReach"), double(V.ReachRatio));
    O.SetNumberField(TEXT("supportTrigger"), double(V.ContactDistanceCm)*0.01);
    O.SetNumberField(TEXT("supportAlpha"), double(V.SupportLeadAlpha));
    O.SetNumberField(TEXT("supportSpeed"), double(V.FootSpeedCmPerSecond));
    O.SetNumberField(TEXT("supportCone"), double(V.FootConeDegrees));
    O.SetNumberField(TEXT("handCone"), double(V.HandConeDegrees));
    O.SetNumberField(TEXT("jumpSkew"), double(V.JumpVerticalSkew));
    O.SetNumberField(TEXT("jumpBuildX"), double(V.SmallJumpThresholdPercent));
    O.SetNumberField(TEXT("jumpBuildY"), double(V.MediumJumpThresholdPercent));
    O.SetNumberField(TEXT("loadMs"), double(V.SmallLoadSeconds)*1000);
    O.SetNumberField(TEXT("loadYMs"), double(V.MediumLoadSeconds)*1000);
    O.SetNumberField(TEXT("loadFullMs"), double(V.FullLoadSeconds)*1000);
    O.SetNumberField(TEXT("buildDepth"), double(V.LoadDepthCm)*0.01);
    O.SetNumberField(TEXT("rebound"), double(V.Rebound));
    O.SetNumberField(TEXT("spinLag"), double(V.SpinLag));
    O.SetNumberField(TEXT("spinInertia"), double(V.SpinInertia));
    O.SetNumberField(TEXT("flipSpeed"), double(V.InitialFlipSpeed));
    O.SetNumberField(TEXT("twistSpeed"), double(V.InitialTwistSpeed));
    O.SetNumberField(TEXT("axis"), int32(V.InitialFlipAxis));
    O.SetBoolField(TEXT("aim"), V.bAim);
    O.SetNumberField(TEXT("aimWeight"), double(V.AimWeight));
    O.SetBoolField(TEXT("kickToArmed"), V.bDirectToArmed);
    O.SetBoolField(TEXT("undoRotation"), V.bUndoAttackRotation);
    O.SetNumberField(TEXT("pelvisAttackCompensation"), double(V.PelvisAttackCompensation));
    O.SetBoolField(TEXT("softAttackLegs"), V.bSoftAttackLegs);
    O.SetBoolField(TEXT("surfaceIK"), V.bSurfaceIK);
    O.SetBoolField(TEXT("matchLeg"), V.bMatchJumpPose);
    O.SetBoolField(TEXT("airFlip"), V.bAirFlip);
    O.SetNumberField(TEXT("standRatio"), double(V.StandingJumpSpeedRatio));
    O.SetNumberField(TEXT("plantPitch"), double(V.PlantPitchDegrees));
    O.SetNumberField(TEXT("toeOffPitch"), double(V.ToeOffPitchDegrees));
    O.SetNumberField(TEXT("footRollSpeed"), double(V.FootRollDegreesPerSecond));
    O.SetBoolField(TEXT("motionCompensation"), V.bMotionCompensation);
    O.SetBoolField(TEXT("distributePelvisTurn"), V.bDistributePelvisTurn);
    O.SetBoolField(TEXT("pikeSpineAbsorb"), V.bPikeThrustSteering);
    O.SetBoolField(TEXT("momentum3D"), V.bMomentum3D);
    O.SetBoolField(TEXT("spaceFallAnimation"), V.bSpaceFallingAnimation);
    if(V.AttackReturnSeconds < 0) O.SetField(TEXT("attackReturnDuration"), MakeShared<FJsonValueNull>()); else O.SetNumberField(TEXT("attackReturnDuration"), V.AttackReturnSeconds);
    O.SetNumberField(TEXT("attackReturnDistance"), V.AttackReturnDistanceWeight);
    O.SetNumberField(TEXT("bigThrowReturnFrames"), V.BigThrowReturnFrames);
    O.SetNumberField(TEXT("smallThrowReturnFrames"), V.SmallThrowReturnFrames);
    O.SetNumberField(TEXT("poseBlendIn"), V.PoseBlendSeconds);
    O.SetNumberField(TEXT("poseBlendDistance"), V.PoseBlendDistanceWeight);
    O.SetNumberField(TEXT("poseEaseIn"), V.PoseEaseIn);
    O.SetNumberField(TEXT("poseExponent"), V.PoseExponent);
    O.SetNumberField(TEXT("poseEaseOut"), V.PoseEaseOut);
    O.SetNumberField(TEXT("poseResponseSpeed"), V.PoseFullResponseDegreesPerSecond);
    O.SetNumberField(TEXT("poseResponseTime"), V.PoseSpinResponseSeconds);
    O.SetBoolField(TEXT("invertPoseVariants"), V.bInvertPoseVariants);
    O.SetBoolField(TEXT("footTargets"), V.bFootTargets);
    O.SetBoolField(TEXT("handTargets"), V.bHandTargets);
    auto Cuts=MakeShared<FJsonObject>();
    for(const auto& Row:V.AttackEndFrames) if(Row.Key!=EProphecyBodyflipAttack::None) Cuts->SetNumberField(Key(Row.Key),Row.Value);
    O.SetObjectField(TEXT("attackEndFrames"),Cuts);
    auto Poses=MakeShared<FJsonObject>();
    for(const auto& Row:V.PoseTuning) if(Row.Key!=EProphecyBodyflipPose::None&&Row.Key!=EProphecyBodyflipPose::Keep)
    {
        auto Tuning=MakeShared<FJsonObject>();Tuning->SetNumberField(TEXT("wobbleSpeed"),Row.Value.WobbleSpeed);Tuning->SetNumberField(TEXT("wobbleAmplitude"),Row.Value.WobbleAmplitude);
        Poses->SetObjectField(Key(Row.Key),Tuning);
    }
    O.SetObjectField(TEXT("poseTuning"),Poses);
    O.SetArrayField(TEXT("jumpEvents"), {});
    O.SetStringField(TEXT("attack"), V.bWeaponDrawn ? TEXT("pike") : TEXT("none"));
    O.SetBoolField(TEXT("ramps"), false);
}
static FString Serialize(const TSharedRef<FJsonObject>& Object){FString Result; FJsonSerializer::Serialize(Object,TJsonWriterFactory<>::Create(&Result));return Result;}
static TSharedRef<FJsonObject> Jump(float Percent,EProphecyBodyflipPush Push,const FProphecyBodyflipSpinOptions& Spin,const FProphecyBodyflipPoseOptions& Pose,const FProphecyBodyflipAttackOptions& Attack)
{
    auto O=MakeShared<FJsonObject>(); O->SetNumberField(TEXT("jumpPercent"),Percent); O->SetStringField(TEXT("pushWith"),Key(Push)); O->SetNumberField(TEXT("spinVersion"),2); Encode(Spin,*O); Encode(Pose,*O); Encode(Attack,*O); return O;
}
}
bool UProphecyBodyflipLibrary::StartBodyflipWithOptions(AProphecyAgent* Agent,const FProphecyBodyflipSettings& Settings,FString& Error)
{ auto O=MakeShared<FJsonObject>(); ProphecyBodyflipOptions::Encode(Settings,*O); return StartBodyflip(Agent,ProphecyBodyflipOptions::Serialize(O),FString(),Error); }
bool UProphecyBodyflipLibrary::QueueBodyflipJumpWithOptions(AProphecyAgent* Agent,float AtTime,float JumpPercent,EProphecyBodyflipPush PushWith,const FProphecyBodyflipSpinOptions& Spin,const FProphecyBodyflipPoseOptions& Pose,const FProphecyBodyflipAttackOptions& Attack,FString& Error,bool Enabled)
{ auto Event=ProphecyBodyflipOptions::Jump(JumpPercent,PushWith,Spin,Pose,Attack);Event->SetBoolField(TEXT("enabled"),Enabled);return QueueBodyflipJump(Agent,AtTime,ProphecyBodyflipOptions::Serialize(Event),Error); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "UObject/UnrealType.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBodyflipBlueprintOptionsTest,"Prophecy.Bodyflip.Controls.BlueprintOptions",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FBodyflipBlueprintOptionsTest::RunTest(const FString&)
{
    using namespace ProphecyBodyflipOptions;
    FProphecyBodyflipSpinOptions Spin; FProphecyBodyflipPoseOptions Pose; FProphecyBodyflipAttackOptions Attack;
    auto O=Jump(100,EProphecyBodyflipPush::Foot,Spin,Pose,Attack);
    TestTrue(TEXT("Unconnected spin preserves previous speeds and axis"),O->Values[TEXT("flip")]->IsNull()&&O->Values[TEXT("twist")]->IsNull()&&O->Values[TEXT("turnAxis")]->IsNull());
    Spin.bInheritFlipSpeed=false;Spin.bInheritTwistSpeed=false;Spin.bInheritAxis=false;
    Spin.FlipDegreesPerSecond=-240;Spin.TwistDegreesPerSecond=0;Spin.Axis=EProphecyBodyflipAxis::Left;Spin.bInstantSpin=true;
    Pose.Pose=EProphecyBodyflipPose::Pose3;Pose.BlendOutSeconds=.7f;
    Attack.Attack=EProphecyBodyflipAttack::BigThrow;Attack.ThrowChargePercent=62;Attack.ThrowSpeedMultiplier=1.4f;Attack.DelaySeconds=.3f;
    O=Jump(175,EProphecyBodyflipPush::BothHands,Spin,Pose,Attack);
    TestEqual(TEXT("Jump strength"),O->GetNumberField(TEXT("jumpPercent")),175.);
    TestEqual(TEXT("Paired hand selection"),O->GetStringField(TEXT("pushWith")),FString(TEXT("handBoth")));
    TestEqual(TEXT("Signed velocity"),O->GetNumberField(TEXT("flip")),-240.);
    TestEqual(TEXT("Explicit zero stops spin"),O->GetNumberField(TEXT("twist")),0.);
    TestEqual(TEXT("Left axis index"),O->GetNumberField(TEXT("turnAxis")),9.);
    TestEqual(TEXT("Speed contract version"),O->GetNumberField(TEXT("spinVersion")),2.);
    TestTrue(TEXT("Instant spin"),O->GetBoolField(TEXT("instantSpin")));
    TestEqual(TEXT("Pose dropdown"),O->GetStringField(TEXT("pose")),FString(TEXT("pose3")));
    TestEqual(TEXT("Pose return"),O->GetNumberField(TEXT("poseOut")),double(.7f));
    TestEqual(TEXT("Throw dropdown"),O->GetStringField(TEXT("attack")),FString(TEXT("big-throw")));
    TestEqual(TEXT("Throw charge"),O->GetNumberField(TEXT("throwCharge")),62.);
    TestEqual(TEXT("Throw speed"),O->GetNumberField(TEXT("throwSpeed")),double(1.4f));
    TestEqual(TEXT("Attack delay"),O->GetNumberField(TEXT("attackDelay")),double(.3f));
    const TCHAR* Attacks[]={TEXT("none"),TEXT("headbutt"),TEXT("hookL"),TEXT("hookR"),TEXT("jabL"),TEXT("jabR"),TEXT("KickL"),TEXT("KickR"),TEXT("overL"),TEXT("overR"),TEXT("pike"),TEXT("slashL"),TEXT("slashLD"),TEXT("slashLU"),TEXT("slashR"),TEXT("slashRD"),TEXT("slashRU"),TEXT("sweepKick"),TEXT("big-throw"),TEXT("small-throw")};
    for(int32 I=0;I<UE_ARRAY_COUNT(Attacks);++I)TestEqual(TEXT("Every attack maps to the canonical clip"),FString(Key(EProphecyBodyflipAttack(I))),FString(Attacks[I]));
    FProphecyBodyflipSettings Settings;auto S=MakeShared<FJsonObject>();Encode(Settings,*S);
    TestEqual(TEXT("Default mode"),S->GetStringField(TEXT("mode")),FString(TEXT("idle")));
    TestEqual(TEXT("No invented initial marker"),S->GetArrayField(TEXT("jumpEvents")).Num(),0);
    TestEqual(TEXT("Fall cap converts cm/s to m/s"),S->GetNumberField(TEXT("fallCap")),20.);
    TestEqual(TEXT("Contact cm to m"),S->GetNumberField(TEXT("supportTrigger")),.05);
    TestEqual(TEXT("Foot speed keeps its authored cm/s"),S->GetNumberField(TEXT("supportSpeed")),800.);
    TestTrue(TEXT("Seconds to load milliseconds"),FMath::IsNearlyEqual(S->GetNumberField(TEXT("loadMs")),100.,.00001));
    TestEqual(TEXT("Load depth cm to m"),S->GetNumberField(TEXT("buildDepth")),.15);
    Settings.Sequence=EProphecyBodyflipSequence::SpaceGym;Settings.bWeaponDrawn=true;Encode(Settings,*S);
    TestEqual(TEXT("Space gym choice"),S->GetStringField(TEXT("mode")),FString(TEXT("spaceGym")));
    TestEqual(TEXT("Drawn NN choice"),S->GetStringField(TEXT("attack")),FString(TEXT("pike")));
    for(const FName Name:{FName(TEXT("StartBodyflipWithOptions")),FName(TEXT("QueueBodyflipJumpWithOptions"))})
    {
        const auto* Function=UProphecyBodyflipLibrary::StaticClass()->FindFunctionByName(Name);
        if(!TestNotNull(TEXT("Typed Blueprint node registered"),Function))continue;
        TestTrue(TEXT("Callable from Blueprint"),Function->HasAnyFunctionFlags(FUNC_BlueprintCallable));
        for(TFieldIterator<FProperty> It(Function);It;++It)
            if(It->HasAnyPropertyFlags(CPF_Parm)&&!It->HasAnyPropertyFlags(CPF_OutParm))
                TestFalse(TEXT("No JSON/string input pins"),It->IsA<FStrProperty>());
    }
    const auto* Function=UProphecyBodyflipLibrary::StaticClass()->FindFunctionByName(TEXT("QueueBodyflipJumpWithOptions"));
    if(Function)for(const FName Name:{FName(TEXT("Spin")),FName(TEXT("Pose")),FName(TEXT("Attack"))})
    {
        const auto* Property=FindFProperty<FStructProperty>(Function,Name);
        if(!TestNotNull(TEXT("Options expose splittable struct pins"),Property))continue;
        for(TFieldIterator<FProperty> It(Property->Struct);It;++It)TestTrue(TEXT("Each option is writable in Blueprint"),It->HasAnyPropertyFlags(CPF_BlueprintVisible)&&!It->HasAnyPropertyFlags(CPF_BlueprintReadOnly));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBodyflipLabTuningTest,"Prophecy.Bodyflip.Controls.SavedLabTuning",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FBodyflipLabTuningTest::RunTest(const FString&)
{
    using namespace ProphecyBodyflipOptions;
    FString Text;TSharedPtr<FJsonObject> Preset;
    if(!TestTrue(TEXT("Captured lab tuning is staged"),FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/LabSettings.json")))))return false;
    if(!TestTrue(TEXT("Captured tuning parses"),FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Preset)))return false;
    const auto Expected=Preset->GetObjectField(TEXT("settings"));auto Actual=MakeShared<FJsonObject>();Encode(FProphecyBodyflipSettings(),*Actual);
    // Scene mode, horizon, initial spin, target and markers belong to the saved-setup node.
    // Normal Start remains idle with no invented gameplay jump or spin.
    for(const auto& Pair:Actual->Values)
    {
        const auto& Key=Pair.Key;
        if(Key==TEXT("mode")||Key==TEXT("trimOut")||Key==TEXT("flipSpeed")||Key==TEXT("attack")||Key==TEXT("ramps")||Key==TEXT("jumpEvents"))continue;
        const auto* Want=Expected->Values.Find(Key);if(!TestNotNull(*Key,Want))continue;
        if(Pair.Value->Type==EJson::Number)TestTrue(*Key,FMath::IsNearlyEqual(Pair.Value->AsNumber(),(*Want)->AsNumber(),1.e-6*FMath::Max(1.,FMath::Abs((*Want)->AsNumber()))));
        else if(Pair.Value->Type==EJson::Boolean)TestEqual(*Key,Pair.Value->AsBool(),(*Want)->AsBool());
        else if(Pair.Value->Type==EJson::String)TestEqual(*Key,Pair.Value->AsString(),(*Want)->AsString());
        else if(Key==TEXT("attackEndFrames"))
        {
            const auto A=Pair.Value->AsObject(),B=(*Want)->AsObject();TestEqual(TEXT("All saved cuts"),A->Values.Num(),B->Values.Num());
            for(const auto& Cut:B->Values)TestEqual(*Cut.Key,A->GetNumberField(Cut.Key),Cut.Value->AsNumber());
        }
        else if(Key==TEXT("poseTuning"))
        {
            const auto A=Pair.Value->AsObject(),B=(*Want)->AsObject();TestEqual(TEXT("All four authored poses"),A->Values.Num(),4);
            for(const auto& Row:B->Values)for(const TCHAR* Field:{TEXT("wobbleSpeed"),TEXT("wobbleAmplitude")})
                TestEqual(*(Row.Key+TEXT(".")+Field),A->GetObjectField(Row.Key)->GetNumberField(Field),Row.Value->AsObject()->GetNumberField(Field));
        }
    }
    TestEqual(TEXT("Keep pose preserves enum compatibility"),FString(Key(EProphecyBodyflipPose::Keep)),FString(TEXT("keep")));
    FProphecyBodyflipAttackOptions Throw;Throw.bUseWorldThrowDirection=true;Throw.WorldThrowDirection=FVector(3,4,5);
    auto E=MakeShared<FJsonObject>();Encode(Throw,*E);
    TestEqual(TEXT("World ray remains a direction for controller conversion"),E->GetArrayField(TEXT("worldThrowDirection"))[2]->AsNumber(),5.);
    FProphecyBodyflipSettings S;S.AttackReturnSeconds=-1;S.AttackEndFrames.Empty();Encode(S,*Actual);
    TestTrue(TEXT("Per-event return fallback is retained"),Actual->Values[TEXT("attackReturnDuration")]->IsNull());
    TestEqual(TEXT("Removing cuts restores clip defaults"),Actual->GetObjectField(TEXT("attackEndFrames"))->Values.Num(),0);
    S.bPikeThrustSteering=false;Encode(S,*Actual);
    TestFalse(TEXT("Pike steering can return to standard aim"),Actual->GetBoolField(TEXT("pikeSpineAbsorb")));
    TestNotNull(TEXT("Pike steering is exposed to Blueprint"),FindFProperty<FBoolProperty>(FProphecyBodyflipSettings::StaticStruct(),TEXT("bPikeThrustSteering")));
    const auto* Function=UProphecyBodyflipLibrary::StaticClass()->FindFunctionByName(TEXT("QueueBodyflipJumpWithOptions"));
    TestNotNull(TEXT("Jump Enabled pin is available"),FindFProperty<FBoolProperty>(Function,TEXT("Enabled")));
    TestNotNull(TEXT("Saved lab setup is callable"),UProphecyBodyflipLibrary::StaticClass()->FindFunctionByName(TEXT("StartBodyflipSavedLabSetup")));
    return !HasAnyErrors();
}
#endif
