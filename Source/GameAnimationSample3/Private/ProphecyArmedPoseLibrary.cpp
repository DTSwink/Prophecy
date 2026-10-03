#include "ProphecyForearmConvention.h"
#include "ProphecyArmedPoseLibrary.h"
#include "ProphecyArmedPose.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyCoreTempering.h"
#include "ProphecySlashReturn.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecyAttackControls.h"
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
static bool CanonicalTargetForearms=false; // Reload a bank cached before this Live Coding correction.
struct FBinding { int32 Bone=INDEX_NONE,Parent=INDEX_NONE;FQuat Goal=FQuat::Identity; };
struct FState
{
    FName Attack;FBinding Bones[Count];FTransform Start[Count],Previous[Count],Current[Count];
    double MaxAngle=0,Alpha=0,Speed=180;bool Holding=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
// Keep the original state layout intact for Live Coding. Only non-default
// blend/alpha settings allocate this sidecar; disabled retains no pose work.
struct FBlendState
{
    int32 Slots[Count];float Weights[Count];
    FTransform Previous[Count],Current[Count];
    double Elapsed=0,Duration=0;
    bool NeedsLocomotion=true,HasSample=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBlendState> Blends;
static FDelegateHandle Cleanup;
static constexpr auto Clock=ProphecyBlendClock::EKind::ArmedUpperPose;
static double Degrees(const FQuat& A,const FQuat& B)
{return FMath::RadiansToDegrees(2.*FMath::Acos(FMath::Clamp(FMath::Abs(A|B),0.,1.)));}
static uint8 HittingHands(FName Attack)
{
    TArray<FName> Bones;bool Sword=false;
    ProphecyAttackControls::ColliderRoles(Attack,Bones,Sword);
    if(Sword || Bones.Contains(TEXT("hand_r")))return 2;
    if(Bones.Contains(TEXT("hand_l")))return 1;
    return 3; // No striking arm: headbutt and kicks use hitting settings for both.
}
static int32 ProfileSlot(FName Bone,uint8 Hitting)
{
    static const FName Core[]={TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};
    static const FName Arms[2][4]={{TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l")},
        {TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")}};
    for(int32 I=0;I<8;++I)if(Bone==Core[I])return I;
    for(int32 Side=0;Side<2;++Side)for(int32 I=0;I<4;++I)if(Bone==Arms[Side][I])return ((Hitting&(1<<Side))?8:12)+I;
    return INDEX_NONE;
}
static double BlendWeight(const FBlendState& B)
{
    const double T=B.Duration<=0?1.:FMath::Clamp(B.Elapsed/B.Duration,0.,1.);
    return T*T*(3-2*T);
}
static void RefreshOwnership(FBlendState& B)
{
    B.NeedsLocomotion=B.Elapsed<B.Duration;
    for(float Weight:B.Weights)B.NeedsLocomotion|=Weight<1.f;
}
static bool LoadTargets()
{
    if(CanonicalTargetForearms && !Targets.IsEmpty())return true;
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
        FTarget Target;TArray<FVector> Positions;
        for(const auto& V:*Pose)
        {
            const auto& Values=V->AsArray();if(Values.Num()!=7)return false;
            FQuat Q(Values[3]->AsNumber(),Values[4]->AsNumber(),Values[5]->AsNumber(),Values[6]->AsNumber());
            if(Q.ContainsNaN() || Q.SizeSquared()<.5)return false;
            Target.Rotation.Add(Q.GetNormalized());
            Positions.Emplace(Values[0]->AsNumber(),Values[1]->AsNumber(),Values[2]->AsNumber());
        }
        // GT controller frames still carry their source forearm roll. Convert
        // both parents before deriving locals, preserving the authored hand Q.
        for(int32 Side=0;Side<2;++Side)
        {
            const int32 Upper=NewNames.IndexOfByKey(FName(Side==0?TEXT("upperarm_l"):TEXT("upperarm_r")));
            const int32 Lower=NewNames.IndexOfByKey(FName(Side==0?TEXT("lowerarm_l"):TEXT("lowerarm_r")));
            const int32 Hand=NewNames.IndexOfByKey(FName(Side==0?TEXT("hand_l"):TEXT("hand_r")));
            if(Upper==INDEX_NONE || Lower==INDEX_NONE || Hand==INDEX_NONE)return false;
            Target.Rotation[Lower]=ProphecyForearmConvention::FromReference(FVector(Side==0?1.:-1.,0,0),
                Positions[Hand]-Positions[Lower],Target.Rotation[Upper]*ProphecyForearmConvention::IdleLocalUE(Side)).GetNormalized();
        }
        NewTargets.Add(FName(Pair.Key),MoveTemp(Target));
    }
    if(NewTargets.IsEmpty())return false;
    GTNames=MoveTemp(NewNames);Targets=MoveTemp(NewTargets);CanonicalTargetForearms=true;return true;
}
// Explicit calls only: sample the shared presented target once; never initialize
// an attack model, read simulated bodies or scan a scene on the hot path.
static bool Read(AProphecyAgent* A,FName Attack,FBinding (&Bones)[Count],FTransform (&Local)[Count],int32* Slots=nullptr)
{
    if(!IsValid(A)||!LoadTargets())return false;
    const FTarget* GT=Targets.Find(Attack);if(!GT)return false;
    const auto* Mesh=A->GetPoseReferenceMesh();const auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
    if(!Asset)return false;
    const auto& Ref=Asset->GetRefSkeleton();const int32 Spine=Ref.FindBoneIndex(TEXT("spine_01"));if(Spine==INDEX_NONE)return false;
    TArray<FName> Names;TArray<FTransform> Future,Pose;float Alpha;FProphecyNNPoseSnapshot Snapshot;
    if(!A->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Pose,Alpha,Snapshot)||Names.Num()!=Pose.Num())return false;
    int32 N=0;const uint8 Hitting=Slots?HittingHands(Attack):0;
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
        if(Slots){Slots[N]=ProfileSlot(Name,Hitting);if(Slots[N]==INDEX_NONE)return false;}
        Local[N]=Pose[Presented].GetRelativeTransform(Pose[PresentedParent]);Local[N].NormalizeRotation();++N;
    }
    return N==Count;
}
bool Active(const AProphecyAgent* A){return !States.IsEmpty() && States.Contains(A);}
bool OwnsUpperOutput(const AProphecyAgent* A)
{
    if(!Active(A))return false;
    const auto* B=Blends.IsEmpty()?nullptr:Blends.Find(A);
    return !B || !B->NeedsLocomotion;
}
void Cancel(const AProphecyAgent* A)
{
    if(!Blends.IsEmpty())Blends.Remove(A);
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
    auto* Blend=Blends.IsEmpty()?nullptr:Blends.Find(A);
    if(Blend)
    {
        for(const auto& B:S->Bones)
            if(!Current.IsValidIndex(B.Bone)||!Previous.IsValidIndex(B.Bone)||
                !Current.IsValidIndex(B.Parent)||!Previous.IsValidIndex(B.Parent)){Cancel(A);return false;}
        if(Advance || !Blend->HasSample)
        {
            if(Advance)
            {
                const double Dt=ProphecyBlendClock::Consume(A,Clock);
                AdvanceState(*S,Dt);Blend->Elapsed+=Dt;
                RefreshOwnership(*Blend);
                if(S->Holding && Blend->Elapsed>=Blend->Duration)ProphecyBlendClock::Stop(A,Clock);
            }
            const double Ramp=BlendWeight(*Blend);
            // Read all locomotion locals before modifying any parent. Cache the
            // composed endpoints so render-only publication never blends twice.
            for(int32 I=0;I<Count;++I)
            {
                const auto& B=S->Bones[I];
                const FTransform Loco=Current[B.Bone].GetRelativeTransform(Current[B.Parent]);
                // Entry must retain the incoming interpolation interval. Start was
                // sampled from the displayed pose, which can be between endpoints;
                // using it as previous rewinds/advances the visible spine at weight 0.
                Blend->Previous[I]=Blend->HasSample?Blend->Current[I]:
                    Previous[B.Bone].GetRelativeTransform(Previous[B.Parent]);
                Blend->Current[I]=Loco;
                const double Weight=Ramp*Blend->Weights[I];
                if(Weight>0)Blend->Current[I].SetRotation(Weight>=1?S->Current[I].GetRotation():
                    FQuat::Slerp(Loco.GetRotation(),S->Current[I].GetRotation(),Weight).GetNormalized());
            }
            Blend->HasSample=true;
        }
        for(int32 I=0;I<Count;++I)
        {
            const auto& B=S->Bones[I];
            Previous[B.Bone]=Blend->Previous[I]*Previous[B.Parent];
            Current[B.Bone]=Blend->Current[I]*Current[B.Parent];
        }
        return true;
    }
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

bool UProphecyArmedPoseLibrary::SetUpperBodyArmedPose(AProphecyAgent* A,bool Enabled,FName Attack,FString& Error,float Speed,float BlendInTime,
    float Spine01,float Spine02,float Spine03,float Spine04,float Spine05,float Neck01,float Neck02,float Head,
    float HittingClavicle,float HittingUpperarm,float HittingLowerarm,float HittingHand,
    float NonHittingClavicle,float NonHittingUpperarm,float NonHittingLowerarm,float NonHittingHand)
{
    using namespace ProphecyArmedPose;Error.Reset();
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||!A->GetWorld()||A->GetWorld()->bIsTearingDown)
    {Error=TEXT("Agent is unavailable.");return false;}
    if(!Enabled){Cancel(A);return true;}
    if(!FMath::IsFinite(Speed)||Speed<=0){Error=TEXT("Max joint speed must be positive and finite.");return false;}
    if(!FMath::IsFinite(BlendInTime)||BlendInTime<0){Error=TEXT("Blend In Time must be nonnegative and finite.");return false;}
    const float Profile[]={Spine01,Spine02,Spine03,Spine04,Spine05,Neck01,Neck02,Head,
        HittingClavicle,HittingUpperarm,HittingLowerarm,HittingHand,NonHittingClavicle,NonHittingUpperarm,NonHittingLowerarm,NonHittingHand};
    bool Custom=BlendInTime>0,Any=false;
    for(float Alpha:Profile)
    {
        if(!FMath::IsFinite(Alpha)||Alpha<0||Alpha>1){Error=TEXT("Joint alphas must be finite and between zero and one.");return false;}
        Custom|=Alpha<1;Any|=Alpha>0;
    }
    if(!Any){Cancel(A);return true;}
    if(UProphecyNNDefenseLibrary::GetAgentState(A)!=EProphecyAgentState::Locomotion)
    {Error=TEXT("Start the Armed pose during locomotion, before triggering the real attack/defense.");return false;}
    if(auto* Existing=States.Find(A);Existing && Existing->Attack==Attack)
    {
        auto* B=Blends.Find(A);
        if(Custom && !B)
        {
            FBinding Bones[Count];FTransform Local[Count];FBlendState New;
            if(!Read(A,Attack,Bones,Local,New.Slots)){Error=TEXT("Upper-body pose is not initialized.");return false;}
            for(int32 I=0;I<Count;++I)New.Previous[I]=New.Current[I]=Local[I];
            // Retuning a running pose must not restart its entry ramp.
            New.Elapsed=BlendInTime;B=&Blends.Add(A,MoveTemp(New));
        }
        Existing->Speed=Speed;
        if(B)
        {
            Any=false;B->Duration=BlendInTime;
            for(int32 I=0;I<Count;++I){B->Weights[I]=Profile[B->Slots[I]];Any|=B->Weights[I]>0;}
            if(!Any){Cancel(A);return true;}
            RefreshOwnership(*B);
            if(!Existing->Holding || B->Elapsed<B->Duration)ProphecyBlendClock::Ensure(A,Clock);
            else ProphecyBlendClock::Stop(A,Clock);
        }
        return true;
    }
    FState S;S.Attack=Attack;S.Speed=Speed;
    FBlendState Blend;Blend.Duration=BlendInTime;
    if(!Read(A,Attack,S.Bones,S.Start,Custom?Blend.Slots:nullptr)){Error=TEXT("Unknown GT attack or upper-body pose is not initialized.");return false;}
    Any=!Custom;
    for(int32 I=0;I<Count;++I)
    {
        S.Previous[I]=S.Current[I]=S.Start[I];S.MaxAngle=FMath::Max(S.MaxAngle,Degrees(S.Start[I].GetRotation(),S.Bones[I].Goal));
        if(Custom)
        {
            Blend.Previous[I]=Blend.Current[I]=S.Start[I];Blend.Weights[I]=Profile[Blend.Slots[I]];Any|=Blend.Weights[I]>0;
        }
    }
    if(!Any){Cancel(A);return true;}
    S.Holding=S.MaxAngle<1.e-6;if(S.Holding)S.Alpha=1;
    Cancel(A);A->StopNNAnimationLayer(0);
    ProphecyHandRecovery::CancelMotion(A);ProphecyCoreTempering::CancelMotion(A);
    ProphecySlashReturn::Cancel(A);ProphecyUpperBodyInertia::Cancel(A);
    States.Add(A,MoveTemp(S));
    if(Custom){RefreshOwnership(Blend);Blends.Add(A,MoveTemp(Blend));}
    if(!States.FindChecked(A).Holding || BlendInTime>0)ProphecyBlendClock::Start(A,Clock);
    if(!Cleanup.IsValid())Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=Blends.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmedForearmConventionTest,"Prophecy.NN.ArmedPose.AllFamilyForearmConvention",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmedForearmConventionTest::RunTest(const FString&)
{
    using namespace ProphecyArmedPose;
    if(!TestTrue(TEXT("Canonical Armed targets load"),LoadTargets()))return false;
    FString Text;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("locomotion/NN/prophecy_slash_half_gt.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
    const auto Families=Root->GetObjectField(TEXT("families"));
    for(const auto& Family:Families->Values)
    {
        const auto& Rows=Family.Value->AsObject()->GetArrayField(TEXT("pose_current"));
        const auto& Target=Targets.FindChecked(FName(Family.Key));
        auto Position=[&](int32 I){const auto& V=Rows[I]->AsArray();return FVector(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());};
        auto Rotation=[&](int32 I){const auto& V=Rows[I]->AsArray();return FQuat(V[3]->AsNumber(),V[4]->AsNumber(),V[5]->AsNumber(),V[6]->AsNumber()).GetNormalized();};
        for(int32 I=0;I<GTNames.Num();++I)
            if(GTNames[I]!=TEXT("lowerarm_l") && GTNames[I]!=TEXT("lowerarm_r"))
                TestTrue(TEXT("Authored hand/sword and all other rotations are preserved"),Target.Rotation[I].AngularDistance(Rotation(I))<1.e-6);
        for(int32 Side=0;Side<2;++Side)
        {
            const int32 U=GTNames.IndexOfByKey(FName(Side==0?TEXT("upperarm_l"):TEXT("upperarm_r")));
            const int32 E=GTNames.IndexOfByKey(FName(Side==0?TEXT("lowerarm_l"):TEXT("lowerarm_r")));
            const int32 H=GTNames.IndexOfByKey(FName(Side==0?TEXT("hand_l"):TEXT("hand_r")));
            const FVector Axis(Side==0?1.:-1.,0,0),Aim=(Position(H)-Position(E)).GetSafeNormal();
            const FQuat Reference=Target.Rotation[U]*ProphecyForearmConvention::IdleLocalUE(Side);
            const FQuat Swing=(Target.Rotation[E]*Reference.Inverse()).GetNormalized();
            TestTrue(TEXT("Every family's forearm aims at its authored wrist"),Target.Rotation[E].RotateVector(Axis).Equals(Aim,1.e-6));
            TestTrue(TEXT("No added axial twist relative to upper-arm-carried idle"),FMath::Abs(FVector::DotProduct(FVector(Swing.X,Swing.Y,Swing.Z),Reference.RotateVector(Axis)))<1.e-6);
            const FQuat WristLocal=(Target.Rotation[E].Inverse()*Target.Rotation[H]).GetNormalized();
            TestTrue(TEXT("Rebased wrist local reconstructs the original sword orientation"),
                (Target.Rotation[E]*WristLocal).AngularDistance(Rotation(H))<1.e-6);
            auto Mirror=[](const FQuat& Q){return FQuat(-Q.X,Q.Y,-Q.Z,Q.W);};
            const FQuat Native=ProphecyForearmConvention::FromReference(Axis,FVector(Aim.X,-Aim.Y,Aim.Z),Mirror(Reference));
            TestTrue(TEXT("Armed and native locomotion/special coordinate boundaries agree"),Mirror(Native).AngularDistance(Target.Rotation[E])<1.e-6);
        }
    }
    return !HasAnyErrors();
}
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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmedPoseRolesTest,"Prophecy.NN.ArmedPose.AttackRoles",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmedPoseRolesTest::RunTest(const FString&)
{
    using namespace ProphecyArmedPose;
    for(FName Name:{FName(TEXT("jabL")),FName(TEXT("hookL")),FName(TEXT("overL"))})
        TestEqual(TEXT("Left punches use left hitting profile"),HittingHands(Name),uint8(1));
    for(FName Name:{FName(TEXT("jabR")),FName(TEXT("hookR")),FName(TEXT("overR")),FName(TEXT("pike")),
        FName(TEXT("slashL")),FName(TEXT("slashR")),FName(TEXT("slashLD")),FName(TEXT("slashRD")),FName(TEXT("slashLU")),FName(TEXT("slashRU"))})
        TestEqual(TEXT("Right punches and every sword direction use right hitting profile"),HittingHands(Name),uint8(2));
    for(FName Name:{FName(TEXT("headbutt")),FName(TEXT("kickL")),FName(TEXT("kickR"))})
        TestEqual(TEXT("Attacks without a striking arm use both hitting profiles"),HittingHands(Name),uint8(3));
    TestEqual(TEXT("Left jab hand uses hitting hand alpha"),ProfileSlot(TEXT("hand_l"),HittingHands(TEXT("jabL"))),11);
    TestEqual(TEXT("Right jab left hand uses non-hitting hand alpha"),ProfileSlot(TEXT("hand_l"),HittingHands(TEXT("jabR"))),15);
    TestEqual(TEXT("Headbutt right clavicle uses hitting clavicle alpha"),ProfileSlot(TEXT("clavicle_r"),HittingHands(TEXT("headbutt"))),8);
    TestEqual(TEXT("Spine has its own joint alpha"),ProfileSlot(TEXT("spine_05"),3),4);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmedPoseBlendTest,"Prophecy.NN.ArmedPose.LocomotionBlendAndJointAlphas",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmedPoseBlendTest::RunTest(const FString&)
{
    using namespace ProphecyArmedPose;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    FState S;S.Holding=true;S.Alpha=1;
    FBlendState B;B.Duration=1;
    const FVector Offset(0,0,5);const FQuat Goal(FVector::UpVector,PI/2);
    for(int32 I=0;I<Count;++I)
    {
        S.Bones[I]={I+1,I,Goal};S.Start[I]=S.Current[I]=S.Previous[I]=FTransform(Goal,Offset);
        B.Slots[I]=I;B.Weights[I]=1;B.Previous[I]=B.Current[I]=FTransform(Offset);
    }
    B.Weights[0]=.5f;B.Weights[1]=0;
    States.Add(A,S);Blends.Add(A,B);ProphecyBlendClock::Start(A,Clock);
    TestFalse(TEXT("Entry blend requires live upper locomotion"),OwnsUpperOutput(A));
    FTransform Previous[25],Current[25],Last[Count];
    for(int32 I=0;I<Count;++I)Last[I]=B.Current[I];
    for(int32 Tick=1;Tick<=60;++Tick)
    {
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
        const FQuat Loco(FVector::UpVector,FMath::DegreesToRadians(10.+Tick*.1));
        Previous[0]=FTransform(FRotator(0,Tick-1,0),FVector(Tick-1,0,90));
        Current[0]=FTransform(FRotator(0,Tick,0),FVector(Tick,0,90));
        for(int32 I=0;I<Count;++I)
        {
            Previous[I+1]=Last[I]*Previous[I];
            Current[I+1]=FTransform(Loco,Offset)*Current[I];
        }
        for(int32 I=17;I<25;++I)Previous[I]=Current[I]=FTransform(FVector(I,2*I,3*I));
        Apply(A,Previous,Current,true);
        const double T=Tick/60.,Ramp=T*T*(3-2*T);
        for(int32 I=0;I<Count;++I)
        {
            const FTransform Local=Current[I+1].GetRelativeTransform(Current[I]);
            const FQuat Expected=FQuat::Slerp(Loco,Goal,Ramp*B.Weights[I]).GetNormalized();
            TestTrue(TEXT("Each local alpha blends the live, moving locomotion pose"),Degrees(Local.GetRotation(),Expected)<1.e-4);
            TestTrue(TEXT("Offsets remain attached"),Local.GetLocation().Equals(Offset,1.e-6));
            TestTrue(TEXT("Previous endpoint is the last accepted composite"),Previous[I+1].GetRelativeTransform(Previous[I]).Equals(Last[I],1.e-6));
            Last[I]=Local;
        }
        const FTransform Once=Current[Count];Apply(A,Previous,Current,false);
        TestTrue(TEXT("Duplicate publication does not re-blend"),Current[Count].Equals(Once,1.e-6));
        for(int32 I=17;I<25;++I)TestTrue(TEXT("Legs remain untouched"),Current[I].GetLocation().Equals(FVector(I,2*I,3*I)));
    }
    TestFalse(TEXT("Partial joints keep normal upper inference alive after entry"),OwnsUpperOutput(A));
    TestEqual(TEXT("Finished entry and manual track retire timer even with partial joints"),ProphecyBlendClock::Consume(A,Clock),0.);
    auto& Full=Blends.FindChecked(A);for(float& Weight:Full.Weights)Weight=1;RefreshOwnership(Full);
    TestTrue(TEXT("Full influence bypasses upper inference"),OwnsUpperOutput(A));
    Cancel(A);TestFalse(TEXT("Stop clears advanced state"),Blends.Contains(A));
    TestFalse(TEXT("Disabled never owns upper inference"),OwnsUpperOutput(A));
    TestFalse(TEXT("Disabled bypasses pose work"),Apply(A,Previous,Current,true));
    W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmedPoseEntryHistoryTest,"Prophecy.NN.ArmedPose.EntryPreservesHistory",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmedPoseEntryHistoryTest::RunTest(const FString&)
{
    using namespace ProphecyArmedPose;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    FState S;S.Holding=true;S.Alpha=1;
    FBlendState B;B.Duration=.1;
    FTransform Previous[17],Current[17],OriginalPrevious[17],OriginalCurrent[17];
    Previous[0]=FTransform(FRotator(5,15,0),FVector(10,20,90));
    Current[0]=FTransform(FRotator(6,18,0),FVector(20,22,91));
    for(int32 I=0;I<Count;++I)
    {
        const FTransform Old(FRotator(I*.3,2,0),FVector(0,0,5));
        const FTransform New(FRotator(I*.3+1,3,0),FVector(0,0,5));
        FTransform Shown;Shown.Blend(Old,New,.5f);
        S.Bones[I]={I+1,I,FQuat::Identity};S.Start[I]=S.Previous[I]=S.Current[I]=Shown;
        B.Weights[I]=.1f;B.Slots[I]=I;B.Previous[I]=B.Current[I]=Shown;
        Previous[I+1]=Old*Previous[I];Current[I+1]=New*Current[I];
    }
    for(int32 I=0;I<17;++I){OriginalPrevious[I]=Previous[I];OriginalCurrent[I]=Current[I];}
    States.Add(A,S);Blends.Add(A,B);
    Apply(A,Previous,Current,false);
    for(int32 I=0;I<17;++I)
    {
        TestTrue(TEXT("Zero-weight entry preserves the previous policy endpoint"),Previous[I].Equals(OriginalPrevious[I],1.e-6));
        TestTrue(TEXT("Zero-weight entry preserves the current policy endpoint"),Current[I].Equals(OriginalCurrent[I],1.e-6));
        for(float Alpha:{0.f,.5f,1.f})
        {
            FTransform Before,After;Before.Blend(OriginalPrevious[I],OriginalCurrent[I],Alpha);After.Blend(Previous[I],Current[I],Alpha);
            TestTrue(TEXT("Spine/head presentation cannot jump on activation at any phase"),Before.Equals(After,1.e-6));
        }
    }
    Cancel(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
