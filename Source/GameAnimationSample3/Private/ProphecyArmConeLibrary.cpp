#include "ProphecyArmConeLibrary.h"
#include "ProphecyArmCone.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNPoseTypes.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

namespace ProphecyArmCone
{
using K=ProphecyBlendClock::EKind;
struct FConfig { float Radius=45,Strength=100,Damping=20,Hold=.3f,Blend=.5f; };
struct FRecovery { FConfig Config; FName Attack; double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,TSet<FName>> Choices,ChoiceBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRecovery> Recoveries;
static TMap<TWeakObjectPtr<const AProphecyAgent>,bool> AttackHolds;
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
static TMap<TWeakObjectPtr<const AProphecyAgent>,uint8> PublishedCorrections;
// Separate live layout; cached rotations use world space to survive carrier rebases.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FPublicationFeedback> PublishedFeedback;
bool bAnyActive=false;
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
        Clean(Configs);Clean(Baselines);Clean(Choices);Clean(ChoiceBaselines);Clean(Recoveries);Clean(AttackHolds);Clean(TargetCorrections);Clean(PublishedArms);Clean(PublishedCorrections);Clean(PublishedFeedback);bAnyActive=!Recoveries.IsEmpty();
    });
}
void Cancel(const AProphecyAgent* A)
{
    if(!AttackHolds.IsEmpty()) AttackHolds.Remove(A);
    if(!TargetCorrections.IsEmpty()) TargetCorrections.Remove(A);
    if(!PublishedArms.IsEmpty()) PublishedArms.Remove(A);
    if(!PublishedCorrections.IsEmpty()) PublishedCorrections.Remove(A);
    if(!PublishedFeedback.IsEmpty()) PublishedFeedback.Remove(A);
    if(!Recoveries.IsEmpty() && Recoveries.Remove(A)) ProphecyBlendClock::Stop(A,K::ArmRepellantCone);
    bAnyActive=!Recoveries.IsEmpty();
}
void BeginAttack(const AProphecyAgent* A,FName Attack)
{
    Cancel(A);
#if WITH_EDITOR
    if(Audit.GetValueOnGameThread()) UE_LOG(LogTemp,Display,TEXT("ArmCone Begin %s attack=%s config=%d choices=%d"),*GetNameSafe(A),*Attack.ToString(),Configs.Contains(A),Choices.Contains(A));
#endif
    if(Configs.IsEmpty() || Choices.IsEmpty()) return;
    const auto* C=Configs.Find(A);const auto* Selected=Choices.Find(A);
    if(!C || !Selected || !Selected->Contains(Attack) || !Valid(A)) return;
    EnsureCleanup();Recoveries.Add(A,FRecovery{*C,Attack});bAnyActive=true;
    AttackHolds.Add(A,true);
}
void Begin(const AProphecyAgent* A,FName Attack)
{
    const auto* Existing=Recoveries.Find(A);
    if(!Existing || Existing->Attack!=Attack || !AttackHolds.Contains(A)) BeginAttack(A,Attack);
    if(auto* R=Recoveries.Find(A))
    {
        AttackHolds.Remove(A);R->Elapsed=0;
        const double Duration=double(R->Config.Hold)+R->Config.Blend;
        if(Duration<=0) Cancel(A);
        else ProphecyBlendClock::Start(A,K::ArmRepellantCone,Duration);
    }
}
void Remove(const AProphecyAgent* A)
{ Cancel(A);Configs.Remove(A);Choices.Remove(A);ForgetReset(A); }
void CaptureReset(const AProphecyAgent* A)
{
    EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A);
    if(const auto* C=Choices.Find(A)) ChoiceBaselines.Add(A,*C);else ChoiceBaselines.Remove(A);
}
void RestoreReset(const AProphecyAgent* A)
{
    Cancel(A);Configs.Remove(A);Choices.Remove(A);
    if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C);
    if(const auto* C=ChoiceBaselines.Find(A)) Choices.Add(A,*C);
}
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A);ChoiceBaselines.Remove(A); }
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
bool Active(const AProphecyAgent* A)
{
    return bAnyActive && Recoveries.Contains(A);
}
bool ApplyNNPose(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Pose,const FTransform& Carrier,float DeltaSeconds)
{
    if(Recoveries.IsEmpty()) return false;
    auto* R=Recoveries.Find(A);
    if(!R || DeltaSeconds<=0 || !Valid(A) || A->GetWorld()->IsPaused() || Names.Num()!=Pose.Num() || Parents.Num()!=Pose.Num()) return false;
    const bool Held=AttackHolds.Contains(A);
    if(!Held) R->Elapsed+=ProphecyBlendClock::Consume(A,K::ArmRepellantCone);
    const double W=Held?1.:Weight(R->Config,R->Elapsed);
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
    // Accepted policy steps use the fixed game-tick scheduler budget, never hitch catch-up.
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
uint8 ApplyNNPublication(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,const FTransform& PreviousCarrier,
    const FTransform& Carrier,float DeltaSeconds,bool NewSample,FPublicationFeedback* Feedback)
{
    if(Feedback) Feedback->Arms=0;
    if(!Active(A)) return false;
    auto ReadFeedback=[&]()
    {
        if(Feedback && AttackHolds.Contains(A)) if(const auto* Saved=PublishedFeedback.Find(A))
        {
            Feedback->Arms=Saved->Arms;
            for(int32 Side=0;Side<2;++Side) if(Saved->Arms & (1<<Side))
                Feedback->WristRotation[Side]=(Carrier.GetRotation().Inverse()*Saved->WristRotation[Side]).GetNormalized();
        }
    };
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
        if(!NewSample) { ReadFeedback();return PublishedCorrections.FindRef(A); }
    }
    else if(!NewSample) return false;
    FTransform Before[6];
    for(int32 I=0;I<6;++I) Before[I]=Current[Indices[I]];
    ApplyNNPose(A,Names,Parents,Current,Carrier,DeltaSeconds);
    if(!Active(A)) return false;
    FPublicationFeedback Cone;
    for(int32 I=0;I<6;++I)
        if(!Current[Indices[I]].Equals(Before[I],1.e-8)) Cone.Arms|=uint8(1<<(I/3));
    // Recovery is a temporary publication correction. Feeding it into the
    // locomotion checkpoint compounds the displacement and prevents a clean fade.
    if(Cone.Arms && AttackHolds.Contains(A))
    {
        for(int32 Side=0;Side<2;++Side) if(Cone.Arms & (1<<Side))
            Cone.WristRotation[Side]=(Carrier.GetRotation()*Current[Indices[Side*3+2]].GetRotation()).GetNormalized();
        PublishedFeedback.Add(A,Cone);
        ReadFeedback();
    }
    else PublishedFeedback.Remove(A);
    auto& Saved=PublishedArms.FindOrAdd(A);
    uint8 ChangedArms=0;
    for(int32 I=0;I<6;++I)
    {
        if(!Current[Indices[I]].Equals(Before[I],1.e-8)) ChangedArms|=uint8(1<<(I/3));
        Saved.Previous[I]=Previous[Indices[I]]*PreviousCarrier;
        Saved.Current[I]=Current[Indices[I]]*Carrier;
    }
    PublishedCorrections.Add(A,ChangedArms);
    return ChangedArms;
}
static void BeginInsideEndEvent(AProphecyAgent* A)
{
    if(Recoveries.Contains(A)) return;
    if(ProphecyAttackRecovery::IsEndEvent(A)) Begin(A,ProphecyAttackRecovery::EndEventAttack(A));
    else if(Configs.Contains(A) && Choices.Contains(A))
    {
        FName Attack;bool Half,Armed,Hit;int32 Frame;
        if(A->GetNNAttackState(Attack,Half,Armed,Hit,Frame)) BeginAttack(A,Attack);
    }
}
}

