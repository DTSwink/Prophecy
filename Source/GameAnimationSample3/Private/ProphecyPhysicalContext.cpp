#include "ProphecyPhysicalContext.h"
#include "ProphecyAgent.h"
#include "ProphecyPhysicalBlendSubsystem.h"
#include "ProphecyPhysicalProfileLibrary.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNPolicyBlend.h"
#include "ProphecyJointDampingPolicy.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ProphecyClampProfiles.inl"

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
    double Begin=0,Duration=0,Hold=0;
    void Sample(double Clock)
    {
        if ((Duration<=0 && Hold<=0) || Clock+1.e-9<Begin) return;
        const double T=Duration<=0 || Clock-Begin+1.e-9>=Duration ? 1. : FMath::Clamp((Clock-Begin)/Duration,0.,1.);
        Value={FMath::Lerp(Start.Scales,Target.Enabled ? Target.Scales : FVector2f::ZeroVector,float(T*T*(3.-2.*T))),true};
        if (T>=1) { Value=Target; Duration=0; Hold=0; }
    }
    void Write(FValue NewValue,float Seconds,double Clock,float HoldSeconds=0)
    {
        Sample(Clock);
        Start=Value;
        if (!Start.Enabled) Start.Scales=FVector2f::ZeroVector;
        Target=NewValue; Hold=HoldSeconds; Begin=Clock+Hold;
        Duration=Seconds>0 && !(Start==Target) ? Seconds : 0;
        if(Hold<=0) Value=Duration>0 ? FValue{Start.Scales,true} : Target;
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
        if (Kind==EKind::Mode) return Cells[0].Value;
        if (Attack) return {Kind==EKind::Feedback ? FVector2f(1000,1000)
            : Kind==EKind::Damping ? FVector2f::ZeroVector : FVector2f(1,1),true};
        const int32 Offset=Drawn ? 2 : 0;
        const auto& A=Cells[Offset].Value;
        const auto& B=Cells[Offset+1].Value;
        if (Walk>=1) return A;
        if (Walk<=0) return B;
        return {FMath::Lerp(B.Enabled ? B.Scales : FVector2f::ZeroVector,
            A.Enabled ? A.Scales : FVector2f::ZeroVector,Walk),A.Enabled || B.Enabled};
    }
    bool Running() const
    { for (const auto& Cell:Cells) if (Cell.Duration>0 || Cell.Hold>0) return true; return false; }
};
struct FAgentState
{
    TArray<FEntry> Entries;
    double Clock=0,WorldTime=0;
    float Walk=0;
    FVector2f Legs=FVector2f::ZeroVector;
    bool Drawn=false,Attack=false,ValidContext=false;
    bool Running=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FAgentState> States;
// Only allocated by an explicit save; never visited by the update path.
static TMap<TWeakObjectPtr<const AProphecyAgent>,TMap<FName,TArray<FEntry>>> Snapshots;
// A restored special owns its saved profiles instead of the legacy attack defaults.
// Separate storage keeps existing Live Coding state layouts unchanged.
static TSet<TWeakObjectPtr<const AProphecyAgent>> SnapshotSpecials;
struct FModeState { float Uniform=1.f;TMap<FName,float> Overrides;uint64 Revision=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FModeState> Modes;
static uint64 ModeRevision=0;
static const FName ModeBone(TEXT("__MagnetizationMode"));
float MagnetizationMode(const AProphecyAgent* Agent)
{ const auto* V=Modes.IsEmpty()?nullptr:Modes.Find(Agent);return V?V->Uniform:1.f; }
float MagnetizationMode(const AProphecyAgent* Agent,FName Bone)
{
    const auto* S=Modes.IsEmpty()?nullptr:Modes.Find(Agent);
    if(!S)return 1.f;
    const auto* V=S->Overrides.Find(Bone);return V?*V:S->Uniform;
}
FModeView MagnetizationModes(const AProphecyAgent* Agent)
{
    const auto* S=Modes.IsEmpty()?nullptr:Modes.Find(Agent);
    return S?FModeView{S->Uniform,S->Overrides.IsEmpty()?nullptr:&S->Overrides,S->Revision}:FModeView{};
}
// Only after edits/blend updates, never on an unchanged pose publication.
static void CompactModes(AProphecyAgent& Agent)
{
    auto* S=Modes.Find(&Agent);if(!S)return;
    for(auto It=S->Overrides.CreateIterator();It;++It)if(It.Value()==S->Uniform)It.RemoveCurrent();
    if(!S->Overrides.IsEmpty())
    {
        const auto* Mesh=Agent.GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
        bool First=true,Same=true;float Common=S->Uniform;
        if(Asset)for(const USkeletalBodySetup* B:Asset->SkeletalBodySetups)if(B)
        {
            const float* V=S->Overrides.Find(B->BoneName);const float Value=V?*V:S->Uniform;
            if(First){Common=Value;First=false;}else if(Value!=Common){Same=false;break;}
        }
        if(!First && Same){S->Uniform=Common;S->Overrides.Reset();S->Revision=++ModeRevision;}
    }
    if(S->Overrides.IsEmpty() && S->Uniform==1.f)Modes.Remove(&Agent);
}
static bool Applying=false;
bool IsApplying() { return Applying; }
bool Valid(EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{ return uint8(L)<=uint8(EProphecyLocomotionSelection::Run) && uint8(E)<=uint8(EProphecyEquipmentSelection::Sheathed); }
void Remove(const AProphecyAgent* Agent)
{ Modes.Remove(Agent);States.Remove(Agent); Snapshots.Remove(Agent);SnapshotSpecials.Remove(Agent);ProphecyBlendClock::Remove(Agent);ProphecyClampProfiles::Remove(Agent); }
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
    if (Entry.Kind==EKind::Mode)
    {
        auto& S=Modes.FindOrAdd(&Agent);
        if(Entry.Bone==ModeBone)S.Uniform=Value.Scales.X;
        else S.Overrides.Add(Entry.Bone,Value.Scales.X);
        S.Revision=++ModeRevision;
    }
    else if (Entry.Kind==EKind::Feedback)
        Agent.SetPhysicalFeedbackTolerance(Entry.Bone,Value.Scales.X,Value.Scales.Y);
    else if (Entry.Kind==EKind::Damping)
    {
        if (!ProphecyJointDamping::ApplyValue(&Agent,Entry.Bone,Value.Scales.X)) return;
    }
    else
        Agent.SetBodyMagnetization(Entry.Bone,Value.Enabled,Value.Scales.X,Value.Scales.Y);
    Entry.Applied=Value; Entry.AppliedValid=true;
}
static bool UpdateState(AProphecyAgent& Agent,FAgentState& State,float Walk,bool Drawn,bool Attack,const FVector2f* LegWeights=nullptr)
{
    AdvanceClock(Agent,State);
    const FVector2f Legs=LegWeights ? *LegWeights : FVector2f(Walk,Walk);
    const bool Changed=!State.ValidContext || State.Walk!=Walk || State.Legs!=Legs || State.Drawn!=Drawn || State.Attack!=Attack;
    if (!Changed && !State.Running) return false;
    State.Running=false;
    bool ModeChanged=false;
    for (auto& Entry:State.Entries)
    {
        if (!Changed && !Entry.Running()) continue;
        for (auto& Cell:Entry.Cells) Cell.Sample(State.Clock);
        Publish(Agent,Entry,Entry.Resolve(ProphecyBodyPolicyWalkWeight(Entry.Bone,Walk,Legs),Drawn,Attack));
        ModeChanged|=Entry.Kind==EKind::Mode;
        State.Running|=Entry.Running();
    }
    if(ModeChanged && !State.Entries.ContainsByPredicate([](const FEntry& E){return E.Kind==EKind::Mode && E.Running();}))CompactModes(Agent);
    State.Walk=Walk; State.Legs=Legs; State.Drawn=Drawn; State.Attack=Attack; State.ValidContext=true;
    if (State.Running) ProphecyBlendClock::Ensure(&Agent,ProphecyBlendClock::EKind::Profiles);
    else ProphecyBlendClock::Stop(&Agent,ProphecyBlendClock::EKind::Profiles);
    return true;
}
void Update(AProphecyAgent* Agent)
{
    auto* State=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!State || !Agent || !Agent->GetWorld()) return;
    const bool Attack=Agent->IsSwordAttackActive() && !SnapshotSpecials.Contains(Agent);
    bool Drawn=false; float Walk=1;FVector2f Legs(1,1);
    if (!Attack)
    {
        Drawn=IsValid(Agent->GetHeldSword());
        if (!Agent->GetLocomotionRegionalWeights(Walk,Legs)) { Walk=1;Legs=FVector2f(1,1); }
    }
    const bool Updated=UpdateState(*Agent,*State,FMath::Clamp(Walk,0.f,1.f),Drawn,Attack,&Legs);
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
    if (Universal && Kind!=EKind::Damping && Kind!=EKind::Mode && !IsManaged(&Agent,Bone,Kind))
    {
        if (Duration>0)
            return Kind==EKind::Feedback ? Agent.BlendPhysicalFeedbackTolerance(Bone,Value.X,Value.Y,Duration)
                : Agent.BlendBodyMagnetization(Bone,Value.X,Value.Y,Duration);
        if (Kind==EKind::Feedback) return Agent.SetPhysicalFeedbackTolerance(Bone,Value.X,Value.Y);
        Agent.SetBodyMagnetization(Bone,Enabled,Value.X,Value.Y); return true;
    }
    FValue Initial;
    if(Kind==EKind::Mode) Initial={{MagnetizationMode(&Agent,Bone),MagnetizationMode(&Agent,Bone)},true};
    else if (Kind==EKind::Feedback)
    {
        FProphecyPhysicalFeedbackToleranceSettings S;
        if (!Agent.GetPhysicalFeedbackTolerance(Bone,S)) return false;
        Initial.Scales={S.LinearToleranceCm,S.AngularToleranceDegrees};
    }
    else if (Kind==EKind::Damping)
    {
        float Damping;
        if (!ProphecyJointDamping::Validate(&Agent,Bone) || !ProphecyJointDamping::Get(&Agent,Bone,Damping)) return false;
        Initial.Scales={Damping,Damping};
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
        if (Kind==EKind::Damping)
        {
            float Values[4];
            if (ProphecyJointDamping::GetProfile(&Agent,Bone,Values))
                for (int32 I=0;I<4;++I) Entry->Cells[I].Value={{Values[I],Values[I]},true};
        }
    }
    // Cancel legacy timeline ownership, without cancelling our other context cells.
    {
        TGuardValue<bool> Guard(Applying,true);
        if (Kind==EKind::Feedback) Agent.CancelPhysicalFeedbackToleranceBlend(Bone);
        else if (Kind==EKind::Damping) ProphecyJointDamping::ReleasePolicy(&Agent,Bone);
        else if(Kind!=EKind::Mode) Agent.CancelBodyMagnetizationBlend(Bone);
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
    // Also cover legacy authored attacks that only signal the shared attack state.
    // Normal NN entry has already restored once through AttackRecovery::EnterSpecial.
    if (Agent->IsSwordAttackActive() && !SnapshotSpecials.Contains(Agent)) EnterSpecial(Agent);
    if (Agent->IsSwordAttackActive() && !SnapshotSpecials.Contains(Agent))
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
            float Damping;
            if (ProphecyJointDamping::Get(Agent,Bone,Damping) && Damping!=0
                && !State.Entries.ContainsByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==EKind::Damping; }))
            {
                float Values[4];ProphecyJointDamping::GetProfile(Agent,Bone,Values);
                auto& Entry=State.Entries.AddDefaulted_GetRef();Entry.Bone=Bone;Entry.Kind=EKind::Damping;
                for (int32 I=0;I<4;++I) Entry.Cells[I].Value={{Values[I],Values[I]},true};
                ProphecyJointDamping::ReleasePolicy(Agent,Bone);
            }
        }
        if (auto* Blends=Agent->GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>())
            Blends->MoveBlendsToContext(*Agent);
        State.ValidContext=false;
    }
    Update(Agent);
    if (!Agent->IsSwordAttackActive())
    {
        SnapshotSpecials.Remove(Agent);
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
        Cell.Hold=0;Cell.Duration=Duration; Cell.Begin=State->Clock-Elapsed;
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
        for (auto& Cell:Entry.Cells) { Cell.Sample(State->Clock); Cell.Duration=0;Cell.Hold=0; }
    State->ValidContext=false;
    Update(Agent);
}
// A whole-body immediate setter replaces the selected kind, including its
// attack override. Do not publish the discarded profile during cancellation.
void Discard(AProphecyAgent* Agent,EKind Kind)
{
    if (Applying || States.IsEmpty()) return;
    auto* State=States.Find(Agent);
    if (!State) return;
    State->Entries.RemoveAllSwap([&](const FEntry& Entry) { return Entry.Kind==Kind; });
    State->Running=State->Entries.ContainsByPredicate([](const FEntry& Entry) { return Entry.Running(); });
    if (!State->Running) ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Profiles);
    if (State->Entries.IsEmpty()) States.Remove(Agent);
}

