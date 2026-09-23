#include "ProphecyKickFootLeewayLibrary.h"
#include "ProphecyKickFootLeeway.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltBody.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"

namespace ProphecyKickFootLeeway
{
struct FSettings { float Leeway=0,Duration=1; };
struct FActive
{
    float Value=0,From=0;
    uint64 Ticks=0,Total=0;
    bool Returning=false;
    float Sample() const
    {
        if (Total==0 || Ticks>=Total) return 0;
        const double A=double(Ticks)/double(Total);
        return From*float(1.-A*A*(3.-2.*A));
    }
};
static TMap<TWeakObjectPtr<AProphecyAgent>,FSettings> Settings;
static TMap<TWeakObjectPtr<AProphecyAgent>,FActive> Active;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static bool IsKick(FName Attack) { return Attack==TEXT("kickL") || Attack==TEXT("kickR"); }
float Current(const AProphecyAgent* Agent)
{
    const auto* State=Active.IsEmpty() ? nullptr : Active.Find(const_cast<AProphecyAgent*>(Agent));
    return State ? State->Value : 0.f;
}
static bool Apply(AProphecyAgent* Agent,float Value,FString& Error)
{
    auto* Character=Agent ? Agent->GetJoltCharacterComponent() : nullptr;
    FProphecyJoltBodyHandle Handle;
    const bool HasRig=Character && Character->GetRigIdentityBody(Handle);
    if (!HasRig) return true;
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return false;
    const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    FVector Axes[2],References[2];
    const FName Feet[]={TEXT("foot_l"),TEXT("foot_r")},Calves[]={TEXT("calf_l"),TEXT("calf_r")};
    for (int Side=0;Side<2;++Side)
    {
        const int32 Bone=Ref.FindBoneIndex(Feet[Side]);
        if (Bone==INDEX_NONE || Ref.GetParentIndex(Bone)==INDEX_NONE || Ref.GetBoneName(Ref.GetParentIndex(Bone))!=Calves[Side])
        { Error=TEXT("Foot leeway requires each foot to be parented to its calf."); return false; }
        References[Side]=Ref.GetRefBonePose()[Bone].GetTranslation();
        Axes[Side]=References[Side].GetSafeNormal();
    }
    auto* Class=FindObject<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltFootJointLibrary"));
    UObject* Library=Class ? Class->GetDefaultObject() : nullptr;
    UFunction* Function=Library ? Library->FindFunction(TEXT("SetFootExtension")) : nullptr;
    if (!Function) { Error=TEXT("Jolt foot-extension bridge is not loaded."); return false; }
    struct FParams
    {
        UObject* WorldContext; FGuid Lifetime; int32 Slot; int64 Generation;
        float Leeway; FVector Left,Right; FString Error; bool Result=false;
    };
    FParams P{Agent,Handle.WorldLifetime,Handle.Slot,int64(Handle.Generation),Value,Axes[0],Axes[1],FString(),false};
    Library->ProcessEvent(Function,&P); Error=MoveTemp(P.Error);
    return P.Result;
}
bool Reapply(AProphecyAgent* Agent,FString& Error)
{
    const float Value=Current(Agent);
    return Value==0 || Apply(Agent,Value,Error);
}
void Cancel(AProphecyAgent* Agent)
{
    if (Active.Contains(Agent))
    {
        FString Error;
        if (!Apply(Agent,0,Error)) UE_LOG(LogTemp,Warning,TEXT("Foot leeway reset: %s"),*Error);
        Active.Remove(Agent); Refresh();
    }
}
void Remove(AProphecyAgent* Agent) { Cancel(Agent); Settings.Remove(Agent); Refresh(); }
void Begin(AProphecyAgent* Agent,FName Attack)
{
    const auto* Config=Settings.Find(Agent);
    if (!IsKick(Attack) || !Config || Config->Leeway==0) return;

    FString Error;
    if (!Apply(Agent,Config->Leeway,Error))
    { UE_LOG(LogTemp,Warning,TEXT("Kick foot leeway could not start: %s"),*Error); return; }
    FActive State; State.Value=Config->Leeway;
    Active.Add(Agent,State); Refresh();
}
void End(AProphecyAgent* Agent)
{
    auto* State=Active.Find(Agent);
    if (!State || State->Returning) return;
    const auto* Config=Settings.Find(Agent);
    if (!Config || Config->Duration==0) { Cancel(Agent); return; }
    State->Returning=true; State->From=State->Value; State->Ticks=0;
    State->Total=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Config->Duration)*60.,9.e15)-1.e-5)));
    Refresh();
}
static void Tick(UWorld* World,ELevelTick Type,float Dt)
{
    if (!World || World->IsPaused() || Type!=LEVELTICK_All || Dt<=0) return;
    for (auto It=Active.CreateIterator();It;++It)
    {
        auto* Agent=It.Key().Get(); auto& State=It.Value();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent(); continue; }
        if (Agent->GetWorld()!=World || !State.Returning) continue;
        ++State.Ticks; State.Value=State.Sample();
        FString Error;
        if (!Apply(Agent,State.Value,Error))
        {
            UE_LOG(LogTemp,Warning,TEXT("Kick foot leeway return stopped: %s"),*Error);
            Apply(Agent,0,Error); It.RemoveCurrent(); continue;
        }
        if (State.Ticks>=State.Total) { It.RemoveCurrent(); }
    }
    Refresh();
}
static void Refresh()
{
    bool NeedsTick=false;
    for (const auto& Pair:Active) NeedsTick|=Pair.Value.Returning;
    if (NeedsTick && !TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    else if (!NeedsTick && TickHandle.IsValid()) { FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle); TickHandle.Reset(); }
    if ((!Settings.IsEmpty() || !Active.IsEmpty()) && !CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Active.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==World)
            { It.RemoveCurrent(); }
            for (auto It=Settings.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            Refresh(); // Native rig teardown owns the temporary constraints.
        });
    else if (Settings.IsEmpty() && Active.IsEmpty() && CleanupHandle.IsValid())
    { FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle); CleanupHandle.Reset(); }
}
}

