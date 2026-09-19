#include "ProphecyPhysicalContext.h"
#include "ProphecyAgent.h"
#include "ProphecyPhysicalBlendSubsystem.h"
#include "ProphecyPhysicalProfileLibrary.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

namespace ProphecyPhysicalContext
{
struct FValue
{
    FVector2f Scales=FVector2f::ZeroVector;
    bool Enabled=true;
    bool operator==(const FValue& Other) const { return Scales==Other.Scales && Enabled==Other.Enabled; }
};
struct FCell
{
    FValue Value,Start,Target;
    double Begin=0,Duration=0;
    void Sample(double Clock)
    {
        if (Duration<=0) return;
        const double T=Clock-Begin+1.e-9>=Duration ? 1. : FMath::Clamp((Clock-Begin)/Duration,0.,1.);
        Value={FMath::Lerp(Start.Scales,Target.Enabled ? Target.Scales : FVector2f::ZeroVector,float(T*T*(3.-2.*T))),true};
        if (T>=1) { Value=Target; Duration=0; }
    }
    void Write(FValue NewValue,float Seconds,double Clock)
    {
        Sample(Clock);
        Start=Value;
        if (!Start.Enabled) Start.Scales=FVector2f::ZeroVector;
        Target=NewValue; Begin=Clock;
        Duration=Seconds>0 && !(Start==Target) ? Seconds : 0;
        Value=Duration>0 ? FValue{Start.Scales,true} : Target;
    }
};
struct FEntry
{
    FName Bone;
    EKind Kind;
    // Walk sheathed, run sheathed, walk drawn, run drawn.
    FCell Cells[4];
    FValue Applied;
    bool AppliedValid=false;
    FValue Resolve(float Walk,bool Drawn,bool Attack) const
    {
        if (Attack) return {Kind==EKind::Feedback ? FVector2f(1000,1000) : FVector2f(1,1),true};
        const int32 Offset=Drawn ? 2 : 0;
        const auto& A=Cells[Offset].Value;
        const auto& B=Cells[Offset+1].Value;
        if (Walk>=1) return A;
        if (Walk<=0) return B;
        return {FMath::Lerp(B.Enabled ? B.Scales : FVector2f::ZeroVector,
            A.Enabled ? A.Scales : FVector2f::ZeroVector,Walk),A.Enabled || B.Enabled};
    }
    bool Running() const
    { for (const auto& Cell:Cells) if (Cell.Duration>0) return true; return false; }
};
struct FAgentState
{
    TArray<FEntry> Entries;
    double Clock=0,WorldTime=0;
    float Walk=0;
    bool Drawn=false,Attack=false,ValidContext=false;
    bool Running=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FAgentState> States;
// Only allocated by an explicit save; never visited by the update path.
static TMap<TWeakObjectPtr<const AProphecyAgent>,TMap<FName,TArray<FEntry>>> Snapshots;
static bool Applying=false;
bool IsApplying() { return Applying; }
bool Valid(EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{ return uint8(L)<=uint8(EProphecyLocomotionSelection::Run) && uint8(E)<=uint8(EProphecyEquipmentSelection::Sheathed); }
void Remove(const AProphecyAgent* Agent)
{ States.Remove(Agent); Snapshots.Remove(Agent);ProphecyBlendClock::Remove(Agent); }
bool IsManaged(const AProphecyAgent* Agent,FName Bone,EKind Kind)
{
    if (Applying || States.IsEmpty()) return false;
    const auto* State=States.Find(Agent);
    return State && State->Entries.ContainsByPredicate([&](const FEntry& E) { return E.Bone==Bone && E.Kind==Kind; });
}
static void AdvanceClock(AProphecyAgent& Agent,FAgentState& State)
{
    if (State.Running)
        State.Clock+=ProphecyBlendClock::Consume(&Agent,ProphecyBlendClock::EKind::Profiles);
}
static void Publish(AProphecyAgent& Agent,FEntry& Entry,FValue Value)
{
    if (Entry.AppliedValid && Entry.Applied==Value) return;
    TGuardValue<bool> Guard(Applying,true);
    if (Entry.Kind==EKind::Feedback)
        Agent.SetPhysicalFeedbackTolerance(Entry.Bone,Value.Scales.X,Value.Scales.Y);
    else
        Agent.SetBodyMagnetization(Entry.Bone,Value.Enabled,Value.Scales.X,Value.Scales.Y);
    Entry.Applied=Value; Entry.AppliedValid=true;
}
static bool UpdateState(AProphecyAgent& Agent,FAgentState& State,float Walk,bool Drawn,bool Attack)
{
    AdvanceClock(Agent,State);
    const bool Changed=!State.ValidContext || State.Walk!=Walk || State.Drawn!=Drawn || State.Attack!=Attack;
    if (!Changed && !State.Running) return false;
    State.Running=false;
    for (auto& Entry:State.Entries)
    {
        if (!Changed && !Entry.Running()) continue;
        for (auto& Cell:Entry.Cells) Cell.Sample(State.Clock);
        Publish(Agent,Entry,Entry.Resolve(Walk,Drawn,Attack));
        State.Running|=Entry.Running();
    }
    State.Walk=Walk; State.Drawn=Drawn; State.Attack=Attack; State.ValidContext=true;
    if (State.Running) ProphecyBlendClock::Ensure(&Agent,ProphecyBlendClock::EKind::Profiles);
    else ProphecyBlendClock::Stop(&Agent,ProphecyBlendClock::EKind::Profiles);
    return true;
}
void Update(AProphecyAgent* Agent)
{
    auto* State=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!State || !Agent || !Agent->GetWorld()) return;
    const bool Attack=Agent->IsSwordAttackActive();
    bool Drawn=false; float Walk=1,Run=0;
    if (!Attack)
    {
        Drawn=IsValid(Agent->GetHeldSword());
        if (!Agent->GetLocomotionCheckpointWeights(Walk,Run)) Walk=1;
    }
    const bool Updated=UpdateState(*Agent,*State,FMath::Clamp(Walk,0.f,1.f),Drawn,Attack);
    if (Updated && !Attack)
    {
        // A completed universal restore needs no ongoing context processing.
        State->Entries.RemoveAllSwap([](const FEntry& Entry)
        {
            if (Entry.Running()) return false;
            for (int32 I=1;I<4;++I) if (!(Entry.Cells[0].Value==Entry.Cells[I].Value)) return false;
            return true;
        });
        if (State->Entries.IsEmpty()) States.Remove(Agent);
    }
}
static bool Matches(int32 Cell,EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{
    const bool Walk=(Cell%2)==0,Drawn=Cell>=2;
    return (L==EProphecyLocomotionSelection::Both || Walk==(L==EProphecyLocomotionSelection::Walk))
        && (E==EProphecyEquipmentSelection::Both || Drawn==(E==EProphecyEquipmentSelection::Drawn));
}
bool Set(AProphecyAgent& Agent,FName Bone,EKind Kind,bool Enabled,FVector2f Value,float Duration,
    EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{
    if (!IsInGameThread() || Agent.IsActorBeingDestroyed() || !Agent.GetWorld() || Bone.IsNone()
        || !Valid(L,E) || !FMath::IsFinite(Value.X) || !FMath::IsFinite(Value.Y) || !FMath::IsFinite(Duration)) return false;
    Value.X=FMath::Max(0.f,Value.X); Value.Y=FMath::Max(0.f,Value.Y);
    const bool Universal=L==EProphecyLocomotionSelection::Both && E==EProphecyEquipmentSelection::Both;
    // Ordinary pre-existing calls stay on their original path, allocating no profile.
    if (Universal && !IsManaged(&Agent,Bone,Kind))
    {
        if (Duration>0)
            return Kind==EKind::Feedback ? Agent.BlendPhysicalFeedbackTolerance(Bone,Value.X,Value.Y,Duration)
                : Agent.BlendBodyMagnetization(Bone,Value.X,Value.Y,Duration);
        if (Kind==EKind::Feedback) return Agent.SetPhysicalFeedbackTolerance(Bone,Value.X,Value.Y);
        Agent.SetBodyMagnetization(Bone,Enabled,Value.X,Value.Y); return true;
    }
    FValue Initial;
    if (Kind==EKind::Feedback)
    {
        FProphecyPhysicalFeedbackToleranceSettings S;
        if (!Agent.GetPhysicalFeedbackTolerance(Bone,S)) return false;
        Initial.Scales={S.LinearToleranceCm,S.AngularToleranceDegrees};
    }
    else
    {
        FProphecyBodyMagnetizationSettings S;
        Agent.GetBodyMagnetizationSettings(Bone,S);
        Initial={FVector2f(S.LinearStrengthScale,S.AngularStrengthScale),S.bMagnetizationEnabled};
    }
    auto* State=States.Find(&Agent);
    if (!State)
    {
        State=&States.Add(&Agent);
        State->WorldTime=Agent.GetWorld()->GetTimeSeconds();
    }
    AdvanceClock(Agent,*State);
    auto* Entry=State->Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; });
    if (!Entry)
    {
        Entry=&State->Entries.AddDefaulted_GetRef(); Entry->Bone=Bone; Entry->Kind=Kind;
        for (auto& Cell:Entry->Cells) Cell.Value=Initial;
    }
    // Cancel legacy timeline ownership, without cancelling our other context cells.
    {
        TGuardValue<bool> Guard(Applying,true);
        if (Kind==EKind::Feedback) Agent.CancelPhysicalFeedbackToleranceBlend(Bone);
        else Agent.CancelBodyMagnetizationBlend(Bone);
    }
    for (int32 I=0;I<4;++I) if (Matches(I,L,E)) Entry->Cells[I].Write({Value,Enabled},Duration,State->Clock);
    State->ValidContext=false;
    Update(&Agent);
    if (Universal && Duration<=0 && !Agent.IsSwordAttackActive())
    {
        if (auto* Remaining=States.Find(&Agent))
        {
            Remaining->Entries.RemoveAllSwap([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; });
            if (Remaining->Entries.IsEmpty()) States.Remove(&Agent);
        }
    }
    return true;
}
void AttackChanged(AProphecyAgent* Agent)
{
    if (!Agent || !Agent->GetWorld()) return;
    if (Agent->IsSwordAttackActive())
    {
        auto* Mesh=Agent->GetPoseReferenceMesh();
        if (!Mesh) return;
        auto& State=States.FindOrAdd(Agent);
        if (State.Entries.IsEmpty()) State.WorldTime=Agent->GetWorld()->GetTimeSeconds();
        auto Capture=[&](FName Bone,EKind Kind,FValue Value)
        {
            if (State.Entries.ContainsByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; })) return;
            auto& Entry=State.Entries.AddDefaulted_GetRef(); Entry.Bone=Bone; Entry.Kind=Kind;
            for (auto& Cell:Entry.Cells) Cell.Value=Value;
        };
        if (const auto* Asset=Mesh->GetPhysicsAsset())
            for (const USkeletalBodySetup* Body:Asset->SkeletalBodySetups) if (Body)
            {
                FProphecyBodyMagnetizationSettings S;
                Agent->GetBodyMagnetizationSettings(Body->BoneName,S);
                Capture(Body->BoneName,EKind::Magnetization,{FVector2f(S.LinearStrengthScale,S.AngularStrengthScale),S.bMagnetizationEnabled});
            }
        TArray<FName> Bones; Mesh->GetBoneNames(Bones);
        for (FName Bone:Bones)
        {
            FProphecyPhysicalFeedbackToleranceSettings S;
            if (Agent->GetPhysicalFeedbackTolerance(Bone,S))
                Capture(Bone,EKind::Feedback,{FVector2f(S.LinearToleranceCm,S.AngularToleranceDegrees),true});
        }
        if (auto* Blends=Agent->GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>())
            Blends->MoveBlendsToContext(*Agent);
        State.ValidContext=false;
    }
    Update(Agent);
    if (!Agent->IsSwordAttackActive())
        if (auto* State=States.Find(Agent))
        {
            // Identical universal settings need no locomotion policy processing.
            State->Entries.RemoveAllSwap([](const FEntry& Entry)
            {
                if (Entry.Running()) return false;
                for (int32 I=1;I<4;++I) if (!(Entry.Cells[0].Value==Entry.Cells[I].Value)) return false;
                return true;
            });
            if (State->Entries.IsEmpty()) States.Remove(Agent);
        }
}
void AdoptBlend(AProphecyAgent& Agent,FName Bone,EKind Kind,FVector2f Start,FVector2f Target,double Elapsed,double Duration)
{
    auto* State=States.Find(&Agent);
    if (!State) return;
    auto* Entry=State->Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; });
    if (!Entry) return;
    AdvanceClock(Agent,*State);
    for (auto& Cell:Entry->Cells)
    {
        Cell.Start={Start,true}; Cell.Target={Target,true};
        Cell.Duration=Duration; Cell.Begin=State->Clock-Elapsed;
        Cell.Sample(State->Clock);
    }
    State->ValidContext=false;
}
void Cancel(AProphecyAgent* Agent,FName Bone,EKind Kind)
{
    if (Applying || States.IsEmpty()) return;
    auto* State=States.Find(Agent);
    if (!State) return;
    AdvanceClock(*Agent,*State);
    for (auto& Entry:State->Entries) if (Entry.Kind==Kind && (Bone.IsNone() || Entry.Bone==Bone))
        for (auto& Cell:Entry.Cells) { Cell.Sample(State->Clock); Cell.Duration=0; }
    State->ValidContext=false;
    Update(Agent);
}

