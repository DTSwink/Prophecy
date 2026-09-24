#include "ProphecyKickFootLeewayLibrary.h"
#include "ProphecyKickFootLeeway.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltBody.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif

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
// Pose-only return: never changes the physical joint allowance or retained layouts.
static TMap<TWeakObjectPtr<AProphecyAgent>,FActive> PoseReturns;
#if WITH_EDITOR
static TAutoConsoleVariable<int32> SharedCalfRecovery(TEXT("Prophecy.Debug.SharedCalfRecovery"),1,
    TEXT("Diagnostic: enable non-kick calf-length handoff; read only on special exit."));
#endif
// Keep retained Live Coding structures unchanged. Centimetres, signed shortening
// or lengthening captured once at the actual visible kick exit.
struct FLengthReturn { FVector2D Upper,Rest,Delta; int32 PoseId=INDEX_NONE; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FLengthReturn> LengthReturns;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static bool IsKick(FName Attack) { return Attack==TEXT("kickL") || Attack==TEXT("kickR"); }
float Current(const AProphecyAgent* Agent)
{
    const auto* State=Active.IsEmpty() ? nullptr : Active.Find(const_cast<AProphecyAgent*>(Agent));
    return State ? State->Value : 0.f;
}
float ReturningLengthDeltaCm(const AProphecyAgent* Agent,int32 Side)
{
    const auto* Length=LengthReturns.IsEmpty() ? nullptr : LengthReturns.Find(Agent);
    const auto* State=Length ? PoseReturns.Find(const_cast<AProphecyAgent*>(Agent)) : nullptr;
    if (Length && !State) State=Active.Find(const_cast<AProphecyAgent*>(Agent));
    return State && State->Returning && State->From>0 && (Side==0 || Side==1)
        ? float(Length->Delta[Side])*State->Value/State->From : 0.f;
}
void CancelPoseRecovery(const AProphecyAgent* Agent)
{
    if (const auto* Length=LengthReturns.Find(Agent))
        ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,FVector2D::ZeroVector,FVector2D::ZeroVector);
    LengthReturns.Remove(Agent);
    if (PoseReturns.Remove(const_cast<AProphecyAgent*>(Agent))) Refresh();
}
static void PublishLengths(const AProphecyAgent* Agent)
{
    if (const auto* Length=LengthReturns.Find(Agent))
        ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,Length->Upper,
            ProphecyLegChainDebug::IsEnabled(Agent)
                ? Length->Rest+FVector2D(ReturningLengthDeltaCm(Agent,0),ReturningLengthDeltaCm(Agent,1))
                : FVector2D::ZeroVector);
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
    CancelPoseRecovery(Agent);
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
    CancelPoseRecovery(Agent);
    const auto* Config=Settings.Find(Agent);
    if (!IsKick(Attack) || !Config || Config->Leeway==0) return;

    FString Error;
    if (!Apply(Agent,Config->Leeway,Error))
    { UE_LOG(LogTemp,Warning,TEXT("Kick foot leeway could not start: %s"),*Error); return; }
    FActive State; State.Value=Config->Leeway;
    Active.Add(Agent,State); Refresh();
}
static bool CaptureLengths(AProphecyAgent* Agent)
{
    // Capture distance, not axial extension: the current checkpoint also permits
    // compression. Never change its attack output or project an attack foot.
    const auto* Mesh=Agent->GetPoseReferenceMesh();
    if (Mesh && Mesh->GetSkeletalMeshAsset())
    {
        const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
        FLengthReturn Length;float Interval;bool Interpolate;
        bool Valid=Agent->GetNNPoseDataSource(Length.PoseId,Interval,Interpolate);
        for (int32 Side=0;Side<2 && Valid;++Side)
        {
            const FName FootName=Side==0 ? TEXT("foot_l") : TEXT("foot_r");
            const FName CalfName=Side==0 ? TEXT("calf_l") : TEXT("calf_r");
            const int32 FootIndex=Ref.FindBoneIndex(FootName),CalfIndex=Ref.FindBoneIndex(CalfName);
            FTransform Previous,Future,Foot,Calf;float Alpha;
            Valid=FootIndex!=INDEX_NONE && CalfIndex!=INDEX_NONE
                && Agent->GetAuthoredBodyWorldTarget(FootName,Previous,Future,Foot,Alpha)
                && Agent->GetAuthoredBodyWorldTarget(CalfName,Previous,Future,Calf,Alpha);
            if (!Valid) break;
            Length.Upper[Side]=Ref.GetRefBonePose()[CalfIndex].GetTranslation().Size();
            Length.Rest[Side]=Ref.GetRefBonePose()[FootIndex].GetTranslation().Size();
            Length.Delta[Side]=(Foot.GetLocation()-Calf.GetLocation()).Size()-Length.Rest[Side];
        }
        if (Valid && !Length.Delta.IsNearlyZero(.0001))
        { LengthReturns.Add(Agent,Length); return true; }
    }
    return false;
}
static void StartPoseReturn(AProphecyAgent* Agent,float Duration)
{
    if (Duration<=0) return;
    FActive Pose; Pose.Returning=true; Pose.From=Pose.Value=1;
    Pose.Total=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Duration)*60.,9.e15)-1.e-5)));
    PoseReturns.Add(Agent,Pose);
    PublishLengths(Agent);Refresh();
}
void End(AProphecyAgent* Agent,bool RecoverPose)
{
    auto* State=Active.Find(Agent);
    const auto* Config=Settings.Find(Agent);
    if (!State || State->Returning)
    {
        // Other full specials use the same configured return duration (default
        // 60 ticks), independently of whether a kick joint allowance is active.
#if WITH_EDITOR
        if (SharedCalfRecovery.GetValueOnGameThread()==0) return;
#endif
        if (!RecoverPose) return;
        CancelPoseRecovery(Agent);
        const float Duration=Config ? Config->Duration : FSettings{}.Duration;
        if (Duration>0 && CaptureLengths(Agent)) StartPoseReturn(Agent,Duration);
        return;
    }
    // Preserve the existing kick episode and its physical/pose shared clock.
    if (!Config || Config->Duration==0) { Cancel(Agent); return; }
    if (RecoverPose) CaptureLengths(Agent);
    State->Returning=true; State->From=State->Value; State->Ticks=0;
    State->Total=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Config->Duration)*60.,9.e15)-1.e-5)));
    PublishLengths(Agent);
    Refresh();
}
static void Tick(UWorld* World,ELevelTick Type,float Dt)
{
    if (!World || World->IsPaused() || Type!=LEVELTICK_All || Dt<=0) return;
    for (auto It=Active.CreateIterator();It;++It)
    {
        auto* Agent=It.Key().Get(); auto& State=It.Value();
        if (!Agent || Agent->IsActorBeingDestroyed())
        {
            if (const auto* Length=LengthReturns.Find(It.Key()))
                ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,FVector2D::ZeroVector,FVector2D::ZeroVector);
            LengthReturns.Remove(It.Key());It.RemoveCurrent(); continue;
        }
        if (Agent->GetWorld()!=World || !State.Returning) continue;
        ++State.Ticks; State.Value=State.Sample();
        FString Error;
        if (!Apply(Agent,State.Value,Error))
        {
            UE_LOG(LogTemp,Warning,TEXT("Kick foot leeway return stopped: %s"),*Error);
            Apply(Agent,0,Error);CancelPoseRecovery(Agent);It.RemoveCurrent(); continue;
        }
        PublishLengths(Agent);
        if (State.Ticks>=State.Total)
        {
            if (!PoseReturns.Contains(Agent)) CancelPoseRecovery(Agent);
            It.RemoveCurrent();
        }
    }
    for (auto It=PoseReturns.CreateIterator();It;++It)
    {
        auto* Agent=It.Key().Get();auto& State=It.Value();
        const bool Valid=Agent && !Agent->IsActorBeingDestroyed();
        if (Valid && Agent->GetWorld()!=World) continue;
        if (Valid) { ++State.Ticks;State.Value=State.Sample();PublishLengths(Agent); }
        if (!Valid || State.Ticks>=State.Total)
        {
            if (const auto* Length=LengthReturns.Find(It.Key()))
                ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,FVector2D::ZeroVector,FVector2D::ZeroVector);
            LengthReturns.Remove(It.Key());It.RemoveCurrent();
        }
    }
    Refresh();
}
static void Refresh()
{
    bool NeedsTick=!PoseReturns.IsEmpty();
    for (const auto& Pair:Active) NeedsTick|=Pair.Value.Returning;
    if (NeedsTick && !TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    else if (!NeedsTick && TickHandle.IsValid()) { FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle); TickHandle.Reset(); }
    if ((!Settings.IsEmpty() || !Active.IsEmpty() || !PoseReturns.IsEmpty()) && !CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Active.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==World)
            {
                if (const auto* Length=LengthReturns.Find(It.Key()))
                    ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,FVector2D::ZeroVector,FVector2D::ZeroVector);
                LengthReturns.Remove(It.Key());It.RemoveCurrent();
            }
            for (auto It=Settings.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=PoseReturns.CreateIterator();It;++It) if (!It.Key().IsValid() || It.Key()->GetWorld()==World)
            {
                if (const auto* Length=LengthReturns.Find(It.Key()))
                    ProphecyNNPresentation::SetRecoveryCalfLengths(Length->PoseId,FVector2D::ZeroVector,FVector2D::ZeroVector);
                LengthReturns.Remove(It.Key());It.RemoveCurrent();
            }
            Refresh(); // Native rig teardown owns the temporary constraints.
        });
    else if (Settings.IsEmpty() && Active.IsEmpty() && PoseReturns.IsEmpty() && CleanupHandle.IsValid())
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
    LengthReturns.Add(Agent,{FVector2D(40,40),FVector2D(42,42),FVector2D(5,-3),-917});
    Tick(World,LEVELTICK_All,1.f/120);
    TestTrue(TEXT("No hold tick"),Current(Agent)<10);
    TestTrue(TEXT("Signed per-foot length return shares existing clock"),ReturningLengthDeltaCm(Agent,0)<5
        && ReturningLengthDeltaCm(Agent,0)>4.99 && ReturningLengthDeltaCm(Agent,1)<-2.99);
    Begin(Agent,TEXT("kickR"));
    TestTrue(TEXT("New kick cancels pose return without modifying attack output"),LengthReturns.IsEmpty());
    TestEqual(TEXT("Next kick immediately interrupts return"),Current(Agent),10.f);
    TestFalse(TEXT("Next kick retires return timer"),TickHandle.IsValid());
    for (float Dt:{1.f/30,1.f/60,1.f/120})
    {
        ProphecyKickFootLeeway::End(Agent);
        LengthReturns.Add(Agent,{FVector2D(40,40),FVector2D(42,42),FVector2D(5,-3),-917});
        for (int I=0;I<60;++I)
        {
            Tick(World,LEVELTICK_All,Dt);
            if (I==29) TestTrue(TEXT("Length halfway at thirty ticks at every FPS"),
                FMath::IsNearlyEqual(ReturningLengthDeltaCm(Agent,0),2.5f)
                && FMath::IsNearlyEqual(ReturningLengthDeltaCm(Agent,1),-1.5f));
        }
        TestEqual(TEXT("60 ticks independent of frame delta"),Current(Agent),0.f);
        TestTrue(TEXT("Completed length return retires all pose state"),LengthReturns.IsEmpty());
        TestFalse(TEXT("Completed return removes timer"),TickHandle.IsValid());
        Begin(Agent,TEXT("kickL"));
    }
    Cancel(Agent); TestEqual(TEXT("Reset closes joints"),Current(Agent),0.f);
    TestTrue(TEXT("Reset retains configured future kicks"),Settings.Contains(Agent));
    Remove(Agent); TestFalse(TEXT("Cleanup leaves no timer"),TickHandle.IsValid());
    for (float Dt:{1.f/30,1.f/60,1.f/120})
    {
        // Signed lengths measured at the reported non-kick exit. Pose recovery
        // must neither open physical joints nor retain work after completion.
        LengthReturns.Add(Agent,{FVector2D(40,40),FVector2D(42.5633,42.5633),FVector2D(2.6754,-2.1974),-917});
        StartPoseReturn(Agent,1.f);
        TestEqual(TEXT("Non-kick leaves physical leeway at zero"),Current(Agent),0.f);
        TestTrue(TEXT("Non-kick entry retains outgoing extension"),FMath::IsNearlyEqual(ReturningLengthDeltaCm(Agent,0),2.6754f));
        Tick(World,LEVELTICK_All,Dt);
        TestTrue(TEXT("1495 does not instantly close 2.675cm gap"),ReturningLengthDeltaCm(Agent,0)>2.67f);
        for (int I=1;I<30;++I) Tick(World,LEVELTICK_All,Dt);
        TestTrue(TEXT("Signed pose return halfway at thirty ticks"),
            FMath::IsNearlyEqual(ReturningLengthDeltaCm(Agent,0),1.3377f)
            && FMath::IsNearlyEqual(ReturningLengthDeltaCm(Agent,1),-1.0987f));
        for (int I=30;I<60;++I) Tick(World,LEVELTICK_All,Dt);
        TestTrue(TEXT("Non-kick completion removes length and clock"),LengthReturns.IsEmpty() && PoseReturns.IsEmpty() && !TickHandle.IsValid());
        TestFalse(TEXT("Completion removes presentation override"),ProphecyNNPresentation::HasRecoveryCalfLengths(-917));
    }
    LengthReturns.Add(Agent,{FVector2D(40,40),FVector2D(42,42),FVector2D(3,-2),-917});
    StartPoseReturn(Agent,1.f);Begin(Agent,TEXT("jabR"));
    TestTrue(TEXT("New non-kick retires pose-only return"),LengthReturns.IsEmpty() && PoseReturns.IsEmpty() && !TickHandle.IsValid());
    LengthReturns.Add(Agent,{FVector2D(40,40),FVector2D(42,42),FVector2D(3,-2),-917});
    StartPoseReturn(Agent,1.f);Cancel(Agent);
    TestTrue(TEXT("Reset retires pose-only return"),LengthReturns.IsEmpty() && PoseReturns.IsEmpty() && !TickHandle.IsValid());
    World->DestroyWorld(false); return true;
}
#endif