bool UProphecyKickFootLeewayLibrary::SetKickFootJointLeeway(AProphecyAgent* Agent,float LeewayCm,float ReturnDurationSeconds)
{
    using namespace ProphecyKickFootLeeway;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || Agent->GetWorld()->bIsTearingDown || !FMath::IsFinite(LeewayCm) || LeewayCm<0
        || !FMath::IsFinite(ReturnDurationSeconds) || ReturnDurationSeconds<0) return false;
    if (LeewayCm==0) { Remove(Agent); return true; }
    Settings.Add(Agent,FSettings{LeewayCm,ReturnDurationSeconds});
    FName Attack; bool Half,Armed,Hit; int32 Frame;
    if (Agent->GetNNAttackState(Attack,Half,Armed,Hit,Frame) && IsKick(Attack)) Begin(Agent,Attack);
    Refresh(); return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FKickFootLeewayTest,"Prophecy.Joints.KickFootLeeway",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FKickFootLeewayTest::RunTest(const FString&)
{
    using namespace ProphecyKickFootLeeway;
    FActive A; A.From=10; A.Total=60;
    TestEqual(TEXT("No hold: starts returning on first tick"),(++A.Ticks,A.Sample())<10,true);
    A.Ticks=30; TestEqual(TEXT("Halfway after 30 ticks"),A.Sample(),5.f);
    A.Ticks=60; TestEqual(TEXT("Exactly zero after 60 ticks"),A.Sample(),0.f);
    A.Total=0; TestEqual(TEXT("Zero duration immediate"),A.Sample(),0.f);
    TestTrue(TEXT("Only kick families qualify"),IsKick(TEXT("kickL")) && IsKick(TEXT("kickR")) && !IsKick(TEXT("hookL")));
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Isolated lifecycle world"),World)) return false;
    AProphecyAgent* Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Isolated agent"),Agent)) { World->DestroyWorld(false); return false; }
    Settings.Add(Agent,FSettings{10,1}); Begin(Agent,TEXT("kickL"));
    TestEqual(TEXT("Kick immediately applies allowance"),Current(Agent),10.f);
    TestFalse(TEXT("No timer while kick is active"),TickHandle.IsValid());
    ProphecyKickFootLeeway::End(Agent);
    Tick(World,LEVELTICK_All,1.f/120);
    TestTrue(TEXT("No hold tick"),Current(Agent)<10);
    Begin(Agent,TEXT("kickR"));
    TestEqual(TEXT("Next kick immediately interrupts return"),Current(Agent),10.f);
    TestFalse(TEXT("Next kick retires return timer"),TickHandle.IsValid());
    for (float Dt:{1.f/30,1.f/60,1.f/120})
    {
        ProphecyKickFootLeeway::End(Agent); for (int I=0;I<60;++I) Tick(World,LEVELTICK_All,Dt);
        TestEqual(TEXT("60 ticks independent of frame delta"),Current(Agent),0.f);
        TestFalse(TEXT("Completed return removes timer"),TickHandle.IsValid());
        Begin(Agent,TEXT("kickL"));
    }
    Cancel(Agent); TestEqual(TEXT("Reset closes joints"),Current(Agent),0.f);
    TestTrue(TEXT("Reset retains configured future kicks"),Settings.Contains(Agent));
    Remove(Agent); TestFalse(TEXT("Cleanup leaves no timer"),TickHandle.IsValid());
    World->DestroyWorld(false); return true;
}
#endif
