#pragma once
#include "CoreMinimal.h"
namespace ProphecySlashReturn
{
inline double TorsoSegmentClearance(FVector A,FVector B,double Width)
{
    const FVector D=B-A;double Lo=0,Hi=1;
    const double Bottom=-3*Width,Top=.3*Width;
    if(FMath::Abs(D.Z)<1.e-8) { if(A.Z<Bottom || A.Z>Top) return 1.e6; }
    else
    {
        const double T0=(Bottom-A.Z)/D.Z,T1=(Top-A.Z)/D.Z;
        Lo=FMath::Max(0.,FMath::Min(T0,T1));Hi=FMath::Min(1.,FMath::Max(T0,T1));
        if(Lo>Hi) return 1.e6;
    }
    const FVector2D P(A.X/(Width*.9),A.Y/(Width*.8)),V(D.X/(Width*.9),D.Y/(Width*.8));
    const double T=FMath::Clamp(-FVector2D::DotProduct(P,V)/FMath::Max(1.e-12,V.SizeSquared()),Lo,Hi);
    return (P+V*T).SizeSquared();
}
// Rotate the elbow on its exact two-bone solution circle. Choose the nearest
// clear angle, refining the boundary rather than quantizing to sampled poles.
// This protects BOTH arm segments, not only the wrist endpoint. The finite turn
// rate permits a smooth escape if the attack already ended in penetration.
inline double ClearElbowAngle(const FVector& Shoulder,const FVector& Elbow,const FVector& Wrist,double Width,double Dt)
{
    Width=FMath::Max(1.,Width);
    const FVector Axis=(Wrist-Shoulder).GetSafeNormal();
    const FVector Center=Shoulder+Axis*FVector::DotProduct(Elbow-Shoulder,Axis);
    const FVector Radius=Elbow-Center,Other=FVector::CrossProduct(Axis,Radius);
    if(Radius.SizeSquared()<1.e-8) return 0;
    auto At=[&](double Angle) { return Center+Radius*FMath::Cos(Angle)+Other*FMath::Sin(Angle); };
    auto Clearance=[&](double Angle) { const FVector E=At(Angle);return FMath::Min(
        TorsoSegmentClearance(Shoulder,E,Width),TorsoSegmentClearance(E,Wrist,Width)); };
    constexpr double Margin=1.02;
    if(Clearance(0)>=Margin) return 0;
    double Best=0,BestScore=Clearance(0),Nearest=1.e6;
    for(double Sign:{-1.,1.}) for(int32 I=1;I<=32;++I)
    {
        const double Angle=Sign*PI*I/32.;const double Score=Clearance(Angle);
        if(Nearest==1.e6 && Score>BestScore+1.e-8) { BestScore=Score;Best=Angle; }
        if(Score<Margin) continue;
        double Low=PI*(I-1)/32.,High=PI*I/32.;
        for(int32 J=0;J<14;++J) { const double Mid=(Low+High)*.5;
            if(Clearance(Sign*Mid)>=Margin) High=Mid;else Low=Mid; }
        if(High<Nearest) { Nearest=High;Best=Sign*High; }break;
    }
    return FMath::Clamp(Best,-8*Dt,8*Dt);
}
// Anatomical X points forward, Y right, Z up. Interpolate unwrapped [-pi,pi]
// azimuths through the FRONT, never through the rear shortest-arc shortcut.
// The elliptical radius preserves endpoint clearance instead of cutting a chord
// through the chest. Vertical motion and wrist rotation remain independent.
inline FVector RouteEndpoint(FVector To,double HalfWidth)
{
    const double X=FMath::Max(1.,HalfWidth*.9),Y=FMath::Max(1.,HalfWidth);
    const double R=FMath::Sqrt(FMath::Square(To.X/X)+FMath::Square(To.Y/Y));
    if(R<1.08) { if(R>1.e-8) {To.X*=1.08/R;To.Y*=1.08/R;}else To.X=1.08*X; }
    return To;
}
inline FVector FrontPath(const FVector& From,const FVector& To,double HalfWidth,double T)
{
    if(T<=0) return From;if(T>=1) return RouteEndpoint(To,HalfWidth);
    const double X=FMath::Max(1.,HalfWidth*.9),Y=FMath::Max(1.,HalfWidth);
    const double A=FMath::Atan2(From.Y/Y,From.X/X),B=FMath::Atan2(To.Y/Y,To.X/X);
    const double R0=FMath::Sqrt(FMath::Square(From.X/X)+FMath::Square(From.Y/Y));
    const double R1=FMath::Max(1.08,FMath::Sqrt(FMath::Square(To.X/X)+FMath::Square(To.Y/Y)));
    // A destination inside the exclusion ellipse must not collapse the arc.
    // Retain continuity when the starting attack pose is already inside it.
    const double R=FMath::Lerp(R0,FMath::Max(1.08,R1),T),Angle=FMath::Lerp(A,B,T);
    return FVector(X*R*FMath::Cos(Angle),Y*R*FMath::Sin(Angle),FMath::Lerp(From.Z,To.Z,T));
}
inline double DirectedHeading(double Start,double Goal,double Side)
{
    double Delta=FMath::UnwindDegrees(Goal-Start);
    if(Side*Delta< -1.e-6) Delta+=Side*360.;
    return Start+Delta;
}
inline FRotator BlendWeaponRotation(const FRotator& From,const FRotator& To,double Alpha)
{
    // Yaw is already unwrapped in the chosen direction. Never quaternion-slerp
    // it: that silently reverses a requested 225-degree outward turn.
    return FRotator(From.Pitch+FMath::UnwindDegrees(To.Pitch-From.Pitch)*Alpha,
        FMath::Lerp(From.Yaw,To.Yaw,Alpha),From.Roll+FMath::UnwindDegrees(To.Roll-From.Roll)*Alpha);
}
// Exact minimum of the blade segment against a padded elliptical torso. The
// padding includes the blade width; using only the wrist misses the hilt/blade.
inline double BladeClearance(const FTransform& Hand,const FVector& Base,const FVector& Tip,double Width,double Padding)
{
    const FVector A=Hand.TransformPosition(Base),D=Hand.TransformPosition(Tip)-A;
    double Lo=0,Hi=1;
    const double Bottom=-3*Width-Padding,Top=.7*Width+Padding;
    if(FMath::Abs(D.Z)<1.e-8) { if(A.Z<Bottom || A.Z>Top) return 1.e6; }
    else { const double T0=(Bottom-A.Z)/D.Z,T1=(Top-A.Z)/D.Z;
        Lo=FMath::Max(0.,FMath::Min(T0,T1));Hi=FMath::Min(1.,FMath::Max(T0,T1));if(Lo>Hi) return 1.e6; }
    const FVector2D P(A.X/(.9*Width+Padding),A.Y/(Width+Padding));
    const FVector2D V(D.X/(.9*Width+Padding),D.Y/(Width+Padding));
    const double T=FMath::Clamp(-FVector2D::DotProduct(P,V)/FMath::Max(1.e-12,V.SizeSquared()),Lo,Hi);
    return (P+V*T).SizeSquared();
}
inline FVector ClearBladePosition(const FTransform& Hand,const FVector& Base,const FVector& Tip,double Width,double Padding)
{
    if(BladeClearance(Hand,Base,Tip,Width,Padding)>=1.04) return Hand.GetLocation();
    // Move outwards from the torso on the same side of the route. Moving just
    // the wrist to the nominal ellipse does not account for grip offset.
    const FVector H=Hand.GetLocation();
    const FVector Out=FVector(H.X/(.9*.9),H.Y,0).GetSafeNormal(1.e-8,FVector::ForwardVector);
    auto At=[&](double D) {FTransform P=Hand;P.AddToTranslation(Out*D);return BladeClearance(P,Base,Tip,Width,Padding);};
    double Lo=0,Hi=FMath::Max(1.,Width);
    for(int32 I=0;I<5 && At(Hi)<1.04;++I) Hi*=2;
    for(int32 I=0;I<18;++I) { const double Mid=(Lo+Hi)*.5;if(At(Mid)<1.04) Lo=Mid;else Hi=Mid; }
    return H+Out*Hi;
}
inline FTransform FrontBlend(const FTransform& From,const FTransform& To,double Width,double T)
{
    return FTransform(FQuat::Slerp(From.GetRotation(),To.GetRotation(),T).GetNormalized(),
        FrontPath(From.GetLocation(),To.GetLocation(),Width,T));
}
// Conservative arc-length bound makes ReturnSpeed a positional speed cap along
// the route, not just an endpoint chord speed. Bound angular steps as well so
// render interpolation cannot take a large shortcut across the front arc.
inline double Advance(const FVector& From,const FVector& To,double Width,double Distance,double TickTime)
{
    const double X=FMath::Max(1.,Width*.9),Y=FMath::Max(1.,Width);
    const double R0=FMath::Sqrt(FMath::Square(From.X/X)+FMath::Square(From.Y/Y));
    const double R1=FMath::Max(1.08,FMath::Sqrt(FMath::Square(To.X/X)+FMath::Square(To.Y/Y)));
    const double Angle=FMath::Abs(FMath::Atan2(To.Y/Y,To.X/X)-FMath::Atan2(From.Y/Y,From.X/X));
    const double Bound=Y*(FMath::Abs(R1-R0)+FMath::Max(R0,R1)*Angle)+FMath::Abs(To.Z-From.Z);
    return FMath::Min3(1.,Distance/FMath::Max(1.e-6,Bound),4.5*TickTime/FMath::Max(1.e-6,Angle));
}
}
