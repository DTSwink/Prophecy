// Included by PhysicalContext: separate maps preserve retained Live Coding layouts.
#include "ProphecyClampProfiles.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
namespace ProphecyClampProfiles
{
using FValue=ProphecyDefenseControls::FClamp;
struct FEntry { EMode Mode; ELimb Limb; FValue Value; };
struct FBlend
{
    FEntry Target;
    float Start=0,End=0;
    double Elapsed=0,Duration=0;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,TMap<FName,TArray<FEntry>>> Snapshots;
static TMap<TWeakObjectPtr<AProphecyAgent>,TArray<FBlend>> Active;
static FDelegateHandle TickHandle,CleanupHandle;
static const FValue& Select(const ProphecyDefenseControls::FSettings& S,ELimb L)
{ return L==ELimb::Foot?S.Foot:L==ELimb::Calf?S.Calf:L==ELimb::Hand?S.Hand:S.Forearm; }
static FValue Read(const AProphecyAgent& A,EMode M,ELimb L)
{
    if (M==EMode::Parry || M==EMode::Dodge)
    { const auto* S=ProphecyDefenseControls::Find(&A,M==EMode::Dodge);return S?Select(*S,L):FValue{}; }
    if (M==EMode::Attack)
    {
        if (L==ELimb::Foot) return {A.bOverrideAttackFootClamp,A.bAttackFootClamp,A.AttackFootClampLeewayCm};
        if (L==ELimb::Calf) return {A.bOverrideAttackCalfClamp,A.bAttackCalfClamp,A.AttackCalfClampLeewayCm};
        return {true,A.bAttackHandClamp,A.AttackHandClampLeewayCm};
    }
    if (L==ELimb::Foot) return {A.bOverrideLocomotionFootClamp,A.bLocomotionFootClamp,A.LocomotionFootClampLeewayCm};
    if (L==ELimb::Calf) return {A.bOverrideLocomotionCalfClamp,A.bLocomotionCalfClamp,A.LocomotionCalfClampLeewayCm};
    if (L==ELimb::Hand) return {A.bOverrideLocomotionHandClamp,A.bLocomotionHandClamp,A.LocomotionHandClampLeewayCm};
    return {true,A.bLocomotionForearmClamp,A.LocomotionForearmClampLeewayCm};
}
static FValue Effective(const AProphecyAgent& A,EMode M,ELimb L,FValue V)
{
    if (V.bOverride) return V;
    if (M==EMode::Dodge || M==EMode::Parry)
    {
        if (M==EMode::Parry && (L==ELimb::Foot || L==ELimb::Calf))
            return Effective(A,EMode::Locomotion,L,Read(A,EMode::Locomotion,L));
        return {true,L==ELimb::Hand,0};
    }
    if (A.GetWorld()) for (TActorIterator<AProphecyNNLocomotionManager> It(A.GetWorld());It;++It)
        if (It->ResolveAgent(A.GetAgentHandle())==&A)
            return {true,L==ELimb::Foot?It->bClampFoot:L==ELimb::Calf?It->bClampCalf:It->bClampHand,0};
    return {true,L==ELimb::Hand,0};
}
static void Write(AProphecyAgent& A,const FEntry& E)
{
    const auto V=E.Value;const auto L=E.Limb;
    if (E.Mode==EMode::Parry || E.Mode==EMode::Dodge)
    { ProphecyDefenseControls::RestoreClamp(&A,E.Mode==EMode::Dodge,L,V);return; }
    if (E.Mode==EMode::Attack)
    {
        if (L==ELimb::Foot) { A.bOverrideAttackFootClamp=V.bOverride;A.bAttackFootClamp=V.bEnabled;A.AttackFootClampLeewayCm=V.LeewayCm; }
        else if (L==ELimb::Calf) { A.bOverrideAttackCalfClamp=V.bOverride;A.bAttackCalfClamp=V.bEnabled;A.AttackCalfClampLeewayCm=V.LeewayCm; }
        else { A.bAttackHandClamp=V.bEnabled;A.AttackHandClampLeewayCm=V.LeewayCm; }
        return;
    }
    if (L==ELimb::Foot) { A.bOverrideLocomotionFootClamp=V.bOverride;A.bLocomotionFootClamp=V.bEnabled;A.LocomotionFootClampLeewayCm=V.LeewayCm; }
    else if (L==ELimb::Calf) { A.bOverrideLocomotionCalfClamp=V.bOverride;A.bLocomotionCalfClamp=V.bEnabled;A.LocomotionCalfClampLeewayCm=V.LeewayCm; }
    else if (L==ELimb::Hand) { A.bOverrideLocomotionHandClamp=V.bOverride;A.bLocomotionHandClamp=V.bEnabled;A.LocomotionHandClampLeewayCm=V.LeewayCm; }
    else { A.bLocomotionForearmClamp=V.bEnabled;A.LocomotionForearmClampLeewayCm=V.LeewayCm; }
}
static void Refresh();
static void Advance(UWorld* World,ELevelTick TickType,float Dt)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || Dt<=0) return;
    for (auto It=Active.CreateIterator();It;++It)
    {
        auto* A=It.Key().Get();
        if (!A || A->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (A->GetWorld()!=World) continue;
        auto& Blends=It.Value();
        for (int32 I=Blends.Num()-1;I>=0;--I)
        {
            auto& B=Blends[I];B.Elapsed+=1./60.;
            if (B.Elapsed+1.e-9>=B.Duration) { Write(*A,B.Target);Blends.RemoveAtSwap(I,1,EAllowShrinking::No); }
            else
            {
                const float T=float(B.Elapsed/B.Duration);
                Write(*A,{B.Target.Mode,B.Target.Limb,{true,true,FMath::Lerp(B.Start,B.End,T*T*(3-2*T))}});
            }
        }
        if (Blends.IsEmpty()) It.RemoveCurrent();
    }
    Refresh();
}
static void Refresh()
{
    if (Active.IsEmpty()) { FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset(); }
    else if (!TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Advance);
    if (Active.IsEmpty() && Snapshots.IsEmpty()) { FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset(); }
    else if (!CleanupHandle.IsValid()) CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for (auto It=Active.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent();
        for (auto It=Snapshots.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent();
        Refresh();
    });
}
void Cancel(const AProphecyAgent* A,EMode M,int32 L)
{
    if (Active.IsEmpty()) return;
    if (auto* B=Active.Find(const_cast<AProphecyAgent*>(A)))
    {
        B->RemoveAllSwap([&](const FBlend& X){return (M==EMode::All || X.Target.Mode==M) && (L<0 || int32(X.Target.Limb)==L);});
        if (B->IsEmpty()) Active.Remove(const_cast<AProphecyAgent*>(A));
    }
    Refresh();
}
void Remove(const AProphecyAgent* A) { Cancel(A);Snapshots.Remove(A);Refresh(); }
void Delete(const AProphecyAgent* A,FName Name)
{ if (auto* S=Snapshots.Find(A)) { S->Remove(Name);if (S->IsEmpty()) Snapshots.Remove(A); } Refresh(); }
void Save(AProphecyAgent* A,FName Name)
{
    TArray<FEntry> Saved;
    for (auto M:{EMode::Locomotion,EMode::Attack,EMode::Parry,EMode::Dodge})
        for (auto L:{ELimb::Foot,ELimb::Calf,ELimb::Hand,ELimb::Forearm})
            if (!(M==EMode::Attack && L==ELimb::Forearm)) Saved.Add({M,L,Read(*A,M,L)});
    Snapshots.FindOrAdd(A).Add(Name,MoveTemp(Saved));Refresh();
}
int32 Restore(AProphecyAgent* A,FName Name,EMode Mode,int32 Limb,float Duration)
{
    if (!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld()
        || A->GetWorld()->bIsTearingDown || !FMath::IsFinite(Duration) || uint8(Mode)>uint8(EMode::Dodge)) return 0;
    const auto* Names=Snapshots.Find(A);const auto* Saved=Names?Names->Find(Name):nullptr;
    if (!Saved) return 0;
    TArray<FBlend> Requests;
    for (const auto& E:*Saved)
    {
        if ((Mode!=EMode::All && Mode!=E.Mode) || (Limb>=0 && Limb!=int32(E.Limb))) continue;
        const auto S=Effective(*A,E.Mode,E.Limb,Read(*A,E.Mode,E.Limb));
        const auto T=Effective(*A,E.Mode,E.Limb,E.Value);
        const float Off=FMath::Max(1000.f,FMath::Max(S.LeewayCm,T.LeewayCm));
        const float Start=S.bEnabled?S.LeewayCm:Off,End=T.bEnabled?T.LeewayCm:Off;
        Requests.Add({E,Start,End,0,(!S.bEnabled && !T.bEnabled) || Start==End?0:double(FMath::Max(0.f,Duration))});
    }
    for (const auto& B:Requests)
    {
        Cancel(A,B.Target.Mode,int32(B.Target.Limb));
        if (B.Duration<=0) Write(*A,B.Target);
        else { Write(*A,{B.Target.Mode,B.Target.Limb,{true,true,B.Start}});Active.FindOrAdd(A).Add(B); }
    }
    Refresh();return Requests.Num();
}
FString Debug(const AProphecyAgent* A,FName Bone)
{
    if (!A) return {};
    const bool Hand=Bone==TEXT("hand_l") || Bone==TEXT("hand_r"),Foot=Bone==TEXT("foot_l") || Bone==TEXT("foot_r");
    if (!Hand && !Foot) return {};
    auto Text=[&](ELimb L)
    {
        const auto V=Effective(*A,EMode::Locomotion,L,Read(*A,EMode::Locomotion,L));
        return V.bEnabled?FString::Printf(TEXT("%.2f"),V.LeewayCm):FString(TEXT("off"));
    };
    return FString::Printf(TEXT(" / Clamp=%s:%s %s:%s"),Hand?TEXT("Hand"):TEXT("Foot"),*Text(Hand?ELimb::Hand:ELimb::Foot),
        Hand?TEXT("Forearm"):TEXT("Calf"),*Text(Hand?ELimb::Forearm:ELimb::Calf));
}
}
bool UProphecyClampProfileLibrary::BlendClampToSnapshot(AProphecyAgent* A,EProphecyClampType Clamp,float Duration,FName Name,EProphecyClampProfileMode Mode)
{
    using ELimb=ProphecyClampProfiles::ELimb;
    ELimb Limb;
    switch (Clamp)
    {
    case EProphecyClampType::Calf: Limb=ELimb::Calf;break;
    case EProphecyClampType::Forearm: Limb=ELimb::Forearm;break;
    case EProphecyClampType::Hand: Limb=ELimb::Hand;break;
    case EProphecyClampType::Foot: Limb=ELimb::Foot;break;
    default:return false;
    }
    return ProphecyClampProfiles::Restore(A,Name,Mode,int32(Limb),Duration)>0;
}
int32 UProphecyClampProfileLibrary::BlendAllClampsToSnapshot(AProphecyAgent* A,float Duration,FName Name,EProphecyClampProfileMode Mode)
{ return ProphecyClampProfiles::Restore(A,Name,Mode,-1,Duration); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyClampSnapshotTest,"Prophecy.PhysicalProfiles.ClampSnapshots",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyClampSnapshotTest::RunTest(const FString&)
{
    using namespace ProphecyClampProfiles;
    using Lib=UProphecyClampProfileLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("World"),W)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
    auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT
    {
        ProphecyPhysicalContext::Remove(A);ProphecyDefenseControls::Remove(A);
        W->DestroyWorld(false);if (GEngine) GEngine->DestroyWorldContext(W);
    };
    if (!TestNotNull(TEXT("Agent"),A)) return false;
    A->bAutoEnsureStandaloneNNManager=false;
    auto* Asset=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Skeleton"),Asset)) return false;
    A->GetAgentMesh()->SetSkeletalMeshAsset(Asset);
    A->SetLocomotionFootClamp(true,3);A->SetLocomotionCalfClamp(true,4);
    A->SetLocomotionHandClamp(true,5);A->SetLocomotionForearmClamp(false,7);
    A->SetAttackHandClamp(false,11);
    ProphecyDefenseControls::Set(A,false,ELimb::Foot,true,12);
    ProphecyDefenseControls::Set(A,true,ELimb::Hand,true,13);
    TestTrue(TEXT("Existing save captures clamps"),UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot(A,TEXT("ClampBase")));
    A->SetLocomotionFootClamp(false,0);A->SetLocomotionCalfClamp(true,20);A->SetLocomotionHandClamp(true,55);
    TestFalse(TEXT("Missing snapshot is nonmutating"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Foot,1,TEXT("Missing")));
    TestTrue(TEXT("Foot selects only the shared foot setting"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Foot,1,TEXT("ClampBase"),EMode::Locomotion));
    TestEqual(TEXT("Foot does not change calf"),A->LocomotionCalfClampLeewayCm,20.f);
    TestTrue(TEXT("Calf can blend independently"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Calf,1,TEXT("ClampBase"),EMode::Locomotion));
    for (int32 I=0;I<30;++I) Advance(W,LEVELTICK_All,I%2?1.f/120.f:1.f/30.f);
    TestEqual(TEXT("Off-to-on half blend uses large allowance"),A->LocomotionFootClampLeewayCm,501.5f);
    TestEqual(TEXT("Calf half blend"),A->LocomotionCalfClampLeewayCm,12.f);
    TestEqual(TEXT("Foot restore does not affect hands"),A->LocomotionHandClampLeewayCm,55.f);
    Advance(W,LEVELTICK_ViewportsOnly,1.f/60.f);
    TestEqual(TEXT("Non-game tick does not advance"),A->LocomotionCalfClampLeewayCm,12.f);
    TestTrue(TEXT("Save mid-blend"),UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot(A,TEXT("Mid")));
    for (int32 I=0;I<30;++I) Advance(W,LEVELTICK_All,1.f/240.f);
    TestEqual(TEXT("Exactly 60 ticks reaches foot baseline"),A->LocomotionFootClampLeewayCm,3.f);
    TestEqual(TEXT("Calf endpoint"),A->LocomotionCalfClampLeewayCm,4.f);
    TestTrue(TEXT("Finished callback removed"),Active.IsEmpty() && !TickHandle.IsValid());
    Lib::BlendClampToSnapshot(A,EProphecyClampType::Foot,0,TEXT("Mid"),EMode::Locomotion);
    TestEqual(TEXT("Snapshot stores current blend value"),A->LocomotionFootClampLeewayCm,501.5f);
    Lib::BlendClampToSnapshot(A,EProphecyClampType::Foot,1,TEXT("ClampBase"),EMode::Locomotion);
    A->SetLocomotionCalfClamp(true,20);
    Lib::BlendClampToSnapshot(A,EProphecyClampType::Calf,1,TEXT("ClampBase"),EMode::Locomotion);
    A->SetLocomotionFootClamp(true,23);
    for (int32 I=0;I<60;++I) Advance(W,LEVELTICK_All,1.f/60.f);
    TestEqual(TEXT("Direct setter cancels only foot return"),A->LocomotionFootClampLeewayCm,23.f);
    TestEqual(TEXT("Uncancelled calf return finishes"),A->LocomotionCalfClampLeewayCm,4.f);
    TestTrue(TEXT("Forearm restores independently"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Forearm,0,TEXT("ClampBase"),EMode::Locomotion));
    TestEqual(TEXT("Forearm does not restore hand"),A->LocomotionHandClampLeewayCm,55.f);
    TestFalse(TEXT("Absent attack forearm is not invented"),Lib::BlendClampToSnapshot(A,EProphecyClampType::Forearm,0,TEXT("ClampBase"),EMode::Attack));
    A->SetAttackHandClamp(true,0);ProphecyDefenseControls::Set(A,true,ELimb::Hand,false,0);
    TestEqual(TEXT("All restores 15 distinct settings, not double-counted sides"),Lib::BlendAllClampsToSnapshot(A,0,TEXT("ClampBase")),15);
    TestTrue(TEXT("Attack disabled flag and remembered allowance restored"),!A->bAttackHandClamp && A->AttackHandClampLeewayCm==11);
    TestTrue(TEXT("Dodge restored independently"),ProphecyDefenseControls::Find(A,true)->Hand.bEnabled && ProphecyDefenseControls::Find(A,true)->Hand.LeewayCm==13);
    TestTrue(TEXT("Parry inherited override state preserved"),!ProphecyDefenseControls::Find(A,false)->Calf.bOverride);
    TestTrue(TEXT("Only endpoints get clamp print"),Debug(A,TEXT("head")).IsEmpty() && Debug(A,TEXT("calf_l")).IsEmpty());
    TestEqual(TEXT("Hands print locomotion only"),Debug(A,TEXT("hand_l")),FString(TEXT(" / Clamp=Hand:5.00 Forearm:off")));
    TestEqual(TEXT("Feet print both settings without units"),Debug(A,TEXT("foot_r")),FString(TEXT(" / Clamp=Foot:3.00 Calf:4.00")));
    TestTrue(TEXT("No ticking work remains"),Active.IsEmpty() && !TickHandle.IsValid());
    return true;
}
#endif
