#include "ProphecyArmConeLibrary.h"
#include "ProphecyArmCone.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"

namespace ProphecyArmCone
{
using K=ProphecyBlendClock::EKind;
struct FConfig { float Radius=45,Strength=100,Damping=20,Hold=.3f,Blend=.5f; };
struct FRecovery { FConfig Config; FName Attack; double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,TSet<FName>> Choices,ChoiceBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRecovery> Recoveries;
// Keep new state separate from allocations retained across Live Coding.
struct FTargetCorrection
{
    FVector Offset[2]={FVector::ZeroVector,FVector::ZeroVector};
    FVector Velocity[2]={FVector::ZeroVector,FVector::ZeroVector};
    TArray<int32,TInlineAllocator<32>> Bones[2];
    int32 Upper[2]={INDEX_NONE,INDEX_NONE},Lower[2]={INDEX_NONE,INDEX_NONE};
    int32 Count=0;
    uint64 Frame=MAX_uint64;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTargetCorrection> TargetCorrections;
struct FPublishedArms { FTransform Previous[6],Current[6]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FPublishedArms> PublishedArms;
#include "ProphecyArmConeTwist.inl"
static FDelegateHandle Cleanup;
#if WITH_EDITOR
static TAutoConsoleVariable<int32> Audit(TEXT("Prophecy.ArmCone.Audit"),0,TEXT("Opt-in arm recoil lifecycle and impulse diagnostics."));
#endif
static const FName UpperNames[]={TEXT("upperarm_l"),TEXT("upperarm_r")};
static const FName LowerNames[]={TEXT("lowerarm_l"),TEXT("lowerarm_r")};
static bool Valid(const AProphecyAgent* A)
{ return IsInGameThread() && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetWorld() && !A->GetWorld()->bIsTearingDown; }
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map) { for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Baselines);Clean(Choices);Clean(ChoiceBaselines);Clean(Recoveries);Clean(TargetCorrections);Clean(PublishedArms);Clean(TwistConfigs);Clean(TwistBaselines);Clean(TwistStates);
    });
}
void Cancel(const AProphecyAgent* A)
{
    if(!TwistStates.IsEmpty()) TwistStates.Remove(A);
    if(!TargetCorrections.IsEmpty()) TargetCorrections.Remove(A);
    if(!PublishedArms.IsEmpty()) PublishedArms.Remove(A);
    if(!Recoveries.IsEmpty() && Recoveries.Remove(A)) ProphecyBlendClock::Stop(A,K::ArmRepellantCone);
}
void Begin(const AProphecyAgent* A,FName Attack)
{
    Cancel(A);
#if WITH_EDITOR
    if(Audit.GetValueOnGameThread()) UE_LOG(LogTemp,Display,TEXT("ArmCone Begin %s attack=%s config=%d choices=%d"),*GetNameSafe(A),*Attack.ToString(),Configs.Contains(A),Choices.Contains(A));
#endif
    if(Configs.IsEmpty() || Choices.IsEmpty()) return;
    const auto* C=Configs.Find(A);const auto* Selected=Choices.Find(A);
    if(!C || !Selected || !Selected->Contains(Attack) || !Valid(A)) return;
    EnsureCleanup();Recoveries.Add(A,FRecovery{*C,Attack});
    ProphecyBlendClock::Start(A,K::ArmRepellantCone,double(C->Hold)+C->Blend);
}
void Remove(const AProphecyAgent* A)
{ Cancel(A);Configs.Remove(A);Choices.Remove(A);TwistConfigs.Remove(A);ForgetReset(A); }
void CaptureReset(const AProphecyAgent* A)
{
    if(const auto* C=TwistConfigs.Find(A)) TwistBaselines.Add(A,*C);else TwistBaselines.Remove(A);
    EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A);
    if(const auto* C=Choices.Find(A)) ChoiceBaselines.Add(A,*C);else ChoiceBaselines.Remove(A);
}
void RestoreReset(const AProphecyAgent* A)
{
    Cancel(A);Configs.Remove(A);Choices.Remove(A);TwistConfigs.Remove(A);
    if(const auto* C=TwistBaselines.Find(A)) TwistConfigs.Add(A,*C);
    if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C);
    if(const auto* C=ChoiceBaselines.Find(A)) Choices.Add(A,*C);
}
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A);ChoiceBaselines.Remove(A);TwistBaselines.Remove(A); }
static double Weight(const FConfig& C,double Time)
{
    if(Time+1.e-6>=double(C.Hold)+C.Blend) return 0;
    if(Time<=C.Hold) return 1;
    const double T=FMath::Clamp((Time-C.Hold)/C.Blend,0.,1.);
    return 1-T*T*(3-2*T);
}
struct FArmConeGeometry
{
    FVector Shoulder[2],Direction[2],Right,Forward;
};
static bool Geometry(TConstArrayView<FName> Names,TConstArrayView<FTransform> Pose,const FTransform& Carrier,FArmConeGeometry& G)
{
    if(Names.Num()!=Pose.Num()) return false;
    for(int32 I=0;I<2;++I)
    {
        const int32 U=Names.IndexOfByKey(UpperNames[I]),L=Names.IndexOfByKey(LowerNames[I]);
        if(!Pose.IsValidIndex(U) || !Pose.IsValidIndex(L)) return false;
        G.Shoulder[I]=Carrier.TransformPosition(Pose[U].GetLocation());
        G.Direction[I]=(Carrier.TransformPosition(Pose[L].GetLocation())-G.Shoulder[I]).GetSafeNormal();
        if(G.Direction[I].IsNearlyZero() || G.Direction[I].ContainsNaN()) return false;
    }
    G.Right=G.Shoulder[1]-G.Shoulder[0];G.Right.Z=0;
    if(!G.Right.Normalize()) return false;
    G.Forward=FVector::CrossProduct(G.Right,FVector::UpVector).GetSafeNormal();return true;
}
static FVector TargetOffset(const FVector& Direction,const FVector& Inward,const FVector& Forward,double Radius)
{
    const double Cos=FMath::Clamp(FVector::DotProduct(Direction,Inward),-1.,1.);
    if(Cos<=FMath::Cos(Radius)) return FVector::ZeroVector;
    FVector Tangent=Direction-Inward*Cos;
    if(!Tangent.Normalize()) Tangent=Forward;
    return FVector::CrossProduct(Inward,Tangent).GetSafeNormal()*(Radius-FMath::Acos(Cos));
}
static FQuat AdvanceTarget(const FVector& Goal,const FConfig& C,double W,double Dt,FVector& Offset,FVector& Velocity)
{
    if(Dt>0)
    {
        Velocity=(Velocity+(Goal-Offset)*(double(C.Strength)*Dt))/(1.+C.Damping*Dt+double(C.Strength)*Dt*Dt);
        Offset+=Velocity*Dt;
    }
    const double Angle=Offset.Size();
    return Angle>SMALL_NUMBER?FQuat(Offset/Angle,Angle*W):FQuat::Identity;
}
bool Active(const AProphecyAgent* A) { return !Recoveries.IsEmpty() && Recoveries.Contains(A); }
bool ApplyNNPose(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Pose,const FTransform& Carrier,float DeltaSeconds)
{
    if(Recoveries.IsEmpty()) return false;
    auto* R=Recoveries.Find(A);
    if(!R || DeltaSeconds<=0 || !Valid(A) || A->GetWorld()->IsPaused() || Names.Num()!=Pose.Num() || Parents.Num()!=Pose.Num()) return false;
    R->Elapsed+=ProphecyBlendClock::Consume(A,K::ArmRepellantCone);
    const double W=Weight(R->Config,R->Elapsed);
    if(W<=0) { Cancel(A);return false; }
    if(R->Config.Radius<=0 || R->Config.Strength<=0) return false;
    FArmConeGeometry G;if(!Geometry(Names,Pose,Carrier,G)) return false;
    auto& S=TargetCorrections.FindOrAdd(A);
    if(S.Count!=Names.Num())
    {
        S.Count=Names.Num();
        for(int32 Arm=0;Arm<2;++Arm)
        {
            S.Upper[Arm]=Names.IndexOfByKey(UpperNames[Arm]);S.Lower[Arm]=Names.IndexOfByKey(LowerNames[Arm]);
            S.Bones[Arm].Reset();
            for(int32 I=0;I<Names.Num();++I)
                for(int32 B=I,Depth=0;Parents.IsValidIndex(B) && Depth<Parents.Num();B=Parents[B],++Depth)
                    if(B==S.Upper[Arm]) { S.Bones[Arm].Add(I);break; }
        }
    }
    // Called once per accepted NN prediction, including catch-up steps in one game frame.
    const double Dt=DeltaSeconds;
    bool Changed=false;
    for(int32 Arm=0;Arm<2;++Arm)
    {
        if(!Pose.IsValidIndex(S.Upper[Arm]) || !Pose.IsValidIndex(S.Lower[Arm])) continue;
        const FVector Pivot=Pose[S.Upper[Arm]].GetLocation();
        const FVector Goal=TargetOffset(G.Direction[Arm],Arm==0?G.Right:-G.Right,G.Forward,FMath::DegreesToRadians(double(R->Config.Radius)));
        const FQuat WorldQ=AdvanceTarget(Goal,R->Config,W,Dt,S.Offset[Arm],S.Velocity[Arm]);
        if(WorldQ.IsIdentity()) continue;
        const FQuat Q=(Carrier.GetRotation().Inverse()*WorldQ*Carrier.GetRotation()).GetNormalized();
        for(const int32 I:S.Bones[Arm])
        {
            Pose[I].SetLocation(Pivot+Q.RotateVector(Pose[I].GetLocation()-Pivot));
            Pose[I].SetRotation((Q*Pose[I].GetRotation()).GetNormalized());
        }
        Changed=true;
#if WITH_EDITOR
        if(Audit.GetValueOnGameThread()) UE_LOG(LogTemp,Display,TEXT("ArmCone NN %s arm=%d elapsed=%.4f weight=%.4f correction=%.3f"),*GetNameSafe(A),Arm,R->Elapsed,W,FMath::RadiansToDegrees(Q.GetAngle()));
#endif
    }
    return Changed;
}
bool ApplyNNPublication(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,const FTransform& PreviousCarrier,
    const FTransform& Carrier,float DeltaSeconds,bool NewSample)
{
    if(!Active(A)) return false;
    static const FName Bones[]={TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    int32 Indices[6];
    for(int32 I=0;I<6;++I)
    {
        Indices[I]=Names.IndexOfByKey(Bones[I]);
        if(!Current.IsValidIndex(Indices[I]) || !Previous.IsValidIndex(Indices[I])) return false;
    }
    if(const auto* Last=PublishedArms.Find(A))
    {
        for(int32 I=0;I<6;++I)
        {
            Previous[Indices[I]]=(NewSample?Last->Current[I]:Last->Previous[I]).GetRelativeTransform(PreviousCarrier);
            if(!NewSample) Current[Indices[I]]=Last->Current[I].GetRelativeTransform(Carrier);
        }
        if(!NewSample) return true;
    }
    else if(!NewSample) return false;
    ApplyNNPose(A,Names,Parents,Current,Carrier,DeltaSeconds);
    if(!Active(A)) return false;
    if(!TwistConfigs.IsEmpty())
    {
        const auto* R=Recoveries.Find(A);
        ApplyTwist(A,Previous,Current,Indices,Names.IndexOfByKey(FName(TEXT("spine_05"))),Names.IndexOfByKey(FName(TEXT("neck_01"))),Weight(R->Config,R->Elapsed),DeltaSeconds);
    }
    auto& Saved=PublishedArms.FindOrAdd(A);
    for(int32 I=0;I<6;++I)
    {
        Saved.Previous[I]=Previous[Indices[I]]*PreviousCarrier;
        Saved.Current[I]=Current[Indices[I]]*Carrier;
    }
    return true;
}
static void BeginInsideEndEvent(AProphecyAgent* A)
{ if(ProphecyAttackRecovery::IsEndEvent(A) && !Recoveries.Contains(A)) Begin(A,ProphecyAttackRecovery::EndEventAttack(A)); }
}

