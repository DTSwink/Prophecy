#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyBodyflipLibrary.h"
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyBodyflipRigProfile.h"
#include "ProphecyBodyflipProjectiles.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyThrowMath.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyPhysicsSkeletalMeshComponent.h"
#include "ProphecyHitEventTestSink.h"
#include "UObject/StrongObjectPtr.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

// Candidate helper for the existing isolated Bodyflip agent test; no new world,
// model, external process or public test hook. Run once after PREPARING clears in
// each kinematic/physical mode, and optionally once while paused. The caller owns
// its test fixture and decides whether to provide an already-loaded valid clip
// and an existing foreign primitive for the additional layer/grab checks.
#include "ProphecyThrowLibrary.h"
#include "ProphecyThrowRuntime.h"
#include "ProphecyReachLibrary.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyArmedPoseLibrary.h"
#include "ProphecyArmedPose.h"
#include "ProphecyGetUpLibrary.h"
#include "ProphecyGetUp.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "Animation/AnimSequence.h"

static bool CheckBodyflipActionAdmission(FAutomationTestBase& Test,
    AProphecyAgent* Agent,AProphecyNNLocomotionManager* Manager,
    UAnimSequenceBase* ValidAnimation=nullptr,UPrimitiveComponent* GrabTarget=nullptr)
{
    FProphecyBodyflipState Before,After;
    if(!Test.TestTrue(TEXT("Admission fixture has active Bodyflip"),
        Agent&&Manager&&ProphecyBodyflip::Active(Agent)
        &&UProphecyBodyflipLibrary::GetBodyflipState(Agent,Before)))return false;
    const FTransform ActorBefore=Agent->GetActorTransform();
    const auto SimulationBefore=Agent->GetSimulationMode();
    FProphecyNNRuntimeBenchmarkStats StatsBefore,StatsAfter;
    const bool HaveStats=Manager->ReadRuntimeBenchmarkStats(StatsBefore);
    const FVector Target=Agent->GetActorLocation()+FVector(100,0,100);
    const FTransform HandTarget(FQuat::Identity,Target);
    bool Ok=true;
    // Both async entry points share Start; refusal must create no ticking throw
    // and therefore no later release event. Both approved throw kinds are valid.
    for(auto Kind:{EProphecyThrow::BigThrow,EProphecyThrow::SmallThrow})
    for(bool Automatic:{false,true})
    {
        auto* Task=Automatic
            ?UProphecyThrowAction::PlayLabThrow(Agent,Kind,Target,FProphecyThrowPhysics{},50)
            :UProphecyThrowAction::BeginLabThrow(Agent,Kind,Target,FProphecyThrowPhysics{});
        if(!Test.TestNotNull(TEXT("Throw request object"),Task)){Ok=false;continue;}
        Task->Activate();
        Ok&=Test.TestFalse(TEXT("Bodyflip refuses legacy throw ownership"),ProphecyThrow::Active(Agent));
        FProphecyThrowState ThrowState;
        Ok&=Test.TestFalse(TEXT("Rejected throw retains no state"),UProphecyThrowLibrary::GetLabThrowState(Agent,ThrowState));
        Ok&=Test.TestFalse(TEXT("Rejected throw cannot release"),UProphecyThrowLibrary::ReleaseLabThrow(Agent));
        UProphecyThrowLibrary::CancelLabThrow(Agent); // Clean up if the guard regresses.
    }
    for(auto Hand:{EProphecyReachHand::Left,EProphecyReachHand::Right})
        Ok&=Test.TestFalse(TEXT("Bodyflip refuses reach"),UProphecyReachLibrary::ReachTarget(Agent,Hand,HandTarget));
    Ok&=Test.TestFalse(TEXT("Bodyflip refuses double reach"),UProphecyReachLibrary::DoubleReach(
        Agent,EProphecyDoubleReachMode::Both,HandTarget,HandTarget));
    if(GrabTarget)Ok&=Test.TestFalse(TEXT("Bodyflip refuses object grab"),UProphecyReachLibrary::GrabObject(
        Agent,EProphecyReachHand::Left,GrabTarget));
    Ok&=Test.TestFalse(TEXT("Rejected reach retains no state"),ProphecyReach::Active(Agent));
    UProphecyReachLibrary::StopReaching(Agent,0);
    Ok&=Test.TestTrue(TEXT("Reach disable remains available"),UProphecyReachLibrary::DoubleReach(
        Agent,EProphecyDoubleReachMode::Off,HandTarget,HandTarget));

    Ok&=Test.TestFalse(TEXT("Bodyflip refuses ordinary attack"),Agent->TriggerNNAttack(TEXT("slashLD"),Target));
    FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;
    Ok&=Test.TestFalse(TEXT("Rejected attack retains no state"),Agent->GetNNAttackState(Attack,Half,Armed,Hit,Frame));
    if(Agent->GetNNAttackState(Attack,Half,Armed,Hit,Frame))Agent->StopNNAttack();
    FString Error;
    // Owner admission has priority over attacker/model validation. The explicit
    // Bodyflip error proves these do not merely fail because the attacker is null.
    Ok&=Test.TestFalse(TEXT("Bodyflip refuses parry"),UProphecyNNDefenseLibrary::StartNNParry(Agent,nullptr,Error,1));
    Ok&=Test.TestTrue(TEXT("Parry reports the owner conflict"),Error.Contains(TEXT("Bodyflip")));
    Error.Reset();
    Ok&=Test.TestFalse(TEXT("Bodyflip refuses dodge"),UProphecyNNDefenseLibrary::StartNNDodge(Agent,nullptr,Error,1));
    Ok&=Test.TestTrue(TEXT("Dodge reports the owner conflict"),Error.Contains(TEXT("Bodyflip")));
    Ok&=Test.TestFalse(TEXT("Rejected defense creates no delayed request"),ProphecyDefenseArmedGate::IsWaiting(Agent));
    if(ProphecyDefenseArmedGate::IsWaiting(Agent)
        ||UProphecyNNDefenseLibrary::GetAgentState(Agent)!=EProphecyAgentState::Locomotion)
        UProphecyNNDefenseLibrary::StopNNDefense(Agent);
    Ok&=Test.TestFalse(TEXT("Bodyflip refuses get-up"),UProphecyGetUpLibrary::GetUp(Agent));
    Ok&=Test.TestFalse(TEXT("Rejected get-up retains no state"),ProphecyGetUp::IsActive(Agent));
    if(ProphecyGetUp::IsActive(Agent))ProphecyGetUp::Cancel(Agent);
    Error.Reset();
    Ok&=Test.TestFalse(TEXT("Bodyflip refuses manual Armed pose"),
        UProphecyArmedPoseLibrary::SetUpperBodyArmedPose(Agent,true,TEXT("slashLD"),Error));
    Ok&=Test.TestTrue(TEXT("Armed pose reports the owner conflict"),Error.Contains(TEXT("Bodyflip")));
    Ok&=Test.TestFalse(TEXT("Rejected Armed pose retains no state"),ProphecyArmedPose::Active(Agent));
    Ok&=Test.TestTrue(TEXT("Armed disable remains available"),
        UProphecyArmedPoseLibrary::SetUpperBodyArmedPose(Agent,false,TEXT("slashLD"),Error));

    if(ValidAnimation)
    {
        Ok&=Test.TestTrue(TEXT("Layer rejection uses a nonempty clip"),ValidAnimation->GetPlayLength()>0);
        Ok&=Test.TestFalse(TEXT("Bodyflip refuses NN animation layer"),Agent->PlayNNAnimationLayer(
            ValidAnimation,TEXT("spine_01"),.2f,.2f,1,false));
        Ok&=Test.TestFalse(TEXT("Rejected layer retains no state"),Agent->IsNNAnimationLayerActive());
        Agent->StopNNAnimationLayer(0);
    }
    if(auto* Anim=Agent->GetProphecyAnimInstance())
    {
        // A non-null transient sequence suffices for the legacy overlay API;
        // unlike NN layers, that API has no length validation or asset load.
        auto* Clip=ValidAnimation?ValidAnimation:NewObject<UAnimSequence>();
        auto* SavedClip=Anim->OverlayAnimation.Get();const auto SavedMode=Anim->OverlayMode;
        const bool SavedEnabled=Anim->bOverlayEnabled,SavedLoop=Anim->bLoopOverlay;
        const float SavedBlend=Anim->OverlayBlendSeconds,SavedRate=Anim->OverlayPlayRate;
        const int32 SavedRevision=Anim->OverlayPlaybackRevision;
        Ok&=Test.TestFalse(TEXT("Bodyflip refuses legacy animation overlay"),Agent->PlayAnimationOverlay(
            Clip,EProphecyAnimationOverlayMode::UpperBodyOnly,.2f,1,false,true));
        Ok&=Test.TestTrue(TEXT("Rejected overlay keeps its asset"),Anim->OverlayAnimation.Get()==SavedClip);
        Anim->OverlayAnimation=Clip; // Give Restart its otherwise-valid prerequisite.
        Ok&=Test.TestFalse(TEXT("Bodyflip refuses overlay restart"),Agent->RestartAnimationOverlay());
        Ok&=Test.TestEqual(TEXT("Rejected restart does not advance revision"),Anim->OverlayPlaybackRevision,SavedRevision);
        Anim->OverlayAnimation=SavedClip;Anim->OverlayMode=SavedMode;Anim->bOverlayEnabled=SavedEnabled;
        Anim->bLoopOverlay=SavedLoop;Anim->OverlayBlendSeconds=SavedBlend;Anim->OverlayPlayRate=SavedRate;
        Anim->OverlayPlaybackRevision=SavedRevision;
    }
    Ok&=Test.TestTrue(TEXT("Rejected actions retain Bodyflip"),UProphecyBodyflipLibrary::GetBodyflipState(Agent,After));
    Ok&=Test.TestTrue(TEXT("Rejected actions preserve source time and playback"),Before.Time==After.Time&&Before.Playing==After.Playing);
    Ok&=Test.TestTrue(TEXT("Rejected actions preserve solved pose and diagnostics"),Before.DiagnosticsJson==After.DiagnosticsJson&&Before.Error==After.Error);
    Ok&=Test.TestTrue(TEXT("Rejected actions preserve carrier"),Agent->GetActorTransform().Equals(ActorBefore,0));
    Ok&=Test.TestTrue(TEXT("Rejected actions preserve saved simulation mode"),Agent->GetSimulationMode()==SimulationBefore);
    if(HaveStats&&Manager->ReadRuntimeBenchmarkStats(StatsAfter))
        Ok&=Test.TestEqual(TEXT("Rejected actions execute no ordinary inference"),StatsAfter.ModelInferenceCalls,StatsBefore.ModelInferenceCalls);
    return Ok;
}

namespace ProphecySwordHolster { bool CheckBodyflipPendingAdmission(FAutomationTestBase& Test,AProphecyAgent* Agent); }

