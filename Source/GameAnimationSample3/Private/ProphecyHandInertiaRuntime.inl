namespace
{
FTransform HandInertiaRoot(const FVector3f& P,float Yaw)
{ return FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),TrainingToUnreal(P)); }
FTransform HandInertiaCarrier(const AProphecyAgent* Actor,const FTransform& Root)
{
    FTransform Capsule=Root;
    Capsule.AddToTranslation(FVector::UpVector*Actor->GetAgentCapsule()->GetScaledCapsuleHalfHeight());
    return (Actor->bManualNNPoseApplication ? Actor->GetAgentMesh()->GetRelativeTransform()
        : Actor->GetAuthoredMeshRelativeTransform())*Capsule;
}
void StoreInertiaArm(const AProphecyNNLocomotionManager::FImpl& Impl,int32 I,
    TArrayView<const FTransform> Pose,const FMat3f& Heading,float* Upper)
{
    const auto& A=Impl.UpperArms[I]; const int32 O=60+15*I;
    WriteStateVec3(Upper,O,TransformRow(LocalUnrealToTraining(Pose[A.End].GetLocation()),Heading));
    WriteRot6(Multiply(MirrorYBasis(QuatToMatrix(Pose[A.End].GetRotation())),Heading),Upper+O+3);
    WriteRot6(Multiply(MirrorYBasis(QuatToMatrix(Pose[A.Start].GetRotation())),Heading),Upper+O+9);
}
bool CorrectInertiaArm(const AProphecyNNLocomotionManager::FImpl& Impl,AProphecyAgent* Actor,int32 I,
    float W,bool Attack,double Time,double Dt,const FTransform& PreviousRoot,const FTransform& Root,
    const FTransform& PreviousHand,const FTransform& Carrier,TArrayView<FTransform> Pose)
{
    const auto& A=Impl.UpperArms[I];
    FTransform Shoulder=Pose[A.Start]*Carrier,Elbow=Pose[A.Mid]*Carrier,Wrist=Pose[A.End]*Carrier;
    const FVector Pole=Shoulder.GetRotation().RotateVector(LocalTrainingToUnreal(A.LocalPoleAxes[0]));
    if (!ProphecyHandInertia::Apply(Actor,I,W,Attack,Time,Dt,PreviousRoot,Root,PreviousHand,
        Shoulder,Elbow,Wrist,Pole,A.Lengths.Y*100.)) return false;
    Pose[A.Start]=Shoulder.GetRelativeTransform(Carrier);
    Pose[A.Mid]=Elbow.GetRelativeTransform(Carrier);
    Pose[A.End]=Wrist.GetRelativeTransform(Carrier);
    // Use the same hand-derived forearm twist as the ordinary decoder.
    const FMat3f Forearm=ForearmRotationFromHand(Impl.UpperLocalOffsets[A.End],
        LocalUnrealToTraining(Pose[A.End].GetLocation()-Pose[A.Mid].GetLocation()),A.LocalPoleAxes[1],
        MirrorYBasis(QuatToMatrix(Pose[A.End].GetRotation())));
    Pose[A.Mid].SetRotation(MatrixToQuat(MirrorYBasis(Forearm)));
    return true;
}
void CorrectLocomotionHands(AProphecyNNLocomotionManager::FImpl* Impl,AProphecyAgent* Actor,int32 Index,double Time,double Dt)
{
    auto& Agent=Impl->Agents[Index];
    float* Upper=UpperStateSlice(Impl->UpperCurrentStateBuffer,Index);
    FTransform Pose[FullBodyBoneCount],Previous[FullBodyBoneCount];
    const FLocomotionClamps Unclamped;
    DecodeLocomotionPose(Impl,StateSlice(Impl->PublishedStateBuffer,Index),Upper,
        Agent.PublishedWalkWeight,MakeArrayView(Pose),nullptr,Unclamped);
    DecodeLocomotionPose(Impl,StateSlice(Impl->PreviousPublishedStateBuffer,Index),
        UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer,Index),Agent.PreviousPublishedWalkWeight,
        MakeArrayView(Previous),nullptr,Unclamped);
    const FTransform Root=HandInertiaRoot(Agent.PublishedRoot,Agent.PublishedYaw);
    const FTransform PrevRoot=HandInertiaRoot(Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw);
    const FTransform Carrier=HandInertiaCarrier(Actor,Root),PrevCarrier=HandInertiaCarrier(Actor,PrevRoot);
    for (int32 I=0; I<2; ++I)
        if (CorrectInertiaArm(*Impl,Actor,I,Agent.PublishedWalkWeight,false,Time,Dt,PrevRoot,Root,
            Previous[Impl->UpperArms[I].End]*PrevCarrier,Carrier,MakeArrayView(Pose)))
            StoreInertiaArm(*Impl,I,MakeArrayView(Pose),Impl->SeedRootRot,Upper);
}
}
