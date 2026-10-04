namespace
{
FTransform HandInertiaRoot(const FVector3f& P,float Yaw)
{ return FTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),TrainingToUnreal(P)); }
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
    SetForearmRollFromUpperArm(Impl.UpperLocalOffsets[A.End],I,Pose[A.Start],Pose[A.Mid],Pose[A.End]);
    return true;
}
}