// A separate transient world and one native agent. No editor map/Blueprint is
// loaded or changed, and no second game instance is launched.
class FBodyflipAgentExercise : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;
    AProphecyNNLocomotionManager* Manager=nullptr;
    AProphecyAgent* Agent=nullptr;
    UPrimitiveComponent* FloorCollider=nullptr;
    bool CheckedAdmission=false;
    int32 Stage=0,Mode=0,Ticks=0,Checked=0,FootDiagnostic=0;
    TArray<TSharedPtr<FJsonValue>> FootMaterials;
    double Began=FPlatformTime::Seconds();
    FTransform Space;
    FTransform FloorSpace;
    FString NativeRigProfile;
    TArray<int32> PhysicalBones;
    bool TestedRebuildSeek=false;
    TArray<FName> TraceNames={TEXT("root"),TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    FVector StopRoot=FVector::ZeroVector;
    FVector InitialRoot=FVector::ZeroVector;
    FTransform BeforeRejectedSeek;
    FTransform StopLeft,StopRight;
    double RejectedSeekTime=0;
    uint64 ManagerInferenceAtStart=0;
    float InitialYaw=0;
    double WorstRoot=0,WorstTarget=0,WorstPhysical=0,WorstRotation=0,WorstPhysicalRotation=0,PhysicalSquared=0,PhysicalAngleSquared=0,WorstSegment=0;
    int32 PhysicalCount=0;TArray<TSharedPtr<FJsonValue>> Trace,BodyInventory;
    bool SawRise=false,SawSpin=false,DidPause=false;double PausedTime=0;
    TArray<TSharedPtr<FJsonValue>> ThrowSamples;
    FString ThrowDiagnosticError;
    FTransform GripInHand=FTransform::Identity;
    // The approved throw-source rig uses hand_l for both throws. New packets may
    // explicitly identify another hand without requiring a fixed pose index here.
    FName ThrowHandBone=TEXT("hand_l");
    FProphecyJoltBodyState ReleaseBody;
    bool HaveGrip=false;
    int32 HeldSamples=0,ReleaseSamples=0,IntegrationSamples=0;
    double ReleaseTime=-1,LastIntegrationTime=-1,WorstGripCm=0,WorstGripRad=0;
    struct FHandShape {FName Name;int32 Bone=INDEX_NONE;FProphecyJoltBodyHandle Handle;TArray<FVector> Corners;};
    TArray<FHandShape> Hands;
    TStrongObjectPtr<UProphecyHitEventTestSink> HandHitSink;
    TArray<TSharedPtr<FJsonValue>> HandContacts;
    TArray<TSharedPtr<FJsonObject>> PendingHandContacts;
    TSharedPtr<FJsonObject> HandEvent;
    TSet<int32> HandFrames;
    FString HandDiagnosticError;
    double HandTickStart=0,HandReturnEnd=-1,WorstArmSegment=0;
    bool IsThrowCase() const {return Mode==3||Mode==4;}
    bool IsHandCase() const {return Mode==5||Mode==6;}
    bool IsSavedCase() const {return Mode==7||Mode==8;}
    double SavedEnd=0,FloorDropCm=0;
    bool IsPhysicalCase() const {return Mode==1||Mode==8||IsThrowCase()||IsHandCase();}
    static TArray<TSharedPtr<FJsonValue>> XYZ(const FVector& V){return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};}
    static TArray<TSharedPtr<FJsonValue>> XYZW(const FQuat& Q){return {MakeShared<FJsonValueNumber>(Q.X),MakeShared<FJsonValueNumber>(Q.Y),MakeShared<FJsonValueNumber>(Q.Z),MakeShared<FJsonValueNumber>(Q.W)};}
    static TSharedPtr<FJsonObject> TransformJson(const FTransform& T){auto O=MakeShared<FJsonObject>();O->SetArrayField(TEXT("p"),XYZ(T.GetLocation()));O->SetArrayField(TEXT("q"),XYZW(T.GetRotation()));O->SetArrayField(TEXT("scale"),XYZ(T.GetScale3D()));return O;}
    static FVector JsonVector(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
    static FTransform JsonPose(const TArray<TSharedPtr<FJsonValue>>& P,const TArray<TSharedPtr<FJsonValue>>& Q)
    {return ProphecyThrow::ToUnreal(FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),JsonVector(P)));}
    static FTransform JsonObjectPose(const TArray<TSharedPtr<FJsonValue>>& P,const TArray<TSharedPtr<FJsonValue>>& Q)
    {
        // Procedural projectile vertices already use the lab-to-UE basis. Unlike
        // imported skeletal bones, their rotations need no FBX bone-axis offset.
        return FTransform(FQuat(-Q[0]->AsNumber(),-Q[2]->AsNumber(),-Q[1]->AsNumber(),Q[3]->AsNumber()).GetNormalized(),
            ProphecyThrow::ToUnrealPoint(JsonVector(P)));
    }
    static TSharedPtr<FJsonObject> BodyJson(const FProphecyJoltBodyState& B)
    {
        auto O=TransformJson(FTransform(B.Rotation,B.PositionCm));O->SetArrayField(TEXT("comCm"),XYZ(B.CenterOfMassPositionCm));
        O->SetArrayField(TEXT("velocityCmPerSecond"),XYZ(B.CenterOfMassVelocityCmPerSecond));O->SetArrayField(TEXT("omegaRadPerSecond"),XYZ(B.AngularVelocityRadiansPerSecond));
        O->SetBoolField(TEXT("dynamic"),B.bDynamic);O->SetBoolField(TEXT("active"),B.bActive);return O;
    }
    bool ReadThrowHand(FProphecyJoltBodyState& Hand,const TSharedPtr<const FJsonObject>& Packet)
    {
        FString HandName;if(Packet&&Packet->TryGetStringField(TEXT("handBone"),HandName))
        {
            if(HandName.IsEmpty()){ThrowDiagnosticError=TEXT("Throw packet has an empty hand bone");return false;}
            ThrowHandBone=FName(*HandName);
        }
        auto* Character=Agent?Agent->GetJoltCharacterComponent():nullptr;auto* Physics=World?World->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;FProphecyJoltBodyHandle Handle;
        if(!Character||!Physics||!Character->GetBodyHandle(ThrowHandBone,Handle)||!Physics->ReadBody(Handle,Hand).IsSuccess()||!Hand.bDynamic)
        {ThrowDiagnosticError=TEXT("Physical throw has no readable dynamic Jolt ")+ThrowHandBone.ToString();return false;}
        if(Hand.PositionCm.ContainsNaN()||Hand.Rotation.ContainsNaN()||Hand.CenterOfMassVelocityCmPerSecond.ContainsNaN()||Hand.AngularVelocityRadiansPerSecond.ContainsNaN())
        {ThrowDiagnosticError=TEXT("Non-finite physical throwing hand");return false;}return true;
    }
    void RecordThrowBoundary(const ProphecyBodyflip::FProjectileDiagnostic& D,const TCHAR* Phase)
    {
        const bool AtRelease=FCString::Strcmp(Phase,TEXT("release"))==0;
        if(!AtRelease&&(ReleaseTime<0||D.Time>ReleaseTime+4./60||D.Time<=LastIntegrationTime+1.e-9))return;
        if(!D.HasBody||!D.Launch){ThrowDiagnosticError=TEXT("Release boundary has no readable native projectile");return;}
        FProphecyJoltBodyState Hand;if(!ReadThrowHand(Hand,D.Launch))return;
        if(D.Body.PositionCm.ContainsNaN()||D.Body.Rotation.ContainsNaN()||D.Body.CenterOfMassVelocityCmPerSecond.ContainsNaN()||D.Body.AngularVelocityRadiansPerSecond.ContainsNaN())
        {ThrowDiagnosticError=TEXT("Non-finite native projectile");return;}
        auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("phase"),Phase);Row->SetNumberField(TEXT("time"),D.Time);Row->SetStringField(TEXT("id"),D.Id);
        Row->SetStringField(TEXT("handBone"),ThrowHandBone.ToString());
        Row->SetObjectField(TEXT("actualJoltHand"),BodyJson(Hand));Row->SetObjectField(TEXT("actualJoltProjectile"),BodyJson(D.Body));Row->SetObjectField(TEXT("visual"),TransformJson(D.Visual));
        FProphecyJoltWorldDiagnostics Diagnostics;World->GetSubsystem<UProphecyJoltWorldSubsystem>()->GetDiagnostics(Diagnostics);Row->SetNumberField(TEXT("completedSharedSteps"),double(Diagnostics.CompletedSteps));
        if(HaveGrip)
        {
            const FTransform FromActualHand=GripInHand*FTransform(Hand.Rotation,Hand.PositionCm);
            Row->SetObjectField(TEXT("objectFromActualHand"),TransformJson(FromActualHand));
            Row->SetNumberField(TEXT("objectToActualHandGapCm"),FVector::Distance(D.Body.PositionCm,FromActualHand.GetLocation()));
            Row->SetNumberField(TEXT("objectToActualHandAngleRad"),D.Body.Rotation.AngularDistance(FromActualHand.GetRotation()));
        }
        if(AtRelease)
        {
            ReleaseSamples++;ReleaseTime=D.ReleaseTime;ReleaseBody=D.Body;
            const FTransform Canonical=JsonObjectPose(D.Launch->GetArrayField(TEXT("p")),D.Launch->GetArrayField(TEXT("q")))*D.Space;
            const FVector Velocity=D.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(JsonVector(D.Launch->GetArrayField(TEXT("v")))));
            const FVector Omega=-D.Space.TransformVectorNoScale(ProphecyThrow::ToUnrealPoint(JsonVector(D.Launch->GetArrayField(TEXT("omega"))))*.01);
            const FVector COM=Canonical.TransformPosition(ProphecyThrow::ToUnrealPoint(JsonVector(D.Launch->GetArrayField(TEXT("comOffset")))));
            const FVector HandTransport=Hand.CenterOfMassVelocityCmPerSecond+FVector::CrossProduct(Hand.AngularVelocityRadiansPerSecond,D.Body.CenterOfMassPositionCm-Hand.CenterOfMassPositionCm);
            // Native Jolt rotations originate in float32. AngularDistance assumes
            // unit inputs; their small length error must not masquerade as a turn.
            const double PositionError=FVector::Distance(D.Body.PositionCm,Canonical.GetLocation()),AngleError=D.Body.Rotation.GetNormalized().AngularDistance(Canonical.GetRotation().GetNormalized());
            Row->SetObjectField(TEXT("canonicalLaunch"),MakeShared<FJsonObject>(*D.Launch));Row->SetObjectField(TEXT("canonicalWorldPose"),TransformJson(Canonical));
            Row->SetNumberField(TEXT("canonicalPositionErrorCm"),PositionError);Row->SetNumberField(TEXT("canonicalRotationErrorRad"),AngleError);
            Row->SetArrayField(TEXT("canonicalCOMErrorCm"),XYZ(D.Body.CenterOfMassPositionCm-COM));
            Row->SetArrayField(TEXT("canonicalVelocityErrorCmPerSecond"),XYZ(D.Body.CenterOfMassVelocityCmPerSecond-Velocity));
            Row->SetArrayField(TEXT("canonicalOmegaErrorRadPerSecond"),XYZ(D.Body.AngularVelocityRadiansPerSecond-Omega));
            Row->SetArrayField(TEXT("actualHandTransportAtProjectileCOM"),XYZ(HandTransport));Row->SetArrayField(TEXT("launchMinusActualHandTransport"),XYZ(D.Body.CenterOfMassVelocityCmPerSecond-HandTransport));
            // Reuse the existing target/geometry precision checks. Grip and launch
            // velocity discrepancies remain measured, without invented acceptance bounds.
            Test->TestTrue(TEXT("Created projectile matches canonical release position"),PositionError<.01);
            Test->TestTrue(TEXT("Created projectile matches canonical release rotation"),AngleError<1.e-5);
        }
        else
        {
            IntegrationSamples++;LastIntegrationTime=D.Time;
            Row->SetArrayField(TEXT("velocityChangeSinceReleaseCmPerSecond"),XYZ(D.Body.CenterOfMassVelocityCmPerSecond-ReleaseBody.CenterOfMassVelocityCmPerSecond));
            Row->SetArrayField(TEXT("omegaChangeSinceReleaseRadPerSecond"),XYZ(D.Body.AngularVelocityRadiansPerSecond-ReleaseBody.AngularVelocityRadiansPerSecond));
            Row->SetArrayField(TEXT("COMDeviationFromInitialVelocityCm"),XYZ(D.Body.CenterOfMassPositionCm-ReleaseBody.CenterOfMassPositionCm-ReleaseBody.CenterOfMassVelocityCmPerSecond*(D.Time-ReleaseTime)));
        }
        ThrowSamples.Add(MakeShared<FJsonValueObject>(Row));
    }
    void RecordHeldThrow(const TSharedPtr<FJsonObject>& Frame)
    {
        const auto& Held=Frame->GetArrayField(TEXT("held"));if(Held.IsEmpty())return;
        TArray<ProphecyBodyflip::FProjectileDiagnostic> Objects;ProphecyBodyflip::ReadProjectileDiagnostics(World,Objects);
        for(const auto& Value:Held)
        {
            const auto Packet=Value->AsObject();const auto* D=Objects.FindByPredicate([&](const auto& O){return O.Id==Packet->GetStringField(TEXT("id"));});
            if(!D||D->HasBody){ThrowDiagnosticError=TEXT("Held throw is missing its visual or already has a flight body");return;}
            FProphecyJoltBodyState Hand;if(!ReadThrowHand(Hand,Packet))return;
            const auto Pose=Frame->GetObjectField(TEXT("pose"));
            const int32 HandIndex=TraceNames.IndexOfByKey(ThrowHandBone);
            const auto& Points=Pose->GetArrayField(TEXT("points"));const auto& Rotations=Pose->GetArrayField(TEXT("q"));
            if(HandIndex==INDEX_NONE||!Points.IsValidIndex(HandIndex)||!Rotations.IsValidIndex(HandIndex))
            {ThrowDiagnosticError=TEXT("Canonical throw pose is missing ")+ThrowHandBone.ToString();return;}
            const FTransform CanonicalHand=JsonPose(Points[HandIndex]->AsArray(),Rotations[HandIndex]->AsArray())*D->Space;
            const FTransform CanonicalObject=JsonObjectPose(Packet->GetArrayField(TEXT("p")),Packet->GetArrayField(TEXT("q")))*D->Space;
            GripInHand=CanonicalObject.GetRelativeTransform(CanonicalHand);HaveGrip=true;
            const FTransform FromActualHand=GripInHand*FTransform(Hand.Rotation,Hand.PositionCm);
            const double Gap=FVector::Distance(D->Visual.GetLocation(),FromActualHand.GetLocation()),Angle=D->Visual.GetRotation().AngularDistance(FromActualHand.GetRotation());
            WorstGripCm=FMath::Max(WorstGripCm,Gap);WorstGripRad=FMath::Max(WorstGripRad,Angle);HeldSamples++;
            auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("phase"),TEXT("held-completed-frame"));Row->SetNumberField(TEXT("time"),D->Time);
            Row->SetStringField(TEXT("handBone"),ThrowHandBone.ToString());
            Row->SetObjectField(TEXT("actualJoltHand"),BodyJson(Hand));Row->SetObjectField(TEXT("canonicalHand"),TransformJson(CanonicalHand));Row->SetObjectField(TEXT("visual"),TransformJson(D->Visual));
            Row->SetObjectField(TEXT("objectFromActualHand"),TransformJson(FromActualHand));Row->SetNumberField(TEXT("objectToActualHandGapCm"),Gap);Row->SetNumberField(TEXT("objectToActualHandAngleRad"),Angle);
            ThrowSamples.Add(MakeShared<FJsonValueObject>(Row));
            Test->TestTrue(TEXT("Held visual follows canonical attachment"),D->Visual.GetLocation().Equals(CanonicalObject.GetLocation(),.01)&&D->Visual.GetRotation().AngularDistance(CanonicalObject.GetRotation())<1.e-5);
        }
    }
    void CheckPhysicalTracking()
    {
        Test->TestTrue(TEXT("Jolt maximum body position tracking error below20cm"),WorstPhysical<20);
        Test->TestTrue(TEXT("Jolt RMS body position tracking error below8cm"),PhysicalCount>0&&FMath::Sqrt(PhysicalSquared/PhysicalCount)<8);
        Test->TestTrue(TEXT("Jolt maximum body rotation tracking error below45deg"),WorstPhysicalRotation<FMath::DegreesToRadians(45.));
        Test->TestTrue(TEXT("Jolt RMS body rotation tracking error below20deg"),PhysicalCount>0&&FMath::Sqrt(PhysicalAngleSquared/PhysicalCount)<FMath::DegreesToRadians(20.));
        Test->TestTrue(TEXT("Physical leg segment length error below3cm"),WorstSegment<3);
    }
    bool InitializeHandAudit(const TSharedPtr<FJsonObject>& Profile,FString& Error)
    {
        auto* Physics=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        for(const FName Name:{FName(TEXT("hand_l")),FName(TEXT("hand_r"))})
        {
            FHandShape Hand;Hand.Name=Name;Hand.Bone=TraceNames.IndexOfByKey(Name);
            if(!Agent->GetJoltCharacterComponent()->GetBodyHandle(Name,Hand.Handle))
            {Error=TEXT("Missing native hand body: ")+Name.ToString();return false;}
            for(const auto& Body:Profile->GetArrayField(TEXT("bodies")))if(Body->AsObject()->GetStringField(TEXT("name"))==Name.ToString())
                for(const auto& Value:Body->AsObject()->GetArrayField(TEXT("shapes")))
                {
                    const auto Shape=Value->AsObject(),Local=Shape->GetObjectField(TEXT("local"));
                    if(Shape->GetStringField(TEXT("kind"))!=TEXT("box")){Error=TEXT("Native hand audit requires the captured support boxes");return false;}
                    const auto& Q=Local->GetArrayField(TEXT("rotation_xyzw"));
                    const FTransform Offset(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),JsonVector(Local->GetArrayField(TEXT("position_cm"))));
                    const FVector Half=JsonVector(Shape->GetArrayField(TEXT("half_extent_cm")));
                    for(int X:{-1,1})for(int Y:{-1,1})for(int Z:{-1,1})Hand.Corners.Add(Offset.TransformPosition(Half*FVector(X,Y,Z)));
                }
            if(Hand.Corners.IsEmpty()){Error=TEXT("Captured profile has no native hand support geometry");return false;}
            Hands.Add(MoveTemp(Hand));
        }
        HandHitSink.Reset(NewObject<UProphecyHitEventTestSink>());
        HandHitSink->OnReceived=[this]()
        {
            const auto& Hit=HandHitSink->LastHit;
            if(Stage!=2)return;
            if(IsHandCase()&&(Hit.GetComponent()!=FloorCollider||(Hit.MyBoneName!=TEXT("hand_l")&&Hit.MyBoneName!=TEXT("hand_r"))))return;
            if(Hit.ImpactPoint.ContainsNaN()||Hit.ImpactNormal.ContainsNaN()||HandHitSink->LastImpulse.ContainsNaN())
            {HandDiagnosticError=TEXT("Native hand contact contains a non-finite point, normal or solved impulse");return;}
            auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("bone"),Hit.MyBoneName.ToString());
            Row->SetStringField(TEXT("otherBone"),Hit.BoneName.ToString());Row->SetBoolField(TEXT("floor"),Hit.GetComponent()==FloorCollider);
            Row->SetNumberField(TEXT("intervalStart"),HandTickStart);Row->SetNumberField(TEXT("worldTime"),World->GetTimeSeconds());
            Row->SetBoolField(TEXT("blocking"),Hit.bBlockingHit);Row->SetArrayField(TEXT("pointCm"),XYZ(Hit.ImpactPoint));Row->SetArrayField(TEXT("normal"),XYZ(Hit.ImpactNormal));
            Row->SetArrayField(TEXT("impulseKgCmPerSecond"),XYZ(HandHitSink->LastImpulse));
            Row->SetNumberField(TEXT("upwardImpulseKgCmPerSecond"),FVector::DotProduct(HandHitSink->LastImpulse,FloorSpace.GetRotation().GetAxisZ()));
            PendingHandContacts.Add(Row);
        };
        Agent->GetPoseReferenceMesh()->OnComponentHit.AddDynamic(HandHitSink.Get(),&UProphecyHitEventTestSink::ComponentHit);
        // Existing rig admission already associated the receiver and bone names.
        // Enable only this fixture's selected native hand notifications.
        for(const auto& Hand:Hands)if(Mode==6||Hand.Name==TEXT("hand_l"))
            if(!Physics->SetBodyHitEvents(Hand.Handle,true).IsSuccess()){Error=TEXT("Could not enable native hand contact notifications");return false;}
        if(!IsHandCase())for(int32 Bone:PhysicalBones){FProphecyJoltBodyHandle Handle;if(!Agent->GetJoltCharacterComponent()->GetBodyHandle(TraceNames[Bone],Handle)||!Physics->SetBodyHitEvents(Handle,true).IsSuccess()){Error=TEXT("Could not enable native tracking contact diagnostics");return false;}}
        return true;
    }
    bool RecordHandFrame(const TSharedPtr<FJsonObject>& Frame,const TSharedPtr<FJsonObject>& Row,const TArray<FTransform>& Actual,double Time)
    {
        HandFrames.Add(FMath::RoundToInt(Time*60));Row->SetNumberField(TEXT("intervalStart"),HandTickStart);
        const TArray<TSharedPtr<FJsonValue>>* Events=nullptr;
        if(Frame->TryGetArrayField(TEXT("events"),Events))for(const auto& Event:*Events)
            if(Event->AsObject()->GetStringField(TEXT("id"))==TEXT("hand-push"))HandEvent=Event->AsObject();
        const auto Pose=Frame->GetObjectField(TEXT("pose"));const auto& Points=Pose->GetArrayField(TEXT("points"));const auto& Rotations=Pose->GetArrayField(TEXT("q"));
        const FVector Normal=FloorSpace.GetRotation().GetAxisZ(),Top=FloorSpace.TransformPosition(FVector(0,0,50));
        TArray<TSharedPtr<FJsonValue>> Rows;
        for(const auto& Hand:Hands)
        {
            FProphecyJoltBodyState Body;
            if(!World->GetSubsystem<UProphecyJoltWorldSubsystem>()->ReadBody(Hand.Handle,Body).IsSuccess()||!Body.bDynamic
                ||Body.PositionCm.ContainsNaN()||Body.Rotation.ContainsNaN()||Body.CenterOfMassPositionCm.ContainsNaN()||Body.CenterOfMassVelocityCmPerSecond.ContainsNaN()||Body.AngularVelocityRadiansPerSecond.ContainsNaN())return false;
            const FTransform Measured(Body.Rotation,Body.PositionCm),Canonical=JsonPose(Points[Hand.Bone]->AsArray(),Rotations[Hand.Bone]->AsArray())*Space;
            double ActualGap=TNumericLimits<double>::Max(),CanonicalGap=ActualGap;FVector Lowest=FVector::ZeroVector;
            for(const FVector& Corner:Hand.Corners)
            {
                const FVector WorldCorner=Measured.TransformPosition(Corner);const double Gap=FVector::DotProduct(WorldCorner-Top,Normal);
                if(Gap<ActualGap){ActualGap=Gap;Lowest=WorldCorner;}
                CanonicalGap=FMath::Min(CanonicalGap,FVector::DotProduct(Canonical.TransformPosition(Corner)-Top,Normal));
            }
            auto H=BodyJson(Body);H->SetStringField(TEXT("bone"),Hand.Name.ToString());H->SetNumberField(TEXT("actualFloorGapCm"),ActualGap);H->SetNumberField(TEXT("canonicalFloorGapCm"),CanonicalGap);
            H->SetArrayField(TEXT("lowestColliderPointCm"),XYZ(Lowest));const FVector FloorLocal=FloorSpace.InverseTransformPosition(Lowest);
            H->SetBoolField(TEXT("lowestPointInsideFloor"),FMath::Abs(FloorLocal.X)<=50&&FMath::Abs(FloorLocal.Y)<=50);
            const FVector Delta=Measured.GetLocation()-Canonical.GetLocation();H->SetNumberField(TEXT("tangentialTrackingErrorCm"),(Delta-Normal*FVector::DotProduct(Delta,Normal)).Length());Rows.Add(MakeShared<FJsonValueObject>(H));
        }
        for(int I:{8,9,12,13})WorstArmSegment=FMath::Max(WorstArmSegment,FMath::Abs(FVector::Distance(Actual[I].GetLocation(),Actual[I+1].GetLocation())-100*FVector::Distance(JsonVector(Points[I]->AsArray()),JsonVector(Points[I+1]->AsArray()))));
        Row->SetNumberField(TEXT("worstArmSegmentLengthErrorCm"),WorstArmSegment);Row->SetArrayField(TEXT("hands"),Rows);return true;
    }
    void CheckHandPush()
    {
        for(int I=0;I<=72;I++)if(!HandFrames.Contains(I)){Test->AddError(FString::Printf(TEXT("Hand fixture missed controller frame %d of 0..72"),I));break;}
        Test->TestTrue(TEXT("Physical arm segment length error below3cm"),WorstArmSegment<3);
        Test->TestTrue(TEXT("Native hand hits are delivered on the game thread"),HandHitSink.Get()&&HandHitSink->bOnlyGameThread);
        if(!HandEvent){Test->AddError(TEXT("Fresh native hand packet contains no hand-push event"));return;}
        FString Status,Kind,Side,Surface;HandEvent->TryGetStringField(TEXT("status"),Status);HandEvent->TryGetStringField(TEXT("supportKind"),Kind);HandEvent->TryGetStringField(TEXT("supportSide"),Side);HandEvent->TryGetStringField(TEXT("surfaceId"),Surface);
        Test->TestTrue(TEXT("Fresh event admits the requested floor hand push"),Status==TEXT("Push")&&Kind==TEXT("hand")&&Surface==TEXT("floor")&&Side==(Mode==6?TEXT("Both"):TEXT("L")));
        double Contact=0,Push=0,Release=0;
        if(!HandEvent->TryGetNumberField(TEXT("contactTime"),Contact)||!HandEvent->TryGetNumberField(TEXT("pushTime"),Push)||!HandEvent->TryGetNumberField(TEXT("releaseTime"),Release)
            ||!FMath::IsFinite(Contact)||!FMath::IsFinite(Push)||!FMath::IsFinite(Release)||Contact<0||Contact>Push||Push>=Release)
        {Test->AddError(TEXT("Fresh hand packet has no ordered finite contact/push/release interval"));return;}
        const TArray<TSharedPtr<FJsonValue>>* Releases=nullptr;double End[2]={-1,-1};
        if(HandEvent->TryGetArrayField(TEXT("handReleases"),Releases))for(const auto& Value:*Releases)
        {
            FString Name;double At=0;bool Early=true;const auto R=Value->AsObject();R->TryGetStringField(TEXT("side"),Name);R->TryGetBoolField(TEXT("early"),Early);
            const int I=Name==TEXT("L")?0:Name==TEXT("R")?1:-1;
            if(I>=0&&R->TryGetNumberField(TEXT("time"),At)&&FMath::IsFinite(At)&&!Early&&At>Push&&At<=Release+1.e-7)End[I]=At;
        }
        const int Count=Mode==6?2:1;
        for(int I=0;I<Count;I++)if(End[I]<0){Test->AddError(TEXT("Requested hand released early or lacks a valid push window"));return;}
        HandReturnEnd=FMath::Max(End[0],End[1])+.25+.4;
        Test->TestTrue(TEXT("Full capture includes the freshly timed hand follow and return"),HandReturnEnd<=1.2+1.e-6);
        int Solved[2]={0,0},Paired=0,Eligible=0;
        for(const auto& Value:Trace)
        {
            const auto Frame=Value->AsObject();const double Begin=Frame->GetNumberField(TEXT("intervalStart")),Finish=Frame->GetNumberField(TEXT("time"));
            if(Finish<=Begin||Begin<Push||Finish>(Count==2?FMath::Min(End[0],End[1]):End[0]))continue;
            ++Eligible;bool Hit[2]={false,false};
            for(const auto& ContactValue:HandContacts)
            {
                const auto C=ContactValue->AsObject();const double Impulse=C->GetNumberField(TEXT("upwardImpulseKgCmPerSecond"));
                if(C->GetNumberField(TEXT("intervalStart"))!=Begin||C->GetNumberField(TEXT("intervalEnd"))!=Finish||!C->GetBoolField(TEXT("blocking"))||!FMath::IsFinite(Impulse)||Impulse<=0)continue;
                Hit[C->GetStringField(TEXT("bone"))==TEXT("hand_l")?0:1]=true;
            }
            for(int I=0;I<Count;I++)Solved[I]+=Hit[I];Paired+=Hit[0]&&Hit[1];
            Frame->SetBoolField(TEXT("leftSolvedFloorContactDuringPush"),Hit[0]);Frame->SetBoolField(TEXT("rightSolvedFloorContactDuringPush"),Hit[1]);
        }
        Test->TestTrue(TEXT("Fresh push contains a complete advancing capture interval"),Eligible>0);
        Test->TestTrue(TEXT("Left hand has a positive solved floor impulse during push"),Solved[0]>0);
        if(Count==2)Test->TestTrue(TEXT("Both hands have solved floor contacts in the same complete push interval"),Solved[1]>0&&Paired>0);
    }
    void SaveReport(const FString& Error=FString())
    {
        auto Report=MakeShared<FJsonObject>();
        const bool Failed=!Error.IsEmpty()||Test->HasAnyErrors();
        Report->SetStringField(TEXT("status"),Failed?TEXT("failed"):TEXT("completed"));Report->SetStringField(TEXT("error"),Error.IsEmpty()&&Failed?TEXT("Automation assertions failed; see the matching test log"):Error);
        Report->SetNumberField(TEXT("stage"),Stage);Report->SetNumberField(TEXT("mode"),Mode);Report->SetNumberField(TEXT("ticks"),Ticks);Report->SetNumberField(TEXT("checkedFrames"),Checked);Report->SetNumberField(TEXT("checkedBodies"),PhysicalBones.Num());Report->SetNumberField(TEXT("elapsedSeconds"),FPlatformTime::Seconds()-Began);
        Report->SetNumberField(TEXT("floorDropCm"),FloorDropCm);Report->SetArrayField(TEXT("frames"),Trace);Report->SetArrayField(TEXT("physicsAssetBodies"),BodyInventory);
        Report->SetNumberField(TEXT("footDiagnostic"),FootDiagnostic);Report->SetArrayField(TEXT("footMaterials"),FootMaterials);
        if(IsPhysicalCase()&&!IsHandCase())Report->SetArrayField(TEXT("trackingContacts"),HandContacts);
        if(IsThrowCase())
        {
            Report->SetArrayField(TEXT("throwSamples"),ThrowSamples);Report->SetNumberField(TEXT("heldSamples"),HeldSamples);Report->SetNumberField(TEXT("releaseSamples"),ReleaseSamples);Report->SetNumberField(TEXT("integrationSamples"),IntegrationSamples);
            Report->SetNumberField(TEXT("heldGapMaxCm"),WorstGripCm);Report->SetNumberField(TEXT("heldAngleMaxRad"),WorstGripRad);
            Report->SetStringField(TEXT("gripAcceptance"),TEXT("Measured only: no grip-gap or launch-velocity acceptance tolerance has been specified"));
            Report->SetStringField(TEXT("integrationLimit"),TEXT("Exact release and first four frames of native substeps. Changes include gravity, aerodynamic forces, gyroscopic motion, damping and contacts; no contact cause is isolated."));
        }
        if(IsHandCase())
        {
            if(HandEvent)Report->SetObjectField(TEXT("handEvent"),HandEvent);
            Report->SetArrayField(TEXT("handFloorContacts"),HandContacts);Report->SetNumberField(TEXT("handReturnEnd"),HandReturnEnd);Report->SetNumberField(TEXT("uniqueControllerFrames"),HandFrames.Num());
            Report->SetNumberField(TEXT("armSegmentLengthMaxCm"),WorstArmSegment);
            Report->SetStringField(TEXT("contactEvidenceLimit"),TEXT("Native solved impulses aggregated per body pair over each completed tick. Same-tick paired hits do not establish simultaneous substep contact or uninterrupted contact duration. Collider gaps are measured throughout push/follow/return without a new acceptance tolerance; released hands are not required to remain pinned."));
        }
        TArray<TSharedPtr<FJsonValue>> NamesJson;for(const auto Name:TraceNames)NamesJson.Add(MakeShared<FJsonValueString>(Name.ToString()));Report->SetArrayField(TEXT("names"),NamesJson);
        Report->SetObjectField(TEXT("worldSpace"),TransformJson(Space));Report->SetObjectField(TEXT("floor"),TransformJson(FloorSpace));Report->SetStringField(TEXT("actualPoseUnits"),TEXT("Unreal world centimetres, Z up"));
        TSharedPtr<FJsonObject> ProfileJson;if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(NativeRigProfile),ProfileJson))Report->SetObjectField(TEXT("nativeRigProfile"),ProfileJson);
        auto Metrics=MakeShared<FJsonObject>();Metrics->SetNumberField(TEXT("rootMaxCm"),WorstRoot);Metrics->SetNumberField(TEXT("targetMaxCm"),WorstTarget);Metrics->SetNumberField(TEXT("targetRotationMaxRad"),WorstRotation);Metrics->SetNumberField(TEXT("physicalMaxCm"),WorstPhysical);Metrics->SetNumberField(TEXT("physicalRotationMaxRad"),WorstPhysicalRotation);Metrics->SetNumberField(TEXT("physicalSamples"),PhysicalCount);Metrics->SetNumberField(TEXT("segmentLengthMaxCm"),WorstSegment);
        if(PhysicalCount){Metrics->SetNumberField(TEXT("physicalRmsCm"),FMath::Sqrt(PhysicalSquared/PhysicalCount));Metrics->SetNumberField(TEXT("physicalRotationRmsRad"),FMath::Sqrt(PhysicalAngleSquared/PhysicalCount));}
        Metrics->SetBoolField(TEXT("sawRise"),SawRise);Metrics->SetBoolField(TEXT("sawSpin"),SawSpin);Metrics->SetBoolField(TEXT("pausedAndResumed"),DidPause);Report->SetObjectField(TEXT("metrics"),Metrics);
        // Capture before Stop/Destroy: an early failure may precede the normal
        // per-frame row, and its exact current body pose is the useful evidence.
        if(Agent&&Agent->GetAgentMesh())
        {
            auto Last=MakeShared<FJsonObject>();Last->SetArrayField(TEXT("carrierRoot"),XYZ(Agent->GetRootLowPoint()));Last->SetObjectField(TEXT("componentWorld"),TransformJson(Agent->GetAgentMesh()->GetComponentTransform()));
            FProphecyBodyflipState State;if(UProphecyBodyflipLibrary::GetBodyflipState(Agent,State)){Last->SetNumberField(TEXT("time"),State.Time);Last->SetStringField(TEXT("phase"),State.Phase);Last->SetStringField(TEXT("controllerError"),State.Error);Last->SetBoolField(TEXT("playing"),State.Playing);TSharedPtr<FJsonObject> Frame;if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(State.DiagnosticsJson),Frame))Last->SetObjectField(TEXT("canonical"),Frame);}
            TArray<FTransform> Actual;Actual.SetNum(TraceNames.Num());if(Agent->SampleActualComponentPose(TraceNames,Actual)){TArray<TSharedPtr<FJsonValue>> Points,Rotations;for(const auto& Component:Actual){const FTransform Body=Component*Agent->GetAgentMesh()->GetComponentTransform();if(Body.ContainsNaN()){Points.Add(MakeShared<FJsonValueNull>());Rotations.Add(MakeShared<FJsonValueNull>());}else{Points.Add(MakeShared<FJsonValueArray>(XYZ(Body.GetLocation())));Rotations.Add(MakeShared<FJsonValueArray>(XYZW(Body.GetRotation())));}}auto Pose=MakeShared<FJsonObject>();Pose->SetArrayField(TEXT("points"),Points);Pose->SetArrayField(TEXT("q"),Rotations);Last->SetObjectField(TEXT("actualPose"),Pose);}
            Report->SetObjectField(TEXT("lastState"),Last);
        }
        FString Json;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BodyflipPort20261030");IFileManager::Get().MakeDirectory(*Folder,true);
        const TCHAR* File=FloorDropCm>0?(Mode==8?TEXT("agent-air-saved-jolt.json"):Mode==3?TEXT("agent-air-big-throw-jolt.json"):TEXT("agent-air-small-throw-jolt.json")):Mode==7?TEXT("agent-saved-kinematic.json"):Mode==8?TEXT("agent-saved-jolt.json"):Mode==0?TEXT("agent-kinematic.json"):Mode==1?TEXT("agent-jolt.json"):Mode==3?TEXT("agent-big-throw-jolt.json"):Mode==4?TEXT("agent-small-throw-jolt.json"):Mode==5?TEXT("agent-hand-left-jolt.json"):Mode==6?TEXT("agent-hand-both-jolt.json"):TEXT("agent-space.json");
        const FString Output=FootDiagnostic?FString::Printf(TEXT("agent-foot-diagnostic-%d.json"),FootDiagnostic):FString(File);
        if(!FFileHelper::SaveStringToFile(Json,*(Folder/Output)))Test->AddError(TEXT("Could not save partial Bodyflip agent diagnostic report"));
    }
    void Cleanup()
    {
        if(HandHitSink.Get())
        {
            HandHitSink->OnReceived={};
            if(Agent&&Agent->GetPoseReferenceMesh())Agent->GetPoseReferenceMesh()->OnComponentHit.RemoveDynamic(HandHitSink.Get(),&UProphecyHitEventTestSink::ComponentHit);
            HandHitSink.Reset();
        }
        if(World&&IsThrowCase())ProphecyBodyflip::SetProjectileDiagnosticObserver(World,{});
        if(Agent)UProphecyBodyflipLibrary::StopBodyflip(Agent);
        if(World){if(World->HasBegunPlay())World->EndPlay(EEndPlayReason::Quit);World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Fail(const FString& Error){Test->AddError(Error);SaveReport(Error);Cleanup();return true;}
    FString PhysicalFailure(const TCHAR* Operation) const
    {
        const auto* Character=Agent?Agent->GetJoltCharacterComponent():nullptr;
        return FString::Printf(TEXT("%s: manual=%d begun=%d mode=%d enabled=%d pending=%d stopped=%d; %s"),Operation,
            Agent&&Agent->bManualNNPoseApplication,Agent&&Agent->HasActorBegunPlay(),Agent?int32(Agent->GetSimulationMode()):-1,
            Agent&&Agent->IsJoltPhysicalAnimationEnabled(),Character&&Character->IsEnablePending(),Character&&Character->IsSteppingStopped(),
            Character?*Character->GetLastError():TEXT("No Jolt character component"));
    }
    bool SpawnManualAgent(FString& Error)
    {
        // The manager's default native shell is nonmanual. Build the production
        // separate-PhysicalMesh contract before BeginPlay, using its real assets.
        Agent=World->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),FTransform::Identity,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if(!Agent){Error=TEXT("Could not create manual Bodyflip agent");return false;}
        Agent->SetFlags(RF_Transient);Agent->bManualNNPoseApplication=true;Agent->bAutoEnsureStandaloneNNManager=false;
        Agent->AutoPossessAI=EAutoPossessAI::Disabled;Agent->AutoPossessPlayer=EAutoReceiveInput::Disabled;
        auto* Base=Agent->GetAgentMesh();auto* Mesh=NewObject<UProphecyPhysicsSkeletalMeshComponent>(Agent,TEXT("PhysicalMesh"),RF_Transient);
        Agent->AddInstanceComponent(Mesh);Mesh->SetupAttachment(Agent->GetAgentCapsule());Mesh->SetRelativeTransform(Base->GetRelativeTransform());
        Mesh->SetSkeletalMesh(Base->GetSkeletalMeshAsset());Mesh->SetPhysicsAsset(Base->GetPhysicsAsset());
        if(!Mesh->GetSkeletalMeshAsset()||!Mesh->GetPhysicsAsset()){Error=TEXT("Manual Bodyflip fixture is missing its actual mannequin or PHAT");return false;}
        Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));Mesh->SetGenerateOverlapEvents(false);Mesh->SetCanEverAffectNavigation(false);
        Mesh->bEnableUpdateRateOptimizations=false;Mesh->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Mesh->KinematicBonesUpdateType=EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
        Mesh->PhysicsTransformUpdateMode=EPhysicsTransformUpdateMode::SimulationUpatesComponentTransform;
        Mesh->RegisterComponent();Mesh->SetAllBodiesSimulatePhysics(false);
        Base->SetSkeletalMesh(nullptr);Agent->FinishSpawning(FTransform::Identity);Manager->PlayerAgent=Agent;
        return true;
    }
    bool BindManualAgent(FString& Error)
    {
        if(!Agent->HasActorBegunPlay())Agent->DispatchBeginPlay();
        int32 Id=INDEX_NONE;float Interval=0;bool Interpolate=false;
        if(!Agent->GetNNPoseDataSource(Id,Interval,Interpolate)){Error=TEXT("Manual Bodyflip agent has no manager pose source");return false;}
        auto* Mesh=Agent->GetPoseReferenceMesh();Mesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
        auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());
        if(!Anim){Error=TEXT("Could not bind Bodyflip fixture's real NN pose proxy");return false;}
        Anim->AgentId=Id;Anim->NNPoseIntervalSeconds=Interval;Anim->bInterpolateNNPose=Interpolate;Anim->bUseViewerGlobalPoseInterpolation=Interpolate;
        Mesh->TickAnimation(0,false);Mesh->RefreshBoneTransforms();
        if(!Agent->HasActorBegunPlay()||!Agent->IsActorTickEnabled()||!Agent->bAutoPublishManualFollowerSubstepTargets)
        {Error=TEXT("Manual Bodyflip fixture did not retain normal BeginPlay, actor ticking and automatic target publication");return false;}
        return true;
    }
