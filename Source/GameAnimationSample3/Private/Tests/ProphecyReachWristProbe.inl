// Included inside the existing editor-only reach inspector. No new registration.
static double ReachWristViolation(FQuat Q,const FConstraintProfileProperties& P)
{
    FQuat S,T;Q.ToSwingTwist(FVector::ForwardVector,S,T);
    if(T.W<0)T=T*-1.;
    const double Twist=FMath::Abs(2.*FMath::Atan2(T.X,T.W));
    double Error=FMath::Max(0.,Twist-ProphecyReachWristLimits::Bound(P.TwistLimit.TwistMotion,P.TwistLimit.TwistLimitDegrees));
    const double Y=FMath::Sin(ProphecyReachWristLimits::Bound(P.ConeLimit.Swing2Motion,P.ConeLimit.Swing2LimitDegrees)*.5);
    const double Z=FMath::Sin(ProphecyReachWristLimits::Bound(P.ConeLimit.Swing1Motion,P.ConeLimit.Swing1LimitDegrees)*.5);
    if(Y==0)Error=FMath::Max(Error,FMath::Abs(S.Y));
    if(Z==0)Error=FMath::Max(Error,FMath::Abs(S.Z));
    const double Ellipse=(Y>0?FMath::Square(S.Y/Y):0.)+(Z>0?FMath::Square(S.Z/Z):0.);
    return FMath::Max(Error,Ellipse-1.);
}
static void VerifyReachWristMath()
{
    double Worst=0,Idempotence=0,FreeError=0,FrameError=0;int Cases=0;
    const EAngularConstraintMotion Modes[]={ACM_Free,ACM_Limited,ACM_Locked};
    FConstraintInstance J;
    J.SetRefFrame(EConstraintFrame::Frame1,FTransform(FRotator(13,27,-38)));
    J.SetRefFrame(EConstraintFrame::Frame2,FTransform(FRotator(-21,61,19)));
    auto& P=J.ProfileInstance;P.ConeLimit.Swing1LimitDegrees=50;P.ConeLimit.Swing2LimitDegrees=23.71f;P.TwistLimit.TwistLimitDegrees=30;
    const FQuat Forearm=FRotator(28,-71,43).Quaternion();
    for(auto X:Modes)for(auto Y:Modes)for(auto Z:Modes)
    {
        P.TwistLimit.TwistMotion=X;P.ConeLimit.Swing2Motion=Y;P.ConeLimit.Swing1Motion=Z;
        for(int I=0;I<180;++I)
        {
            const FQuat Q=FRotator(I*17.,I*31.,I*47.).Quaternion();
            const FQuat Clamped=ProphecyReachWristLimits::Project(Q,P);
            Worst=FMath::Max(Worst,ReachWristViolation(Clamped,P));
            if(Clamped.ContainsNaN()||!Clamped.IsNormalized())Worst=1.e9;
            Idempotence=FMath::Max(Idempotence,Clamped.AngularDistance(ProphecyReachWristLimits::Project(Clamped,P)));
            if(X==ACM_Free&&Y==ACM_Free&&Z==ACM_Free)FreeError=FMath::Max(FreeError,Q.AngularDistance(Clamped));
            for(bool First:{false,true})
            {
                const FQuat H=ProphecyReachWristLimits::Constrain(J,First,Forearm,Q);
                const FQuat A=(First?H:Forearm)*J.GetRefFrame(EConstraintFrame::Frame1).GetRotation();
                const FQuat B=(First?Forearm:H)*J.GetRefFrame(EConstraintFrame::Frame2).GetRotation();
                FrameError=FMath::Max(FrameError,ReachWristViolation((B.Inverse()*A).GetNormalized(),P));
            }
            ++Cases;
        }
    }
    // All-locked must land exactly on the authored joint frames, in either order.
    P.TwistLimit.TwistMotion=P.ConeLimit.Swing1Motion=P.ConeLimit.Swing2Motion=ACM_Locked;
    for(bool First:{false,true})
    {
        const FQuat H=ProphecyReachWristLimits::Constrain(J,First,Forearm,FRotator(73,-128,54).Quaternion());
        const FQuat F1=J.GetRefFrame(EConstraintFrame::Frame1).GetRotation(),F2=J.GetRefFrame(EConstraintFrame::Frame2).GetRotation();
        const FQuat Expected=First?Forearm*F2*F1.Inverse():Forearm*F1*F2.Inverse();
        FrameError=FMath::Max(FrameError,H.AngularDistance(Expected));
    }
    const bool Passed=Worst<1.e-8&&FrameError<1.e-7&&Idempotence<1.e-7&&FreeError<1.e-7;
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("passed=%d cases=%d violation=%.12g frame_error=%.12g idempotence_rad=%.12g free_error_rad=%.12g\n"),Passed,Cases,Worst,FrameError,Idempotence,FreeError),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachWristPHAT20261015/math.txt")));
}
static void InspectReachWrists(UWorld* World)
{
    using namespace ProphecyReach;
    FString CSV=TEXT("agent,side,active,returning,gripped,violation,correction_rad,swing1,swing2,twist,mode1,mode2,mode_twist,qx,qy,qz,qw\n");
    for(const auto& Entry:States)
    {
        const auto* A=Entry.Key.Get();if(!A||A->GetWorld()!=World)continue;
        const auto& S=*Entry.Value;if(S.Pose.IsEmpty())continue;
        for(int Side=0;Side<2;++Side)if(const auto* J=WristConstraint(A,Side))
        {
            const auto& H=S.Hands[Side];const auto& P=J->ProfileInstance;
            const bool First=J->ConstraintBone1==HandName(Side);
            const FQuat Hand=S.Pose[ArmIndex(Side,3)].GetRotation(),Forearm=S.Pose[ArmIndex(Side,2)].GetRotation();
            const FQuat Q1=(First?Hand:Forearm)*J->GetRefFrame(EConstraintFrame::Frame1).GetRotation();
            const FQuat Q2=(First?Forearm:Hand)*J->GetRefFrame(EConstraintFrame::Frame2).GetRotation();
            const FQuat Relative=(Q2.Inverse()*Q1).GetNormalized();
            const FQuat Corrected=ProphecyReachWristLimits::Constrain(*J,First,Forearm,Hand);
            CSV+=FString::Printf(TEXT("%s,%d,%d,%d,%d,%.12g,%.12g,%.9g,%.9g,%.9g,%d,%d,%d,%.12g,%.12g,%.12g,%.12g\n"),*A->GetName(),Side,H.Enabled,H.Returning,H.Gripped,ReachWristViolation(Relative,P),Hand.AngularDistance(Corrected),P.ConeLimit.Swing1LimitDegrees,P.ConeLimit.Swing2LimitDegrees,P.TwistLimit.TwistLimitDegrees,int(P.ConeLimit.Swing1Motion),int(P.ConeLimit.Swing2Motion),int(P.TwistLimit.TwistMotion),Relative.X,Relative.Y,Relative.Z,Relative.W);
        }
    }
    FFileHelper::SaveStringToFile(CSV,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachWristPHAT20261015/wrists.csv")));
}
