// Included after GetUpRuntime: uses the same NN pose/history encoder.
#include "ProphecyRobotLocomotion.h"
namespace
{
struct FRobotReturnPose
{
    uint64 Start=0,Sample=MAX_uint64;
    FTransform Initial[25],PreviousLocal[25],Last[25],Current[25];
};
TMap<TWeakObjectPtr<const AProphecyAgent>,FRobotReturnPose> RobotReturns;
FDelegateHandle RobotReturnCleanup;
float RobotReturnPresentationAlpha(const AProphecyAgent* Actor,float Alpha)
{
    const auto* S=RobotReturns.Find(Actor);
    return S&&S->Sample==S->Start?1.f:Alpha;
}
bool ApplyRobotReturn(AProphecyNNLocomotionManager::FImpl& Impl,int32 I,const AProphecyAgent* Actor,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local)
{
    auto* S=RobotReturns.Find(Actor);if(!S)return false;
    const auto C=ProphecyRobot::ReturnSettings(Actor);
    const float Time=float(Impl.GameTick-S->Start)/60.f;
    if(S->Sample!=Impl.GameTick)
    {
        if(S->Sample!=MAX_uint64)for(int32 B=0;B<25;++B)S->Last[B]=S->Current[B];
        for(int32 B=0;B<25;++B)
        {
            const int32 Parent=Impl.Parents[B];bool Lower=B==0;
            for(const auto& L:Impl.Limbs)Lower|=B==L.Start||B==L.Mid||B==L.End||B==L.Toe;
            const float Duration=Lower?C.Lower:C.Upper;
            const float Elapsed=Lower?Time-C.LowerHold:Time;
            float T=Elapsed<0?0.f:Duration>0?FMath::Clamp(Elapsed/Duration,0.f,1.f):1.f;
            if(Lower)T=T*T*(3-2*T);
            if(!Lower)
            {
                T=C.Hold>=1?(T>=1?1.f:0.f):FMath::Clamp((T-C.Hold)/(1-C.Hold),0.f,1.f);
                T=FMath::Pow(T,C.Coefficient);T=FMath::Lerp(T,T*T*T*(T*(T*6-15)+10),C.Easing);
            }
            FTransform Source=S->Initial[B];
            if(!Lower&&C.Inertia>0&&T<1)
            {
                FQuat Delta=(S->Initial[B].GetRotation()*S->PreviousLocal[B].GetRotation().Inverse()).GetNormalized();if(Delta.W<0)Delta=-Delta;
                // Finite parent-local momentum, decaying as the NN takes over.
                Source.SetRotation((FQuat::MakeFromRotationVector(Delta.ToRotationVector()*(30.f*Time*C.Inertia*(1-T)))*Source.GetRotation()).GetNormalized());
            }
            const FTransform Candidate=Parent<0?Current[B]:Current[B].GetRelativeTransform(Current[Parent]);
            FTransform Mixed;Mixed.Blend(Source,Candidate,T);Mixed.NormalizeRotation();
            S->Current[B]=Parent<0?Mixed:Mixed*S->Current[Parent];
        }
        S->Sample=Impl.GameTick;
    }
    for(int32 B=0;B<25;++B)
    {
        Previous[B]=S->Last[B];Current[B]=S->Current[B];const int32 P=Impl.Parents[B];
        Local[B]=P<0?Current[B]:Current[B].GetRelativeTransform(Current[P]);
    }
    CommitGetUpPose(Impl,I,Previous,Current);
    if(Time>=FMath::Max(C.Lower+C.LowerHold,C.Upper))RobotReturns.Remove(Actor);
    return true;
}
}
void ProphecyRobot::ForgetReturn(const AProphecyAgent* A){RobotReturns.Remove(A);}
bool AProphecyNNLocomotionManager::SeedLocomotionFromPhysical(FProphecyAgentHandle Handle,const FVector& COM,
    const FVector& Velocity,float YawRadiansPerSecond,FString& Error)
{
    auto* Actor=ResolveAgent(Handle);
    if(!Impl||!Impl->bInitialized||!Actor||IsSimBridgeActive()||COM.ContainsNaN()||Velocity.ContainsNaN()||!FMath::IsFinite(YawRadiansPerSecond))
    {Error=TEXT("NN physical handoff requires a valid registered native agent and finite COM motion.");return false;}
    auto* Mesh=Actor->GetAgentMesh();const auto* P=ProphecyRobot::Profile(Error);if(!Mesh||!P)return false;
    FTransform World[25],PreviousWorld[25];
    if(!Actor->SampleActualComponentPose(Impl->PublishedBoneNames,MakeArrayView(World)))
    {Error=TEXT("Cannot sample the physical handoff pose.");return false;}
    const auto* PhysicalMesh=Actor->GetPoseReferenceMesh();
    if(!PhysicalMesh||!PhysicalMesh->GetSkeletalMeshAsset()){Error=TEXT("No physical skeleton for robot exit.");return false;}
    const auto& Skeleton=PhysicalMesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    for(int32 B=0;B<25;++B)
    {
        World[B]=World[B]*Mesh->GetComponentTransform();int32 Group=INDEX_NONE;
        for(int32 Bone=Skeleton.FindBoneIndex(Impl->PublishedBoneNames[B]);Bone!=INDEX_NONE&&Group==INDEX_NONE;Bone=Skeleton.GetParentIndex(Bone))
            Group=P->Bodies.IndexOfByPredicate([&](const auto& Spec){return Spec.Aliases.Contains(Skeleton.GetBoneName(Bone));});
        if(Group==INDEX_NONE){Error=TEXT("Handoff bone has no physical robot parent.");return false;}
        FTransform Body;FVector V,W;bool Sim=false;
        if(!Actor->GetPhysicalBodyState(P->Bodies[Group].Bone,Body,V,W,Sim))return false;
        const FVector Center=Body.TransformPosition(P->Bodies[Group].MassFrame.GetLocation());
        const FQuat Back=FQuat::MakeFromRotationVector(-W/30.);
        PreviousWorld[B]=FTransform((Back*World[B].GetRotation()).GetNormalized(),Center-V/30.+Back.RotateVector(World[B].GetLocation()-Center),World[B].GetScale3D());
    }
    StopAgentNNDefense(Handle);StopAgentNNAttack(Handle);
    if(ResolveAgent(Handle)!=Actor){Error=TEXT("Agent was removed during handoff callbacks.");return false;}
    auto& A=Impl->Agents[Handle.Index];
    ProphecyGetUp::Cancel(Actor);ProphecyArmedPose::Cancel(Actor);ProphecyFKReturn::Cancel(Actor);ProphecyAttackRecovery::Cancel(Actor);
    ProphecyLowerTempering::Remove(Actor);ProphecyHandRecovery::CancelMotion(Actor);ProphecyCoreTempering::CancelMotion(Actor);
    ProphecyUpperBodyInertia::Cancel(Actor);ProphecySlashReturn::Cancel(Actor);ProphecyLegRecovery::Cancel(Actor);
    ProphecyWalkPinning::ResetSmoothing(Actor);ProphecyRootBalance::ResetMotion(Actor);
    ProphecyPelvisInertia::ResetMotion(Actor);ProphecyHandInertia::ResetMotion(Actor);
    A.AnimationLayer.Reset();Actor->ActiveNNAnimationLayerAsset=nullptr;
    const FVector OldRoot=TrainingToUnreal(A.PublishedRoot);
    const FVector3f Root=UnrealToTraining(FVector(COM.X,COM.Y,OldRoot.Z));
    const FVector3f RootVelocity=UnrealToTraining(FVector(Velocity.X,Velocity.Y,0));
    const float Yaw=-FMath::DegreesToRadians(Actor->GetActorRotation().Yaw),YawRate=-YawRadiansPerSecond;
    A.CurRootPos=A.PublishedRoot=Root;A.PrevRootPos=A.PreviousPublishedRoot=Root-RootVelocity/30.f;
    A.CurRootYaw=A.PublishedYaw=Yaw;A.PrevRootYaw=A.PreviousPublishedYaw=Yaw-YawRate/30.f;
    A.MoverState={};A.MoverState.position={Root.X,Root.Z};A.MoverState.velocity={RootVelocity.X,RootVelocity.Z};
    A.MoverState.yaw_radians=Yaw;A.MoverState.previous_yaw_radians=Yaw-YawRate/30.f;
    A.MoverIntent.orientation_yaw_radians=Yaw;A.bHasPhysicalSample=false;A.PinProbability=FVector2f::ZeroVector;
    if(auto* W=ProphecyNNRootWindow::Find(Actor)){const auto Factors=W->Factors;*W={};W->Factors=Factors;}
    const FTransform Carrier=GetUpCarrier(Actor,Root,Yaw),PreviousCarrier=GetUpCarrier(Actor,A.PreviousPublishedRoot,A.PreviousPublishedYaw);
    FTransform Current[25],Previous[25];FRobotReturnPose Return;Return.Start=Impl->GameTick;
    for(int32 B=0;B<25;++B)
    {
        Current[B]=World[B].GetRelativeTransform(Carrier);Previous[B]=PreviousWorld[B].GetRelativeTransform(PreviousCarrier);
        const int32 Parent=Impl->Parents[B];Return.Initial[B]=Parent<0?Current[B]:Current[B].GetRelativeTransform(Current[Parent]);
        Return.PreviousLocal[B]=Parent<0?Previous[B]:Previous[B].GetRelativeTransform(Previous[Parent]);
        Return.Last[B]=Previous[B];Return.Current[B]=Current[B];
    }
    CommitGetUpPose(*Impl,Handle.Index,MakeArrayView(Previous),MakeArrayView(Current));
    if(!RobotReturnCleanup.IsValid())RobotReturnCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {for(auto It=RobotReturns.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();});
    RobotReturns.Add(Actor,MoveTemp(Return));PublishAgentPose(Handle.Index,A.PublishedPoseTimeSeconds);
    // History is needed by inference, but the ownership transfer displays the captured current pose.
    ProphecyNNPresentation::Publish(PoseStoreAgentBase+Handle.Index,A.PublishedPoseTimeSeconds,1.f);
    return true;
}
