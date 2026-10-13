#include "ProphecyReachLibrary.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyDoubleReachSolver.h"
#include "ProphecyAgent.h"
#include "ProphecySwordHolsterPose.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsEngine/BodySetup.h"
#include "DrawDebugHelpers.h"
#include "Misc/ScopeRWLock.h"

namespace ProphecyReach
{
constexpr double Dt=1./60.;
static FName HandName(int Side) { return Side==0?TEXT("hand_l"):TEXT("hand_r"); }
struct FFingerBone
{
    FName Name; int Parent=-1, Finger=0;
    FTransform Open,Closed,Local,World;
    float Curl=0;
};
struct FHand
{
    bool Enabled=false,Grab=false,Gripped=false,Physical=false,Fitted=false,Returning=false;
    FTransform Target=FTransform::Identity;
    float Speed=300,RotationSpeed=360,Close=0,Distance=0;
    TWeakObjectPtr<UPrimitiveComponent> Component;
    TWeakObjectPtr<UBodySetup> Collider;
    FName Bone;
    FVector Point=FVector::ZeroVector,Normal=FVector::UpVector,Palm=FVector::ZeroVector;
    FQuat GripRotation=FQuat::Identity,Rotation=FQuat::Identity;
    TArray<FFingerBone> Fingers;
    FTransform ReturnLocal[4];
    float ReturnTime=0,ReturnDuration=.25f,ReturnClose=0;
    int Contacts=0;
    FProphecyJoltJointHandle Joint;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Physics;
};
struct FState
{
    int Id=INDEX_NONE;
    uint64 Frame=MAX_uint64;
    FHand Hands[2];
    ProphecyNativeReach::FState Solver;
    TArray<FName> Names;
    TArray<FTransform> Future,Base,Ordered,Pose,ReturnStart;
    TArray<int> Indices,Parents;
    float ReturnTime=0,ReturnDuration=.25f;
    bool Returning=false,Debug=false;
};
struct FOutput { TMap<FName,FTransform> Bones,Fingers; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,TUniquePtr<FState>> States;
static TMap<int,FOutput> Outputs;
static FRWLock Lock;
static TAtomic<bool> Any(false);
static thread_local bool Reading=false;
static FDelegateHandle Cleanup;
static bool ValidHand(int Side) { return Side>=0&&Side<2; }
static int ArmIndex(int Side,int Joint)
{
    static const int Indices[2][4]={
        {ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("clavicle_l")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("upperarm_l")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("lowerarm_l")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("hand_l"))},
        {ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("clavicle_r")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("upperarm_r")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("lowerarm_r")),ProphecyNativeReach::BoneNames().IndexOfByKey(TEXT("hand_r"))}};
    return Indices[Side][Joint];
}
static void BeginHandReturn(FState& S,int Side,float Seconds)
{
    auto& H=S.Hands[Side];if(!H.Enabled)return;
    H.Returning=Seconds>0&&FMath::IsFinite(Seconds)&&!S.Pose.IsEmpty();
    H.ReturnTime=0;H.ReturnDuration=Seconds;H.ReturnClose=H.Close;
    if(H.Returning)for(int J=0;J<4;++J)
    { const int I=ArmIndex(Side,J);H.ReturnLocal[J]=S.Pose[I].GetRelativeTransform(S.Pose[S.Parents[I]]); }
}
static void SeedHand(AProphecyAgent* A,FState& S,int Side)
{
    auto& H=S.Hands[Side];if(H.Enabled)return;
    const auto* Mesh=A->GetPoseReferenceMesh();const auto Space=A->GetAgentMesh()->GetComponentTransform();
    H.Rotation=Mesh->GetSocketQuaternion(HandName(Side));H.Returning=false;
    S.Solver.Active[Side]=true;
    S.Solver.Targets[Side]=Space.InverseTransformPosition(Mesh->GetSocketLocation(HandName(Side)))*.01;
    S.Solver.Elbows[Side]=Space.InverseTransformPosition(Mesh->GetSocketLocation(Side==0?TEXT("lowerarm_l"):TEXT("lowerarm_r")))*.01;
}