static FEntry Capture(AProphecyAgent& Agent,FName Bone,EKind Kind)
{
    if (const auto* State=States.Find(&Agent))
        if (const auto* Entry=State->Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; }))
        {
            FEntry Copy=*Entry;
            for (auto& Cell:Copy.Cells) { Cell.Sample(State->Clock); Cell.Duration=0; }
            Copy.AppliedValid=false;
            return Copy;
        }
    FEntry Entry; Entry.Bone=Bone; Entry.Kind=Kind;
    FValue Value;
    if (Kind==EKind::Magnetization)
    {
        FProphecyBodyMagnetizationSettings S; Agent.GetBodyMagnetizationSettings(Bone,S);
        Value={FVector2f(S.LinearStrengthScale,S.AngularStrengthScale),S.bMagnetizationEnabled};
    }
    else
    {
        FProphecyPhysicalFeedbackToleranceSettings S; Agent.GetPhysicalFeedbackTolerance(Bone,S);
        Value.Scales={S.LinearToleranceCm,S.AngularToleranceDegrees};
    }
    for (auto& Cell:Entry.Cells) Cell.Value=Value;
    return Entry;
}
static bool SaveSnapshot(AProphecyAgent* Agent,FName Name)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()) return false;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return false;
    Update(Agent);
    TArray<FEntry> Saved;
    TArray<FName> Bodies;
    if (const auto* Asset=Mesh->GetPhysicsAsset())
        for (const USkeletalBodySetup* Body:Asset->SkeletalBodySetups) if (Body) Bodies.AddUnique(Body->BoneName);
    for (const auto& Pair:Agent->BodyMagnetizationSettings) Bodies.AddUnique(Pair.Key);
    for (FName Bone:Bodies) Saved.Add(Capture(*Agent,Bone,EKind::Magnetization));
    TArray<FName> Bones; Mesh->GetBoneNames(Bones);
    for (FName Bone:Bones)
    {
        FProphecyPhysicalFeedbackToleranceSettings S;
        if (Agent->GetPhysicalFeedbackTolerance(Bone,S)) Saved.Add(Capture(*Agent,Bone,EKind::Feedback));
    }
    if (Saved.IsEmpty()) return false;
    for (auto It=Snapshots.CreateIterator();It;++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    Snapshots.FindOrAdd(Agent).Add(Name,MoveTemp(Saved));
    return true;
}
// Selection: 0 = one bone, 1 = subtree, 2 = every saved bone of the requested kind.
static int32 RestoreSnapshot(AProphecyAgent* Agent,FName Name,EKind Kind,FName Bone,int32 Selection,bool IncludeParent,float Duration)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || !FMath::IsFinite(Duration) || (Selection!=2 && Bone.IsNone())) return 0;
    const auto* AgentSnapshots=Snapshots.Find(Agent);
    const auto* Saved=AgentSnapshots ? AgentSnapshots->Find(Name) : nullptr;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Saved || !Mesh) return 0;
    TArray<const FEntry*> Selected;
    for (const auto& Entry:*Saved)
        if (Entry.Kind==Kind && (Selection==2 || (Entry.Bone==Bone && (Selection==0 || IncludeParent))
            || (Selection==1 && Entry.Bone!=Bone && Mesh->BoneIsChildOf(Entry.Bone,Bone)))) Selected.Add(&Entry);
    if (Selected.IsEmpty()) return 0;
    Update(Agent);
    auto& State=States.FindOrAdd(Agent);
    if (State.Entries.IsEmpty()) State.WorldTime=Agent->GetWorld()->GetTimeSeconds();
    AdvanceClock(*Agent,State);
    for (const FEntry* Target:Selected)
    {
        const FEntry Current=Capture(*Agent,Target->Bone,Kind);
        // Transfer timeline ownership without cancelling the other contexts or bones.
        {
            TGuardValue<bool> Guard(Applying,true);
            if (Kind==EKind::Magnetization) Agent->CancelBodyMagnetizationBlend(Target->Bone);
            else Agent->CancelPhysicalFeedbackToleranceBlend(Target->Bone);
        }
        auto* Entry=State.Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Target->Bone && X.Kind==Kind; });
        if (!Entry) Entry=&State.Entries.Add_GetRef(Current);
        for (int32 I=0;I<4;++I) Entry->Cells[I].Write(Target->Cells[I].Value,Duration,State.Clock);
        Entry->AppliedValid=false;
    }
    State.ValidContext=false;
    Update(Agent);
    return Selected.Num();
}
}

