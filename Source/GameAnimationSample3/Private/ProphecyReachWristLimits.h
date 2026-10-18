#pragma once
#include "PhysicsEngine/ConstraintInstance.h"

namespace ProphecyReachWristLimits
{
// Same quaternion-space cone domain as the native Jolt swing/twist constraint:
// Twist=X, Swing2=Y, Swing1=Z. Project along the swing direction into its ellipse.
inline double Bound(EAngularConstraintMotion Motion,double Degrees)
{
    return Motion==ACM_Free?PI:Motion==ACM_Locked?0.:FMath::DegreesToRadians(FMath::Clamp(Degrees,0.,180.));
}
inline FQuat Project(FQuat Q,const FConstraintProfileProperties& P)
{
    const double X=Bound(P.TwistLimit.TwistMotion,P.TwistLimit.TwistLimitDegrees);
    const double Y=Bound(P.ConeLimit.Swing2Motion,P.ConeLimit.Swing2LimitDegrees);
    const double Z=Bound(P.ConeLimit.Swing1Motion,P.ConeLimit.Swing1LimitDegrees);
    if(X>=PI&&Y>=PI&&Z>=PI)return Q;
    FQuat Swing,Twist;Q.ToSwingTwist(FVector::ForwardVector,Swing,Twist);
    if(Swing.W<0)Swing=Swing*-1.;
    if(Twist.W<0)Twist=Twist*-1.;
    const double Angle=2.*FMath::Atan2(Twist.X,Twist.W);
    if(FMath::Abs(Angle)>X)Twist=FQuat(FVector::ForwardVector,FMath::Clamp(Angle,-X,X));
    const double RY=FMath::Sin(Y*.5),RZ=FMath::Sin(Z*.5);
    double SY=RY>0?Swing.Y:0.,SZ=RZ>0?Swing.Z:0.;
    const double Radius=(RY>0?FMath::Square(SY/RY):0.)+(RZ>0?FMath::Square(SZ/RZ):0.);
    if(Radius>1.){const double Scale=1./FMath::Sqrt(Radius);SY*=Scale;SZ*=Scale;}
    if(SY!=Swing.Y||SZ!=Swing.Z)Swing=FQuat(0,SY,SZ,FMath::Sqrt(FMath::Max(0.,1.-SY*SY-SZ*SZ)));
    return (Swing*Twist).GetNormalized();
}
inline FQuat Constrain(const FConstraintInstance& Joint,bool HandIsFirst,FQuat Forearm,FQuat Hand)
{
    // GetRefFrame already contains authored offset axes. Do not apply the
    // AngularRotationOffset property again. Preserve actual endpoint order.
    const FQuat F1=Joint.GetRefFrame(EConstraintFrame::Frame1).GetRotation();
    const FQuat F2=Joint.GetRefFrame(EConstraintFrame::Frame2).GetRotation();
    const FQuat Q1=(HandIsFirst?Hand:Forearm)*F1,Q2=(HandIsFirst?Forearm:Hand)*F2;
    const FQuat Relative=(Q2.Inverse()*Q1).GetNormalized();
    const FQuat Limited=Project(Relative,Joint.ProfileInstance);
    return (HandIsFirst?Q2*Limited*F1.Inverse():Q1*Limited.Inverse()*F2.Inverse()).GetNormalized();
}
}
