// Included after the manager's existing pose codec. Bodyflip is an opt-in pose
// owner; inactive lanes never enter this path and their wiring/tuning is intact.
namespace
{
bool PublishBodyflipPose(AProphecyNNLocomotionManager::FImpl& Impl,int32 Index,
    AProphecyAgent* Actor,int32 PoseId,double SourceTime)
{
    FVector Position,Velocity;float YawDegrees=0;
    if(!ProphecyBodyflip::Root(Actor,Position,YawDegrees,&Velocity))return false;
    auto& A=Impl.Agents[Index];const FVector3f Root=UnrealToTraining(Position);
    const FVector3f Speed=UnrealToTraining(Velocity);const float Yaw=-FMath::DegreesToRadians(YawDegrees);
    const FTransform Carrier=GetUpCarrier(Actor,Root,Yaw);
    auto Previous=TransformSlice(Impl.PreviousComponentTransformBuffer,Index);
    auto Current=TransformSlice(Impl.ComponentTransformBuffer,Index);
    auto Local=TransformSlice(Impl.LocalTransformBuffer,Index);
    if(!ProphecyBodyflip::Apply(Actor,Impl.PublishedBoneNames,Impl.Parents,
        Previous,Current,Local,Carrier,SourceTime))return false;
    // Apply supplies both world histories in this same carrier. Recurrence is
    // then rebased into its actual preceding root, retaining incoming velocity.
    A.PreviousPublishedRoot=A.PublishedRoot=A.CurRootPos=Root;
    FVector PreviousRoot=Position;float PreviousYaw=YawDegrees;
    ProphecyBodyflip::History(Actor,PreviousRoot,PreviousYaw);
    A.PrevRootPos=UnrealToTraining(PreviousRoot);
    A.PreviousPublishedYaw=A.PublishedYaw=A.CurRootYaw=Yaw;
    A.PrevRootYaw=-FMath::DegreesToRadians(PreviousYaw);
    A.MoverState.position={Root.X,Root.Z};A.MoverState.velocity={Speed.X,Speed.Z};
    A.MoverState.yaw_radians=A.MoverState.previous_yaw_radians=Yaw;
    A.MoverIntent.orientation_yaw_radians=Yaw;
    A.bHasAppliedVisualRoot=true;A.bPhysicalWorldBlockedPending=false;
    A.PublishedPoseTimeSeconds=SourceTime;
    CommitGetUpPose(Impl,Index,Previous,Current);
    FProphecyNNPoseStore::SetAgentLocalPose(PoseId,Impl.PublishedBoneNames,Local,
        Previous,Current,Carrier,Carrier,SourceTime,true,false,0,FVector2D::ZeroVector,
        FProphecyNNFixedArms(),false,false);
    ProphecyNNPresentation::Publish(PoseId,SourceTime,1.f);
    return true;
}
}