bool UProphecyArmConeLibrary::SetArmRepellantCone(AProphecyAgent* A,bool Enabled,float Radius,float Strength,float Damping,float Hold,float Blend)
{
    using namespace ProphecyArmCone;
    if(!Valid(A))return false;
    if(!Enabled){Cancel(A);Configs.Remove(A);return true;}
    if(!FMath::IsFinite(Radius)||!FMath::IsFinite(Strength)||!FMath::IsFinite(Damping)||
        !FMath::IsFinite(Hold)||!FMath::IsFinite(Blend)||Radius<0||Radius>=90||Strength<0||Damping<0||Hold<0||Blend<0)return false;
    if(Radius==0||Strength==0){Cancel(A);Configs.Remove(A);return true;}
    EnsureCleanup();const FConfig C{Radius,Strength,Damping,Hold,Blend};Configs.Add(A,C);
    if(auto* R=Recoveries.Find(A))
    {
        R->Config=C;
        if(!AttackHolds.Contains(A))
        {
            R->Elapsed+=ProphecyBlendClock::Consume(A,K::ArmRepellantCone);
            const double Remaining=double(C.Hold)+C.Blend-R->Elapsed;
            if(Remaining<=0) Cancel(A);
            else ProphecyBlendClock::Start(A,K::ArmRepellantCone,Remaining);
        }
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
    if(Configs.IsEmpty() || !Configs.Contains(A))return false;
    const auto* R=Recoveries.Find(A);const auto* C=R?&R->Config:Configs.Find(A);const FConfig Default;
    if(!C) C=&Default;
    TArray<FName> Names;TArray<FTransform> Future,Presented;float Alpha=0;
    FProphecyNNPoseSnapshot Snapshot;
    if(!A->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Presented,Alpha,Snapshot)) return false;
    FArmConeGeometry G;if(!Geometry(Names,Presented,FTransform::Identity,G)) return false;
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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeFeedbackTest,"Prophecy.Physics.ArmCone.FeedbackOnlyCorrectedArms",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeFeedbackTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    const FName Names[]={TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const int32 Parents[]={-1,0,1,-1,3,4};FTransform Previous[6],Current[6];
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 I=3*Side;const FVector Shoulder(0,Side?15:-15,100);
        Current[I]=FTransform(Shoulder);
        Current[I+1]=FTransform(Shoulder+FVector(0,Side?25:-25,0));
        Current[I+2]=FTransform(Current[I+1].GetLocation()+FVector(15,0,-20));
        for(int32 B=0;B<3;++B)Previous[I+B]=Current[I+B];
    }
    L::SetArmRepellantCone(A,true,60,1000000,20,1,.5);
    L::SetAttackArmRepellantConeEnabled(A,false,true);Begin(A,TEXT("slashR"));
    FPublicationFeedback Feedback;
    auto Publish=[&](bool New){return ApplyNNPublication(A,Names,Parents,Previous,Current,
        FTransform::Identity,FTransform::Identity,New?1.f/30:0.f,New,&Feedback);};
    TestEqual(TEXT("Active cone outside both limits requests no recurrent rewrite"),Publish(true),uint8(0));
    TestEqual(TEXT("Repeated uncorrected publication also bypasses feedback"),Publish(false),uint8(0));
    Current[1].SetLocation(Current[0].GetLocation()+FVector(1,25,0));
    Current[2].SetLocation(Current[1].GetLocation()+FVector(15,0,-20));
    const FTransform Right[3]={Current[3],Current[4],Current[5]};
    TestEqual(TEXT("Only inward left arm requests feedback"),Publish(true),uint8(1));
    TestEqual(TEXT("Recovery correction does not rewrite the checkpoint"),Feedback.Arms,uint8(0));
    for(int32 I=0;I<3;++I)TestTrue(TEXT("Uncorrected right arm untouched"),Current[I+3].Equals(Right[I],1.e-8));
    TestEqual(TEXT("Repeated corrected publication preserves its arm mask"),Publish(false),uint8(1));
    TestEqual(TEXT("Repeated recovery also leaves checkpoint motion untouched"),Feedback.Arms,uint8(0));
    L::SetArmRepellantCone(A,false);
    TestFalse(TEXT("Cancel clears feedback sidecar"),PublishedCorrections.Contains(A));
    TestFalse(TEXT("Cancel clears cone-only feedback pose"),PublishedFeedback.Contains(A));
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
    TestFalse(TEXT("FK upper return cancels legacy cone"),Recoveries.Contains(A));
    Begin(A,TEXT("slashR"));TestTrue(TEXT("Explicit opt-in recovery is retained"),Recoveries.Contains(A));
    ProphecyAttackRecovery::EnterSpecial(A,true);TestFalse(TEXT("New half special cancels"),Recoveries.Contains(A));
    ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),false,true);
    TestFalse(TEXT("Full FK return cancels legacy cone"),Recoveries.Contains(A));
    Begin(A,TEXT("slashR"));
    L::SetAttackArmRepellantConeEnabled(A);TestFalse(TEXT("Removing active attack immediately cancels"),Recoveries.Contains(A));
    L::SetAttackArmRepellantConeEnabled(A,false,true);CaptureReset(A);
    L::SetArmRepellantCone(A,false);Begin(A,TEXT("slashR"));TestFalse(TEXT("Master off bypasses"),Recoveries.Contains(A));
    RestoreReset(A);Begin(A,TEXT("slashR"));TestTrue(TEXT("Reset restores configuration and selection"),Recoveries.Contains(A));
    Cancel(A);ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),false,false);
    TestFalse(TEXT("Interrupted special starts no recoil"),Recoveries.Contains(A));
    Begin(A,TEXT("slashL"));TestFalse(TEXT("Unselected attack bypass"),Recoveries.Contains(A));
    L::SetArmRepellantCone(A,true,45,0);Begin(A,TEXT("slashR"));
    TestFalse(TEXT("Zero strength erases settings and recovery"),Configs.Contains(A)||Recoveries.Contains(A));
    L::SetArmRepellantCone(A,true,45,100,20,0,0);BeginAttack(A,TEXT("slashR"));
    TestTrue(TEXT("Zero post duration permits attack-only recoil"),Active(A));
    Begin(A,TEXT("slashR"));TestFalse(TEXT("Attack-only retires at upper release"),Active(A));
    TestFalse(TEXT("Invalid radius rejected"),L::SetArmRepellantCone(A,true,100));
    Remove(A);ProphecyAttackRecovery::Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeAttackHoldTest,"Prophecy.Physics.ArmCone.AttackHoldAndRelease",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeAttackHoldTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    const FName Names[]={TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    TArray<FName> PoseNames;PoseNames.Append(Names,UE_ARRAY_COUNT(Names));PoseNames.Add(TEXT("spine_05"));
    const int32 Parents[]={6,0,1,6,3,4,-1};FTransform Raw[7],Previous[7],Current[7];
    Raw[6]=Previous[6]=Current[6]=FTransform::Identity;
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 I=3*Side;const FVector Shoulder(0,Side?15:-15,100);
        const FVector Dir=FVector(1,Side?-4:4,0).GetSafeNormal();
        Raw[I]=FTransform(Shoulder);Raw[I+1]=FTransform(Shoulder+30*Dir);Raw[I+2]=FTransform(Shoulder+55*Dir);
        for(int32 B=0;B<3;++B)Previous[I+B]=Raw[I+B];
    }
    L::SetArmRepellantCone(A,true,60,1000000,20,.5f,1.f);
    L::SetAttackArmRepellantConeEnabled(A,false,true);BeginAttack(A,TEXT("slashR"));
    auto Step=[&]()
    {
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
        for(int32 I=0;I<7;++I)Current[I]=Raw[I];
        return ApplyNNPublication(A,PoseNames,Parents,Previous,Current,FTransform::Identity,FTransform::Identity,1.f/60,true);
    };
    for(int32 Tick=0;Tick<240;++Tick)
    {
        L::SetArmRepellantCone(A,true,60,1000000,20,.5f,1.f);
        Step();
    }
    TestTrue(TEXT("Long attack stays active beyond post-release duration"),Active(A));
    TestEqual(TEXT("Attack does not consume hold or blend"),Recoveries.FindChecked(A).Elapsed,0.);
    TestEqual(TEXT("No cone clock during attack"),ProphecyBlendClock::Consume(A,K::ArmRepellantCone),0.);
    FArmConeGeometry G;Geometry(PoseNames,Current,FTransform::Identity,G);
    TestTrue(TEXT("Attack correction retains full cone weight"),FVector::DotProduct(G.Direction[0],G.Right)<.501);
    ProphecyAttackRecovery::NotifyLowerEnded(A,TEXT("slashR"),true,true);
    TestTrue(TEXT("Full-to-half does not release attack hold"),AttackHolds.Contains(A));
    const FVector Offset=TargetCorrections.FindChecked(A).Offset[0];
    Begin(A,TEXT("slashR")); // Exercise retained opt-in hold/blend, not automatic FK handoff.
    TestFalse(TEXT("Explicit release removes hold"),AttackHolds.Contains(A));
    TestTrue(TEXT("Upper end preserves recoil spring"),TargetCorrections.FindChecked(A).Offset[0].Equals(Offset));
    for(int32 Tick=0;Tick<30;++Tick)Step();
    TestTrue(TEXT("Post-release hold is full weight"),FMath::IsNearlyEqual(Weight(Recoveries.FindChecked(A).Config,Recoveries.FindChecked(A).Elapsed),1.,1.e-6));
    for(int32 Tick=0;Tick<30;++Tick)Step();
    TestTrue(TEXT("Then blend reaches half weight"),FMath::IsNearlyEqual(Weight(Recoveries.FindChecked(A).Config,Recoveries.FindChecked(A).Elapsed),.5,1.e-6));
    for(int32 Tick=0;Tick<30;++Tick)Step();
    TestFalse(TEXT("Completed blend retires"),Active(A));
    BeginAttack(A,TEXT("slashR"));ProphecyAttackRecovery::NotifyEnded(A,TEXT("slashR"),false,false);
    TestFalse(TEXT("Interrupted attack cancels held recoil"),Active(A));
    L::SetArmRepellantCone(A,false);BeginAttack(A,TEXT("slashR"));
    TestFalse(TEXT("Disabled attack has no pose work"),Step()!=0);
    Remove(A);ProphecyAttackRecovery::Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmConeDisabledTest,"Prophecy.Physics.ArmCone.DisabledByDefault",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmConeDisabledTest::RunTest(const FString&)
{
    using namespace ProphecyArmCone;using L=UProphecyArmConeLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    L::SetAttackArmRepellantConeEnabled(A,false,true);
    TestTrue(TEXT("Default setter succeeds"),L::SetArmRepellantCone(A));
    BeginAttack(A,TEXT("slashR"));
    TestFalse(TEXT("Selected attack cannot override disabled master"),Active(A)||Configs.Contains(A));
    TestFalse(TEXT("No state or publication cache while disabled"),TargetCorrections.Contains(A)||PublishedArms.Contains(A)||Recoveries.Contains(A));
    TestFalse(TEXT("Disabled visualization does not require or read a pose"),L::VisualizeArmRepellantCone(A));
    TestEqual(TEXT("Disabled has no blend clock"),ProphecyBlendClock::Consume(A,K::ArmRepellantCone),0.);
    L::SetArmRepellantCone(A,true);BeginAttack(A,TEXT("slashR"));
    TestTrue(TEXT("Retained cone can be explicitly enabled"),Active(A)&&AnyActive());
    L::SetArmRepellantCone(A);
    TestFalse(TEXT("Disabling immediately retires active work"),Active(A)||Recoveries.Contains(A));
    TestEqual(TEXT("Global fast gate matches live state"),AnyActive(),!Recoveries.IsEmpty());
    Remove(A);ProphecyAttackRecovery::Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