public:
    explicit FBodyflipAgentExercise(FAutomationTestBase* In,int32 InMode=0,double InFloorDropCm=0,int32 InFootDiagnostic=0):Test(In),Mode(InMode),FootDiagnostic(InFootDiagnostic),FloorDropCm(InFloorDropCm){}
    ~FBodyflipAgentExercise(){Cleanup();}
    virtual bool Update() override
    {
        if(FPlatformTime::Seconds()-Began>240)return Fail(TEXT("Bodyflip native agent exercise timed out"));
        if(Stage==0)
        {
            const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
                .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
                .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
            if(!World)return Fail(TEXT("Could not create isolated Bodyflip world"));
            if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();
            if(!Manager)return Fail(TEXT("Could not create single-agent manager"));
            Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");
            Manager->EndpointAFallback=FVector(0,0,0);Manager->EndpointBFallback=FVector(0,2000,0);
            FString Error;if(!SpawnManualAgent(Error))return Fail(TEXT("Manual spawn: ")+Error);
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();
            if(Manager->ResolveAgent(Manager->GetAgentHandle(0))!=Agent)return Fail(TEXT("Native manager did not register the fixture's manual agent"));
            if(!BindManualAgent(Error))return Fail(TEXT("Manual pose binding: ")+Error);
            if(const auto* PhysicsAsset=Agent->GetPoseReferenceMesh()->GetPhysicsAsset())for(const auto& Entry:PhysicsAsset->SkeletalBodySetups){const auto* Body=Entry.Get();if(!Body)continue;auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("name"),Body->BoneName.ToString());Row->SetNumberField(TEXT("boxes"),Body->AggGeom.BoxElems.Num());Row->SetNumberField(TEXT("capsules"),Body->AggGeom.SphylElems.Num());Row->SetNumberField(TEXT("spheres"),Body->AggGeom.SphereElems.Num());Row->SetNumberField(TEXT("convexes"),Body->AggGeom.ConvexElems.Num());Row->SetNumberField(TEXT("massKg"),Body->CalculateMass(Agent->GetPoseReferenceMesh()));BodyInventory.Add(MakeShared<FJsonValueObject>(Row));}
            Stage=1;return false;
        }
        if(IsPhysicalCase()&&Stage==2){FProphecyBodyflipState Before;UProphecyBodyflipLibrary::GetBodyflipState(Agent,Before);HandTickStart=Before.Time;}
        World->Tick(LEVELTICK_All,1.f/60);
        if(IsPhysicalCase()&&Stage>=2)
        {
            FProphecyJoltWorldDiagnostics Health;
            const auto Result=World->GetSubsystem<UProphecyJoltWorldSubsystem>()->GetDiagnostics(Health);
            if(!Result.IsSuccess()||Health.bFaulted)return Fail(TEXT("Physical world stopped during playback: ")+Health.Failure);
        }
        if(Stage==1)
        {
            if(++Ticks<8)return false;Ticks=0;
            FString Error;auto* Physics=World->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldDiagnostics Ready;
            if(!Physics||!Physics->GetDiagnostics(Ready).IsSuccess())return Fail(TEXT("Cannot inspect the fixture's shared Jolt world"));
            if(Ready.bFaulted)return Fail(TEXT("Fixture's shared Jolt world is faulted: ")+Ready.Failure);
            // Normal agent startup can already own this world. Never replace it
            // merely to request the fixture's smaller capacity or worker setting.
            const bool ReusedWorld=Ready.bInitialized;
            if(!ReusedWorld&&!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(World,Error,256,0))return Fail(Error);
            if(!Physics->GetDiagnostics(Ready).IsSuccess()||!Ready.bInitialized||Ready.bFaulted||!Ready.WorldLifetime.IsValid())
                return Fail(TEXT("Fixture's shared Jolt world is not ready"));
            if(!Ready.Settings.GravityCmPerSecondSquared.Equals(FVector(0,0,World->GetGravityZ()),.001))
                return Fail(TEXT("Fixture's existing Jolt gravity differs from its Unreal world"));
            const uint32 RequiredBodies=uint32(BodyInventory.Num())+2; // Rig, floor and one projectile.
            if(Ready.Settings.MaxBodies<Ready.BodyCount||Ready.Settings.MaxBodies-Ready.BodyCount<RequiredBodies)
                return Fail(TEXT("Fixture's shared Jolt world lacks capacity for its rig, floor and projectile"));
            Test->AddInfo(FString::Printf(TEXT("%s shared Jolt world: bodies %u/%u, workers %d"),ReusedWorld?TEXT("Reusing"):TEXT("Initialized"),Ready.BodyCount,Ready.Settings.MaxBodies,Ready.Settings.WorkerThreads));
            Space=(Agent->bManualNNPoseApplication?Agent->GetAgentMesh()->GetRelativeTransform():Agent->GetAuthoredMeshRelativeTransform())*Agent->GetActorTransform();
            InitialRoot=Agent->GetRootLowPoint();const FTransform FloorTransform(Space.GetRotation(),InitialRoot+Space.TransformVector(FVector(0,0,-20-FloorDropCm)),FVector(20,20,.4));auto* Floor=World->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(),FloorTransform);if(!Floor)return Fail(TEXT("Could not create physical floor"));Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);Floor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));Floor->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Static);Floor->FinishSpawning(FloorTransform);
            auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(World);
            if(!Scene)
            {
                Scene=NewObject<UProphecyJoltSceneCollisionComponent>(Floor,NAME_None,RF_Transient);Floor->AddInstanceComponent(Scene);Scene->RegisterComponent();Scene->bAutomaticScenePhysics=true;
                if(!Scene->EnableSceneCollision(Error))return Fail(TEXT("Scene collision admission: ")+Error);
            }
            FloorSpace=FloorTransform;FloorCollider=Floor->GetStaticMeshComponent();
            if(!Scene->IsSceneCollisionEnabled()||Scene->IsEnablePending()||!Scene->bAutomaticScenePhysics)
                return Fail(TEXT("Shared scene collision is not ready for automatic stepping: ")+Scene->GetLastError());
            // Reconcile the newly spawned floor through the existing owner. This
            // preparation call imports queued sources without advancing physics.
            if(!Scene->PrepareJoltWorldStep(1.f/60,false,Error))return Fail(TEXT("Refresh fixture floor: ")+Error);
            FProphecyJoltBodyHandle FloorHandle;UObject* Associated=nullptr;
            if(!Scene->IsSceneCollisionEnabled()||Scene->IsEnablePending()||Scene->GetImportedBodyCount()!=1||!Scene->GetBodyHandle(*Floor->GetStaticMeshComponent(),INDEX_NONE,FloorHandle)||!Physics->OwnsBody(FloorHandle)||!Physics->ResolveAssociatedObject(FloorHandle,Associated).IsSuccess()||Associated!=Floor->GetStaticMeshComponent())return Fail(TEXT("Actual native floor was not imported into the shared Jolt world"));
            if(IsPhysicalCase())
            {
                // Match FightSetup/SwordFixture's discrete native admission using
                // only this transient agent and its freshly created live bodies.
                Agent->SetMACDEnabled(false);
                if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))return Fail(PhysicalFailure(TEXT("Physical mode admission")));
                for(FBodyInstance* Instance:Agent->GetPoseReferenceMesh()->Bodies)if(Instance)Instance->SetUseCCD(false);
                if(!Agent->EnableJoltPhysicalAnimation())return Fail(PhysicalFailure(TEXT("Jolt backend admission")));
                auto* Character=Agent->GetJoltCharacterComponent();FProphecyJoltBodyHandle Pelvis;FProphecyJoltBodyState Body;
                if(!Character||!Agent->IsJoltPhysicalAnimationEnabled()||Character->IsEnablePending()||Character->IsSteppingStopped()
                    ||Agent->GetSimulationMode()!=EProphecyAgentSimulationMode::Physical||!Character->GetBodyHandle(TEXT("pelvis"),Pelvis)
                    ||!Physics->OwnsBody(Pelvis)||!Physics->ReadBody(Pelvis,Body).IsSuccess()||!Body.bDynamic)
                    return Fail(PhysicalFailure(TEXT("Validate admitted native rig")));
            }
            InitialYaw=float(Agent->GetActorRotation().Yaw);
            // Controlled diagnostics only: preserve restitution, drives, shapes and
            // every non-foot material. Mode 3 isolates just the foot/foot pair.
            if(FootDiagnostic)
            {
                for(const FName Bone:{FName(TEXT("foot_l")),FName(TEXT("foot_r"))})
                {
                    FProphecyJoltBodyHandle Handle;FProphecyJoltBodyMaterial Before,After;
                    if(!Agent->GetJoltCharacterComponent()->GetBodyHandle(Bone,Handle)||!Physics->ReadBodyMaterial(Handle,Before).IsSuccess())return Fail(TEXT("Read diagnostic foot material"));
                    if(FootDiagnostic==2)
                    {
                        FProphecyJoltMaterialUpdate Update;Update.Handle=Handle;Update.Material=Before;Update.Material.Friction=0;Update.Material.FrictionCombineMode=1; // Minimum
                        if(!Physics->UpdateBodyMaterials(MakeArrayView(&Update,1)).IsSuccess())return Fail(TEXT("Apply zero foot friction"));
                    }
                    if(!Physics->ReadBodyMaterial(Handle,After).IsSuccess())return Fail(TEXT("Verify diagnostic foot material"));
                    auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("bone"),Bone.ToString());Row->SetNumberField(TEXT("beforeFriction"),Before.Friction);Row->SetNumberField(TEXT("afterFriction"),After.Friction);Row->SetNumberField(TEXT("beforeCombine"),Before.FrictionCombineMode);Row->SetNumberField(TEXT("afterCombine"),After.FrictionCombineMode);Row->SetNumberField(TEXT("restitution"),After.Restitution);FootMaterials.Add(MakeShared<FJsonValueObject>(Row));
                    Test->TestEqual(TEXT("Foot diagnostic preserves restitution"),After.Restitution,Before.Restitution);
                    if(FootDiagnostic==2)Test->TestEqual(TEXT("Zero friction applied to actual native foot"),After.Friction,0.f);
                }
                if(FootDiagnostic==3&&!Agent->SetJoltBodyPairSelfCollisionEnabled(TEXT("foot_l"),TEXT("foot_r"),false,Error))return Fail(Error);
            }
            FString Settings=TEXT("{\"mode\":\"idle\",\"trimOut\":1.2,\"ramps\":false,\"aim\":false,\"spinLag\":0.6,\"platforms\":[{\"id\":\"floor\",\"position\":[0,-0.2,0],\"size\":[20,0.4,20],\"rotation\":[0,0,0,1]}],\"jumpEvents\":[{\"id\":\"push\",\"time\":0.1,\"jumpPercent\":35,\"flip\":120,\"twist\":30,\"spinVersion\":2,\"attack\":\"KickL\"}]}");
            if(IsThrowCase())
            {
                Settings=FString::Printf(TEXT("{\"mode\":\"spaceGym\",\"trimOut\":2,\"aim\":false,\"spinLag\":0.6,\"jumpEvents\":[{\"id\":\"physical-throw\",\"time\":0.1,\"jumpPercent\":0,\"attack\":\"%s\",\"throwCharge\":%d,\"spinVersion\":2}]}"),Mode==3?TEXT("big-throw"):TEXT("small-throw"),Mode==3?100:37);
                ProphecyBodyflip::SetProjectileDiagnosticObserver(World,[this](const auto& D,const TCHAR* Phase){RecordThrowBoundary(D,Phase);});
            }
            if(IsHandCase())Settings=FString::Printf(TEXT("{\"mode\":\"idle\",\"trimOut\":1.2,\"ramps\":false,\"aim\":false,\"spinLag\":0.6,\"handFollow\":0.25,\"handReturn\":0.4,\"platforms\":[{\"id\":\"floor\",\"position\":[0,-0.2,0],\"size\":[20,0.4,20],\"rotation\":[0,0,0,1]}],\"jumpEvents\":[{\"id\":\"hand-push\",\"time\":0.1,\"jumpPercent\":35,\"flip\":0,\"twist\":0,\"spinVersion\":2,\"attack\":\"none\",\"pushWith\":\"%s\"}]}"),Mode==6?TEXT("handBoth"):TEXT("handL"));
            Settings.InsertAt(1,TEXT("\"traceSource\":true,"));
            if(!ProphecySwordHolster::CheckBodyflipPendingAdmission(*Test,Agent))return Fail(TEXT("Bodyflip admitted a pre-existing queued sword action"));
            if(IsSavedCase())
            {
                FString Text;TSharedPtr<FJsonObject> Preset;
                if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/LabSettings.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Preset))return Fail(TEXT("Missing captured scene"));
                SavedEnd=Preset->GetObjectField(TEXT("settings"))->GetNumberField(TEXT("trimOut"));
                if(!UProphecyBodyflipLibrary::StartBodyflipSavedLabSetup(Agent,Error))return Fail(Error);
            }
            else if(!UProphecyBodyflipLibrary::StartBodyflip(Agent,Settings,TEXT(""),Error))return Fail(Error);
            if(!ProphecyBodyflip::CaptureRigProfile(Agent,NativeRigProfile,Error))return Fail(Error);
            TSharedPtr<FJsonObject> Profile;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(NativeRigProfile),Profile))return Fail(TEXT("Invalid captured physical rig profile"));
            PhysicalBones.Reset();for(const auto& Body:Profile->GetArrayField(TEXT("bodies"))){const FName Name(*Body->AsObject()->GetStringField(TEXT("name")));const int32 Bone=TraceNames.IndexOfByKey(Name);if(Bone==INDEX_NONE||PhysicalBones.Contains(Bone))return Fail(TEXT("Physical rig body is missing or duplicated in the full pose trace: ")+Name.ToString());PhysicalBones.Add(Bone);}
            if(PhysicalBones.IsEmpty())return Fail(TEXT("Physical rig profile has no tracked bodies"));
            if(IsPhysicalCase()&&!InitializeHandAudit(Profile,Error))return Fail(Error);
            FProphecyNNRuntimeBenchmarkStats Stats;if(!Manager->ReadRuntimeBenchmarkStats(Stats))return Fail(TEXT("Missing native manager timing counters"));ManagerInferenceAtStart=Stats.ModelInferenceCalls;
            Stage=2;return false;
        }
        FProphecyBodyflipState State;
        if(Stage==2)
        {
            if(!UProphecyBodyflipLibrary::GetBodyflipState(Agent,State))return Fail(TEXT("Active Bodyflip state disappeared"));
            for(const auto& Contact:PendingHandContacts){Contact->SetNumberField(TEXT("intervalEnd"),State.Time);Contact->SetStringField(TEXT("phase"),State.Phase);HandContacts.Add(MakeShared<FJsonValueObject>(Contact));}PendingHandContacts.Reset();
            if(!HandDiagnosticError.IsEmpty())return Fail(HandDiagnosticError);
            if(!State.Error.IsEmpty())return Fail(State.Error);
            FProphecyNNRuntimeBenchmarkStats Stats;Manager->ReadRuntimeBenchmarkStats(Stats);if(Stats.ModelInferenceCalls!=ManagerInferenceAtStart)return Fail(TEXT("Normal manager NN inference continued while Bodyflip owned its only agent"));
            if(State.Phase==TEXT("PREPARING"))return false;
            if(!CheckedAdmission){CheckedAdmission=true;if(!CheckBodyflipActionAdmission(*Test,Agent,Manager,nullptr,FloorCollider))return Fail(TEXT("An external action bypassed active Bodyflip ownership"));}
            WorstRoot=FMath::Max(WorstRoot,FVector::Distance(State.Root,Agent->GetRootLowPoint()));
            if(State.Time<.01)Test->TestTrue(TEXT("Frame zero preserves carrier yaw"),FMath::Abs(FMath::FindDeltaAngleDegrees(InitialYaw,float(Agent->GetActorRotation().Yaw)))<.01);
            SawRise|=State.Phase==TEXT("RISE")||State.Phase==TEXT("rise");
            TSharedPtr<FJsonObject> Frame;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(State.DiagnosticsJson),Frame))return Fail(TEXT("Invalid controller diagnostics"));
            if(State.Time<.01){Test->TestTrue(TEXT("Frame zero preserves initial root low point"),State.Root.Equals(InitialRoot,.001));const auto& R=Frame->GetArrayField(TEXT("root"));Space.SetTranslation(InitialRoot-Space.TransformVector(ProphecyThrow::ToUnrealPoint(FVector(R[0]->AsNumber(),R[1]->AsNumber(),R[2]->AsNumber()))));}
            const auto Pose=Frame->GetObjectField(TEXT("pose"));const auto& Points=Pose->GetArrayField(TEXT("points"));const auto& Rotations=Pose->GetArrayField(TEXT("q"));
            auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("time"),State.Time);Row->SetObjectField(TEXT("canonical"),Frame);TArray<TSharedPtr<FJsonValue>> PhysicalRows;
            TArray<FTransform> AllActual;AllActual.SetNum(TraceNames.Num());if(!Agent->SampleActualComponentPose(TraceNames,AllActual))return Fail(TEXT("Cannot read full completed native skeleton for frame audit"));
            auto FullPose=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> AllPoints,AllRotations;for(const auto& Component:AllActual){const FTransform Body=Component*Agent->GetAgentMesh()->GetComponentTransform();if(Body.ContainsNaN())return Fail(TEXT("Non-finite completed native skeleton"));AllPoints.Add(MakeShared<FJsonValueArray>(XYZ(Body.GetLocation())));AllRotations.Add(MakeShared<FJsonValueArray>(XYZW(Body.GetRotation())));}FullPose->SetArrayField(TEXT("points"),AllPoints);FullPose->SetArrayField(TEXT("q"),AllRotations);Row->SetObjectField(TEXT("actualPose"),FullPose);Row->SetArrayField(TEXT("carrierRoot"),XYZ(Agent->GetRootLowPoint()));
            for(const int32 Bone:PhysicalBones)
            {
                const auto& P=Points[Bone]->AsArray();const auto& Q=Rotations[Bone]->AsArray();
                const FTransform Expected=ProphecyThrow::ToUnreal(FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber())))*Space;
                FTransform Previous,Current,Interpolated;float Alpha=0;
                if(!Agent->GetAuthoredBodyWorldTarget(TraceNames[Bone],Previous,Current,Interpolated,Alpha))return Fail(TEXT("Native pose store did not publish Bodyflip target"));
                WorstTarget=FMath::Max(WorstTarget,FVector::Distance(Expected.GetLocation(),Current.GetLocation()));WorstRotation=FMath::Max(WorstRotation,Expected.GetRotation().AngularDistance(Current.GetRotation()));
                if(Expected.ContainsNaN()||Current.ContainsNaN())return Fail(TEXT("Non-finite Bodyflip target"));
                if(IsPhysicalCase()){const FTransform Physical=AllActual[Bone]*Agent->GetAgentMesh()->GetComponentTransform();if(Physical.ContainsNaN())return Fail(TEXT("Non-finite Jolt pose"));const double Distance=FVector::Distance(Expected.GetLocation(),Physical.GetLocation()),Angle=Expected.GetRotation().AngularDistance(Physical.GetRotation());WorstPhysical=FMath::Max(WorstPhysical,Distance);WorstPhysicalRotation=FMath::Max(WorstPhysicalRotation,Angle);PhysicalSquared+=Distance*Distance;PhysicalAngleSquared+=Angle*Angle;PhysicalCount++;
                    auto Body=MakeShared<FJsonObject>();Body->SetStringField(TEXT("name"),TraceNames[Bone].ToString());Body->SetNumberField(TEXT("errorCm"),Distance);Body->SetNumberField(TEXT("angleRad"),Angle);const FVector Position=Physical.GetLocation();const FQuat Rotation=Physical.GetRotation();Body->SetArrayField(TEXT("p"),{MakeShared<FJsonValueNumber>(Position.X),MakeShared<FJsonValueNumber>(Position.Y),MakeShared<FJsonValueNumber>(Position.Z)});Body->SetArrayField(TEXT("q"),{MakeShared<FJsonValueNumber>(Rotation.X),MakeShared<FJsonValueNumber>(Rotation.Y),MakeShared<FJsonValueNumber>(Rotation.Z),MakeShared<FJsonValueNumber>(Rotation.W)});PhysicalRows.Add(MakeShared<FJsonValueObject>(Body));}
            }
            if(IsPhysicalCase()){const FName LegNames[]={TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r")};const int32 LegBones[]={18,19,20,22,23,24};FTransform Legs[6];if(!Agent->SampleActualComponentPose(MakeArrayView(LegNames,6),MakeArrayView(Legs,6)))return Fail(TEXT("Missing physical leg chain"));for(int32 I:{0,1,3,4}){const auto& A=Points[LegBones[I]]->AsArray();const auto& B=Points[LegBones[I+1]]->AsArray();const double Expected=100*FVector(A[0]->AsNumber()-B[0]->AsNumber(),A[1]->AsNumber()-B[1]->AsNumber(),A[2]->AsNumber()-B[2]->AsNumber()).Length();const double ActualLength=FVector::Distance(Legs[I].GetLocation(),Legs[I+1].GetLocation());if(!FMath::IsFinite(ActualLength))return Fail(TEXT("Non-finite physical limb length"));WorstSegment=FMath::Max(WorstSegment,FMath::Abs(Expected-ActualLength));}Row->SetNumberField(TEXT("worstSegmentLengthErrorCm"),WorstSegment);}
            if(const auto* Spin=Frame->Values.Find(TEXT("spin"));Spin&&(*Spin)->Type==EJson::Object){double Rate=0;(*Spin)->AsObject()->TryGetNumberField(TEXT("flipRate"),Rate);SawSpin|=FMath::Abs(Rate)>.01;}
            Row->SetArrayField(TEXT("physical"),PhysicalRows);Trace.Add(MakeShared<FJsonValueObject>(Row));Checked++;
            if(IsSavedCase())
            {
                if(State.Time>=.6&&!DidPause){DidPause=true;PausedTime=State.Time;UProphecyBodyflipLibrary::PauseBodyflip(Agent,true);Stage=4;Ticks=0;return false;}
                if(State.Time<SavedEnd-1.e-5)return false;
                Test->TestTrue(TEXT("Saved scene reaches its complete trim"),Checked>=FMath::FloorToInt(SavedEnd*60));
                Test->TestTrue(TEXT("Saved scene pause resumes"),DidPause);
                Test->TestFalse(TEXT("Attack limit override ends with the return"),Frame->GetBoolField(TEXT("attackFree")));
                FString RetainedProfile,ProfileError;
                Test->TestTrue(TEXT("Authored rig remains readable"),ProphecyBodyflip::CaptureRigProfile(Agent,RetainedProfile,ProfileError));
                Test->TestEqual(TEXT("Attacks do not rewrite user joint tuning"),RetainedProfile,NativeRigProfile);
                Test->TestTrue(TEXT("Saved scene carrier equals controller root"),WorstRoot<.01);
                Test->TestTrue(TEXT("Saved scene publishes canonical targets"),WorstTarget<.01);
                Test->TestTrue(TEXT("Saved scene publishes canonical orientations"),WorstRotation<1.e-5);
                if(IsPhysicalCase())CheckPhysicalTracking();
                SaveReport();Cleanup();return true;
            }
            if(IsHandCase())
            {
                if(!RecordHandFrame(Frame,Row,AllActual,State.Time))return Fail(TEXT("Cannot read a finite dynamic native hand for the full push/return trace"));
                if(State.Time<1.2-1.e-6)return false;
                CheckHandPush();CheckPhysicalTracking();
                Test->TestTrue(TEXT("Active carrier equals controller root"),WorstRoot<.01);
                Test->TestTrue(TEXT("Published world targets match canonical controller"),WorstTarget<.01);
                Test->TestTrue(TEXT("Published body orientations match canonical controller"),WorstRotation<1.e-5);
                SaveReport();Cleanup();return true;
            }
            if(IsThrowCase())
            {
                RecordHeldThrow(Frame);if(!ThrowDiagnosticError.IsEmpty())return Fail(ThrowDiagnosticError);
                if(ReleaseTime>=0&&State.Time>=2.-1.e-5)
                {
                    Test->TestTrue(TEXT("Physical throw includes held frames"),HeldSamples>0);
                    Test->TestEqual(TEXT("Physical throw creates exactly one released body"),ReleaseSamples,1);
                    Test->TestTrue(TEXT("Physical throw integrates after release"),IntegrationSamples>0);
                    Test->TestFalse(TEXT("Throw return releases the temporary joint-limit override"),Frame->GetBoolField(TEXT("attackFree")));
                    FString RetainedProfile,ProfileError;
                    Test->TestTrue(TEXT("Throw rig remains readable"),ProphecyBodyflip::CaptureRigProfile(Agent,RetainedProfile,ProfileError));
                    Test->TestEqual(TEXT("Throw preserves user joint tuning"),RetainedProfile,NativeRigProfile);
                    CheckPhysicalTracking();
                    Test->TestTrue(TEXT("Active carrier equals controller root"),WorstRoot<.01);
                    Test->TestTrue(TEXT("Published world targets match canonical controller"),WorstTarget<.01);
                    Test->TestTrue(TEXT("Published body orientations match canonical controller"),WorstRotation<1.e-5);
                    SaveReport();Cleanup();return true;
                }
                if(ReleaseTime<0&&State.Time>=1.95)return Fail(TEXT("Physical throw did not release within its two-second fixture"));
                return false;
            }
            if(State.Time>=.6&&!DidPause){DidPause=true;PausedTime=State.Time;UProphecyBodyflipLibrary::PauseBodyflip(Agent,true);Stage=4;Ticks=0;return false;}if(State.Time<.9)return false;
            StopRoot=Agent->GetRootLowPoint();if(Mode==1)UProphecyBodyflipLibrary::PauseBodyflip(Agent,true);UProphecyBodyflipLibrary::StopBodyflip(Agent);
            if(Mode==1){FVector Linear,Angular;Agent->GetRootVelocity(Linear,Angular);Test->TestTrue(TEXT("Same-frame pause then stop hands back zero root velocity"),Linear.IsNearlyZero(.001)&&Angular.IsNearlyZero(.001));}
            FTransform Prev,Interpolated;float Alpha=0;Agent->GetAuthoredBodyWorldTarget(TEXT("thigh_l"),Prev,StopLeft,Interpolated,Alpha);Agent->GetAuthoredBodyWorldTarget(TEXT("thigh_r"),Prev,StopRight,Interpolated,Alpha);Ticks=0;Stage=3;return false;
        }
        if(Stage==4)
        {
            UProphecyBodyflipLibrary::GetBodyflipState(Agent,State);Test->TestEqual(TEXT("Pause retains source time"),double(State.Time),PausedTime);
            FVector Root,Velocity;float Yaw=0;ProphecyBodyflip::Root(Agent,Root,Yaw,&Velocity);Test->TestTrue(TEXT("Paused root has no feed-forward velocity"),Velocity.IsNearlyZero());
            FTransform Previous,Current,Interpolated;float Alpha=0;Agent->GetAuthoredBodyWorldTarget(TEXT("pelvis"),Previous,Current,Interpolated,Alpha);Test->TestTrue(TEXT("Paused body has no feed-forward velocity"),Previous.Equals(Current,.001));
            if(Ticks==0&&!CheckBodyflipActionAdmission(*Test,Agent,Manager,nullptr,FloorCollider))return Fail(TEXT("An external action bypassed paused Bodyflip ownership"));
            if(++Ticks<3)return false;UProphecyBodyflipLibrary::PauseBodyflip(Agent,false);Stage=2;return false;
        }
        if(Stage==3)
        {
            const double Travel=FVector::Distance(StopRoot,Agent->GetRootLowPoint());
            Test->TestTrue(TEXT("Stop does not snap to old route root"),Travel<35);
            FTransform Prev,Current,Interpolated;float Alpha=0;for(const FName Name:{FName(TEXT("thigh_l")),FName(TEXT("thigh_r"))}){auto& Last=Name==FName(TEXT("thigh_l"))?StopLeft:StopRight;Agent->GetAuthoredBodyWorldTarget(Name,Prev,Current,Interpolated,Alpha);Test->TestTrue(TEXT("NN handoff does not reverse thigh in one frame"),Last.GetRotation().AngularDistance(Current.GetRotation())<PI/2);Last=Current;}
            if(++Ticks<2)return false;
            if(Mode==1)CheckPhysicalTracking();
            Test->TestTrue(TEXT("Active carrier equals controller root"),WorstRoot<.01);
            Test->TestTrue(TEXT("Published world targets match canonical controller"),WorstTarget<.01);
            Test->TestTrue(TEXT("Published body orientations match canonical controller"),WorstRotation<1.e-5);
            Test->TestTrue(TEXT("Jump entered rise"),SawRise);Test->TestTrue(TEXT("Jump retained commanded spin"),SawSpin);
            SaveReport();
            Test->AddInfo(FString::Printf(TEXT("%s: %d frames; root error %.8g cm, target error %.8g cm, physical tracking %.8g cm"),Mode==0?TEXT("Kinematic"):TEXT("Jolt Sim"),Checked,WorstRoot,WorstTarget,WorstPhysical));
            if(Mode++==0){Cleanup();Agent=nullptr;Manager=nullptr;Stage=0;Ticks=0;Checked=0;WorstRoot=WorstTarget=WorstPhysical=WorstRotation=WorstPhysicalRotation=PhysicalSquared=PhysicalAngleSquared=WorstSegment=0;PhysicalCount=0;Trace.Reset();BodyInventory.Reset();PhysicalBones.Reset();NativeRigProfile.Reset();CheckedAdmission=false;FloorCollider=nullptr;SawRise=SawSpin=DidPause=false;return false;}
            Stage=5;return false;
        }
        if(Stage==5)
        {
            if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
                ||Agent->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic||Agent->IsJoltPhysicalAnimationEnabled())
                return Fail(PhysicalFailure(TEXT("Return to kinematic mode before seek")));
            FString Error;
            InitialRoot=Agent->GetRootLowPoint();
            const FString Settings=TEXT("{\"mode\":\"spaceGym\",\"trimOut\":0.1,\"aim\":false,\"jumpEvents\":[{\"id\":\"seek-throw\",\"time\":0,\"jumpPercent\":0,\"attack\":\"big-throw\",\"spinVersion\":2}]}");
            if(!UProphecyBodyflipLibrary::StartBodyflip(Agent,Settings,TEXT(""),Error))return Fail(Error);Stage=6;return false;
        }
        if(Stage==6)
        {
            UProphecyBodyflipLibrary::GetBodyflipState(Agent,State);if(!State.Error.IsEmpty())return Fail(State.Error);if(State.Phase==TEXT("PREPARING"))return false;if(State.Time<.01)Test->TestTrue(TEXT("Space starts at current root without adding its authored1.2m offset"),State.Root.Equals(InitialRoot,.001));if(State.Time<.05)return false;
            if(!TestedRebuildSeek)
            {
                TestedRebuildSeek=true;UProphecyBodyflipLibrary::PauseBodyflip(Agent,true);const float BeforeTime=State.Time;
                FString Error;if(!UProphecyBodyflipLibrary::SetBodyflipTarget(Agent,InitialRoot+FVector(100,150,50),Error)||!UProphecyBodyflipLibrary::SeekBodyflip(Agent,1.f/60,Error))return Fail(Error);
                FProphecyBodyflipState Pending;UProphecyBodyflipLibrary::GetBodyflipState(Agent,Pending);
                Test->TestEqual(TEXT("Pending rebuild seek retains displayed time"),Pending.Time,BeforeTime);
                Test->TestEqual(TEXT("Pending rebuild cannot publish a stale cached phase"),Pending.Phase,FString(TEXT("PREPARING")));
                Test->TestFalse(TEXT("Pending rebuild seek has no feed-forward motion"),Pending.Playing);
                Stage=8;return false;
            }
            UProphecyBodyflipLibrary::PauseBodyflip(Agent,true);RejectedSeekTime=State.Time;FTransform Previous,Interpolated;float Alpha=0;Agent->GetAuthoredBodyWorldTarget(TEXT("pelvis"),Previous,BeforeRejectedSeek,Interpolated,Alpha);
            FString Error;if(!UProphecyBodyflipLibrary::SeekBodyflip(Agent,1,Error))return Fail(TEXT("Expected uncached seek preparation: ")+Error);Stage=7;return false;
        }
        if(Stage==8)
        {
            UProphecyBodyflipLibrary::GetBodyflipState(Agent,State);if(!State.Error.IsEmpty())return Fail(State.Error);if(State.Phase==TEXT("PREPARING"))return false;
            Test->TestTrue(TEXT("Queued seek lands on the requested frame of the rebuilt generation"),FMath::IsNearlyEqual(State.Time,1.f/60,1.e-6f));
            Test->TestFalse(TEXT("Queued seek preserves the user's paused choice"),State.Playing);
            UProphecyBodyflipLibrary::PauseBodyflip(Agent,false);Stage=6;return false;
        }
        if(Stage==7)
        {
            UProphecyBodyflipLibrary::GetBodyflipState(Agent,State);if(State.Phase==TEXT("PREPARING"))return false;
            Test->TestTrue(TEXT("Unrecorded future projectile seek reports rejection"),State.Error.Contains(TEXT("not been recorded")));
            Test->TestEqual(TEXT("Rejected async seek restores source time"),double(State.Time),RejectedSeekTime);Test->TestFalse(TEXT("Rejected async seek restores pause state"),State.Playing);
            FTransform Previous,Current,Interpolated;float Alpha=0;Agent->GetAuthoredBodyWorldTarget(TEXT("pelvis"),Previous,Current,Interpolated,Alpha);Test->TestTrue(TEXT("Rejected async seek preserves displayed pose"),Current.Equals(BeforeRejectedSeek,.001));
            SaveReport();Cleanup();return true;
        }
        return false;
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipAgentTest,"Prophecy.Bodyflip.AgentKinematicAndSim",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipAgentTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPhysicalBigThrowTest,"Prophecy.Bodyflip.PhysicalBigThrow",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPhysicalBigThrowTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,3));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPhysicalSmallThrowTest,"Prophecy.Bodyflip.PhysicalSmallThrow",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPhysicalSmallThrowTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,4));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPhysicalHandLeftTest,"Prophecy.Bodyflip.PhysicalHandLeft",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPhysicalHandLeftTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,5));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipPhysicalHandBothTest,"Prophecy.Bodyflip.PhysicalHandBoth",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipPhysicalHandBothTest::RunTest(const FString&)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,6));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipFootBaselineTest,"Prophecy.Bodyflip.FootDiagnostic.Baseline",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipFootBaselineTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,8,0,1));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipFootFrictionTest,"Prophecy.Bodyflip.FootDiagnostic.ZeroFriction",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipFootFrictionTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,8,0,2));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipFootPairTest,"Prophecy.Bodyflip.FootDiagnostic.NoFootPair",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipFootPairTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,8,0,3));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipSavedKinematicTest,"Prophecy.Bodyflip.SavedSetup.Kinematic",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipSavedKinematicTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,7));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipSavedPhysicalTest,"Prophecy.Bodyflip.SavedSetup.Physical",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipSavedPhysicalTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,8));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipSavedAirPhysicalTest,"Prophecy.Bodyflip.SavedSetup.AirPhysical",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipSavedAirPhysicalTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,8,120));return true;}
// Space Gym authors its root 1.2 m above the floor. Keep the original
// floor-contact throw tests above, and separately cover the intended air use.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipAirBigThrowTest,"Prophecy.Bodyflip.AirBigThrow",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipAirBigThrowTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,3,120));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipAirSmallThrowTest,"Prophecy.Bodyflip.AirSmallThrow",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipAirSmallThrowTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(FBodyflipAgentExercise(this,4,120));return true;}
#endif