static FEntry Capture(AProphecyAgent& Agent,FName Bone,EKind Kind)
{
    if (const auto* State=States.Find(&Agent))
        if (const auto* Entry=State->Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Bone && X.Kind==Kind; }))
        {
            FEntry Copy=*Entry;
            for (auto& Cell:Copy.Cells) { Cell.Sample(State->Clock); Cell.Duration=0;Cell.Hold=0; }
            Copy.AppliedValid=false;
            return Copy;
        }
    FEntry Entry; Entry.Bone=Bone; Entry.Kind=Kind;
    FValue Value;
    if(Kind==EKind::Mode) Value={{MagnetizationMode(&Agent,Bone),MagnetizationMode(&Agent,Bone)},true};
    else if (Kind==EKind::Magnetization)
    {
        FProphecyBodyMagnetizationSettings S; Agent.GetBodyMagnetizationSettings(Bone,S);
        Value={FVector2f(S.LinearStrengthScale,S.AngularStrengthScale),S.bMagnetizationEnabled};
    }
    else if (Kind==EKind::Damping)
    {
        float Values[4]={};ProphecyJointDamping::GetProfile(&Agent,Bone,Values);
        for (int32 I=0;I<4;++I) Entry.Cells[I].Value={{Values[I],Values[I]},true};
        return Entry;
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
    Saved.Add(Capture(*Agent,ModeBone,EKind::Mode));
    TArray<FName> Bodies;
    if (const auto* Asset=Mesh->GetPhysicsAsset())
        for (const USkeletalBodySetup* Body:Asset->SkeletalBodySetups) if (Body) Bodies.AddUnique(Body->BoneName);
    for (const auto& Pair:Agent->BodyMagnetizationSettings) Bodies.AddUnique(Pair.Key);
    for (FName Bone:Bodies)
    { Saved.Add(Capture(*Agent,Bone,EKind::Magnetization));Saved.Add(Capture(*Agent,Bone,EKind::Mode)); }
    TArray<FName> Bones; Mesh->GetBoneNames(Bones);
    for (FName Bone:Bones)
    {
        FProphecyPhysicalFeedbackToleranceSettings S;
        if (Agent->GetPhysicalFeedbackTolerance(Bone,S)) Saved.Add(Capture(*Agent,Bone,EKind::Feedback));
        float Damping;
        if (ProphecyJointDamping::Get(Agent,Bone,Damping)) Saved.Add(Capture(*Agent,Bone,EKind::Damping));
    }
    if (Saved.IsEmpty()) return false;
    for (auto It=Snapshots.CreateIterator();It;++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    Snapshots.FindOrAdd(Agent).Add(Name,MoveTemp(Saved));
    ProphecyClampProfiles::Save(Agent,Name);
    return true;
}
// Selection: 0 = one bone, 1 = subtree, 2 = every saved bone of the requested kind.
static int32 RestoreSnapshot(AProphecyAgent* Agent,FName Name,EKind Kind,FName Bone,int32 Selection,bool IncludeParent,float Duration,bool AllowOfflineDamping=false,float Hold=0)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || !FMath::IsFinite(Duration) || !FMath::IsFinite(Hold) || Hold<0 || (Selection!=2 && Bone.IsNone())) return 0;
    const auto* AgentSnapshots=Snapshots.Find(Agent);
    const auto* Saved=AgentSnapshots ? AgentSnapshots->Find(Name) : nullptr;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Saved || !Mesh) return 0;
    TArray<const FEntry*> Selected;
    for (const auto& Entry:*Saved)
        if (Entry.Kind==Kind && (Selection==2 || (Entry.Bone==Bone && (Selection==0 || IncludeParent))
            || (Selection==1 && Entry.Bone!=Bone && Mesh->BoneIsChildOf(Entry.Bone,Bone)))) Selected.Add(&Entry);
    if (Selected.IsEmpty()) return 0;
    bool UniformModeRestore=false;
    // Uniform -> uniform uses exactly the original single scalar timeline.
    if(Kind==EKind::Mode && Selection==2 && !MagnetizationModes(Agent).Overrides)
    {
        const FEntry* Base=nullptr;for(const auto* E:Selected)if(E->Bone==ModeBone){Base=E;break;}
        if(Base && !Selected.ContainsByPredicate([&](const FEntry* E){return !(E->Cells[0].Value==Base->Cells[0].Value);}))
        { Selected.Reset();Selected.Add(Base);UniformModeRestore=true; }
    }
    if (Kind==EKind::Damping && !AllowOfflineDamping)
        for (const FEntry* Target:Selected) if (!ProphecyJointDamping::Validate(Agent,Target->Bone)) return 0;
    Update(Agent);
    if(UniformModeRestore)Discard(Agent,EKind::Mode);
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
            else if (Kind==EKind::Damping) ProphecyJointDamping::ReleasePolicy(Agent,Target->Bone);
            else if(Kind!=EKind::Mode) Agent->CancelPhysicalFeedbackToleranceBlend(Target->Bone);
        }
        auto* Entry=State.Entries.FindByPredicate([&](const FEntry& X) { return X.Bone==Target->Bone && X.Kind==Kind; });
        if (!Entry) Entry=&State.Entries.Add_GetRef(Current);
        for (int32 I=0;I<4;++I) Entry->Cells[I].Write(Target->Cells[I].Value,Duration,State.Clock,Hold);
        Entry->AppliedValid=false;
    }
    State.ValidContext=false;
    Update(Agent);
    return Selected.Num();
}
bool RestoreResetSnapshot(AProphecyAgent* Agent,FName Name)
{
    const auto* Saved=Snapshots.Find(Agent);
    if (!Saved || !Saved->Contains(Name)) return false;
    for (EKind Kind:{EKind::Magnetization,EKind::Feedback,EKind::Damping,EKind::Mode})
        RestoreSnapshot(Agent,Name,Kind,NAME_None,2,true,0,true);
    ProphecyClampProfiles::Cancel(Agent);
    ProphecyClampProfiles::Restore(Agent,Name,ProphecyClampProfiles::EMode::All,-1,0);
    return true;
}
bool EnterSpecial(AProphecyAgent* Agent)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    static const FName Slot(TEXT("1"));
    const auto* Saved=Snapshots.Find(Agent);
    if (!Saved || !Saved->Contains(Slot)) { SnapshotSpecials.Remove(Agent);return false; }
    SnapshotSpecials.Add(Agent);
    // Zero-duration restore replaces all four context cells, cancels old per-bone
    // timelines and restores exact clamp flags/leeways across every saved mode.
    return RestoreResetSnapshot(Agent,Slot);
}
void ExitSpecial(const AProphecyAgent* Agent) { SnapshotSpecials.Remove(Agent); }
void DeleteSnapshot(const AProphecyAgent* Agent,FName Name)
{
    ProphecyClampProfiles::Delete(Agent,Name);
    if (auto* Saved=Snapshots.Find(Agent))
    { Saved->Remove(Name);if (Saved->IsEmpty()) Snapshots.Remove(Agent); }
}
}

