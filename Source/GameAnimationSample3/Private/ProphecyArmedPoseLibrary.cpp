#include "ProphecyArmedPoseLibrary.h"
#include "ProphecyArmedPose.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyCoreTempering.h"
#include "ProphecySlashReturn.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecyNNPoseTypes.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyArmedPose
{
constexpr int32 Count=16;
// Independent storage avoids changing retained manager/agent layouts.
struct FTarget { TArray<FQuat> Rotation; };
static TArray<FName> GTNames;
static TMap<FName,FTarget> Targets;
struct FBinding { int32 Bone=INDEX_NONE,Parent=INDEX_NONE;FQuat Goal=FQuat::Identity; };
struct FState
{
    FName Attack;FBinding Bones[Count];FTransform Start[Count],Previous[Count],Current[Count];
    double MaxAngle=0,Alpha=0,Speed=180;bool Holding=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static FDelegateHandle Cleanup;
static constexpr auto Clock=ProphecyBlendClock::EKind::ArmedUpperPose;
static double Degrees(const FQuat& A,const FQuat& B)
{return FMath::RadiansToDegrees(2.*FMath::Acos(FMath::Clamp(FMath::Abs(A|B),0.,1.)));}
static bool LoadTargets()
{
    if(!Targets.IsEmpty())return true;
    FString Text;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("locomotion/NN/prophecy_slash_half_gt.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root) || !Root)return false;
    const TArray<TSharedPtr<FJsonValue>>* Names=nullptr;const TSharedPtr<FJsonObject>* Families=nullptr;
    if(!Root->TryGetArrayField(TEXT("bone_names"),Names)||!Root->TryGetObjectField(TEXT("families"),Families))return false;
    TArray<FName> NewNames;for(const auto& V:*Names)NewNames.Add(FName(V->AsString()));
    TMap<FName,FTarget> NewTargets;
    for(const auto& Pair:(*Families)->Values)
    {
        const auto Row=Pair.Value->AsObject();const TArray<TSharedPtr<FJsonValue>>* Pose=nullptr;
        if(!Row || !Row->TryGetArrayField(TEXT("pose_current"),Pose) || Pose->Num()!=NewNames.Num())return false;
        FTarget Target;
        for(const auto& V:*Pose)
        {
            const auto& Values=V->AsArray();if(Values.Num()!=7)return false;
            FQuat Q(Values[3]->AsNumber(),Values[4]->AsNumber(),Values[5]->AsNumber(),Values[6]->AsNumber());
            if(Q.ContainsNaN() || Q.SizeSquared()<.5)return false;
            Target.Rotation.Add(Q.GetNormalized());
        }
        NewTargets.Add(FName(Pair.Key),MoveTemp(Target));
    }
    if(NewTargets.IsEmpty())return false;
    GTNames=MoveTemp(NewNames);Targets=MoveTemp(NewTargets);return true;
}
// Explicit calls only: sample the shared presented target once; never initialize
// an attack model, read simulated bodies or scan a scene on the hot path.
static bool Read(AProphecyAgent* A,FName Attack,FBinding (&Bones)[Count],FTransform (&Local)[Count])
{
    if(!IsValid(A)||!LoadTargets())return false;
    const FTarget* GT=Targets.Find(Attack);if(!GT)return false;
    const auto* Mesh=A->GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
    if(!Asset)return false;
    const auto& Ref=Asset->GetRefSkeleton();const int32 Spine=Ref.FindBoneIndex(TEXT("spine_01"));if(Spine==INDEX_NONE)return false;
    TArray<FName> Names;TArray<FTransform> Future,Pose;float Alpha;FProphecyNNPoseSnapshot Snapshot;
    if(!A->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Pose,Alpha,Snapshot)||Names.Num()!=Pose.Num())return false;
    int32 N=0;
    // Physical target order can differ and include extra bodies. Bind only the
    // authored NN bones, in the same parent-first order used by publication.
    for(int32 I=0;I<Snapshot.BoneNames.Num();++I)
    {
        const FName Name=Snapshot.BoneNames[I];
        const int32 RefBone=Ref.FindBoneIndex(Name);if(RefBone==INDEX_NONE)continue;
        if(RefBone!=Spine && !Ref.BoneIsChildOf(RefBone,Spine))continue;
        if(N>=Count)return false;
        const int32 RefParent=Ref.GetParentIndex(RefBone);
        if(RefParent==INDEX_NONE)return false;
        const FName ParentName=Ref.GetBoneName(RefParent);
        const int32 Parent=Snapshot.BoneNames.IndexOfByKey(ParentName),Source=GTNames.IndexOfByKey(Name),SourceParent=GTNames.IndexOfByKey(ParentName);
        const int32 Presented=Names.IndexOfByKey(Name),PresentedParent=Names.IndexOfByKey(ParentName);
        if(Parent<0 || Parent>=I || Source<0 || SourceParent<0 || Presented<0 || PresentedParent<0)return false;
        Bones[N]={I,Parent,(GT->Rotation[SourceParent].Inverse()*GT->Rotation[Source]).GetNormalized()};
        Local[N]=Pose[Presented].GetRelativeTransform(Pose[PresentedParent]);Local[N].NormalizeRotation();++N;
    }
    return N==Count;
}
bool Active(const AProphecyAgent* A){return !States.IsEmpty() && States.Contains(A);}
void Cancel(const AProphecyAgent* A)
{
    if(States.IsEmpty() || !States.Remove(A))return;
    ProphecyBlendClock::Stop(A,Clock);
    if(States.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
}
static void AdvanceState(FState& S,double Dt)
{
    if(S.Holding)return;
    S.Alpha=FMath::Min(1.,S.Alpha+S.Speed*Dt/FMath::Max(S.MaxAngle,1.e-9));
    for(int32 I=0;I<Count;++I)
    {
        S.Previous[I]=S.Current[I];
        S.Current[I].SetRotation(S.Alpha>=1?S.Bones[I].Goal:FQuat::Slerp(S.Start[I].GetRotation(),S.Bones[I].Goal,S.Alpha).GetNormalized());
    }
    S.Holding=S.Alpha>=1;
}
bool Apply(const AProphecyAgent* A,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,bool Advance)
{
    auto* S=States.IsEmpty()?nullptr:States.Find(A);if(!S)return false;
    if(Advance)
    {
        if(!S->Holding)
        {
            AdvanceState(*S,ProphecyBlendClock::Consume(A,Clock));
            if(S->Holding)ProphecyBlendClock::Stop(A,Clock);
        }
        else for(int32 I=0;I<Count;++I)S->Previous[I]=S->Current[I];
    }
    for(int32 I=0;I<Count;++I)
    {
        const auto& B=S->Bones[I];
        if(!Current.IsValidIndex(B.Bone)||!Previous.IsValidIndex(B.Bone)){Cancel(A);return false;}
        Previous[B.Bone]=S->Previous[I]*Previous[B.Parent];
        Current[B.Bone]=S->Current[I]*Current[B.Parent];
    }
    return true;
}
}

bool UProphecyArmedPoseLibrary::SetUpperBodyArmedPose(AProphecyAgent* A,bool Enabled,FName Attack,FString& Error,float Speed)
{
    using namespace ProphecyArmedPose;Error.Reset();
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||!A->GetWorld()||A->GetWorld()->bIsTearingDown)
    {Error=TEXT("Agent is unavailable.");return false;}
    if(!Enabled){Cancel(A);return true;}
    if(!FMath::IsFinite(Speed)||Speed<=0){Error=TEXT("Max joint speed must be positive and finite.");return false;}
    if(UProphecyNNDefenseLibrary::GetAgentState(A)!=EProphecyAgentState::Locomotion)
    {Error=TEXT("Start the Armed pose during locomotion, before triggering the real attack/defense.");return false;}
    if(auto* Existing=States.Find(A);Existing && Existing->Attack==Attack)
    {Existing->Speed=Speed;return true;}
    FState S;S.Attack=Attack;S.Speed=Speed;
    if(!Read(A,Attack,S.Bones,S.Start)){Error=TEXT("Unknown GT attack or upper-body pose is not initialized.");return false;}
    for(int32 I=0;I<Count;++I)
    {
        S.Previous[I]=S.Current[I]=S.Start[I];S.MaxAngle=FMath::Max(S.MaxAngle,Degrees(S.Start[I].GetRotation(),S.Bones[I].Goal));
    }
    S.Holding=S.MaxAngle<1.e-6;if(S.Holding)S.Alpha=1;
    Cancel(A);A->StopNNAnimationLayer(0);
    ProphecyHandRecovery::CancelMotion(A);ProphecyCoreTempering::CancelMotion(A);
    ProphecySlashReturn::Cancel(A);ProphecyUpperBodyInertia::Cancel(A);
    States.Add(A,MoveTemp(S));
    if(!States.FindChecked(A).Holding)ProphecyBlendClock::Start(A,Clock);
    if(!Cleanup.IsValid())Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        if(States.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    });
    return true;
}
bool UProphecyArmedPoseLibrary::StopUpperBodyArmedPose(AProphecyAgent* A)
{
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed())return false;
    ProphecyArmedPose::Cancel(A);return true;
}
bool UProphecyArmedPoseLibrary::GetUpperBodyArmedPoseDistance(AProphecyAgent* A,FName Attack,float& Average)
{
    using namespace ProphecyArmedPose;Average=0;
    if(!IsInGameThread())return false;
    FBinding Bones[Count];FTransform Local[Count];if(!Read(A,Attack,Bones,Local))return false;
    double Total=0;for(int32 I=0;I<Count;++I)Total+=Degrees(Local[I].GetRotation(),Bones[I].Goal);
    Average=float(Total/Count);return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmedPoseTest,"Prophecy.NN.ArmedPose.SynchronizedJoints",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmedPoseTest::RunTest(const FString&)
{
    using namespace ProphecyArmedPose;
    TestTrue(TEXT("GT Armed pose bank loads without initializing attack inference"),LoadTargets());
    TestEqual(TEXT("All GT attack families including kicks available"),Targets.Num(),16);
    TestTrue(TEXT("Quaternion sign does not change distance"),Degrees(FQuat::Identity,FQuat(0,0,0,-1))<1.e-6);
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        FState S;S.Speed=120;S.MaxAngle=160;
        for(int32 I=0;I<Count;++I)
        {
            S.Bones[I]={I+1,I,FQuat(FVector::UpVector,FMath::DegreesToRadians(double((I+1)*10)))};
            S.Start[I]=S.Previous[I]=S.Current[I]=FTransform(FVector(0,0,5));
        }
        States.Add(A,S);ProphecyBlendClock::Start(A,Clock);
        FTransform Previous[25],Current[25];for(int32 I=0;I<25;++I)Previous[I]=Current[I]=FTransform(FVector(I,2*I,3*I));
        for(int32 Tick=1;Tick<=80;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1/FPS);
            if(Tick%2)continue;
            Previous[0]=Current[0];Current[0]=FTransform(FRotator(0,Tick*3,0),FVector(Tick,0,90));
            TestTrue(TEXT("Active pose applies"),Apply(A,MakeArrayView(Previous),MakeArrayView(Current),true));
            const auto& Now=States.FindChecked(A);
            TestTrue(TEXT("One progress value preserves same arrival time"),FMath::IsNearlyEqual(Now.Alpha,Tick/80.,1.e-9));
            for(int32 I=0;I<Count;++I)
            {
                const double Initial=(I+1)*10.;
                TestTrue(TEXT("Every local joint follows common progress despite moving pelvis"),FMath::Abs(
                    Degrees(Current[I+1].GetRelativeTransform(Current[I]).GetRotation(),Now.Bones[I].Goal)-Initial*(1-Tick/80.))<1.e-4);
                TestTrue(TEXT("No joint exceeds maximum speed"),Degrees(Now.Previous[I].GetRotation(),Now.Current[I].GetRotation())<=4.00001);
                TestTrue(TEXT("Joint offsets and lengths unchanged"),Current[I+1].GetRelativeTransform(Current[I]).GetLocation().Equals(FVector(0,0,5),1.e-5));
            }
            for(int32 I=17;I<25;++I)TestTrue(TEXT("Lower bones untouched"),Current[I].GetLocation().Equals(FVector(I,2*I,3*I)));
            const double Alpha=Now.Alpha;Apply(A,MakeArrayView(Previous),MakeArrayView(Current),false);
            TestEqual(TEXT("Duplicate publication does not advance"),States.FindChecked(A).Alpha,Alpha);
        }
        TestTrue(TEXT("All joints arrive and hold together"),States.FindChecked(A).Holding);
        TestEqual(TEXT("Arrival retires clock"),ProphecyBlendClock::Consume(A,Clock),0.);
        TestTrue(TEXT("Farthest joint moved at the limit before arrival"),FMath::IsNearlyEqual(Degrees(States.FindChecked(A).Previous[15].GetRotation(),States.FindChecked(A).Current[15].GetRotation()),4.,1.e-5));
        TestTrue(TEXT("Explicit stop succeeds"),UProphecyArmedPoseLibrary::StopUpperBodyArmedPose(A));
        TestTrue(TEXT("Repeated stop is harmless"),UProphecyArmedPoseLibrary::StopUpperBodyArmedPose(A));
        TestFalse(TEXT("Stop removes state"),Active(A));
        TestFalse(TEXT("Inactive apply bypasses pose work"),Apply(A,MakeArrayView(Previous),MakeArrayView(Current),true));
    }
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