bool UProphecyArmConeLibrary::SetArmRepellantCone(AProphecyAgent* A,bool Enabled,float Radius,float Strength,float Damping,float Hold,float Blend,
    bool EnableTwist,float TwistLimit,float TwistStrength,float TwistDamping)
{
    using namespace ProphecyArmCone;
    if(!Valid(A) || !FMath::IsFinite(Radius) || !FMath::IsFinite(Strength) || !FMath::IsFinite(Damping) ||
        !FMath::IsFinite(Hold) || !FMath::IsFinite(Blend) || Radius<0 || Radius>=90 || Strength<0 || Damping<0 || Hold<0 || Blend<0) return false;
    if(!FMath::IsFinite(TwistLimit) || !FMath::IsFinite(TwistStrength) || !FMath::IsFinite(TwistDamping) ||
        TwistLimit<0 || TwistLimit>=180 || TwistStrength<0 || TwistDamping<0) return false;
    const bool Twist=EnableTwist && (TwistStrength>0 || TwistDamping>0);
    if(!Enabled || ((!Twist) && (Radius==0 || Strength==0)) || (Hold==0 && Blend==0))
    { Cancel(A);Configs.Remove(A);TwistConfigs.Remove(A);return true; }
    if(Twist) TwistConfigs.Add(A,FTwistConfig{TwistLimit,TwistStrength,TwistDamping});
    else { TwistConfigs.Remove(A);TwistStates.Remove(A); }
    EnsureCleanup();const FConfig C{Radius,Strength,Damping,Hold,Blend};Configs.Add(A,C);
    if(auto* R=Recoveries.Find(A))
    {
        R->Elapsed+=ProphecyBlendClock::Consume(A,K::ArmRepellantCone);R->Config=C;
        const double Remaining=double(C.Hold)+C.Blend-R->Elapsed;
        if(Remaining<=0) Cancel(A);
        else ProphecyBlendClock::Start(A,K::ArmRepellantCone,Remaining);
    }
    BeginInsideEndEvent(A);return true;
}
bool UProphecyArmConeLibrary::SetAttackArmRepellantConeEnabled(AProphecyAgent* A,
    bool SlashL,bool SlashR,bool SlashLD,bool SlashRD,bool SlashLU,bool SlashRU,bool Pike,
    bool JabL,bool JabR,bool HookL,bool HookR,bool OverL,bool OverR,bool Headbutt,bool KickL,bool KickR)
{
    using namespace ProphecyArmCone;if(!Valid(A)) return false;
    const TCHAR* Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),TEXT("pike"),
        TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};
    const bool Selected[]={SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR};
    TSet<FName> Set;for(int32 I=0;I<UE_ARRAY_COUNT(Names);++I) if(Selected[I]) Set.Add(Names[I]);
    if(const auto* R=Recoveries.Find(A);R && !Set.Contains(R->Attack)) Cancel(A);
    if(Set.IsEmpty()) Choices.Remove(A);else { EnsureCleanup();Choices.Add(A,MoveTemp(Set)); }
    BeginInsideEndEvent(A);return true;
}
bool UProphecyArmConeLibrary::VisualizeArmRepellantCone(AProphecyAgent* A,float Length,float Duration)
{
    using namespace ProphecyArmCone;
    if(!Valid(A) || !FMath::IsFinite(Length) || !FMath::IsFinite(Duration) || Length<=0 || Duration<0) return false;
    const auto* R=Recoveries.Find(A);const auto* C=R?&R->Config:Configs.Find(A);const FConfig Default;
    if(!C) C=&Default;
    TArray<FName> Names;TArray<FTransform> Future,Presented;float Alpha=0;
    if(!A->ReadNNFutureWorldPose(Names,Future,Presented,Alpha)) return false;
    FArmConeGeometry G;if(!Geometry(Names,Presented,FTransform::Identity,G)) return false;
    DrawTwist(A,Names,Presented,Length,Duration,R!=nullptr);
    const float Radius=FMath::DegreesToRadians(C->Radius);
    for(int32 I=0;I<2;++I)
    {
        const FVector Inward=I==0?G.Right:-G.Right;
        const bool Inside=FVector::DotProduct(G.Direction[I],Inward)>FMath::Cos(Radius);
        const FColor Color=!R?FColor::Silver:Inside?FColor::Red:FColor::Green;
        DrawDebugCone(A->GetWorld(),G.Shoulder[I],Inward,Length,Radius,Radius,20,Color,false,Duration,0,.6f);
        DrawDebugLine(A->GetWorld(),G.Shoulder[I],G.Shoulder[I]+G.Direction[I]*Length,Color,false,Duration,0,2.f);
    }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWristHorizontalAxisTest,"Prophecy.Physics.ArmCone.WristHorizontalAxis",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyWristHorizontalAxisTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;
    const FVector Up=FVector(1,.014,0).GetSafeNormal();
    const FTransform Spine(FRotator(25,70,-15),FVector(100,20,80));
    const FTransform Lower(FQuat::Identity,FVector(15,20,90));
    const FTransform Hand(FRotator(10,15,45),Lower.GetLocation()+FVector(-15,25,-20));
    FTwistArm S;TestTrue(TEXT("Tilted forearm reference seeds"),SeedTwist(S,Spine,Lower,Hand,Up));
    TestTrue(TEXT("Axis is spine-to-neck up, independent of arm aim"),S.LocalAxis.Equals(Up,1.e-8));
    const FVector Pitch=FVector::CrossProduct(Up,FVector::RightVector).GetSafeNormal();
    TestTrue(TEXT("Pure pitch is not horizontal twist"),FMath::Abs(WristAngle(S,FQuat(Pitch,1.)*S.Reference,0))<1.e-7);
    for(double Sign:{-1.,1.})
    {
        const FQuat Proposed=FQuat(Up,FMath::DegreesToRadians(Sign*110))*S.Reference;
        const double Angle=WristAngle(S,Proposed,0);S.AcceptedAngle=Angle;S.Velocity=0;
        const FTwistConfig C{60,1000000,0};AdvanceTwist(S,Angle,C,1,1./30);
        const FQuat Accepted=AcceptWristStep(S,Proposed,Proposed,Angle,Angle,S.AcceptedAngle,C,1,1./30);
        TestTrue(TEXT("Recoil approaches horizontal limit"),FMath::Abs(FMath::RadiansToDegrees(WristAngle(S,Accepted,S.AcceptedAngle)))<60.1);
        for(const FVector Blade:{FVector::ForwardVector,FVector::RightVector,FVector::UpVector})
        {
            const double Before=FVector::DotProduct(Proposed.RotateVector(Blade),Up);
            const double After=FVector::DotProduct(Accepted.RotateVector(Blade),Up);
            TestTrue(TEXT("Horizontal recoil preserves blade elevation in spine space"),FMath::IsNearlyEqual(Before,After,1.e-7));
        }
        const FQuat Previous=FQuat(Up,FMath::DegreesToRadians(Sign*20))*FQuat(Pitch,.5)*S.Reference;
        const double PreviousAngle=WristAngle(S,Previous,0);S.AcceptedAngle=PreviousAngle;S.Velocity=0;
        AdvanceTwist(S,Angle,C,1,1./30);
        const FQuat Moving=AcceptWristStep(S,Previous,Proposed,PreviousAngle,Angle,S.AcceptedAngle,C,1,1./30);
        TestTrue(TEXT("Recoil never borrows an older pitch from the preceding pose"),FMath::IsNearlyEqual(
            FVector::DotProduct(Proposed.RotateVector(FVector::RightVector),Up),
            FVector::DotProduct(Moving.RotateVector(FVector::RightVector),Up),1.e-7));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWristSpineStopTest,"Prophecy.Physics.ArmCone.WristSpineStop",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyWristSpineStopTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;
    const FTwistConfig C{60,0,10000};FTwistArm S;
    const FTransform Spine=FTransform::Identity,Lower(FVector::ZeroVector),Hand(FVector(25,0,0));
    SeedTwist(S,Spine,Lower,Hand);
    const FQuat Before(FVector::ForwardVector,FMath::DegreesToRadians(60.));
    const FQuat Proposed=FQuat(FVector::ForwardVector,FMath::DegreesToRadians(90.))*FQuat(FVector::RightVector,FMath::DegreesToRadians(40.));
    const double PreviousAngle=WristAngle(S,Before,0),Angle=WristAngle(S,Proposed,PreviousAngle);
    S.AcceptedAngle=PreviousAngle;AdvanceTwist(S,Angle,C,1,1./30);
    const FQuat Accepted=AcceptWristStep(S,Before,Proposed,PreviousAngle,Angle,S.AcceptedAngle,C,1,1./30);
    TestTrue(TEXT("At limit the full bent-wrist step stops, without an upward counter-swing"),FMath::RadiansToDegrees(Accepted.AngularDistance(Before))<.3);
    TestTrue(TEXT("Analytical quaternion boundary matches accepted twist"),FMath::Abs(WristAngle(S,Accepted,S.AcceptedAngle)-S.AcceptedAngle)<1.e-6);
    const FQuat SpineTurn(FVector::UpVector,.6);
    const FQuat WorldStill=SpineTurn.Inverse()*Before;
    const double StillAngle=WristAngle(S,WorldStill,PreviousAngle);
    const FQuat Follow=AcceptWristStep(S,Before,WorldStill,PreviousAngle,StillAngle,StillAngle,C,1,1./30);
    TestTrue(TEXT("At boundary stationary world wrist follows spine, including swing"),FMath::RadiansToDegrees(Follow.AngularDistance(Before))<.2);
    FTransform ChangedForearm(FQuat(FVector::UpVector,1.),FVector(0,20,0));
    FTransform UnchangedWrist(Before,FVector(25,0,0));FVector Axis,Ref,Actual;double Measured=0;
    MeasureTwist(S,Spine,ChangedForearm,UnchangedWrist,Axis,Ref,Actual,Measured);
    TestTrue(TEXT("Moving elbow cannot change stationary spine-local wrist angle"),FMath::Abs(Measured-PreviousAngle)<1.e-6);
    const FQuat Returning(FVector::ForwardVector,FMath::DegreesToRadians(20.));
    S.AcceptedAngle=PreviousAngle;const double ReturnAngle=WristAngle(S,Returning,PreviousAngle);
    AdvanceTwist(S,ReturnAngle,C,1,1./30);
    TestTrue(TEXT("Inward wrist step remains untouched"),AcceptWristStep(S,Before,Returning,PreviousAngle,ReturnAngle,S.AcceptedAngle,C,1,1./30).Equals(Returning,1.e-8));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeDampingTest,"Prophecy.Physics.ArmCone.SpineLocalDamping",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeDampingTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;
    const FTwistConfig C{30,0,10000};
    for(double Sign:{-1.,1.})
    {
        FTwistArm S;
        TestEqual(TEXT("Inside limit damping is idle"),AdvanceTwist(S,FMath::DegreesToRadians(Sign*20),C,1,1./30),0.);
        AdvanceTwist(S,FMath::DegreesToRadians(Sign*90),C,1,1./30);
        TestTrue(TEXT("Damping only blocks outward spin at both limits"),FMath::Abs(FMath::RadiansToDegrees(S.AcceptedAngle))<30.2);
        TestEqual(TEXT("Inward recovery is undamped"),AdvanceTwist(S,FMath::DegreesToRadians(Sign*15),C,1,1./30),0.);
        S.AcceptedAngle=FMath::DegreesToRadians(Sign*90);
        TestEqual(TEXT("Zero recoil does not pull stationary excess back"),AdvanceTwist(S,S.AcceptedAngle,C,1,1./30),0.);
        const double NoWeight=AdvanceTwist(S,FMath::DegreesToRadians(Sign*120),C,0,1./30);
        TestEqual(TEXT("Faded-out damping leaves NN alone"),NoWeight,0.);
    }
    FTwistArm S;
    const FTransform Spine=FTransform::Identity,Lower(FVector(0,0,0)),Hand(FVector(25,0,0));
    TestTrue(TEXT("Reference seeds from spine"),SeedTwist(S,Spine,Lower,Hand));
    const FTransform RotatedSpine(FQuat(FVector::ForwardVector,FMath::DegreesToRadians(90.)));
    FVector Axis,Ref,Actual;double Angle=0;
    MeasureTwist(S,RotatedSpine,Lower,Hand,Axis,Ref,Actual,Angle);
    TestTrue(TEXT("Spine turning under world-still wrist registers relative twist"),FMath::IsNearlyEqual(FMath::RadiansToDegrees(Angle),-90.,1.e-4));
    const double Correction=AdvanceTwist(S,Angle,C,1,1./30);
    TestTrue(TEXT("Damping turns wrist with spine after reaching limit"),FMath::RadiansToDegrees(Correction)>59.8);
    FTransform CorrectedLower=Lower,CorrectedHand=Hand;
    CorrectedLower.SetRotation(FQuat(Axis,Correction));CorrectedHand.SetRotation(FQuat(Axis,Correction));
    MeasureTwist(S,RotatedSpine,CorrectedLower,CorrectedHand,Axis,Ref,Actual,Angle);
    TestTrue(TEXT("Accepted wrist remains near spine-local boundary"),FMath::Abs(FMath::RadiansToDegrees(Angle))<30.2);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeTwistTest,"Prophecy.Physics.ArmCone.WristTwistRecoil",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeTwistTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    const FName Names[]={TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("spine_05")};
    const int32 Parents[]={6,0,1,6,3,4,-1};FTransform Previous[7],Current[7];
    Previous[6]=Current[6]=FTransform::Identity;
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 I=3*Side;const FVector Shoulder(0,Side?15:-15,100);
        Previous[I]=FTransform(Shoulder);Previous[I+1]=FTransform(Shoulder+FVector(0,Side?25:-25,0));
        Previous[I+2]=FTransform(FQuat(FVector::UpVector,.3),Previous[I+1].GetLocation()+FVector(25,0,0));
        for(int32 B=0;B<3;++B)Current[I+B]=Previous[I+B];
        const FQuat Twist(FVector::ForwardVector,FMath::DegreesToRadians(Side?-150.:150.));
        for(int32 B=1;B<3;++B)Current[I+B].SetRotation(Twist*Current[I+B].GetRotation());
    }
    const FTransform Carrier(FRotator(10,80,20),FVector(100,40,20));
    TestFalse(TEXT("Disabled publication bypass"),ApplyNNPublication(A,Names,Parents,Previous,Current,Carrier,Carrier,1.f/30,true));
    TestTrue(TEXT("Twist only with zero cone radius"),L::SetArmRepellantCone(A,true,0,0,20,1,.5,true,30,1000000,20));
    L::SetAttackArmRepellantConeEnabled(A,false,true);CaptureReset(A);Begin(A,TEXT("slashR"));
    const FQuat WristSwing=(Current[1].GetRotation().Inverse()*Current[2].GetRotation()).GetNormalized();
    TestTrue(TEXT("Twist corrects NN without physics"),ApplyNNPublication(A,Names,Parents,Previous,Current,Carrier,Carrier,1.f/30,true));
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 I=Side*3;FVector Axis,Ref,Actual;double Angle=0;
        MeasureTwist(TwistStates.FindChecked(A).Arm[Side],Current[6],Current[I+1],Current[I+2],Axis,Ref,Actual,Angle);
        TestTrue(TEXT("Mirrored twist approaches 30 degree limit"),FMath::Abs(FMath::RadiansToDegrees(Angle))<30.3);
        for(int32 B=0;B<3;++B)TestTrue(TEXT("Twist leaves every joint position unchanged"),Current[I+B].GetLocation().Equals(Previous[I+B].GetLocation(),1.e-8));
        TestTrue(TEXT("Wrist swing preserved"),(Current[I+1].GetRotation().Inverse()*Current[I+2].GetRotation()).Equals(WristSwing,1.e-7));
        const FQuat Rigid(FVector::UpVector,1.1);FTransform Moved[3];
        for(int32 B=0;B<3;++B)Moved[B]=Current[I+B]*FTransform(Rigid,FVector(12,40,0));
        double MovedAngle=0;MeasureTwist(TwistStates.FindChecked(A).Arm[Side],Current[6]*FTransform(Rigid,FVector(12,40,0)),Moved[1],Moved[2],Axis,Ref,Actual,MovedAngle);
        TestTrue(TEXT("Spine-local reference ignores rigid body movement"),FMath::IsNearlyEqual(Angle,MovedAngle,1.e-7));
    }
    const FQuat Once=Current[1].GetRotation();
    TestTrue(TEXT("Repeated publication reuses accepted endpoint"),ApplyNNPublication(A,Names,Parents,Previous,Current,Carrier,Carrier,0,false));
    TestTrue(TEXT("Repeated publication does not integrate twice"),Current[1].GetRotation().Equals(Once,1.e-7));
    TestTrue(TEXT("Unwrap does not jump at 180"),FMath::IsNearlyEqual(FMath::RadiansToDegrees(UnwrapTwist(FMath::DegreesToRadians(-179.),FMath::DegreesToRadians(175.))),181.,1.e-4));
    FTwistArm S;S.AcceptedAngle=FMath::DegreesToRadians(175.);
    AdvanceTwist(S,FMath::DegreesToRadians(-179.),FTwistConfig{30,1000000,20},1,1./30);
    TestTrue(TEXT("Crossing 180 recoils to same side of limit"),S.AcceptedAngle>0 && FMath::RadiansToDegrees(S.AcceptedAngle)<30.3);
    L::SetArmRepellantCone(A,false);TestFalse(TEXT("Disable clears twist state"),TwistStates.Contains(A));
    RestoreReset(A);TestTrue(TEXT("Reset restores twist settings"),TwistConfigs.Contains(A));
    L::SetArmRepellantCone(A,true,0,0,20,1,.5,true,30,0,10000);
    TestTrue(TEXT("Zero recoil retains damping-only configuration"),TwistConfigs.Contains(A));
    L::SetArmRepellantCone(A,true,0,0,20,1,.5,true,30,0,0);
    TestFalse(TEXT("Zero recoil and damping bypass"),TwistConfigs.Contains(A));
    L::SetArmRepellantCone(A,true);TestFalse(TEXT("Default cone has no twist config"),TwistConfigs.Contains(A));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeNNPoseTest,"Prophecy.Physics.ArmCone.NNPoseWithoutPhysics",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeNNPoseTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A) return false;
    const FName Names[]={TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const int32 Parents[]={-1,0,1,-1,3,4};FTransform P[6];
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 I=3*Side;const FVector Shoulder(0,Side?15:-15,100);
        const FVector Dir=FVector(1,Side?-4:4,0).GetSafeNormal();
        P[I]=FTransform(Shoulder);P[I+1]=FTransform(Shoulder+30*Dir);P[I+2]=FTransform(Shoulder+30*Dir+FVector(8,0,-20));
    }
    const FTransform Carrier(FRotator(0,90,0),FVector(100,40,15));
    TestFalse(TEXT("Disabled bypass without physical mesh"),ApplyNNPose(A,Names,Parents,MakeArrayView(P),Carrier,1.f/30));
    L::SetArmRepellantCone(A,true,60,1000000,20,1,.5);
    L::SetAttackArmRepellantConeEnabled(A,false,true);Begin(A,TEXT("slashR"));
    TestEqual(TEXT("Agent is kinematic"),A->GetSimulationMode(),EProphecyAgentSimulationMode::Kinematic);
    TestTrue(TEXT("NN correction needs no simulated body"),ApplyNNPose(A,Names,Parents,MakeArrayView(P),Carrier,1.f/30));
    FArmConeGeometry G;TestTrue(TEXT("NN geometry from corrected pose"),Geometry(Names,MakeArrayView(P),Carrier,G));
    for(int32 Side=0;Side<2;++Side)
    {
        const double Angle=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(G.Direction[Side],Side?-G.Right:G.Right),-1.,1.)));
        TestTrue(TEXT("Both NN arms reach the cone in a rotated carrier"),Angle>59.8);
        const int32 I=3*Side;
        TestTrue(TEXT("NN upper length preserved"),FMath::IsNearlyEqual(FVector::Distance(P[I].GetLocation(),P[I+1].GetLocation()),30.,1.e-7));
        TestTrue(TEXT("NN forearm length preserved"),FMath::IsNearlyEqual(FVector::Distance(P[I+1].GetLocation(),P[I+2].GetLocation()),FVector(8,0,-20).Size(),1.e-7));
    }
    Cancel(A);TestFalse(TEXT("Cancel removes pose sidecar"),TargetCorrections.Contains(A));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeDriveTest,"Prophecy.Physics.ArmCone.CoherentDriveTargets",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeDriveTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;
    FConfig C;C.Radius=60;C.Strength=1000000;C.Damping=20;
    const FVector In(0,1,0),Forward(1,0,0),Dir=FVector(1,4,0).GetSafeNormal();
    const FVector Goal=TargetOffset(Dir,In,Forward,FMath::DegreesToRadians(60.));
    FVector Offset=FVector::ZeroVector,Velocity=FVector::ZeroVector;
    FQuat Q=AdvanceTarget(Goal,C,1,1./60,Offset,Velocity);
    const auto Angle=[&](FQuat Rotation) { return FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Rotation.RotateVector(Dir),In),-1.,1.))); };
    TestTrue(TEXT("Million strength projects the drive to the boundary, not halfway"),Angle(Q)>59.7);
    for(int32 I=0;I<60;++I) Q=AdvanceTarget(Goal,C,1,1./60,Offset,Velocity);
    TestTrue(TEXT("Sustained inward checkpoint cannot defeat the corrected target"),FMath::IsNearlyEqual(Angle(Q),60.,1.e-4));
    TestTrue(TEXT("No upper-arm axial twist"),FMath::Abs(FVector::DotProduct(Offset,Dir))<1.e-8);
    TestTrue(TEXT("Fade reaches identity"),AdvanceTarget(Goal,C,0,0,Offset,Velocity).IsIdentity());
    const FVector Elbow=Dir*30,Hand=Elbow+FVector(7,0,-20);
    TestTrue(TEXT("Elbow and wrist move rigidly, preserving forearm length"),FMath::IsNearlyEqual(
        FVector::Distance(Q.RotateVector(Elbow),Q.RotateVector(Hand)),FVector::Distance(Elbow,Hand),1.e-8));
    FConfig Soft=C;Soft.Strength=100;FVector X=FVector::ZeroVector,V=X;
    TestTrue(TEXT("Low strength remains continuous and weaker"),Angle(AdvanceTarget(Goal,Soft,1,1./60,X,V))<Angle(Q));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeMathTest,"Prophecy.Physics.ArmCone.GeometryAndDamping",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeMathTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;const FConfig C;const FVector In(0,1,0),Forward(1,0,0);
    const FVector Inside=FVector(1,3,0).GetSafeNormal();
    const double Radius=FMath::DegreesToRadians(double(C.Radius));
    const FVector Goal=TargetOffset(Inside,In,Forward,Radius);
    TestTrue(TEXT("No axial twist"),FMath::Abs(FVector::DotProduct(Goal,Inside))<1.e-9);
    TestTrue(TEXT("Arm down untouched"),TargetOffset(FVector(0,0,-1),In,Forward,Radius).IsZero());
    TestTrue(TEXT("Outside untouched"),TargetOffset(Forward,In,Forward,Radius).IsZero());
    TestTrue(TEXT("Center escapes forward"),TargetOffset(In,In,Forward,Radius).Z<0);
    const FVector Mirror=TargetOffset(FVector(Inside.X,-Inside.Y,0),-In,Forward,Radius);
    TestTrue(TEXT("Mirrored cones"),FMath::IsNearlyEqual(Goal.Z,-Mirror.Z,1.e-9));
    FVector X=FVector::ZeroVector,V=X,XD=X,VD=X;FConfig Damped=C;Damped.Damping=100;
    const FQuat Q=AdvanceTarget(Goal,C,1,1./60,X,V),QD=AdvanceTarget(Goal,Damped,1,1./60,XD,VD);
    TestTrue(TEXT("Damping slows correction"),QD.GetAngle()<Q.GetAngle());
    TestEqual(TEXT("Full hold"),Weight(C,C.Hold),1.);
    TestTrue(TEXT("Mid fade"),FMath::IsNearlyEqual(Weight(C,C.Hold+C.Blend*.5),.5,1.e-6));
    TestEqual(TEXT("Retired at endpoint"),Weight(C,double(C.Hold)+C.Blend),0.);
    TestEqual(TEXT("Float settings retire on the 48th authored tick"),Weight(C,48./60),0.);
    FConfig HoldOnly=C;HoldOnly.Blend=0;
    TestEqual(TEXT("Zero blend safely retires"),Weight(HoldOnly,C.Hold),0.);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeLifecycleTest,"Prophecy.Physics.ArmCone.RegionalLifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A) return false;
    Begin(A,TEXT("slashR"));TestFalse(TEXT("Default has no recovery"),Recoveries.Contains(A));
    L::SetArmRepellantCone(A,true);Begin(A,TEXT("slashR"));TestFalse(TEXT("No selected attack no recovery"),Recoveries.Contains(A));
    L::SetAttackArmRepellantConeEnabled(A,false,true);
    ProphecyAttackRecovery::NotifyLowerEnded(A,TEXT("slashR"),true,true);
    TestFalse(TEXT("Full to half lower release never starts cone"),Recoveries.Contains(A));
    ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),true,true);
    TestTrue(TEXT("Half upper release starts cone"),Recoveries.Contains(A));
    ProphecyAttackRecovery::EnterSpecial(A,true);TestFalse(TEXT("New half special cancels"),Recoveries.Contains(A));
    ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),false,true);
    TestTrue(TEXT("Full attack end starts cone"),Recoveries.Contains(A));
    L::SetAttackArmRepellantConeEnabled(A);TestFalse(TEXT("Removing active attack immediately cancels"),Recoveries.Contains(A));
    L::SetAttackArmRepellantConeEnabled(A,false,true);CaptureReset(A);
    L::SetArmRepellantCone(A,false);Begin(A,TEXT("slashR"));TestFalse(TEXT("Master off bypasses"),Recoveries.Contains(A));
    RestoreReset(A);Begin(A,TEXT("slashR"));TestTrue(TEXT("Reset restores configuration and selection"),Recoveries.Contains(A));
    Cancel(A);ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),false,false);
    TestFalse(TEXT("Interrupted special starts no recoil"),Recoveries.Contains(A));
    Begin(A,TEXT("slashL"));TestFalse(TEXT("Unselected attack bypass"),Recoveries.Contains(A));
    L::SetArmRepellantCone(A,true,45,0);Begin(A,TEXT("slashR"));
    TestFalse(TEXT("Zero strength erases settings and recovery"),Configs.Contains(A)||Recoveries.Contains(A));
    L::SetArmRepellantCone(A,true,45,100,20,0,0);TestFalse(TEXT("Zero duration erases settings"),Configs.Contains(A));
    TestFalse(TEXT("Invalid radius rejected"),L::SetArmRepellantCone(A,true,100));
    Remove(A);ProphecyAttackRecovery::Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
