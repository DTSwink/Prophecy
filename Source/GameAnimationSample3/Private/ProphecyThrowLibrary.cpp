#include "ProphecyThrowLibrary.h"
#include "ProphecyThrowRuntime.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyGetUp.h"
#include "ProphecySwordHolsterPose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"

namespace ProphecyThrow
{
struct FActive
{
    FModel Model;
    FProphecyThrowPhysics Physics;
    TWeakObjectPtr<UProphecyThrowAction> Action;
    FVector Target=FVector::ZeroVector,LocalTarget=FVector::ZeroVector;
    FTransform Space=FTransform::Identity;
    double Frame=0,AppliedFrame=0,SourceTime=-DBL_MAX;
    bool Charging=true,Automatic=false,ReleaseRequested=false,Released=false,PendingRelease=false,Finished=false;
    FProphecyThrowState State;
    FPose Previous,Current;
};
static TMap<TWeakObjectPtr<AProphecyAgent>,TUniquePtr<FActive>> ActiveThrows;
static FDelegateHandle TickHandle,PostHandle,CleanupHandle;
static void Refresh();
static FTransform Space(AProphecyAgent* A)
{
    return (A->bManualNNPoseApplication?A->GetAgentMesh()->GetRelativeTransform():A->GetAuthoredMeshRelativeTransform())*A->GetActorTransform();
}
static void Describe(FActive& S)
{
    S.State.Frame=float(S.Frame);S.State.ThrowPercent=float(S.Model.Amount*100);S.State.ReleaseFrame=float(S.Model.Release);
    S.State.Phase=S.Finished?EProphecyThrowPhase::Finished:S.Released?EProphecyThrowPhase::Released:S.Charging?EProphecyThrowPhase::Charging:EProphecyThrowPhase::Throwing;
    const auto P=S.Model.Sample(S.Frame);S.State.HandWorld=ToUnreal(P[10])*S.Space;
    if(!S.Released)S.State.WeaponWorld=ToUnreal(S.Model.Held(P))*S.Space;
}
static void Release(FActive& S)
{
    FVector V,W;const auto Held=S.Model.Launch(V,W);
    S.State.WeaponWorld=ToUnreal(Held)*S.Space;
    S.State.LinearVelocityCmPerSecond=S.Physics.VelocityRotation.RotateVector(S.Space.TransformVectorNoScale(ToUnrealPoint(V)))*S.Physics.VelocityMultiplier;
    // Axial vectors acquire the determinant sign under the Y/Z reflection.
    S.State.AngularVelocityRadiansPerSecond=S.Space.TransformVectorNoScale(-ToUnrealPoint(W)*.01);
    if(S.Physics.bOverrideTwist){const FVector Axis=S.Space.TransformVectorNoScale(ToUnrealPoint(Held.GetRotation().RotateVector(S.Model.Profile->Axis))*.01);S.State.AngularVelocityRadiansPerSecond=-Axis*(S.Physics.TwistDegreesPerFrame*UE_DOUBLE_PI/3);}
    S.State.ReleaseRemainderFrames=float(FMath::Clamp(S.Frame-S.Model.Release,0.,1.));S.Released=true;S.PendingRelease=true;
}
static void Trigger(FActive& S)
{
    const auto& C=*S.Model.Profile;const bool Small=C.Id==TEXT("small-throw");
    if(!Small&&S.Frame<C.Armed){S.ReleaseRequested=true;return;}
    const double Amount=Small?(C.Armed>0?FMath::Clamp(S.Frame/C.Armed,0.,1.):1.):1.;
    S.Model.Prepare(C,Amount,FromUnrealPoint(S.Space.InverseTransformPosition(S.Target)));S.Charging=false;S.ReleaseRequested=false;
}
static void Tick(UWorld* World,ELevelTick Type,float DeltaSeconds)
{
    if(!World||World->IsPaused()||Type!=LEVELTICK_All||DeltaSeconds<=0)return;
    for(auto It=ActiveThrows.CreateIterator();It;++It){auto* A=It.Key().Get();if(!A||A->IsActorBeingDestroyed()){It.RemoveCurrent();continue;}if(A->GetWorld()!=World)continue;
        auto& S=*It.Value();S.Space=Space(A);
        const FVector LocalTarget=FromUnrealPoint(S.Space.InverseTransformPosition(S.Target));
        if(!S.Released&&S.Model.Profile->Aim&&!LocalTarget.Equals(S.LocalTarget,1.e-8)){S.LocalTarget=LocalTarget;S.Model.Prepare(*S.Model.Profile,S.Model.Amount,LocalTarget);}
        if(S.Charging){S.Frame=FMath::Min(S.Frame+1,S.Model.Profile->Armed);if(S.ReleaseRequested&&S.Frame>=S.Model.Profile->Armed)Trigger(S);}
        else S.Frame+=1;
        if(!S.Charging&&!S.Released&&S.Frame>=S.Model.Release)Release(S);
        S.Finished=S.Frame>=S.Model.Profile->End;Describe(S);
    }
    Refresh();
}
static void Post(UWorld* World,ELevelTick Type,float)
{
    if(!World||World->IsPaused()||Type!=LEVELTICK_All)return;
    // Dispatch after iteration: Blueprint callbacks may start/cancel throws.
    struct FEvent{TWeakObjectPtr<UProphecyThrowAction> Action;FProphecyThrowState State;};TArray<FEvent> Events;
    for(auto It=ActiveThrows.CreateIterator();It;++It){auto* A=It.Key().Get();if(!A||A->GetWorld()!=World)continue;auto& S=*It.Value();
        if(S.PendingRelease){auto Event=S.State;Event.Phase=EProphecyThrowPhase::Released;Events.Add({S.Action,Event});S.PendingRelease=false;}
        if(S.Finished){Events.Add({S.Action,S.State});It.RemoveCurrent();}}
    Refresh();for(auto& E:Events)if(auto* Action=E.Action.Get())Action->Notify(E.State);
}
static void Refresh()
{
    if(ActiveThrows.IsEmpty()){FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();FWorldDelegates::OnWorldPostActorTick.Remove(PostHandle);PostHandle.Reset();FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();return;}
    if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    if(!PostHandle.IsValid())PostHandle=FWorldDelegates::OnWorldPostActorTick.AddStatic(&Post);
    if(!CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){for(auto It=ActiveThrows.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();Refresh();});
}
bool AnyActive(){return !ActiveThrows.IsEmpty();}
bool Active(const AProphecyAgent* A){return !ActiveThrows.IsEmpty()&&ActiveThrows.Contains(const_cast<AProphecyAgent*>(A));}
bool Apply(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,const FTransform& ComponentWorld,double SourceTime)
{
    auto* Found=ActiveThrows.IsEmpty()?nullptr:ActiveThrows.Find(A);if(!Found)return false;auto& S=**Found;S.Space=ComponentWorld;
    if(S.SourceTime!=SourceTime||S.AppliedFrame!=S.Frame){const auto Sample=S.Model.Sample(S.Frame);S.Previous=S.Current;S.Current.SetNum(Names.Num());
        for(int J=0;J<Names.Num();++J){const int K=S.Model.Profile->Names.IndexOfByKey(Names[J]);if(K==INDEX_NONE)return false;S.Current[J]=ToUnreal(Sample[K]);}
        if(S.Previous.Num()!=Names.Num())S.Previous=S.Current;S.SourceTime=SourceTime;S.AppliedFrame=S.Frame;}
    for(int J=0;J<Names.Num();++J){Previous[J]=S.Previous[J];Current[J]=S.Current[J];Local[J]=Parents[J]<0?Current[J]:Current[J].GetRelativeTransform(Current[Parents[J]]);}return true;
}
static bool Start(AProphecyAgent* A,EProphecyThrow Kind,const FVector& Target,const FProphecyThrowPhysics& Physics,bool Auto,float Percent,UProphecyThrowAction* Action,FString& Error)
{
    if(!IsValid(A)||!A->GetWorld()||!A->GetWorld()->IsGameWorld()||!A->GetAgentMesh()||!A->HasValidAgentHandle()){Error=TEXT("A live Prophecy agent registered with the NN manager is required");return false;}
    if(Active(A)){Error=TEXT("This agent already has an active throw");return false;}
    FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;ProphecySwordHolsterPose::FStatus Holster;
    if(A->GetNNAttackState(Attack,Half,Armed,Hit,Frame)||A->IsNNAnimationLayerActive()||ProphecyReach::Active(A)||ProphecyGetUp::IsActive(A)||(ProphecySwordHolsterPose::Status(A,Holster)&&!Holster.Finished)){Error=TEXT("Finish the agent's current attack, animation layer, reach, get-up or sword action before throwing");return false;}
    if(Target.ContainsNaN()||!FMath::IsFinite(Percent)||!FMath::IsFinite(Physics.VelocityMultiplier)||Physics.VelocityMultiplier<0||Physics.VelocityRotation.ContainsNaN()||!FMath::IsFinite(Physics.TwistDegreesPerFrame)){Error=TEXT("Throw controls must be finite; velocity multiplier must be nonnegative");return false;}
    const auto* C=Profile(Kind==EProphecyThrow::SmallThrow,Error);if(!C)return false;
    auto S=MakeUnique<FActive>();S->Space=Space(A);S->Target=Target;S->Physics=Physics;S->Automatic=Auto;S->Charging=!Auto;S->Action=Action;
    const double Amount=Kind==EProphecyThrow::BigThrow||!Auto?1.:Percent<0?C->Amount:FMath::Clamp(double(Percent)*.01,0.,1.);
    S->LocalTarget=FromUnrealPoint(S->Space.InverseTransformPosition(Target));S->Model.Prepare(*C,Amount,S->LocalTarget);S->State.ObjectKind=FName(*C->Kind);S->State.WeaponScale=C->Scale;Describe(*S);ActiveThrows.Add(A,MoveTemp(S));Refresh();return true;
}
}
UProphecyThrowAction* UProphecyThrowAction::BeginLabThrow(AProphecyAgent* A,EProphecyThrow Throw,FVector TargetWorld,const FProphecyThrowPhysics& InPhysics)
{auto* Task=NewObject<UProphecyThrowAction>();Task->Agent=A;Task->Kind=Throw;Task->Target=TargetWorld;Task->Physics=InPhysics;if(IsValid(A))Task->RegisterWithGameInstance(A);return Task;}
UProphecyThrowAction* UProphecyThrowAction::PlayLabThrow(AProphecyAgent* A,EProphecyThrow Throw,FVector TargetWorld,const FProphecyThrowPhysics& InPhysics,float ThrowPercent)
{auto* Task=BeginLabThrow(A,Throw,TargetWorld,InPhysics);Task->Automatic=true;Task->Percent=ThrowPercent;return Task;}
void UProphecyThrowAction::Activate()
{FString Error;if(!ProphecyThrow::Start(Agent.Get(),Kind,Target,Physics,Automatic,Percent,this,Error)){FProphecyThrowState S;S.Error=Error;Notify(S);}}
void UProphecyThrowAction::Notify(const FProphecyThrowState& S)
{switch(S.Phase){case EProphecyThrowPhase::Released:Released.Broadcast(S);return;case EProphecyThrowPhase::Finished:Completed.Broadcast(S);break;case EProphecyThrowPhase::Cancelled:Cancelled.Broadcast(S);break;default:Failed.Broadcast(S);break;}SetReadyToDestroy();}
bool UProphecyThrowLibrary::ReleaseLabThrow(AProphecyAgent* A)
{auto* P=ProphecyThrow::ActiveThrows.Find(A);if(!P||!(*P)->Charging)return false;ProphecyThrow::Trigger(**P);ProphecyThrow::Describe(**P);return true;}
bool UProphecyThrowLibrary::CancelLabThrow(AProphecyAgent* A)
{TUniquePtr<ProphecyThrow::FActive> S;if(!ProphecyThrow::ActiveThrows.RemoveAndCopyValue(A,S))return false;ProphecyThrow::Refresh();S->State.Phase=EProphecyThrowPhase::Cancelled;if(auto* Action=S->Action.Get())Action->Notify(S->State);return true;}
bool UProphecyThrowLibrary::GetLabThrowState(AProphecyAgent* A,FProphecyThrowState& State)
{const auto* S=ProphecyThrow::ActiveThrows.Find(A);if(!S){State={};State.Error=TEXT("No active throw");return false;}State=(*S)->State;return true;}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyThrowClockTest,"Prophecy.Throws.ControlsAndClock",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyThrowClockTest::RunTest(const FString&)
{
    using namespace ProphecyThrow;
    FString Error;const auto* C=Profile(true,Error);if(!C){AddError(Error);return false;}
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;
    if(!A){AddError(TEXT("Cannot create isolated throw fixture"));return false;}
    FModel Full;Full.Prepare(*C,1,C->Target);const int Before=ActiveThrows.Num();
    for(const float FPS:{5.f,30.f,60.f,120.f}){
        auto S=MakeUnique<FActive>();S->Space=Space(A);S->Target=S->Space.TransformPosition(ToUnrealPoint(C->Target));S->Model.Prepare(*C,1,C->Target);
        ActiveThrows.Add(A,MoveTemp(S));Refresh();
        for(int I=0;I<6;++I)Tick(World,LEVELTICK_All,1/FPS);
        auto& Live=*ActiveThrows.FindChecked(A);
        TestEqual(TEXT("One authored frame per unpaused tick"),Live.Frame,6.);
        const auto Prefix=Live.Model.Sample(6),Expected=Full.Sample(6);
        for(int J=0;J<Prefix.Num();++J)TestTrue(TEXT("Charge prefix does not know future release"),Prefix[J].Equals(Expected[J],1.e-9));
        Tick(World,LEVELTICK_All,0);TestEqual(TEXT("Zero-delta tick does not spend a frame"),Live.Frame,6.);
        TestTrue(TEXT("Release accepts live charge"),UProphecyThrowLibrary::ReleaseLabThrow(A));
        TestTrue(TEXT("Charge comes from actual trigger-up frame"),FMath::IsNearlyEqual(Live.Model.Amount,6./C->Armed,1.e-12));
        TestFalse(TEXT("Duplicate release rejected"),UProphecyThrowLibrary::ReleaseLabThrow(A));
        int Releases=0;
        while(ActiveThrows.Contains(A)){
            Tick(World,LEVELTICK_All,1/FPS);
            if(auto* P=ActiveThrows.Find(A)){auto& State=**P;if(State.PendingRelease){++Releases;TestTrue(TEXT("Fractional release remainder is bounded"),State.State.ReleaseRemainderFrames>=0&&State.State.ReleaseRemainderFrames<1);}}
            Post(World,LEVELTICK_All,1/FPS);
        }
        TestEqual(TEXT("Exactly one release per throw"),Releases,1);TestEqual(TEXT("Completed state retires"),ActiveThrows.Num(),Before);
    }
    auto S=MakeUnique<FActive>();S->Model.Prepare(*C,1,C->Target);ActiveThrows.Add(A,MoveTemp(S));Refresh();
    TestTrue(TEXT("Cancel active throw"),UProphecyThrowLibrary::CancelLabThrow(A));TestFalse(TEXT("Cancelled throw is inactive"),Active(A));
    if(Before==0)TestFalse(TEXT("No recurring callback after completion/cancel"),TickHandle.IsValid()||PostHandle.IsValid()||CleanupHandle.IsValid());
    World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