bool UProphecyPhysicalProfileLibrary::SetMagnetizationMode(AProphecyAgent* Agent,float Mode)
{
    if(!IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(Mode) || Mode<0 || Mode>1)return false;
    ProphecyPhysicalContext::Discard(Agent,ProphecyPhysicalContext::EKind::Mode);
    ProphecyPhysicalContext::Modes.Remove(Agent);
    return ProphecyPhysicalContext::Set(*Agent,ProphecyPhysicalContext::ModeBone,ProphecyPhysicalContext::EKind::Mode,true,{Mode,Mode},0);
}
bool UProphecyPhysicalProfileLibrary::SetBodyMagnetizationMode(AProphecyAgent* Agent,FName Bone,float Mode)
{
    if(!IsValid(Agent) || !FMath::IsFinite(Mode) || Mode<0 || Mode>1)return false;
    const auto* Mesh=Agent->GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
    if(!Asset || Asset->FindBodyIndex(Bone)==INDEX_NONE)return false;
    return ProphecyPhysicalContext::Set(*Agent,Bone,ProphecyPhysicalContext::EKind::Mode,true,{Mode,Mode},0);
}
int32 UProphecyPhysicalProfileLibrary::SetMagnetizationModeBelow(AProphecyAgent* Agent,FName Parent,float Mode,bool Include)
{
    if(!IsValid(Agent) || !FMath::IsFinite(Mode) || Mode<0 || Mode>1)return 0;
    const auto* Mesh=Agent->GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
    if(!Asset || Mesh->GetBoneIndex(Parent)==INDEX_NONE)return 0;
    TArray<FName,TInlineAllocator<32>> Bones;int32 Total=0;
    for(const USkeletalBodySetup* B:Asset->SkeletalBodySetups)if(B)
    { ++Total;if((Include && B->BoneName==Parent) || (B->BoneName!=Parent && Mesh->BoneIsChildOf(B->BoneName,Parent)))Bones.Add(B->BoneName); }
    if(Bones.Num()==Total)return SetMagnetizationMode(Agent,Mode)?Total:0;
    int32 Count=0;for(FName Bone:Bones)Count+=SetBodyMagnetizationMode(Agent,Bone,Mode);return Count;
}
float UProphecyPhysicalProfileLibrary::GetBodyMagnetizationMode(AProphecyAgent* Agent,FName Bone)
{ return ProphecyPhysicalContext::MagnetizationMode(Agent,Bone); }
float UProphecyPhysicalProfileLibrary::GetMagnetizationMode(AProphecyAgent* Agent)
{ return ProphecyPhysicalContext::MagnetizationMode(Agent); }
bool UProphecyPhysicalProfileLibrary::BlendMagnetizationModeToSnapshot(AProphecyAgent* Agent,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Mode,NAME_None,2,true,Duration,false,Hold)>0; }
bool UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationModeToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Mode,Bone,0,true,Duration,false,Hold)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendMagnetizationModeBelowToSnapshot(AProphecyAgent* Agent,FName Parent,bool Include,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Mode,Parent,1,Include,Duration,false,Hold); }
bool UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot(AProphecyAgent* Agent,FName Name)
{ return ProphecyPhysicalContext::SaveSnapshot(Agent,Name); }
bool UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,Bone,0,true,Duration,false,Hold)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationBelowToSnapshot(AProphecyAgent* Agent,FName Bone,bool Include,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,Bone,1,Include,Duration,false,Hold); }
int32 UProphecyPhysicalProfileLibrary::BlendAllBodyMagnetizationToSnapshot(AProphecyAgent* Agent,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Magnetization,NAME_None,2,true,Duration,false,Hold); }
bool UProphecyPhysicalProfileLibrary::BlendPhysicalFeedbackToleranceToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,Bone,0,true,Duration,false,Hold)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendPhysicalFeedbackToleranceBelowToSnapshot(AProphecyAgent* Agent,FName Bone,bool Include,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,Bone,1,Include,Duration,false,Hold); }
int32 UProphecyPhysicalProfileLibrary::BlendAllPhysicalFeedbackTolerancesToSnapshot(AProphecyAgent* Agent,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Feedback,NAME_None,2,true,Duration,false,Hold); }
bool UProphecyPhysicalProfileLibrary::BlendJointAngularDampingToSnapshot(AProphecyAgent* Agent,FName Bone,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Damping,Bone,0,true,Duration,false,Hold)>0; }
int32 UProphecyPhysicalProfileLibrary::BlendJointAngularDampingBelowToSnapshot(AProphecyAgent* Agent,FName Bone,bool Include,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Damping,Bone,1,Include,Duration,false,Hold); }
int32 UProphecyPhysicalProfileLibrary::BlendAllJointAngularDampingToSnapshot(AProphecyAgent* Agent,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Damping,NAME_None,2,true,Duration,false,Hold); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySnapshotHoldTest,"Prophecy.Agent.PhysicalContext.SnapshotHold",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySnapshotHoldTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;
    FCell C;C.Value={{.2f,.4f},false};C.Write({{1,2},true},1,0,1);
    C.Sample(.9);TestTrue(TEXT("Hold preserves exact value and disabled flag"),C.Value.Scales==FVector2f(.2f,.4f) && !C.Value.Enabled);
    C.Sample(1.5);TestTrue(TEXT("Blend begins after hold from effective disabled zero"),C.Value.Scales==FVector2f(.5f,1.f) && C.Value.Enabled);
    C.Sample(2);TestTrue(TEXT("Exact endpoint retires hold and blend"),C.Value.Scales==FVector2f(1,2) && C.Duration==0 && C.Hold==0);
    C.Write({{0,0},true},0,2,1);C.Sample(2.99);TestEqual(TEXT("Zero duration still holds"),C.Value.Scales.X,1.f);
    C.Sample(3);TestEqual(TEXT("Zero duration snaps at hold boundary"),C.Value.Scales.X,0.f);
    C.Write({{1,1},true},1,3,1);C.Write({{.3f,.3f},true},0,3.5);C.Sample(10);
    TestEqual(TEXT("Immediate replacement cancels pending hold"),C.Value.Scales.X,.3f);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDampingProfileMathTest,"Prophecy.Joints.DampingProfileBlend",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyDampingProfileMathTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;
    FEntry Entry;Entry.Kind=EKind::Damping;
    const float Values[]={10,30,100,300};
    for (int32 I=0;I<4;++I) Entry.Cells[I].Value={{Values[I],Values[I]},true};
    TestEqual(TEXT("Checkpoint blending"),Entry.Resolve(.25f,true,false).Scales.X,250.f);
    TestEqual(TEXT("Attack override"),Entry.Resolve(.25f,true,true).Scales.X,0.f);
    const FEntry Saved=Entry;
    for (auto& Cell:Entry.Cells) Cell.Write({{0,0},true},1,0);
    for (auto& Cell:Entry.Cells) Cell.Sample(.5);
    TestEqual(TEXT("Timed damping halfway"),Entry.Resolve(1,false,false).Scales.X,5.f);
    for (int32 I=0;I<4;++I) Entry.Cells[I].Write(Saved.Cells[I].Value,1,.5);
    for (auto& Cell:Entry.Cells) Cell.Sample(1);
    TestEqual(TEXT("Retarget starts at current blend"),Entry.Resolve(1,false,false).Scales.X,7.5f);
    TestEqual(TEXT("Snapshot remains immutable"),Saved.Cells[0].Value.Scales.X,10.f);
    for (auto& Cell:Entry.Cells) Cell.Sample(1.5);
    TestFalse(TEXT("Completed timeline retired"),Entry.Running());
    TestEqual(TEXT("All saved profiles restored"),Entry.Resolve(0,true,false).Scales.X,300.f);
    return true;
}
#include "Misc/ScopeExit.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "ProphecyAttackRecovery.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialSnapshotTest,"Prophecy.Agent.PhysicalContext.SpecialSnapshot1",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySpecialSnapshotTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;
    using Profiles=UProphecyPhysicalProfileLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("World"),World)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT
    {
        Remove(Agent);ProphecyJointDamping::Remove(Agent);ProphecyDefenseControls::Remove(Agent);
        ProphecyAttackRecovery::Remove(Agent);World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
    };
    if (!TestNotNull(TEXT("Agent"),Agent)) return false;
    Agent->bAutoEnsureStandaloneNNManager=false;
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Skeleton"),Mesh)) return false;
    Agent->GetAgentMesh()->SetSkeletalMeshAsset(Mesh);
    auto Mag=[&]() { FProphecyBodyMagnetizationSettings V;Agent->GetBodyMagnetizationSettings(TEXT("head"),V);return V; };
    auto Feedback=[&]() { FProphecyPhysicalFeedbackToleranceSettings V;Agent->GetPhysicalFeedbackTolerance(TEXT("head"),V);return V; };
    Agent->SetBodyMagnetization(TEXT("head"),true,.2f,.4f);
    TestFalse(TEXT("Missing slot is a no-op"),EnterSpecial(Agent));
    TestEqual(TEXT("Missing slot preserves value"),Mag().LinearStrengthScale,.2f);
    Agent->SetBodyMagnetization(TEXT("head"),true,.8f,1.6f,EProphecyLocomotionSelection::Run,EProphecyEquipmentSelection::Drawn);
    Agent->SetBodyMagnetization(TEXT("hand_l"),false,.3f,.7f);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),8,9);
    TestTrue(TEXT("Stage saved damping"),ProphecyJointDamping::ApplyValue(Agent,TEXT("head"),37));
    Agent->SetLocomotionFootClamp(false,6);
    Agent->SetLocomotionCalfClamp(true,4);
    Agent->bOverrideAttackCalfClamp=false;Agent->AttackCalfClampLeewayCm=7;
    for (bool Dodge:{false,true})
        ProphecyDefenseControls::Set(Agent,Dodge,ProphecyDefenseControls::ELimb::Foot,true,Dodge?13:12);
    Profiles::SetMagnetizationMode(Agent,.25f);
    TestTrue(TEXT("Save requested slot 1"),Profiles::SavePhysicalProfileSnapshot(Agent,TEXT("1")));
    Agent->SetBodyMagnetization(TEXT("head"),true,.9f,.9f);
    Agent->SetPhysicalFeedbackTolerance(TEXT("head"),90,90);
    ProphecyJointDamping::ApplyValue(Agent,TEXT("head"),99);
    Profiles::SetMagnetizationMode(Agent,1.f);
    TestTrue(TEXT("Other default snapshot must not be selected"),Profiles::SavePhysicalProfileSnapshot(Agent));
    for (int32 Kind=0;Kind<4;++Kind) // full attack, half attack, Parry, Dodge share entry.
    {
        Agent->SetBodyMagnetization(TEXT("head"),true,0,0);
        Agent->SetBodyMagnetization(TEXT("hand_l"),true,1,1);
        Agent->SetPhysicalFeedbackTolerance(TEXT("head"),0,0);
        ProphecyJointDamping::ApplyValue(Agent,TEXT("head"),3);
        Agent->SetLocomotionFootClamp(true,80);Agent->SetLocomotionCalfClamp(true,80);
        Agent->bOverrideAttackCalfClamp=true;Agent->AttackCalfClampLeewayCm=80;
        for (bool Dodge:{false,true})
            ProphecyDefenseControls::Set(Agent,Dodge,ProphecyDefenseControls::ELimb::Foot,true,80);
        Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),10);
        Profiles::BlendPhysicalFeedbackToleranceToSnapshot(Agent,TEXT("head"),10);
        RestoreSnapshot(Agent,NAME_None,EKind::Damping,TEXT("head"),0,true,10,true);
        ProphecyClampProfiles::Restore(Agent,NAME_None,ProphecyClampProfiles::EMode::All,-1,10);
        Profiles::SetMagnetizationMode(Agent,.9f);
        TestTrue(TEXT("Mode return with hold schedules"),Profiles::BlendMagnetizationModeToSnapshot(Agent,10,NAME_None,5));
        ProphecyAttackRecovery::EnterSpecial(Agent,Kind==1);
        TestEqual(TEXT("Special entry immediately restores saved mode despite hold"),Profiles::GetMagnetizationMode(Agent),.25f);
        if (Kind<2) Agent->NotifySwordAttackState(true);
        TestEqual(TEXT("Slot 1 magnetization wins over blend and attack default"),Mag().LinearStrengthScale,.2f);
        TestEqual(TEXT("Saved tolerance wins over attack default"),Feedback().AngularToleranceDegrees,9.f);
        float Damping=0;ProphecyJointDamping::Get(Agent,TEXT("head"),Damping);
        TestEqual(TEXT("Saved damping wins over attack zero"),Damping,37.f);
        FProphecyBodyMagnetizationSettings Hand;Agent->GetBodyMagnetizationSettings(TEXT("hand_l"),Hand);
        TestFalse(TEXT("Saved disabled flag restored"),Hand.bMagnetizationEnabled);
        TestEqual(TEXT("Saved disabled scale restored"),Hand.LinearStrengthScale,.3f);
        TestFalse(TEXT("Saved clamp disabled flag restored"),Agent->bLocomotionFootClamp);
        TestEqual(TEXT("Saved clamp remembered leeway restored"),Agent->LocomotionFootClampLeewayCm,6.f);
        TestEqual(TEXT("Saved calf leeway restored"),Agent->LocomotionCalfClampLeewayCm,4.f);
        TestFalse(TEXT("Attack clamp inheritance restored"),Agent->bOverrideAttackCalfClamp);
        TestEqual(TEXT("Attack clamp remembered allowance restored"),Agent->AttackCalfClampLeewayCm,7.f);
        for (bool Dodge:{false,true})
            TestEqual(TEXT("Defense clamp restored"),ProphecyDefenseControls::Find(Agent,Dodge)->Foot.LeewayCm,Dodge?13.f:12.f);
        TestFalse(TEXT("Clamp return retired"),ProphecyClampProfiles::Active.Contains(Agent));
        if (const auto* State=States.Find(Agent))
        {
            TestFalse(TEXT("Profile timelines retired"),State->Running);
            for (const auto& Entry:State->Entries) TestFalse(TEXT("No hidden cell timeline survives"),Entry.Running());
        }
        for (int32 Tick=0;Tick<65;++Tick)
        { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60.f);Update(Agent); }
        TestEqual(TEXT("Old mode hold cannot overwrite special snapshot"),Profiles::GetMagnetizationMode(Agent),.25f);
        TestEqual(TEXT("Old blend cannot overwrite restored values"),Mag().LinearStrengthScale,.2f);
        if (auto* State=States.Find(Agent))
        {
            UpdateState(*Agent,*State,0,true,false);
            TestEqual(TEXT("All four saved context cells restored"),Mag().LinearStrengthScale,.8f);
            State->ValidContext=false;Update(Agent);
        }
        if (Kind<2) Agent->NotifySwordAttackState(false);
        ProphecyAttackRecovery::NotifyEnded(Agent,NAME_None,Kind==1,false,
            Kind<2?EProphecyAgentState::Attacking:Kind==2?EProphecyAgentState::Parrying:EProphecyAgentState::Dodging);
        TestFalse(TEXT("All special exits release override suppression"),SnapshotSpecials.Contains(Agent));
        TestEqual(TEXT("Special exit does not revive old blend"),Mag().LinearStrengthScale,.2f);
    }
    Profiles::SetMagnetizationMode(Agent,1);
    TestFalse(TEXT("Invalid hold cannot mutate mode"),Profiles::BlendMagnetizationModeToSnapshot(Agent,1,TEXT("1"),-1));
    TestFalse(TEXT("Invalid mode rejected"),Profiles::SetMagnetizationMode(Agent,2));
    TestTrue(TEXT("Mode blend scheduled"),Profiles::BlendMagnetizationModeToSnapshot(Agent,1,TEXT("1"),.5f));
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120.f);Update(Agent);}
    TestEqual(TEXT("Mode holds for 30 authored ticks"),Profiles::GetMagnetizationMode(Agent),1.f);
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/30.f);Update(Agent);}
    TestEqual(TEXT("Mode halfway after hold"),Profiles::GetMagnetizationMode(Agent),.625f);
    Profiles::SavePhysicalProfileSnapshot(Agent,TEXT("ModeMid"));
    for(int I=0;I<30;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60.f);Update(Agent);}
    TestEqual(TEXT("Mode reaches saved endpoint"),Profiles::GetMagnetizationMode(Agent),.25f);
    Profiles::BlendMagnetizationModeToSnapshot(Agent,0,TEXT("ModeMid"));
    TestEqual(TEXT("Snapshot captures current mode, not pending destination"),Profiles::GetMagnetizationMode(Agent),.625f);
    // Legacy authored attack entry also snaps even without the NN entry helper.
    Agent->NotifySwordAttackState(false);
    Agent->SetBodyMagnetization(TEXT("head"),true,.5f,.5f);
    Agent->NotifySwordAttackState(true);
    TestEqual(TEXT("Legacy attack entry restores slot 1"),Mag().LinearStrengthScale,.2f);
    Agent->NotifySwordAttackState(false);
    return true;
}
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
    TestTrue(TEXT("Snapshot includes inbound joint damping"),Snapshots.FindChecked(Agent).FindChecked(TEXT("Baseline"))
        .ContainsByPredicate([](const FEntry& X){return X.Bone==TEXT("head") && X.Kind==EKind::Damping;}));
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
    // Death-style all-body disable must supersede both kinds of active restore,
    // including the attack override, without cancelling unrelated tolerance work.
    for (bool Attack:{false,true})
    {
        Agent->SetAllBodyMagnetization(true,1,1);
        Profiles::SavePhysicalProfileSnapshot(Agent,TEXT("DeathBaseline"));
        Agent->SetBodyMagnetization(TEXT("head"),true,0,0);
        Agent->SetPhysicalFeedbackTolerance(TEXT("head"),0,0);
        Agent->BlendBodyMagnetization(TEXT("hand_l"),1,1,1);
        Profiles::BlendBodyMagnetizationToSnapshot(Agent,TEXT("head"),1,TEXT("DeathBaseline"));
        Profiles::BlendPhysicalFeedbackToleranceToSnapshot(Agent,TEXT("head"),1,TEXT("DeathBaseline"));
        Agent->NotifySwordAttackState(Attack);
        Agent->SetAllBodyMagnetization(false,1,1);
        TestFalse(TEXT("All-body disable wins immediately during snapshot/attack"),Read().bMagnetizationEnabled);
        const auto* Remaining=States.Find(Agent);
        TestTrue(TEXT("No magnetization profile survives all-body setter"),!Remaining || !Remaining->Entries.ContainsByPredicate(
            [](const FEntry& Entry) { return Entry.Kind==EKind::Magnetization; }));
        TestTrue(TEXT("Tolerance restore remains active"),Remaining && Remaining->Entries.ContainsByPredicate(
            [](const FEntry& Entry) { return Entry.Kind==EKind::Feedback && Entry.Running(); }));
        for (int32 Tick=0;Tick<70;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60.f);
            Update(Agent);
        }
        Agent->NotifySwordAttackState(false);
        TestFalse(TEXT("Snapshot completion and attack exit cannot revive magnetization"),Read().bMagnetizationEnabled);
        FProphecyBodyMagnetizationSettings Hand;Agent->GetBodyMagnetizationSettings(TEXT("hand_l"),Hand);
        TestFalse(TEXT("Ordinary blend cannot revive magnetization either"),Hand.bMagnetizationEnabled);
        TestEqual(TEXT("Unrelated tolerance finishes normally"),Feedback().LinearToleranceCm,8.f);
        Agent->SetAllBodyMagnetization(true,1,1);
        TestTrue(TEXT("Explicit all-body enable still works"),Read().bMagnetizationEnabled);
    }
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBoneModesTest,"Prophecy.Agent.PhysicalContext.BoneModes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyBoneModesTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;using P=UProphecyPhysicalProfileLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!TestNotNull(TEXT("World"),World))return false;
    if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* A=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT{Remove(A);World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);};
    if(!TestNotNull(TEXT("Agent"),A))return false;
    A->bAutoEnsureStandaloneNNManager=false;
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if(!TestNotNull(TEXT("Mesh"),Mesh))return false;
    A->GetAgentMesh()->SetSkeletalMeshAsset(Mesh);
    auto Value=[&](const TCHAR* B){return P::GetBodyMagnetizationMode(A,B);};
    auto Advance=[&](int N){for(int I=0;I<N;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/60);Update(A);}};
    TestTrue(TEXT("Uniform set"),P::SetMagnetizationMode(A,.2f));
    TestNull(TEXT("Uniform has no body lookup"),MagnetizationModes(A).Overrides);
    TestFalse(TEXT("Invalid body rejected"),P::SetBodyMagnetizationMode(A,TEXT("not_a_bone"),0));
    TestEqual(TEXT("Right arm subtree has three bodies"),P::SetMagnetizationModeBelow(A,TEXT("upperarm_r"),0,true),3);
    TestEqual(TEXT("Right hand follows selected subtree"),Value(TEXT("hand_r")),0.f);
    TestEqual(TEXT("Left hand isolated"),Value(TEXT("hand_l")),.2f);
    TestEqual(TEXT("Exclude parent selects forearm and hand"),P::SetMagnetizationModeBelow(A,TEXT("upperarm_r"),.8f,false),2);
    TestEqual(TEXT("Parent excluded"),Value(TEXT("upperarm_r")),0.f);
    P::SetBodyMagnetizationMode(A,TEXT("hand_r"),.6f);
    TestEqual(TEXT("Single body leaves forearm alone"),Value(TEXT("lowerarm_r")),.8f);
    TestTrue(TEXT("Save mixed snapshot"),P::SavePhysicalProfileSnapshot(A,TEXT("1")));
    P::SetMagnetizationMode(A,1);
    TestNull(TEXT("All setter removes sparse overrides"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Below restore count"),P::BlendMagnetizationModeBelowToSnapshot(A,TEXT("upperarm_r"),true,1,TEXT("1"),.5f),3);
    Advance(30);TestEqual(TEXT("Body modes hold unchanged"),Value(TEXT("hand_r")),1.f);
    Advance(30);TestEqual(TEXT("Hand halfway after hold"),Value(TEXT("hand_r")),.8f);
    TestEqual(TEXT("Unselected arm unchanged"),Value(TEXT("hand_l")),1.f);
    P::SetMagnetizationMode(A,0);Advance(90);
    TestEqual(TEXT("All setter cancels pending subtree returns"),Value(TEXT("hand_r")),0.f);
    TestNull(TEXT("Cancelled uniform has no body lookup"),MagnetizationModes(A).Overrides);
    P::BlendMagnetizationModeToSnapshot(A,0,TEXT("1"));
    TestEqual(TEXT("Full restore keeps mixed hand"),Value(TEXT("hand_r")),.6f);
    TestEqual(TEXT("Full restore keeps mixed forearm"),Value(TEXT("lowerarm_r")),.8f);
    TestEqual(TEXT("Full restore restores baseline elsewhere"),Value(TEXT("hand_l")),.2f);
    P::SetMagnetizationMode(A,1);P::BlendMagnetizationModeToSnapshot(A,1,TEXT("1"));Advance(30);
    TestEqual(TEXT("Mixed return midpoint"),Value(TEXT("hand_r")),.8f);
    const float Pin=Value(TEXT("upperarm_l"));P::SetBodyMagnetizationMode(A,TEXT("upperarm_l"),Pin);
    Advance(30);TestEqual(TEXT("Fixed body survives moving fallback even when equal at assignment"),Value(TEXT("upperarm_l")),Pin);
    TestEqual(TEXT("Other bodies finish their return"),Value(TEXT("hand_l")),.2f);
    P::SetMagnetizationMode(A,.25f);P::SavePhysicalProfileSnapshot(A,TEXT("Uniform"));
    P::SetMagnetizationMode(A,.75f);P::BlendMagnetizationModeToSnapshot(A,1,TEXT("Uniform"));Advance(30);
    TestNull(TEXT("Uniform snapshot blend keeps scalar path"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Uniform midpoint"),Value(TEXT("head")),.5f);
    P::SetBodyMagnetizationMode(A,TEXT("head"),.5f);Advance(30);
    TestEqual(TEXT("Body setter pins scalar-blend midpoint"),Value(TEXT("head")),.5f);
    TestEqual(TEXT("Uniform fallback finishes independently"),Value(TEXT("hand_l")),.25f);
    P::BlendBodyMagnetizationModeToSnapshot(A,TEXT("head"),0,TEXT("Uniform"));
    TestNull(TEXT("Restoring last differing bone collapses to uniform"),MagnetizationModes(A).Overrides);
    P::SetMagnetizationModeBelow(A,TEXT("pelvis"),.3f,true);
    TestNull(TEXT("Whole pelvis subtree uses uniform path"),MagnetizationModes(A).Overrides);
    TestEqual(TEXT("Whole subtree configured mode"),P::GetMagnetizationMode(A),.3f);
    TestTrue(TEXT("Special restores mixed snapshot1"),EnterSpecial(A));
    TestEqual(TEXT("Special restores right hand"),Value(TEXT("hand_r")),.6f);
    TestEqual(TEXT("Special restores left hand"),Value(TEXT("hand_l")),.2f);
    return !HasAnyErrors();
}
#endif