static void Drop(FHand& H)
{
    if (auto* W=H.Physics.Get())
    {
        if(W->OwnsJoint(H.Joint)) W->DestroyJoint(H.Joint);
        W->UpdateScopedContactRules(&H,{},{});
    }
    H.Joint={};H.Gripped=false;H.Physical=false;H.Physics.Reset();
}
void Remove(const AProphecyAgent* A)
{
    if (auto* S=States.Find(A))
    {
        for (auto& H:(*S)->Hands) Drop(H);
        FWriteScopeLock Guard(Lock);Outputs.Remove((*S)->Id);Any.Store(!Outputs.IsEmpty());
    }
    States.Remove(A);
}
bool Active(const AProphecyAgent* A) { return !States.IsEmpty()&&States.Contains(A); }
void Apply(int Id,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space)
{
    if (Reading||!Any.Load()) return;
    FReadScopeLock Guard(Lock);
    if (const auto* P=Outputs.Find(Id)) for (int I=0;I<Names.Num();++I)
        if (const auto* T=P->Bones.Find(Names[I])) Pose[I]=T->GetRelativeTransform(Space);
}
void Fingers(const AProphecyAgent* A,TFunctionRef<void(FName,const FTransform&)> Visit)
{
    const auto* S=States.Find(A);if (!S) return;
    FReadScopeLock Guard(Lock);
    if (const auto* P=Outputs.Find((*S)->Id)) for (const auto& B:P->Fingers) Visit(B.Key,B.Value);
}
static bool BasePose(AProphecyAgent* A,FState& S)
{
    float Alpha;TGuardValue<bool> Guard(Reading,true);
    if (!A->ReadNNFutureWorldPose(S.Names,S.Future,S.Base,Alpha)) return false;
    const auto Names=ProphecyNativeReach::BoneNames();
    if (S.Indices.IsEmpty())
    {
        const auto* Mesh=A->GetPoseReferenceMesh();
        if (!Mesh||!Mesh->GetSkeletalMeshAsset()) return false;
        const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
        for (FName Name:Names)
        {
            const int Id=S.Names.IndexOfByKey(Name);S.Indices.Add(Id);
            if (Id<0&&Name!=TEXT("root")) return false;
            int Bone=Ref.FindBoneIndex(Name),Parent=-1;
            while (Bone>=0) { Bone=Ref.GetParentIndex(Bone);if (Bone>=0) { Parent=Names.IndexOfByKey(Ref.GetBoneName(Bone));if (Parent>=0) break; } }
            S.Parents.Add(Parent);
        }
    }
    const FTransform Space=A->GetAgentMesh()->GetComponentTransform();
    S.Ordered.SetNum(Names.Num());
    for (int I=0;I<Names.Num();++I) S.Ordered[I]=S.Indices[I]<0?FTransform::Identity:S.Base[S.Indices[I]].GetRelativeTransform(Space);
    return true;
}
static FState* Admit(AProphecyAgent* A)
{
    if (!IsInGameThread()||!IsValid(A)||!A->HasActorBegunPlay()) return nullptr;
    ProphecySwordHolsterPose::FStatus Holster;
    if (ProphecySwordHolsterPose::Status(A,Holster)&&!Holster.Finished) return nullptr;
    if (auto* S=States.Find(A)) { (*S)->Returning=false;return S->Get(); }
    auto S=MakeUnique<FState>();float Interval;bool Interpolate;
    if (!A->GetNNPoseDataSource(S->Id,Interval,Interpolate)||!BasePose(A,*S)) return nullptr;
    for (int K=0;K<2;++K) S->Hands[K].Rotation=A->GetPoseReferenceMesh()->GetSocketQuaternion(HandName(K));
    auto* Result=S.Get();States.Add(A,MoveTemp(S));
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        TArray<TWeakObjectPtr<const AProphecyAgent>> RemoveKeys;
        for (const auto& P:States) if (!P.Key.IsValid()||P.Key->GetWorld()==W) RemoveKeys.Add(P.Key);
        for (auto Key:RemoveKeys) { if (Key.IsValid()) Remove(Key.Get());else { for(auto& H:States[Key]->Hands)Drop(H);FWriteScopeLock Guard(Lock);Outputs.Remove(States[Key]->Id);States.Remove(Key); } }
        Any.Store(!Outputs.IsEmpty());
    });
    return Result;
}
static FTransform TargetFrame(const FHand& H)
{
    if (auto* C=H.Component.Get()) return H.Bone.IsNone()?C->GetComponentTransform():C->GetSocketTransform(H.Bone);
    return FTransform::Identity;
}
static UBodySetup* Collider(UPrimitiveComponent* C,FName Bone)
{
    if (auto* M=Cast<USkeletalMeshComponent>(C))
    {
        auto* Asset=M->GetPhysicsAsset();const int I=Asset?Asset->FindBodyIndex(Bone):INDEX_NONE;
        return I>=0?Asset->SkeletalBodySetups[I]:nullptr;
    }
    return C?C->GetBodySetup():nullptr;
}
static bool BuildFingers(const USkeletalMesh* Mesh,UAnimSequence* Clip,int Side,FHand& H)
{
    if (!Mesh||!Clip||!Clip->GetSkeleton()||Clip->IsValidAdditive()) return false;
    const auto& Ref=Mesh->GetRefSkeleton();const auto& CR=Clip->GetSkeleton()->GetReferenceSkeleton();
    TArray<FTransform> RefCS,ClipRef,ClipPose;RefCS.SetNum(Ref.GetNum());ClipRef.SetNum(CR.GetNum());ClipPose.SetNum(CR.GetNum());
    for (int I=0;I<CR.GetNum();++I)
    {
        const int P=CR.GetParentIndex(I);auto T=CR.GetRefBonePose()[I];
        Clip->GetBoneTransform(T,FSkeletonPoseBoneIndex(I),FAnimExtractContext(0.),false);
        ClipRef[I]=P<0?CR.GetRefBonePose()[I]:CR.GetRefBonePose()[I]*ClipRef[P];
        ClipPose[I]=P<0?T:T*ClipPose[P];
    }
    for (int I=0;I<Ref.GetNum();++I) { int P=Ref.GetParentIndex(I);RefCS[I]=P<0?Ref.GetRefBonePose()[I]:Ref.GetRefBonePose()[I]*RefCS[P]; }
    const int Hand=Ref.FindBoneIndex(HandName(Side));if (Hand<0) return false;
    const TCHAR* Prefixes[]={TEXT("thumb"),TEXT("index"),TEXT("middle"),TEXT("ring"),TEXT("pinky")};
    for (int F=0;F<5;++F) for (int J=1;J<=3;++J)
    {
        const FName Name(*FString::Printf(TEXT("%s_%02d_%s"),Prefixes[F],J,Side==0?TEXT("l"):TEXT("r")));
        const int I=Ref.FindBoneIndex(Name),CI=CR.FindBoneIndex(Name);if (I<0||CI<0) return false;
        int P=Ref.GetParentIndex(I),CP=CR.FindBoneIndex(Ref.GetBoneName(P));if (CP<0) return false;
        auto Converted=[&](int B,int CB) { return RefCS[B].GetRelativeTransform(ClipRef[CB])*ClipPose[CB]; };
        auto& B=H.Fingers.AddDefaulted_GetRef();B.Name=Name;B.Finger=F;B.Parent=J==1?-1:H.Fingers.Num()-2;
        // Fold the unchanged metacarpal into the first phalanx for contact FK.
        B.Open=J==1?RefCS[I].GetRelativeTransform(RefCS[Hand]):Ref.GetRefBonePose()[I];
        B.Closed=J==1?Converted(I,CI).GetRelativeTransform(Converted(Hand,CR.FindBoneIndex(HandName(Side)))):Converted(I,CI).GetRelativeTransform(Converted(P,CP));
        B.Closed.SetTranslation(B.Open.GetLocation());B.Local=B.Open;
    }
    const FVector Forward=H.Fingers[6].Open.GetLocation().GetSafeNormal();
    H.Palm=H.Fingers[6].Open.GetLocation()*.5+(Side==0?-FVector::RightVector:FVector::RightVector)*1.2;
    return !Forward.IsNearlyZero();
}
static FTransform GrabTarget(const FHand& H)
{
    const FTransform Frame=TargetFrame(H);const FQuat Q=(Frame.GetRotation()*H.GripRotation).GetNormalized();
    const FVector Surface=Frame.TransformPosition(H.Point),Normal=Frame.TransformVectorNoScale(H.Normal).GetSafeNormal();
    return FTransform(Q,Surface+Normal*.35-Q.RotateVector(H.Palm));
}
static bool BodyHandle(UPrimitiveComponent* C,FName Bone,FProphecyJoltBodyHandle& Out)
{
    if (!C) return false;
    if (auto* Character=C->GetOwner()->FindComponentByClass<UProphecyJoltCharacterComponent>();Character&&Cast<USkeletalMeshComponent>(C))
        return Character->GetBodyHandle(Bone,Out);
    TInlineComponentArray<UProphecyJoltBodyComponent*> Bodies(C->GetOwner());
    for (auto* B:Bodies) if (B->GetSourceComponent()==C) return B->GetBodyHandle(Out);
    if (auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(C->GetWorld())) return Scene->GetBodyHandle(*C,INDEX_NONE,Out);
    return false;
}
static bool Grip(AProphecyAgent* A,int Side,FHand& H)
{
    if (H.Gripped) return true;
    if (A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic) { H.Gripped=true;return true; }
    auto* W=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltBodyHandle Hand,Target;
    if (!W||!BodyHandle(A->GetPoseReferenceMesh(),HandName(Side),Hand)||!BodyHandle(H.Component.Get(),H.Bone,Target)) return false;
    FProphecyJoltBodyState HB,TB;if (!W->ReadBody(Hand,HB).IsSuccess()||!W->ReadBody(Target,TB).IsSuccess()) return false;
    FProphecyJoltJointSettings Joint;Joint.Type=EProphecyJoltJointType::Fixed;Joint.BodyA=Hand;Joint.BodyB=Target;
    const FTransform Anchor(H.Target.GetRotation(),TargetFrame(H).TransformPosition(H.Point));
    Joint.FrameA=Anchor.GetRelativeTransform(FTransform(HB.Rotation,HB.PositionCm));
    Joint.FrameB=Anchor.GetRelativeTransform(FTransform(TB.Rotation,TB.PositionCm));
    const FProphecyJoltBodyPair Pair{Hand,Target};
    if (!W->CreateJoint(Joint,MakeArrayView(&Pair,1),H.Joint).IsSuccess()) return false;
    H.Physics=W;H.Gripped=H.Physical=true;return true;
}
static void PrepareContact(AProphecyAgent* A,int Side,FHand& H)
{
    if(H.Physics.IsValid()||A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic)return;
    auto* W=A->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltBodyHandle Target,Hand,Forearm;
    if(!W||!BodyHandle(H.Component.Get(),H.Bone,Target)||!BodyHandle(A->GetPoseReferenceMesh(),HandName(Side),Hand))return;
    TArray<FProphecyJoltBodyPair,TInlineAllocator<2>> Pairs;Pairs.Add({Hand,Target});
    if(BodyHandle(A->GetPoseReferenceMesh(),Side==0?TEXT("lowerarm_l"):TEXT("lowerarm_r"),Forearm))Pairs.Add({Forearm,Target});
    if(W->UpdateScopedContactRules(&H,Pairs,{}).IsSuccess())H.Physics=W;
}
static void FingerFK(FHand& H,const FTransform& Wrist,float Alpha,int Finger=-1)
{
    const int First=Finger<0?0:Finger*3,End=Finger<0?H.Fingers.Num():First+3;
    for (int I=First;I<End;++I)
    {
        auto& B=H.Fingers[I];
        B.Local=B.Open;B.Local.SetRotation(FQuat::Slerp(B.Open.GetRotation(),B.Closed.GetRotation(),B.Curl*Alpha).GetNormalized());
        B.World=B.Local*(B.Parent<0?Wrist:H.Fingers[B.Parent].World);
    }
}
static bool FingerContact(FHand& H,int Finger,int FirstJoint,const FTransform& Wrist)
{
    FingerFK(H,Wrist,1,Finger);const auto* Shape=H.Collider.Get();if (!Shape) return false;
    const auto Frame=TargetFrame(H);
    for (int J=FirstJoint;J<3;++J)
    {
        const int I=Finger*3+J;const auto& B=H.Fingers[I];const FVector Start=B.World.GetLocation();
        const FVector End=J<2?H.Fingers[I+1].World.GetLocation():Start+B.World.GetRotation().RotateVector(B.Open.GetLocation().GetSafeNormal()*2.0);
        for (int K=0;K<=4;++K)
            if (Shape->GetShortestDistanceToPoint(FMath::Lerp(Start,End,K*.25),Frame,true)<.65) return true;
    }
    return false;
}
static void FitFingers(FHand& H)
{
    H.Contacts=0;
    for (int F=0;F<5;++F)
    {
        bool Contact=false;
        for (int J=0;J<3;++J)
        {
            auto& B=H.Fingers[F*3+J];float Lo=0,Hi=1;
            for (int Step=1;Step<=12;++Step)
            {
                B.Curl=Step/12.f;
                if (FingerContact(H,F,J,H.Target)) { Hi=B.Curl;Contact=true;break; }
                Lo=B.Curl;
            }
            if (Lo<1) for (int Step=0;Step<6;++Step)
            { B.Curl=(Lo+Hi)*.5f;if (FingerContact(H,F,J,H.Target)) Hi=B.Curl;else Lo=B.Curl; }
            B.Curl=Lo;
        }
        H.Contacts+=Contact;
    }
    H.Fitted=true;
}
static void Publish(AProphecyAgent* A,FState& S,const FTransform& Space)
{
    FWriteScopeLock Guard(Lock);auto& P=Outputs.FindOrAdd(S.Id);P.Bones.Reset();P.Fingers.Reset();
    const auto Names=ProphecyNativeReach::BoneNames();
    for (int I=1;I<S.Pose.Num();++I) P.Bones.Add(Names[I],S.Pose[I]*Space);
    const auto& Ref=A->GetPoseReferenceMesh()->GetSkeletalMeshAsset()->GetRefSkeleton();
    for (int K=0;K<2;++K)
    {
        auto& H=S.Hands[K];if ((!H.Enabled||!H.Grab)&&!H.Returning) continue;
        const auto Wrist=S.Pose[Names.IndexOfByKey(HandName(K))]*Space;FingerFK(H,Wrist,H.Close);
        for (const auto& B:H.Fingers)
        {
            FTransform Local=B.Local;
            if (B.Parent<0)
            {
                const int I=Ref.FindBoneIndex(B.Name),Parent=Ref.GetParentIndex(I);
                if (Ref.GetBoneName(Parent)!=HandName(K)) Local=Local.GetRelativeTransform(Ref.GetRefBonePose()[Parent]);
            }
            P.Fingers.Add(B.Name,Local);
            if (S.Debug) { DrawDebugSphere(A->GetWorld(),B.World.GetLocation(),.65,6,FColor::Yellow,false,0,0,.35);if (B.Parent>=0) DrawDebugLine(A->GetWorld(),B.World.GetLocation(),H.Fingers[B.Parent].World.GetLocation(),FColor::Yellow,false,0,0,.5); }
        }
    }
    Any.Store(true);
}
void Update(AProphecyAgent* A,int Id)
{
    auto* Found=States.IsEmpty()?nullptr:States.Find(A);if (!Found) return;auto& S=**Found;
    if (S.Frame==GFrameCounter||!A->GetWorld()||A->GetWorld()->IsPaused()) return;S.Frame=GFrameCounter;S.Id=Id;
    ProphecySwordHolsterPose::FStatus Holster;
    if (ProphecySwordHolsterPose::Status(A,Holster)&&!Holster.Finished) { Remove(A);return; }
    if (!BasePose(A,S)) { Remove(A);return; }
    const auto Space=A->GetAgentMesh()->GetComponentTransform();const auto Names=ProphecyNativeReach::BoneNames();
    if (S.Returning)
    {
        const float PreviousT=FMath::Clamp(S.ReturnTime/S.ReturnDuration,0.f,1.f);
        S.ReturnTime+=Dt;const float T=FMath::Clamp(S.ReturnTime/S.ReturnDuration,0.f,1.f);
        if (T>=1) { Remove(A);return; }
        S.Pose.SetNum(S.Ordered.Num());const float Alpha=T*T*(3-2*T);
        // Keep the solver's body offset consistent if reaching resumes mid-return.
        const float PreviousAlpha=PreviousT*PreviousT*(3-2*PreviousT);
        for(auto& V:S.Solver.Body)V*=(1-Alpha)/FMath::Max(1.e-6f,1-PreviousAlpha);
        for(auto& H:S.Hands)H.Close=H.ReturnClose*(1-Alpha);
        for (int I=0;I<S.Pose.Num();++I)
        {
            const int P=S.Parents[I];auto From=S.ReturnStart[I],To=S.Ordered[I];
            if (P>=0) { From=From.GetRelativeTransform(S.ReturnStart[P]);To=To.GetRelativeTransform(S.Ordered[P]); }
            S.Pose[I].Blend(From,To,Alpha);if (P>=0) S.Pose[I]=S.Pose[I]*S.Pose[P];
        }
        Publish(A,S,Space);return;
    }
    FVector Targets[2];float Speeds[2];bool Enabled[2];
    for (int K=0;K<2;++K)
    {
        auto& H=S.Hands[K];
        if (H.Grab&&(!H.Component.IsValid()||!H.Collider.IsValid()||(H.Physical&&(!H.Physics.IsValid()||!H.Physics->OwnsJoint(H.Joint)))))
        { BeginHandReturn(S,K,.25f);Drop(H);H.Enabled=false;H.Grab=false; }
        if (H.Grab) { PrepareContact(A,K,H);H.Target=GrabTarget(H); }
        Enabled[K]=H.Enabled;Targets[K]=Space.InverseTransformPosition(H.Target.GetLocation());Speeds[K]=H.Speed;
    }
    if (!Enabled[0]&&!Enabled[1]) { UProphecyReachLibrary::StopReaching(A);return; }
    const auto Mode=Enabled[0]?(Enabled[1]?EProphecyDoubleReachMode::Both:EProphecyDoubleReachMode::Left):EProphecyDoubleReachMode::Right;
    if (!ProphecyNativeReach::Step(S.Ordered,Mode,Targets,Speeds,S.Solver,S.Pose,Dt)) { Remove(A);return; }
    for(int K=0;K<2;++K)
    {
        auto& H=S.Hands[K];if(!H.Returning)continue;
        H.ReturnTime+=Dt;const float T=FMath::Clamp(H.ReturnTime/H.ReturnDuration,0.f,1.f),Alpha=T*T*(3-2*T);
        FTransform Destinations[4];
        for(int J=0;J<4;++J){const int I=ArmIndex(K,J);Destinations[J]=S.Pose[I].GetRelativeTransform(S.Pose[S.Parents[I]]);}
        for(int J=0;J<4;++J){const int I=ArmIndex(K,J);FTransform Local;Local.Blend(H.ReturnLocal[J],Destinations[J],Alpha);S.Pose[I]=Local*S.Pose[S.Parents[I]];}
        H.Close=H.ReturnClose*(1-Alpha);if(T>=1)H.Returning=false;
    }
    for (int K=0;K<2;++K) if (Enabled[K])
    {
        auto& H=S.Hands[K];const int Hand=Names.IndexOfByKey(HandName(K));
        const double Angle=H.Rotation.AngularDistance(H.Target.GetRotation()),Step=FMath::DegreesToRadians(H.RotationSpeed)*Dt;
        H.Rotation=FQuat::Slerp(H.Rotation,H.Target.GetRotation(),Angle>1.e-9?FMath::Min(1.,Step/Angle):1.).GetNormalized();
        S.Pose[Hand].SetRotation((Space.GetRotation().Inverse()*H.Rotation).GetNormalized());
        const FTransform Wrist=S.Pose[Hand]*Space;
        H.Distance=FVector::Distance(Wrist.GetLocation(),H.Target.GetLocation());
        if (H.Grab)
        {
            if (!H.Fitted) FitFingers(H);
            if (H.Distance<3&&Angle<FMath::DegreesToRadians(8.)) H.Close=FMath::Min(1.f,H.Close+float(Dt/.2));
            const FTransform Actual=A->GetPoseReferenceMesh()->GetSocketTransform(HandName(K));
            if (!H.Gripped&&H.Close>=1&&H.Distance<1.25&&FVector::Distance(Actual.GetLocation(),H.Target.GetLocation())<2&&Actual.GetRotation().AngularDistance(H.Target.GetRotation())<FMath::DegreesToRadians(6.)) Grip(A,K,H);
        }
        if (S.Debug)
        {
            DrawDebugCoordinateSystem(A->GetWorld(),Wrist.GetLocation(),Wrist.Rotator(),8,false,0,0,.5);
            DrawDebugSphere(A->GetWorld(),H.Grab?TargetFrame(H).TransformPosition(H.Point):H.Target.GetLocation(),1.1,8,H.Gripped?FColor::Green:FColor::Cyan,false,0,0,.7);
        }
    }
    if (S.Debug) for (int I=2;I<S.Pose.Num();++I) if (S.Parents[I]>=0) DrawDebugLine(A->GetWorld(),(S.Pose[I]*Space).GetLocation(),(S.Pose[S.Parents[I]]*Space).GetLocation(),FColor::Cyan,false,0,0,.6);
    Publish(A,S,Space);
}
static bool StartGrab(AProphecyAgent* A,int Side,UPrimitiveComponent* C,FName Bone,FVector Point,bool Explicit,float Speed,float RotationSpeed)
{
    if (!ValidHand(Side)||!IsValid(C)||!IsValid(A)||!A->GetPoseReferenceMesh()||C->GetWorld()!=A->GetWorld()||C->GetOwner()==A||Point.ContainsNaN()||!FMath::IsFinite(Speed)||Speed<=0||!FMath::IsFinite(RotationSpeed)||RotationSpeed<=0) return false;
    UBodySetup* Shape=Collider(C,Bone);if (!Shape||Shape->AggGeom.SphereElems.Num()+Shape->AggGeom.SphylElems.Num()+Shape->AggGeom.BoxElems.Num()+Shape->AggGeom.ConvexElems.Num()==0) return false;
    if(A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)
    { FProphecyJoltBodyHandle Target;if(!BodyHandle(C,Bone,Target))return false; }
    // Repeated Blueprint calls must not rebuild the finger references or restart closure.
    if(auto* ExistingState=States.Find(A))
    {
        auto& Existing=(*ExistingState)->Hands[Side];
        if(Existing.Enabled&&Existing.Grab&&Existing.Component==C&&Existing.Bone==Bone&&(!Explicit||TargetFrame(Existing).InverseTransformPosition(Point).Equals(Existing.Point,.01)))
        { Existing.Speed=Speed;Existing.RotationSpeed=RotationSpeed;return true; }
    }
    FHand H;H.Component=C;H.Bone=Bone;H.Collider=Shape;H.Speed=Speed;H.RotationSpeed=RotationSpeed;H.Enabled=H.Grab=true;
    const FTransform Frame=TargetFrame(H);FVector Closest,Normal;
    if (!BuildFingers(A->GetPoseReferenceMesh()->GetSkeletalMeshAsset(),A->ClosedFistAnimation.LoadSynchronous(),Side,H)) return false;
    const FTransform Wrist=A->GetPoseReferenceMesh()->GetSocketTransform(HandName(Side));
    if (!Explicit) Point=Wrist.TransformPosition(H.Palm);
    // Query just outside a supplied point so primitive interior conventions do not erase its normal.
    const FVector Probe=Explicit?Point+(Wrist.GetLocation()-Point).GetSafeNormal()*.05:Point;
    const float Distance=Shape->GetClosestPointAndNormal(Probe,Frame,Closest,Normal,true);
    if (!FMath::IsFinite(Distance)||Distance==FLT_MAX||Normal.IsNearlyZero()) return false;
    if (!Explicit) Point=Closest;
    H.Point=Frame.InverseTransformPosition(Point);H.Normal=Frame.InverseTransformVectorNoScale(Normal).GetSafeNormal();
    const FVector LocalForward=H.Fingers[6].Open.GetLocation().GetSafeNormal(),LocalNormal=Side==0?-FVector::RightVector:FVector::RightVector;
    FVector Forward=FVector::VectorPlaneProject(FVector::UpVector,Normal).GetSafeNormal();
    if (Forward.IsNearlyZero()) Forward=FVector::VectorPlaneProject(A->GetActorForwardVector(),Normal).GetSafeNormal();
    const FQuat Desired=(FRotationMatrix::MakeFromXZ(Forward,-Normal).ToQuat()*FRotationMatrix::MakeFromXZ(LocalForward,LocalNormal).ToQuat().Inverse()).GetNormalized();
    H.GripRotation=(Frame.GetRotation().Inverse()*Desired).GetNormalized();H.Rotation=Wrist.GetRotation();H.Target=GrabTarget(H);
    // A curl can stop at contact, but cannot undo an already intersecting open thumb.
    // Find the minimum outward wrist clearance once; preserve the requested surface point.
    const FVector Palm=H.Palm,LocalNormalOut=Desired.UnrotateVector(Normal);
    auto ClearAt=[&](float Offset)
    {
        H.Palm=Palm-LocalNormalOut*Offset;H.Target=GrabTarget(H);
        for(int F=0;F<5;++F)if(FingerContact(H,F,0,H.Target))return false;
        return true;
    };
    if(!ClearAt(0))
    {
        float Lo=0,Hi=4;if(!ClearAt(Hi))return false;
        for(int I=0;I<8;++I){const float Mid=(Lo+Hi)*.5f;if(ClearAt(Mid))Hi=Mid;else Lo=Mid;}
        ClearAt(Hi);
    }
    auto* S=Admit(A);if (!S) return false;
    auto& Existing=S->Hands[Side];
    SeedHand(A,*S,Side);Drop(Existing);Existing=MoveTemp(H);return true;
}
}