bool UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot(AProphecyAgent* Agent,FName Name)
{ return ProphecyPhysicalContext::SaveSnapshot(Agent,Name); }
bool UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,Bone,0,true,Duration)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationBelowToSnapshot(AProphecyAgent* Agent,FName Bone,bool Include,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,Bone,1,Include,Duration); }
int32 UProphecyPhysicalProfileLibrary::BlendAllBodyMagnetizationToSnapshot(AProphecyAgent* Agent,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,NAME_None,2,true,Duration); }
bool UProphecyPhysicalProfileLibrary::BlendPhysicalFeedbackToleranceToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,Bone,0,true,Duration)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendPhysicalFeedbackToleranceBelowToSnapshot(AProphecyAgent* Agent,FName Bone,bool Include,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,Bone,1,Include,Duration); }
int32 UProphecyPhysicalProfileLibrary::BlendAllPhysicalFeedbackTolerancesToSnapshot(AProphecyAgent* Agent,float Duration,FName Name)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,NAME_None,2,true,Duration); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPhysicalContextTest,"Prophecy.Agent.PhysicalContext.SelectionAndAttacks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPhysicalContextTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;
    using L=EProphecyLocomotionSelection;
    using E=EProphecyEquipmentSelection;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("Test world"),World)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    AProphecyAgent* Agent=nullptr;
    ON_SCOPE_EXIT
    {
        Remove(Agent);
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
    };
    Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Test agent"),Agent)) return false;
    Agent->bAutoEnsureStandaloneNNManager=false;
    auto* MeshAsset=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Real skeleton"),MeshAsset)) return false;
    Agent->GetAgentMesh()->SetSkeletalMeshAsset(MeshAsset);
    auto Read=[&]() { FProphecyBodyMagnetizationSettings V; Agent->GetBodyMagnetizationSettings(TEXT("head"),V); return V; };
    auto Feedback=[&]() { FProphecyPhysicalFeedbackToleranceSettings V; Agent->GetPhysicalFeedbackTolerance(TEXT("head"),V); return V; };
    TestEqual(TEXT("Legacy Below selects head"),Agent->SetBodyMagnetizationBelow(TEXT("head"),true,true,.2f,.4f),1);
    TestFalse(TEXT("Both/Both default creates no policy"),States.Contains(Agent));
    TestEqual(TEXT("Conditional Below selects head"),Agent->SetBodyMagnetizationBelow(TEXT("head"),true,true,.8f,1.6f,L::Walk,E::Drawn),1);
    TestEqual(TEXT("Inactive drawn condition preserves sheathed baseline"),Read().LinearStrengthScale,.2f);
    auto& State=States.FindChecked(Agent);
    UpdateState(*Agent,State,1,true,false);
    TestEqual(TEXT("Walk drawn override"),Read().LinearStrengthScale,.8f);
    UpdateState(*Agent,State,0,true,false);
    TestEqual(TEXT("Run drawn baseline"),Read().LinearStrengthScale,.2f);
    UpdateState(*Agent,State,.5f,true,false);
    TestEqual(TEXT("Actual checkpoint weights mix strengths"),Read().LinearStrengthScale,.5f);
    Agent->SetPhysicalFeedbackToleranceBelow(TEXT("head"),true,2,4,L::Both,E::Drawn);
    UpdateState(*Agent,State,0,true,false);
    TestEqual(TEXT("Both locomotion modes drawn feedback"),Feedback().AngularToleranceDegrees,4.f);
    TestEqual(TEXT("Conditional timed Below"),Agent->BlendBodyMagnetizationBelow(TEXT("head"),true,0,0,1,L::Walk,E::Drawn),1);
    State.Clock+=.5;
    UpdateState(*Agent,State,1,true,false);
    TestEqual(TEXT("Timed blend progresses in selected cell"),Read().LinearStrengthScale,.4f);
    UpdateState(*Agent,State,0,true,false);
    TestEqual(TEXT("Other checkpoint unaffected by timeline"),Read().LinearStrengthScale,.2f);
    Agent->NotifySwordAttackState(true);
    TestEqual(TEXT("Attack magnetization linear default"),Read().LinearStrengthScale,1.f);
    TestEqual(TEXT("Attack magnetization angular default"),Read().AngularStrengthScale,1.f);
    TestTrue(TEXT("Attack magnetization enabled"),Read().bMagnetizationEnabled);
    TestEqual(TEXT("Attack feedback linear default"),Feedback().LinearToleranceCm,1000.f);
    TestEqual(TEXT("Attack feedback angular default"),Feedback().AngularToleranceDegrees,1000.f);
    Agent->SetBodyMagnetizationBelow(TEXT("head"),true,true,.6f,.7f);
    TestEqual(TEXT("Both/Both writes cannot break attack default"),Read().LinearStrengthScale,1.f);
    Agent->NotifySwordAttackState(false);
    TestEqual(TEXT("Locomotion restores latest universal setting"),Read().LinearStrengthScale,.6f);
    Agent->SetPhysicalFeedbackToleranceBelow(TEXT("head"),true,8,9);
    TestEqual(TEXT("Both/Both resets conditional feedback"),Feedback().LinearToleranceCm,8.f);
    TestFalse(TEXT("Universal writes release context storage"),States.Contains(Agent));
    Agent->BlendBodyMagnetization(TEXT("head"),1,1,1);
    for (int32 Tick=0;Tick<15;++Tick) FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/30.f);
    Agent->NotifySwordAttackState(true);
    auto& DuringAttack=States.FindChecked(Agent);
    auto* Head=DuringAttack.Entries.FindByPredicate([](const FEntry& X) { return X.Bone==TEXT("head") && X.Kind==EKind::Magnetization; });
    TestTrue(TEXT("Attack transfers the active timeline without discarding it"),Head && Head->Running());
    if (Head)
    {
        TestNearlyEqual(TEXT("Transfer preserves elapsed smoothstep"),Head->Cells[0].Value.Scales.X,.6625f,1.e-6f);
        for (int32 Tick=0;Tick<45;++Tick) FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120.f);
        UpdateState(*Agent,DuringAttack,1,false,true);
    }
    Agent->NotifySwordAttackState(false);
    TestEqual(TEXT("Timeline completes behind attack override"),Read().LinearStrengthScale,1.f);
    TestFalse(TEXT("Completed attack-only storage removed"),States.Contains(Agent));
    Agent->SetBodyMagnetization(TEXT("head"),true,.2f,.4f);
    Agent->SetBodyMagnetization(TEXT("head"),true,.8f,1.6f,L::Run,E::Drawn);
    auto& SingleState=States.FindChecked(Agent);
    UpdateState(*Agent,SingleState,0,true,false);
    TestEqual(TEXT("Single-bone setter selects run/drawn"),Read().LinearStrengthScale,.8f);
    UpdateState(*Agent,SingleState,1,true,false);
    TestEqual(TEXT("Single-bone setter preserves unselected walk"),Read().LinearStrengthScale,.2f);
    TestTrue(TEXT("Single feedback accepts selectors"),Agent->SetPhysicalFeedbackTolerance(TEXT("head"),3,5,L::Run,E::Sheathed));
    UpdateState(*Agent,SingleState,0,false,false);
    TestEqual(TEXT("Single feedback selects run/sheathed"),Feedback().AngularToleranceDegrees,5.f);
    TestTrue(TEXT("Single body blend accepts selectors"),Agent->BlendBodyMagnetization(TEXT("head"),0,0,1,L::Run,E::Drawn));
    TestTrue(TEXT("Single feedback blend accepts selectors"),Agent->BlendPhysicalFeedbackTolerance(TEXT("head"),7,9,1,L::Run,E::Sheathed));
    SingleState.Clock+=.5;
    UpdateState(*Agent,SingleState,0,true,false);
    TestEqual(TEXT("Single body blend uses selected cell"),Read().LinearStrengthScale,.4f);
    UpdateState(*Agent,SingleState,0,false,false);
    TestEqual(TEXT("Single feedback blend uses selected cell"),Feedback().AngularToleranceDegrees,7.f);
    Agent->SetBodyMagnetization(TEXT("head"),true,.6f,.7f);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),8,9);
    TestFalse(TEXT("Single Both/Both defaults release policies"),States.Contains(Agent));
    using Profiles=UProphecyPhysicalProfileLibrary;
    Agent->SetBodyMagnetization(TEXT("head"),true,.8f,1.6f,L::Run,E::Drawn);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),30,50,L::Run,E::Drawn);
    TestTrue(TEXT("Save full named per-agent snapshot"),Profiles::SavePhysicalProfileSnapshot(Agent,TEXT("Baseline")));
    Agent->SetBodyMagnetization(TEXT("head"),true,0,0);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),0,0);
    TestFalse(TEXT("Unknown snapshot fails without mutation"),Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),1,TEXT("Missing")));
    TestEqual(TEXT("Failed restore leaves current settings"),Read().LinearStrengthScale,0.f);
    TestTrue(TEXT("Restore magnetization snapshot"),Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),1,TEXT("Baseline")));
    TestTrue(TEXT("Restore tolerance snapshot"),Profiles::BlendPhysicalFeedbackToleranceToSnapshot(Agent,TEXT("head"),1,TEXT("Baseline")));
    auto& Restoring=States.FindChecked(Agent);
    Restoring.Clock+=.5;
    UpdateState(*Agent,Restoring,0,true,false);
    TestEqual(TEXT("Saved run/drawn magnetization halfway"),Read().LinearStrengthScale,.4f);
    TestEqual(TEXT("Saved run/drawn tolerance halfway"),Feedback().LinearToleranceCm,15.f);
    UpdateState(*Agent,Restoring,1,false,false);
    TestEqual(TEXT("Other saved profile also blends"),Read().LinearStrengthScale,.3f);
    TestEqual(TEXT("Other saved tolerance profile also blends"),Feedback().LinearToleranceCm,4.f);
    Restoring.Clock+=.5;
    UpdateState(*Agent,Restoring,0,true,false);
    TestEqual(TEXT("Saved run/drawn exact endpoint"),Read().LinearStrengthScale,.8f);
    TestEqual(TEXT("Saved tolerance exact endpoint"),Feedback().AngularToleranceDegrees,50.f);
    Agent->NotifySwordAttackState(true);
    TestTrue(TEXT("Restore underlying profiles during attack"),Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),0,TEXT("Baseline")));
    TestEqual(TEXT("Snapshot cannot override attack default"),Read().LinearStrengthScale,1.f);
    Agent->NotifySwordAttackState(false);
    TestEqual(TEXT("After attack selected saved locomotion profile restored"),Read().LinearStrengthScale,.6f);
    Agent->SetBodyMagnetization(TEXT("head"),false,.7f,.9f);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),8,9);
    TestTrue(TEXT("Save disabled endpoint"),Profiles::SavePhysicalProfileSnapshot(Agent));
    TestFalse(TEXT("Saving alone creates no tick state"),States.Contains(Agent));
    Agent->SetBodyMagnetization(TEXT("head"),true,1,1);
    TestTrue(TEXT("Blend back to disabled snapshot"),Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),1));
    auto& DisabledBlend=States.FindChecked(Agent);
    DisabledBlend.Clock+=.5;
    UpdateState(*Agent,DisabledBlend,1,false,false);
    TestEqual(TEXT("Disabled destination fades toward zero"),Read().LinearStrengthScale,.5f);
    DisabledBlend.Clock+=.5;
    Update(Agent);
    TestFalse(TEXT("Disabled flag restored"),Read().bMagnetizationEnabled);
    TestEqual(TEXT("Disabled endpoint remembers original scale"),Read().LinearStrengthScale,.7f);
    TestFalse(TEXT("Completed uniform restore releases update state"),States.Contains(Agent));
    TestEqual(TEXT("Below respects excluded leaf parent"),Profiles::BlendBodyMagnetizationBelowToSnapshot(Agent,TEXT("head"),false,0),0);
    TestEqual(TEXT("Below includes parent"),Profiles::BlendBodyMagnetizationBelowToSnapshot(Agent,TEXT("head"),true,0),1);
    TestTrue(TEXT("Restore full tolerance snapshot"),Profiles::BlendAllPhysicalFeedbackTolerancesToSnapshot(Agent,0)>0);
    TestTrue(TEXT("Restore full magnetization snapshot"),Profiles::BlendAllBodyMagnetizationToSnapshot(Agent,0)>0);
    TestFalse(TEXT("Immediate full restore leaves no context tick state"),States.Contains(Agent));
    auto* OtherAgent=World->SpawnActor<AProphecyAgent>();
    if (OtherAgent)
    {
        OtherAgent->bAutoEnsureStandaloneNNManager=false;
        OtherAgent->GetAgentMesh()->SetSkeletalMeshAsset(MeshAsset);
        TestFalse(TEXT("Snapshots cannot leak between agents"),Profiles::BlendBodyMagnetizationToSnapshot(OtherAgent,TEXT("head"),0));
        OtherAgent->Destroy();
    }
    for (const TCHAR* Name:{TEXT("SetBodyMagnetizationBelow"),TEXT("SetPhysicalFeedbackToleranceBelow"),
        TEXT("BlendBodyMagnetizationBelow"),TEXT("BlendPhysicalFeedbackToleranceBelow"),
        TEXT("SetBodyMagnetization"),TEXT("SetPhysicalFeedbackTolerance"),
        TEXT("BlendBodyMagnetization"),TEXT("BlendPhysicalFeedbackTolerance")})
    {
        const auto* Function=Agent->FindFunction(Name);
        TestTrue(TEXT("Both enum pins exist with backwards-compatible defaults"),Function
            && Function->GetMetaData(TEXT("CPP_Default_Locomotion"))==TEXT("Both")
            && Function->GetMetaData(TEXT("CPP_Default_Equipment"))==TEXT("Both"));
    }
    return true;
}
#endif
