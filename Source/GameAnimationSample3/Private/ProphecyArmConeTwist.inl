// Included inside ProphecyArmCone. Separate allocations preserve Live Coding state layouts.
struct FTwistConfig { double Limit=90,Strength=100,Damping=20; };
struct FTwistArm
{
    FQuat Reference=FQuat::Identity;
    FVector LocalAxis=FVector::ForwardVector,LocalRadial=FVector::UpVector;
    double AcceptedAngle=0,Offset=0,Velocity=0;
    bool Ready=false;
};
struct FTwistState { FTwistArm Arm[2]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTwistConfig> TwistConfigs,TwistBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTwistState> TwistStates;

static double UnwrapTwist(double Wrapped,double Near)
{ return Near+FMath::UnwindRadians(Wrapped-Near); }
static bool SeedTwist(FTwistArm& S,const FTransform& Spine,const FTransform& Lower,const FTransform& Hand,
    const FVector& SpineLocalUp=FVector::ForwardVector)
{
    const FVector Axis=(Hand.GetLocation()-Lower.GetLocation()).GetSafeNormal();
    if(Axis.IsNearlyZero()) return false;
    S.Reference=(Spine.GetRotation().Inverse()*Hand.GetRotation()).GetNormalized();
    // Horizontal torso turn: use anatomical spine-up, NOT the outgoing forearm.
    // This skeleton's spine-up is near local +X, not Unreal's world +Z.
    S.LocalAxis=SpineLocalUp.GetSafeNormal(1.e-12,FVector::ForwardVector);
    S.LocalRadial=Lower.GetRotation().UnrotateVector(Axis);
    S.Ready=true;return true;
}
static double WristAngle(const FTwistArm& S,const FQuat& SpineLocalWrist,double Near)
{
    const FQuat Delta=(SpineLocalWrist*S.Reference.Inverse()).GetNormalized();
    const double Projection=FVector::DotProduct(FVector(Delta.X,Delta.Y,Delta.Z),S.LocalAxis);
    // A pure 180 degree swing has no observable twist. Retain continuity there.
    if(Projection*Projection+Delta.W*Delta.W<1.e-12)return Near;
    return UnwrapTwist(2*FMath::Atan2(Projection,Delta.W),Near);
}
static bool MeasureTwist(const FTwistArm& S,const FTransform& Spine,const FTransform& Lower,
    const FTransform& Hand,FVector& Axis,FVector& ReferenceRadial,FVector& ActualRadial,double& Angle)
{
    const FQuat Local=(Spine.GetRotation().Inverse()*Hand.GetRotation()).GetNormalized();
    Angle=WristAngle(S,Local,S.AcceptedAngle);
    Axis=Spine.GetRotation().RotateVector(S.LocalAxis);
    const FVector Basis=FMath::Abs(S.LocalAxis.Z)<.8?FVector::UpVector:FVector::RightVector;
    const FVector Radial=(Basis-S.LocalAxis*FVector::DotProduct(Basis,S.LocalAxis)).GetSafeNormal();
    ReferenceRadial=Spine.GetRotation().RotateVector(Radial);
    ActualRadial=FQuat(Axis,Angle).RotateVector(ReferenceRadial);
    return true;
}
// Stop along the actual spine-local wrist quaternion step. Counter-rotating about
// the moving forearm axis instead can tip a bent wrist (and sword) upward.
static double DampedWristAngle(double Previous,double Proposed,const FTwistConfig& C,double Dt)
{
    const double Limit=FMath::DegreesToRadians(C.Limit);
    if(Proposed>Limit && Proposed>Previous)
    {const double Start=FMath::Max(Limit,Previous);return Start+(Proposed-Start)/(1+C.Damping*Dt);}
    if(Proposed<-Limit && Proposed<Previous)
    {const double Start=FMath::Min(-Limit,Previous);return Start+(Proposed-Start)/(1+C.Damping*Dt);}
    return Proposed;
}
static FQuat AcceptWristStep(const FTwistArm& S,const FQuat& Previous,FQuat Proposed,
    double PreviousAngle,double ProposedAngle,double AcceptedAngle,const FTwistConfig& C,double Weight,double Dt)
{
    if((Previous|Proposed)<0)Proposed=Proposed*-1.;
    const double DampedAngle=FMath::Lerp(ProposedAngle,DampedWristAngle(PreviousAngle,ProposedAngle,C,Dt),Weight);
    auto StopStep=[&]() -> FQuat
    {
        const double Delta=ProposedAngle-PreviousAngle;
        if(FMath::Abs(Delta)<1.e-8 && FMath::Abs(ProposedAngle)>=FMath::DegreesToRadians(C.Limit)-1.e-8 && C.Damping>0)
            return FQuat::Slerp(Previous,Proposed,1-Weight+Weight/(1+C.Damping*Dt)).GetNormalized();
        if(FMath::Abs(DampedAngle-ProposedAngle)<1.e-10)return Proposed;
        if(FMath::Abs(Delta)>1.e-8 && (DampedAngle-PreviousAngle)/Delta>=0 && (DampedAngle-PreviousAngle)/Delta<=1)
        {
            // Exact intersection of the quaternion arc and desired yaw plane.
            const double Sin=FMath::Sin(DampedAngle*.5),Cos=FMath::Cos(DampedAngle*.5);
            auto Plane=[&](const FQuat& Q)
            {const FQuat D=Q*S.Reference.Inverse();return FVector::DotProduct(FVector(D.X,D.Y,D.Z),S.LocalAxis)*Cos-D.W*Sin;};
            const double A=Plane(Previous),B=Plane(Proposed);
            const double Alpha=FMath::Abs(A-B)>1.e-12?FMath::Clamp(A/(A-B),0.,1.):0.;
            return (Previous*(1-Alpha)+Proposed*Alpha).GetNormalized();
        }
        return Proposed;
    };
    const FQuat Damped=StopStep();
    // Damping arrests the authored step. Recoil is separately a pure horizontal
    // yaw about anatomical spine-up and must not pull toward an older pitch.
    const double Recoil=AcceptedAngle-DampedAngle;
    return FMath::Abs(Recoil)<1.e-10?Damped:(FQuat(S.LocalAxis,Recoil)*Damped).GetNormalized();
}
static double AdvanceTwist(FTwistArm& S,double Angle,const FTwistConfig& C,double Weight,double Dt)
{
    // Unwrap around the preceding ACCEPTED roll, so +/-180 cannot reset the limit.
    Angle=UnwrapTwist(Angle,S.AcceptedAngle);
    const double Limit=FMath::DegreesToRadians(C.Limit);
    // Dampen the authored outward motion in spine space, not merely the recoil
    // spring's velocity. Keep the within-limit part of a boundary-crossing step.
    const double Damped=DampedWristAngle(S.AcceptedAngle,Angle,C,Dt);
    const double Error=Damped-FMath::Clamp(Damped,-Limit,Limit);
    // Recoil adds attraction back to the boundary. With strength zero there is
    // still outward damping, but no positional attraction or leftover spring.
    if(C.Strength>0 && Error!=0)
        S.Velocity=(S.Velocity-C.Strength*Error*Dt)/(1+C.Damping*Dt+C.Strength*Dt*Dt);
    else S.Velocity=0;
    const double Correction=(Damped-Angle+S.Velocity*Dt)*Weight;
    S.Offset=Correction;
    S.AcceptedAngle=Angle+Correction;
    return Correction;
}
static void ApplyTwist(AProphecyAgent* A,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,
    const int32* Indices,int32 Spine,int32 Neck,double Weight,double Dt)
{
    if(TwistConfigs.IsEmpty() || Dt<=0) return;
    const auto* C=TwistConfigs.Find(A);if(!C || !Previous.IsValidIndex(Spine) || !Current.IsValidIndex(Spine))return;
    auto& State=TwistStates.FindOrAdd(A);
    for(int32 Side=0;Side<2;++Side)
    {
        auto& S=State.Arm[Side];const int32 L=Indices[3*Side+1],H=Indices[3*Side+2];
        if(!S.Ready)
        {
            const FVector Up=Previous.IsValidIndex(Neck)?Previous[Spine].GetRotation().UnrotateVector(
                Previous[Neck].GetLocation()-Previous[Spine].GetLocation()):FVector::ForwardVector;
            if(!SeedTwist(S,Previous[Spine],Previous[L],Previous[H],Up))continue;
        }
        const FQuat Before=(Previous[Spine].GetRotation().Inverse()*Previous[H].GetRotation()).GetNormalized();
        const FQuat Proposed=(Current[Spine].GetRotation().Inverse()*Current[H].GetRotation()).GetNormalized();
        const double PreviousAngle=WristAngle(S,Before,S.AcceptedAngle);
        S.AcceptedAngle=PreviousAngle;
        const double Angle=WristAngle(S,Proposed,PreviousAngle);
        AdvanceTwist(S,Angle,*C,Weight,Dt);
        const FQuat Accepted=AcceptWristStep(S,Before,Proposed,PreviousAngle,Angle,S.AcceptedAngle,*C,Weight,Dt);
        S.AcceptedAngle=WristAngle(S,Accepted,S.AcceptedAngle);
        if(Accepted.Equals(Proposed,1.e-10))continue;
        const FQuat Wrist=(Current[Spine].GetRotation()*Accepted).GetNormalized();
        Current[H].SetRotation(Wrist);
        // Rebuild forearm roll from the corrected wrist, exactly as the ordinary
        // NN decoder does. Joint positions are untouched; wrist bend may change.
        const FVector From=Wrist.RotateVector(S.LocalRadial);
        const FVector To=(Current[H].GetLocation()-Current[L].GetLocation()).GetSafeNormal();
        FQuat Swing=FQuat::FindBetweenNormals(From,To);
        if(FVector::DotProduct(From,To)<-1+1.e-12)
        {
            const FVector Basis=FMath::Abs(S.LocalRadial.Z)<.8?FVector::UpVector:FVector::RightVector;
            Swing=FQuat(Wrist.RotateVector((Basis-S.LocalRadial*FVector::DotProduct(Basis,S.LocalRadial)).GetSafeNormal()),UE_DOUBLE_PI);
        }
        Current[L].SetRotation((Swing*Wrist).GetNormalized());
    }
}
static void DrawTwist(AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<FTransform> Pose,float Length,float Duration,bool Active)
{
    if(TwistConfigs.IsEmpty())return;
    const auto* C=TwistConfigs.Find(A);if(!C)return;
    const int32 Spine=Names.IndexOfByKey(FName(TEXT("spine_05")));
    const int32 Neck=Names.IndexOfByKey(FName(TEXT("neck_01")));
    if(!Pose.IsValidIndex(Spine))return;
    const auto* State=TwistStates.Find(A);
    const double Limit=FMath::DegreesToRadians(C->Limit),Radius=Length*.35;
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 U=Names.IndexOfByKey(Side?FName(TEXT("upperarm_r")):FName(TEXT("upperarm_l")));
        const int32 L=Names.IndexOfByKey(Side?FName(TEXT("lowerarm_r")):FName(TEXT("lowerarm_l")));
        const int32 H=Names.IndexOfByKey(Side?FName(TEXT("hand_r")):FName(TEXT("hand_l")));
        if(!Pose.IsValidIndex(U)||!Pose.IsValidIndex(L)||!Pose.IsValidIndex(H))continue;
        FTwistArm Preview;
        const FTwistArm* S=State&&State->Arm[Side].Ready?&State->Arm[Side]:&Preview;
        if(S==&Preview)
        {
            const FVector Up=Pose.IsValidIndex(Neck)?Pose[Spine].GetRotation().UnrotateVector(
                Pose[Neck].GetLocation()-Pose[Spine].GetLocation()):FVector::ForwardVector;
            if(!SeedTwist(Preview,Pose[Spine],Pose[L],Pose[H],Up))continue;
        }
        FVector Axis,Ref,Actual;double Angle=0;
        if(!MeasureTwist(*S,Pose[Spine],Pose[L],Pose[H],Axis,Ref,Actual,Angle))continue;
        Angle=UnwrapTwist(Angle,S->AcceptedAngle);
        const FVector Center=Pose[H].GetLocation();
        const FColor Color=!Active?FColor::Silver:FMath::Abs(Angle)>Limit+1.e-4?FColor::Red:FColor::Green;
        auto Point=[&](double T){return Center+FQuat(Axis,T).RotateVector(Ref)*Radius;};
        for(int32 I=0;I<24;++I)DrawDebugLine(A->GetWorld(),Point(-Limit+2*Limit*I/24),Point(-Limit+2*Limit*(I+1)/24),FColor::Yellow,false,Duration,0,.6f);
        for(double T:{-Limit,Limit})DrawDebugLine(A->GetWorld(),Center,Point(T),FColor::Yellow,false,Duration,0,.6f);
        DrawDebugLine(A->GetWorld(),Center,Point(0),FColor::Cyan,false,Duration,0,1.f);
        DrawDebugLine(A->GetWorld(),Center,Center+Actual*Radius,Color,false,Duration,0,2.f);
        DrawDebugString(A->GetWorld(),Center+Axis*3,FString::Printf(TEXT("%s spine twist %.1f / +/-%.1f"),Side?TEXT("R"):TEXT("L"),FMath::RadiansToDegrees(Angle),C->Limit),nullptr,Color,Duration,false,.8f);
    }
}
