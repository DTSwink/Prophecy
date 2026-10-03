#include "ProphecyForearmStretch.h"
#include "ProphecyAttackWristLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltFootJointLibrary.h"
#include "Misc/ScopeExit.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "PhysicsEngine/BodyInstance.h"

namespace ProphecyForearmStretch
{
static const FName Hands[]={TEXT("hand_l"),TEXT("hand_r")},Elbows[]={TEXT("lowerarm_l"),TEXT("lowerarm_r")};
struct FState
{
    FVector2D Rest,Delta=FVector2D::ZeroVector,PhysicalDelta=FVector2D::ZeroVector;
    FVector Axes[2];
    uint64 Tick=0,Total=0;
    int32 PoseId=INDEX_NONE;
    bool Returning=false;
    double Weight() const {return Total?1.-FMath::Min(double(Tick)/double(Total),1.):0.;}
    FVector2D Lengths() const {return Rest+Delta*Weight();}
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Settings,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
// Only returning agents are visited by the finite game-tick callback.
static TSet<TWeakObjectPtr<const AProphecyAgent>> Returning;
struct FChaosJoint
{
    TWeakObjectPtr<UPhysicsConstraintComponent> Extra;
    FConstraintInstance* Original=nullptr;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,TArray<FChaosJoint>> Chaos;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static bool Valid(const AProphecyAgent* A)
{return IsInGameThread() && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetWorld() && !A->GetWorld()->bIsTearingDown;}
bool OwnsPosition(const AProphecyAgent* A)
{const auto* S=States.IsEmpty()?nullptr:States.Find(A);return S && (!S->Returning || S->Tick<S->Total);}
static void ClearChaos(const AProphecyAgent* A)
{
    if(auto* Entries=Chaos.Find(A))for(auto& J:*Entries)
    {
        if(auto* Extra=J.Extra.Get())
        {
            // Original pointers only remain valid while the same mesh physics state exists.
            auto* Mesh=A->GetPoseReferenceMesh();
            if(Mesh && Mesh->Constraints.Contains(J.Original))
            {J.Original->SetLinearXLimit(LCM_Locked,0);J.Original->SetLinearYLimit(LCM_Locked,0);J.Original->SetLinearZLimit(LCM_Locked,0);}
            Extra->DestroyComponent();
        }
    }
    Chaos.Remove(A);
}
static bool Physics(AProphecyAgent* A,const FState* State,FString& Error)
{
    auto* Character=A->GetJoltCharacterComponent();FProphecyJoltBodyHandle Handle;
    const bool Jolt=Character && Character->GetRigIdentityBody(Handle);
    const FVector2D Min=!State?FVector2D::ZeroVector:State->Returning?State->PhysicalDelta*State->Weight():FVector2D(-5,-5);
    const FVector2D Max=!State?FVector2D::ZeroVector:State->Returning?Min:FVector2D(5,5);
    if(Jolt)
    {
        ClearChaos(A);
        return UProphecyJoltFootJointLibrary::SetWristRange(A,Handle.WorldLifetime,Handle.Slot,int64(Handle.Generation),
            Min,Max,State?State->Axes[0]:FVector::ForwardVector,State?State->Axes[1]:FVector::ForwardVector,Error);
    }
    auto* Mesh=A->GetPoseReferenceMesh();
    if(!State || (State->Returning && State->Tick>=State->Total) || !Mesh || !Mesh->IsAnySimulatingPhysics())
    {ClearChaos(A);return true;}
    auto* Entries=Chaos.Find(A);
    if(!Entries)
    {
        TArray<FChaosJoint> New;
        for(int Side=0;Side<2;++Side)
        {
            FConstraintInstance* Joint=nullptr;
            for(auto* C:Mesh->Constraints)if(C && ((C->ConstraintBone1==Hands[Side] && C->ConstraintBone2==Elbows[Side]) ||
                (C->ConstraintBone2==Hands[Side] && C->ConstraintBone1==Elbows[Side]))){Joint=C;break;}
            if(!Joint){for(auto& J:New)if(auto* E=J.Extra.Get())E->DestroyComponent();Error=TEXT("Missing physical wrist joint.");return false;}
            auto* Extra=NewObject<UPhysicsConstraintComponent>(A);
            Extra->SetAngularSwing1Limit(ACM_Free,0);Extra->SetAngularSwing2Limit(ACM_Free,0);Extra->SetAngularTwistLimit(ACM_Free,0);
            Extra->SetLinearXLimit(LCM_Limited,5);Extra->SetLinearYLimit(LCM_Locked,0);Extra->SetLinearZLimit(LCM_Locked,0);
            Extra->RegisterComponent();Extra->SetConstrainedComponents(Mesh,Elbows[Side],Mesh,Hands[Side]);
            const FVector X=State->Axes[Side];FVector Y,Z;X.FindBestAxisVectors(Y,Z);
            Extra->SetConstraintReferenceOrientation(EConstraintFrame::Frame1,X,Y);
            Extra->SetConstraintReferencePosition(EConstraintFrame::Frame1,X*State->Rest[Side]);
            Extra->SetConstraintReferencePosition(EConstraintFrame::Frame2,FVector::ZeroVector);
            New.Add({Extra,Joint});
        }
        for(auto& J:New){J.Original->SetLinearXLimit(LCM_Free,0);J.Original->SetLinearYLimit(LCM_Free,0);J.Original->SetLinearZLimit(LCM_Free,0);}
        Entries=&Chaos.Add(A,MoveTemp(New));
    }
    for(int Side=0;Side<2;++Side)if(auto* Extra=(*Entries)[Side].Extra.Get())
    {
        Extra->SetLinearXLimit(State->Returning?LCM_Locked:LCM_Limited,State->Returning?0:5);
        Extra->SetConstraintReferencePosition(EConstraintFrame::Frame1,State->Axes[Side]*(State->Rest[Side]+(State->Returning?Min[Side]:0.)));
    }
    return true;
}
bool Reapply(AProphecyAgent* A,FString& Error)
{const auto* S=States.Find(A);return S?Physics(A,S,Error):true;}
void BeforeModeChange(AProphecyAgent* A){ClearChaos(A);}
void PhysicalTarget(const AProphecyAgent* A,FName Bone,const FTransform& Elbow,FTransform& Hand)
{
    const auto* S=States.IsEmpty()?nullptr:States.Find(A);if(!S || !S->Returning)return;
    const int Side=Bone==Hands[0]?0:Bone==Hands[1]?1:INDEX_NONE;if(Side==INDEX_NONE)return;
    const FVector Axis=(Hand.GetLocation()-Elbow.GetLocation()).GetSafeNormal();
    Hand.SetLocation(Elbow.GetLocation()+Axis*(S->Rest[Side]+S->PhysicalDelta[Side]*S->Weight()));
}
void Cancel(AProphecyAgent* A)
{
    if(const auto* S=States.Find(A))
    {
        FProphecyNNPoseStore::SetForearmReturnLengths(S->PoseId,FVector2D::ZeroVector);
        FString Error;if(!Physics(A,nullptr,Error))UE_LOG(LogTemp,Warning,TEXT("Wrist return reset: %s"),*Error);
        States.Remove(A);
    }
    Returning.Remove(A);Refresh();
}
void Remove(AProphecyAgent* A){Cancel(A);Settings.Remove(A);Baselines.Remove(A);ClearChaos(A);}
void CaptureReset(const AProphecyAgent* A){if(const auto* S=Settings.Find(A))Baselines.Add(A,*S);else Baselines.Remove(A);}
void ForgetReset(const AProphecyAgent* A){Baselines.Remove(A);}
void RestoreReset(AProphecyAgent* A){Cancel(A);Settings.Remove(A);if(const auto* S=Baselines.Find(A))Settings.Add(A,*S);}
void Begin(AProphecyAgent* A)
{
    Cancel(A);if(!Settings.Contains(A))return;
    auto* Mesh=A->GetPoseReferenceMesh();if(!Mesh || !Mesh->GetSkeletalMeshAsset())return;
    const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    FState S;float Interval;bool Interpolate;if(!A->GetNNPoseDataSource(S.PoseId,Interval,Interpolate))return;
    for(int Side=0;Side<2;++Side)
    {
        const int H=Ref.FindBoneIndex(Hands[Side]);
        if(H==INDEX_NONE || Ref.GetParentIndex(H)==INDEX_NONE || Ref.GetBoneName(Ref.GetParentIndex(H))!=Elbows[Side])return;
        const FVector Offset=Ref.GetRefBonePose()[H].GetTranslation();S.Rest[Side]=Offset.Size();S.Axes[Side]=Offset.GetSafeNormal();
    }
    FString Error;if(!Physics(A,&S,Error)){UE_LOG(LogTemp,Warning,TEXT("Wrist stretch start: %s"),*Error);return;}
    States.Add(A,S);Refresh();
}
void End(AProphecyAgent* A,bool Recover)
{
    auto* S=States.Find(A);if(!S || S->Returning)return;
    if(!Recover){Cancel(A);return;}
    for(int Side=0;Side<2;++Side)
    {
        FTransform P,F,Hand,Elbow;float Alpha;
        if(!A->GetAuthoredBodyWorldTarget(Hands[Side],P,F,Hand,Alpha) || !A->GetAuthoredBodyWorldTarget(Elbows[Side],P,F,Elbow,Alpha))
        {Cancel(A);return;}
        S->Delta[Side]=FVector::Distance(Hand.GetLocation(),Elbow.GetLocation())-S->Rest[Side];
        auto* Jolt=A->GetJoltCharacterComponent();FVector V,W;bool Sim=false;
        if(Jolt && Jolt->GetBodyState(Hands[Side],Hand,V,W,Sim) && Sim && Jolt->GetBodyState(Elbows[Side],Elbow,V,W,Sim) && Sim)
            S->PhysicalDelta[Side]=FVector::Distance(Hand.GetLocation(),Elbow.GetLocation())-S->Rest[Side];
        else if(auto* Mesh=A->GetPoseReferenceMesh();Mesh && Mesh->IsAnySimulatingPhysics())
        {
            const auto* H=Mesh->GetBodyInstance(Hands[Side]);const auto* E=Mesh->GetBodyInstance(Elbows[Side]);
            if(H && E)S->PhysicalDelta[Side]=FVector::Distance(H->GetUnrealWorldTransform().GetLocation(),E->GetUnrealWorldTransform().GetLocation())-S->Rest[Side];
        }
    }
    S->Total=uint64(FMath::Max(0.,FMath::CeilToDouble(double(Settings.FindRef(A))*60.-1.e-5)));
    S->Returning=true;S->Tick=0;
    FProphecyNNPoseStore::SetForearmReturnLengths(S->PoseId,S->Lengths());
    FString Error;if(!Physics(A,S,Error))UE_LOG(LogTemp,Warning,TEXT("Wrist length capture: %s"),*Error);
    if(S->Total)Returning.Add(A);Refresh();
}
bool Apply(const AProphecyAgent* A,TConstArrayView<FName> Names,TArrayView<FTransform> Previous,
    TArrayView<FTransform> Current,TArrayView<FTransform> Local,bool FKReturning)
{
    auto* S=States.Find(A);if(!S || !S->Returning)return false;
    const FVector2D Lengths=S->Lengths();
    for(int Side=0;Side<2;++Side)
    {
        const int H=Names.IndexOfByKey(Hands[Side]),E=Names.IndexOfByKey(Elbows[Side]);
        if(!Current.IsValidIndex(H) || !Current.IsValidIndex(E))continue;
        // The presentation sidecar enforces this length after interpolation, too.
        // Preserve FK direction and rotation; never reorient the elbow or hand.
        const FVector Axis=(Current[H].GetLocation()-Current[E].GetLocation()).GetSafeNormal();
        Current[H].SetTranslation(Current[E].GetLocation()+Axis*Lengths[Side]);
        Local[H]=Current[H].GetRelativeTransform(Current[E]);
    }
    if(S->Tick>=S->Total && !FKReturning)
    {
        FProphecyNNPoseStore::SetForearmReturnLengths(S->PoseId,FVector2D::ZeroVector);
        States.Remove(A);
    }
    return true;
}
static void Tick(UWorld* World,ELevelTick Type,float Delta)
{
    if(!World || World->IsPaused() || Type!=LEVELTICK_All || Delta<=0)return;
    for(auto It=Returning.CreateIterator();It;++It)
    {
        auto* A=const_cast<AProphecyAgent*>(It->Get());auto* S=States.Find(*It);
        if(!A || A->IsActorBeingDestroyed() || !S){It.RemoveCurrent();continue;}
        if(A->GetWorld()!=World)continue;
        ++S->Tick;FProphecyNNPoseStore::SetForearmReturnLengths(S->PoseId,S->Lengths());
        FString Error;if(!Physics(A,S,Error))UE_LOG(LogTemp,Warning,TEXT("Wrist length return: %s"),*Error);
        if(S->Tick>=S->Total)It.RemoveCurrent();
    }
    Refresh();
}
static void Refresh()
{
    if(Returning.IsEmpty()){FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();}
    else if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
    if(!CleanupHandle.IsValid() && (!Settings.IsEmpty() || !States.IsEmpty()))
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
        {
            auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
            for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==W)
            {FProphecyNNPoseStore::SetForearmReturnLengths(It.Value().PoseId,FVector2D::ZeroVector);It.RemoveCurrent();}
            Clean(Settings);Clean(Baselines);Clean(Chaos);
            for(auto It=Returning.CreateIterator();It;++It)if(!It->IsValid() || (*It)->GetWorld()==W)It.RemoveCurrent();
            Refresh();
        });
}
}
bool UProphecyAttackWristLibrary::SetAttackForearmStretchReturn(AProphecyAgent* Agent,bool Enabled,float ReturnTime)
{
    using namespace ProphecyForearmStretch;
    if(!Valid(Agent) || !FMath::IsFinite(ReturnTime) || ReturnTime<0 || ReturnTime>1.e6f)return false;
    if(Enabled)Settings.Add(Agent,ReturnTime);
    else {Cancel(Agent);Settings.Remove(Agent);}
    Refresh();return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyForearmReturnTest,"Prophecy.Attack.ForearmStretch.Return",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyForearmReturnTest::RunTest(const FString&)
{
    using namespace ProphecyForearmStretch;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT {Remove(A);W->DestroyWorld(false);};
    const FName Names[]={Elbows[0],Hands[0],Elbows[1],Hands[1]};
    for(float Dt:{1.f/120,1.f/30,.5f})
    {
        FState S;S.Rest=FVector2D(22,23);S.Delta=FVector2D(-3,4);S.Returning=true;S.Total=18;S.PoseId=998800;
        States.Add(A,S);Returning.Add(A);Refresh();
        for(int I=0;I<=18;++I)
        {
            if(I)Tick(W,LEVELTICK_All,Dt);
            FTransform Cur[4],Prev[4],Local[4];Cur[1].SetLocation(FVector(0,5,0));Cur[3].SetLocation(FVector(0,0,5));
            const FQuat Q(FVector::ForwardVector,.7);Cur[1].SetRotation(Q);
            Apply(A,Names,Prev,Cur,Local,true);
            const double Alpha=double(I)/18;
            TestTrue(TEXT("Signed shortening returns independently"),FMath::IsNearlyEqual(Cur[1].GetLocation().Y,19+3*Alpha,1.e-8));
            TestTrue(TEXT("Signed extension returns independently"),FMath::IsNearlyEqual(Cur[3].GetLocation().Z,27-4*Alpha,1.e-8));
            TestTrue(TEXT("Hand rotation retained"),Cur[1].GetRotation().Equals(Q));
            Apply(A,Names,Prev,Cur,Local,true);
            TestEqual(TEXT("Repeated publications never advance time"),States.FindChecked(A).Tick,uint64(I));
        }
        TestFalse(TEXT("Completed return stops clock"),Returning.Contains(A));
        TestFalse(TEXT("Completed return restores normal wrist decoding"),OwnsPosition(A));
        TestTrue(TEXT("Rest guard survives a longer FK return"),States.Contains(A));
        FTransform Cur[4],Prev[4],Local[4];Cur[1].SetLocation(FVector(0,100,0));Cur[3].SetLocation(FVector(0,0,100));
        Apply(A,Names,Prev,Cur,Local,false);
        TestFalse(TEXT("Normal publication retires state"),States.Contains(A));
    }
    UProphecyAttackWristLibrary::SetAttackForearmStretchReturn(A,true,.5f);CaptureReset(A);
    UProphecyAttackWristLibrary::SetAttackForearmStretchReturn(A,false,.5f);RestoreReset(A);
    TestEqual(TEXT("Reset restores configured duration"),Settings.FindRef(A),.5f);
    return !HasAnyErrors();
}
#endif
