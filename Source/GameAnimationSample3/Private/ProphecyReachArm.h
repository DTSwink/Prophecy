#pragma once

// Direct port of REACH coupled.js. Component-space centimetres, fixed 60 Hz.
// The projection callback reads the currently loaded PHAT, including frame order.
namespace ProphecyReachArm
{
inline FVector Unit(FVector V) { const double N=V.Length();return N>1.e-12?V/N:FVector::ZeroVector; }
inline FQuat Align(FQuat Q,FVector A,FVector B)
{ return (FQuat::FindBetweenNormals(Unit(A),Unit(B))*Q).GetNormalized(); }
struct FInput
{
    FVector Shoulder,RawElbow,BaseHand,Anchor,Palm;
    FTransform Previous[3];
    FQuat Desired,Command;
    FQuat ForearmHint=FQuat::Identity;
    bool HasForearmHint=false;
    FVector PoleHint=FVector::ZeroVector;
    double UpperLength=0,LowerLength=0,Speed=120;
};
struct FResult
{
    FTransform Upper,Lower,Hand;
    int Evaluations=0;
};
template<class FProject> FResult Solve(const FInput& I,FProject&& Project)
{
    const FVector OldS=I.Previous[0].GetLocation(),OldE=I.Previous[1].GetLocation(),OldH=I.Previous[2].GetLocation();
    const FVector OldUpper=OldE-OldS,OldLower=OldH-OldE;
    const FVector OldAxis=Unit(OldH-OldS),Bend=OldUpper-OldAxis*FVector::DotProduct(OldUpper,OldAxis);
    const double Step=I.Speed/60.,L1=I.UpperLength,L2=I.LowerLength;
    FQuat HandQ=I.Command;FResult Result;
    for(int Outer=0;Outer<2;++Outer)
    {
        const FVector Goal=I.Anchor-HandQ.RotateVector(I.Palm),Delta=Goal-OldH;
        FVector Hand=Delta.Length()>Step?OldH+Unit(Delta)*Step:Goal;
        FVector Axis=Hand-I.Shoulder;double D=Axis.Length();
        Axis=D>1.e-8?Axis/D:Unit(I.BaseHand-I.Shoulder);
        D=FMath::Clamp(D,FMath::Abs(L1-L2)+.0001,L1+L2-.0001);Hand=I.Shoulder+Axis*D;
        const double Along=(L1*L1-L2*L2+D*D)/(2*D),Height=FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
        const FVector Center=I.Shoulder+Axis*Along;
        FVector U=FQuat::FindBetweenNormals(OldAxis,Axis).RotateVector(Bend);U-=Axis*FVector::DotProduct(U,Axis);
        if(U.Length()<1.e-6){U=I.RawElbow-Center;U-=Axis*FVector::DotProduct(U,Axis);}
        if(U.Length()<1.e-6)U=FVector::CrossProduct(Axis,FMath::Abs(Axis.Z)<.9?FVector::UpVector:FVector::RightVector);
        U=Unit(U);const FVector V=FVector::CrossProduct(Axis,U);
        double ElbowStep=FMath::Min(FMath::DegreesToRadians(8.),Step*1.2/FMath::Max(Height,.1)),RollStep=FMath::DegreesToRadians(4.);
        struct FCandidate { FVector Elbow;FQuat Forearm; };
        auto Follow=[&](double Theta,double Roll)
        {
            const FVector Elbow=Center+(U*FMath::Cos(Theta)+V*FMath::Sin(Theta))*Height,Lower=Hand-Elbow;
            const FQuat Forearm=(FQuat(Unit(Lower),Roll)*Align(I.Previous[1].GetRotation(),OldLower,Lower)).GetNormalized();
            return FCandidate{Elbow,Forearm};
        };
        auto Best=Follow(0,0);
        if(I.HasForearmHint)
        {
            const FQuat Hint=I.ForearmHint;
            const FVector LocalLower=I.Previous[1].GetRotation().UnrotateVector(OldLower);
            double Theta=0;
            const FVector GoalAxis=Unit(I.Anchor-I.Desired.RotateVector(I.Palm)-I.Shoulder);
            const FVector Offset=FQuat::FindBetweenNormals(GoalAxis,Axis).RotateVector(I.PoleHint);
            if(!I.PoleHint.IsNearlyZero(1.e-8))Theta=FMath::Atan2(FVector::DotProduct(Offset,V),FVector::DotProduct(Offset,U));
            const FVector Elbow=Center+(U*FMath::Cos(Theta)+V*FMath::Sin(Theta))*Height,Direction=Unit(Hand-Elbow);
            const FQuat Aligned=Align(Hint,Hint.RotateVector(LocalLower),Direction);
            FQuat DeltaQ=Aligned*Align(I.Previous[1].GetRotation(),OldLower,Direction).Inverse();
            if(DeltaQ.W<0)DeltaQ=DeltaQ*-1.;
            const double Roll=2*FMath::Atan2(FVector::DotProduct(FVector(DeltaQ.X,DeltaQ.Y,DeltaQ.Z),Direction),DeltaQ.W);
            Best=Follow(FMath::Clamp(Theta,-ElbowStep,ElbowStep),FMath::Clamp(Roll,-RollStep,RollStep));
        }
        HandQ=Project(Best.Forearm,I.Command,false);++Result.Evaluations;
        Result.Upper=FTransform(Align(I.Previous[0].GetRotation(),OldUpper,Best.Elbow-I.Shoulder),I.Shoulder);
        Result.Lower=FTransform(Best.Forearm,Best.Elbow);Result.Hand=FTransform(HandQ,Hand);
        if(FVector::Distance(I.Anchor-HandQ.RotateVector(I.Palm),Goal)<.01)break;
    }
    return Result;
}
struct FPlan { FQuat Forearm=FQuat::Identity;double Cos=1;int Evaluations=0; };
template<class FProject> FPlan PlanStraight(FVector Shoulder,FVector Wrist,FQuat Desired,FVector LocalLower,bool Locked,FProject&& Project)
{
    const FVector Delta=Wrist-Shoulder;const double Distance=Delta.Length();
    const FVector Direction=Distance>1.e-8?Delta/Distance:FVector::RightVector;
    const FQuat Aligned=FQuat::FindBetweenNormals(Unit(LocalLower),Direction);
    FPlan Best;double BestRoll=0;int Evaluations=0;
    auto Evaluate=[&](double Roll)
    {
        ++Evaluations;const FQuat Candidate=FQuat(Direction,Roll)*Aligned;
        const FQuat Forearm=Project(Desired,Candidate,true);
        return FPlan{Forearm,FMath::Clamp(FVector::DotProduct(Unit(Forearm.RotateVector(LocalLower)),Direction),-1.,1.),0};
    };
    Best=Evaluate(0);
    if(Best.Cos<1-1.e-10&&!Locked)
    {
        for(int N=1;N<8;++N){const double Roll=N*UE_PI/4;auto C=Evaluate(Roll);if(C.Cos>Best.Cos){Best=C;BestRoll=Roll;}}
        for(double Step:{UE_PI/8,UE_PI/16,UE_PI/32})
        {
            const double A=BestRoll-Step,B=BestRoll+Step;const auto PA=Evaluate(A),PB=Evaluate(B);
            if(PA.Cos>Best.Cos){Best=PA;BestRoll=A;}if(PB.Cos>Best.Cos){Best=PB;BestRoll=B;}
        }
    }
    Best.Evaluations=Evaluations;return Best;
}
template<class FProject> FPlan Track(FVector Shoulder,FVector Wrist,FQuat Desired,FVector LocalLower,FVector PreviousWrist,FQuat PreviousDesired,FQuat PreviousForearm,FProject&& Project)
{
    const FQuat Rotation=Desired*PreviousDesired.Inverse();
    const FQuat Candidate=Align(Rotation*PreviousForearm,Rotation.RotateVector(PreviousWrist-Shoulder),Wrist-Shoulder);
    const FQuat Forearm=Project(Desired,Candidate,true);
    return FPlan{Forearm,FMath::Clamp(FVector::DotProduct(Unit(Forearm.RotateVector(LocalLower)),Unit(Wrist-Shoulder)),-1.,1.),1};
}
inline double RotationFraction(double Angle,double RotationSpeed,double Speed,double Distance,double Sync)
{
    const double Normal=Angle>1.e-9?FMath::Min(1.,FMath::DegreesToRadians(RotationSpeed)/60./Angle):1.;
    const double Arrival=FMath::Min(1.,Speed/60./FMath::Max(Distance,1.e-8));
    return Normal+(FMath::Min(Normal,Arrival)-Normal)*Sync;
}
inline double Smooth(double A,double B,double V)
{ const double T=FMath::Clamp((V-A)/(B-A),0.,1.);return T*T*(3-2*T); }
inline FVector Preferred(FVector Axis,double Sign,double Blend)
{
    const FVector Outward=FVector(Sign,0,0)-Axis*(Sign*Axis.X),Preference(Sign,-.22,-.28);
    FVector Projected=Preference-Axis*FVector::DotProduct(Preference,Axis);
    if(Projected.Length()<1.e-7){const FVector Fallback(0,-.65,-.35);Projected=Fallback-Axis*FVector::DotProduct(Fallback,Axis);}
    FVector Bend=Unit(Projected);const double O=Outward.Length();
    if(O>1.e-5)
    {
        const FVector Out=Outward/O;const double Amount=FVector::DotProduct(Bend,Out);
        if(Amount<.55)
        {
            const FVector Transverse=Unit(FVector::CrossProduct(Axis,Out)*Sign),Canonical=Unit(Out*.55+Transverse*FMath::Sqrt(1-.55*.55));
            const double Weight=Smooth(.25,.55,O)*Smooth(0,.15,.55-Amount);Bend=Unit(Bend*(1-Weight)+Canonical*Weight);
        }
    }
    const double Weight=(1-.3*Smooth(0,.65,Axis.Y))*Smooth(.25,.65,FMath::Sqrt(Axis.X*Axis.X+Axis.Y*Axis.Y))*Blend;
    const FVector Down=-FVector::UpVector+Axis*Axis.Z,Relaxed=Unit(Down+Outward*.2);
    return Unit(Bend*(1-Weight)+Relaxed*Weight);
}
struct FPosture { FVector Pole,Direction;FQuat Forearm=FQuat::Identity; };
inline FPosture Posture(FVector Shoulder,FVector Wrist,FVector LocalLower,double L1,double Sign,double Blend)
{
    const double L2=LocalLower.Length();const FVector Delta=Wrist-Shoulder;
    const FVector Axis=Delta.Length()>1.e-8?Unit(Delta):FVector::RightVector;
    const double D=FMath::Clamp(Delta.Length(),FMath::Abs(L1-L2)+.0001,L1+L2-.0001);
    const double Along=(L1*L1-L2*L2+D*D)/(2*D),Height=FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    const FVector Pole=Preferred(Axis,Sign,Blend);return {Pole,Unit(Axis*(D-Along)-Pole*Height)};
}
}