bool UProphecyReachLibrary::ReachTarget(AProphecyAgent* A,EProphecyReachHand Hand,FTransform Target,float Speed,float RotationSpeed)
{
    using namespace ProphecyReach;
    if (!ValidHand(int(Hand))||Target.ContainsNaN()||!Target.GetRotation().IsNormalized()||!FMath::IsFinite(Speed)||Speed<=0||!FMath::IsFinite(RotationSpeed)||RotationSpeed<=0) return false;
    auto* S=Admit(A);if (!S) return false;auto& H=S->Hands[int(Hand)];
    SeedHand(A,*S,int(Hand));
    if (H.Grab) { Drop(H);H.Grab=false;H.Fingers.Reset(); }
    H.Enabled=true;H.Target=Target;H.Target.NormalizeRotation();H.Speed=Speed;H.RotationSpeed=RotationSpeed;return true;
}
bool UProphecyReachLibrary::DoubleReach(AProphecyAgent* A,EProphecyDoubleReachMode Mode,FTransform L,FTransform R,float Speed,float RotationSpeed)
{
    if (Mode==EProphecyDoubleReachMode::Off) { StopReaching(A);return true; }
    const bool Left=Mode==EProphecyDoubleReachMode::Left||Mode==EProphecyDoubleReachMode::Both;
    const bool Right=Mode==EProphecyDoubleReachMode::Right||Mode==EProphecyDoubleReachMode::Both;
    if((!Left&&!Right)||(Left&&(L.ContainsNaN()||!L.GetRotation().IsNormalized()))||(Right&&(R.ContainsNaN()||!R.GetRotation().IsNormalized()))||!FMath::IsFinite(Speed)||Speed<=0||!FMath::IsFinite(RotationSpeed)||RotationSpeed<=0||!ProphecyReach::Admit(A))return false;
    if (!Left) ReleaseGrab(A,EProphecyReachHand::Left);
    if (!Right) ReleaseGrab(A,EProphecyReachHand::Right);
    return (!Left||ReachTarget(A,EProphecyReachHand::Left,L,Speed,RotationSpeed))&&(!Right||ReachTarget(A,EProphecyReachHand::Right,R,Speed,RotationSpeed));
}
bool UProphecyReachLibrary::GrabObject(AProphecyAgent* A,EProphecyReachHand H,UPrimitiveComponent* C,float S,bool Explicit,FVector Point,float R)
{ return ProphecyReach::StartGrab(A,int(H),C,NAME_None,Point,Explicit,S,R); }
bool UProphecyReachLibrary::GrabBone(AProphecyAgent* A,EProphecyReachHand H,USkeletalMeshComponent* M,FName Bone,FVector Point,float S,float R)
{ return !Bone.IsNone()&&M&&M->GetBoneIndex(Bone)>=0&&ProphecyReach::StartGrab(A,int(H),M,Bone,Point,true,S,R); }
void UProphecyReachLibrary::ReleaseGrab(AProphecyAgent* A,EProphecyReachHand Hand,float Seconds)
{
    if(!ProphecyReach::ValidHand(int(Hand)))return;
    if (auto* P=ProphecyReach::States.Find(A))
    {
        auto& S=**P;auto& H=S.Hands[int(Hand)];ProphecyReach::BeginHandReturn(S,int(Hand),Seconds);ProphecyReach::Drop(H);H.Enabled=false;H.Grab=false;
        if (!S.Hands[0].Enabled&&!S.Hands[1].Enabled) StopReaching(A,Seconds);
    }
}
void UProphecyReachLibrary::StopReaching(AProphecyAgent* A,float Seconds)
{
    if (auto* P=ProphecyReach::States.Find(A))
    {
        auto& S=**P;if (S.Returning) return;
        for(int K=0;K<2;++K){auto& H=S.Hands[K];ProphecyReach::BeginHandReturn(S,K,Seconds);ProphecyReach::Drop(H);H.Enabled=false;}
        if (Seconds<=0||!FMath::IsFinite(Seconds)||S.Pose.IsEmpty()) { ProphecyReach::Remove(A);return; }
        S.Returning=true;S.ReturnTime=0;S.ReturnDuration=Seconds;S.ReturnStart=S.Pose;
    }
}
FProphecyGrabStatus UProphecyReachLibrary::GetGrabStatus(AProphecyAgent* A,EProphecyReachHand Hand)
{
    FProphecyGrabStatus Out;
    if(!ProphecyReach::ValidHand(int(Hand)))return Out;
    if (const auto* S=ProphecyReach::States.Find(A))
    {
        const auto& H=(*S)->Hands[int(Hand)];Out.Active=H.Enabled;Out.Gripped=H.Gripped;Out.PhysicalGrip=H.Physical;
        Out.DistanceCm=H.Distance;Out.ContactFingers=H.Contacts;Out.SurfacePoint=H.Grab?ProphecyReach::TargetFrame(H).TransformPosition(H.Point):H.Target.GetLocation();
    }
    return Out;
}
void UProphecyReachLibrary::SetReachVisualization(AProphecyAgent* A,bool Enabled)
{ if (auto* S=ProphecyReach::States.Find(A)) (*S)->Debug=Enabled; }

#include "Tests/ProphecyReachTests.inl"
#include "Tests/ProphecyReachProbe.inl"
