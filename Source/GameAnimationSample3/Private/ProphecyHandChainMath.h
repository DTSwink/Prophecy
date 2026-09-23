#pragma once
#include "CoreMinimal.h"

namespace ProphecyHandChain
{
inline FVector Plane(const FVector& V,const FVector& Axis,const FVector& Fallback)
{
    return (V-Axis*FVector::DotProduct(V,Axis)).GetSafeNormal(1.e-12,
        (Fallback-Axis*FVector::DotProduct(Fallback,Axis)).GetSafeNormal(1.e-12,
            FVector::CrossProduct(Axis,FMath::Abs(Axis.Z)<.8?FVector::UpVector:FVector::ForwardVector).GetSafeNormal()));
}

inline FVector TransportPole(const FVector& From,const FVector& To,const FVector& Pole)
{
    const double C=FVector::DotProduct(From,To);
    // A half turn has no unique shortest axis. Retain the hinge rather than
    // selecting an arbitrary world axis (or reversing the bend).
    return Plane(C<-.999999 ? Pole : Pole-(From+To)*(FVector::DotProduct(Pole,To)/(1.+C)),To,Pole);
}
inline double Confidence(double V)
{ V=FMath::Clamp(V,0.,1.);return V*V*(3.-2.*V); }

// Solve BOTH coherent source hinges at the final wrist before blending them.
// Mixing a shoulder quaternion and an endpoint first does not describe a valid
// intermediate arm: its projected bend can collapse or reverse. Wrist roll is
// deliberately absent from the hinge calculation.
inline void Resolve(const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,
    const FTransform& Target,const FVector& LocalUpper,const FVector& LocalPole,double Follow)
{
    const FVector Hip=Shoulder.GetLocation();
    const double L1=LocalUpper.Length();
    // Honor the source's allowed forearm length; forcing rest length here made
    // unclamped NN arms change length abruptly when reconstruction switched off.
    const double L2=FMath::Lerp((PreviousWrist.GetLocation()-PreviousElbow.GetLocation()).Length(),
        (Wrist.GetLocation()-Elbow.GetLocation()).Length(),Follow);
    if (L1<1.e-6 || L2<1.e-6) { Wrist=Target;return; }
    const FVector Delta=Target.GetLocation()-Hip;
    const FVector Axis=Delta.GetSafeNormal(1.e-12,(PreviousWrist.GetLocation()-PreviousShoulder.GetLocation()).GetSafeNormal());
    const double Distance=FMath::Clamp(Delta.Length(),FMath::Max(1.e-6,FMath::Abs(L1-L2)),L1+L2);
    struct FHinge { FVector Upper,Axis,Pole,Normal;FQuat Rotation;double Radius; };
    auto Hinge=[&](const FTransform& S,const FTransform& W)
    {
        FHinge H;H.Rotation=S.GetRotation();H.Upper=H.Rotation.RotateVector(LocalUpper);
        H.Axis=(W.GetLocation()-S.GetLocation()).GetSafeNormal(1.e-12,H.Upper.GetSafeNormal());
        H.Radius=(H.Upper-H.Axis*FVector::DotProduct(H.Upper,H.Axis)).Length();
        H.Pole=Plane(H.Upper,H.Axis,H.Rotation.RotateVector(LocalPole));
        H.Normal=FVector::CrossProduct(H.Axis,H.Pole).GetSafeNormal();return H;
    };
    const FHinge P=Hinge(PreviousShoulder,PreviousWrist),N=Hinge(Shoulder,Wrist);
    const FVector Prior=TransportPole(P.Axis,Axis,P.Pole),Next=TransportPole(N.Axis,Axis,N.Pole);
    const double Cos=FMath::Clamp(FVector::DotProduct(Prior,Next),-1.,1.);
    // Suppress unobservable guidance continuously: an almost straight source,
    // antipodal aim or antipodal poles must not amplify floating-point noise.
    const double Trust=Confidence(N.Radius/(L1*.02))*Confidence((1.+FVector::DotProduct(N.Axis,Axis))/.05)
        *Confidence((1.+Cos)/.02);
    const double Weight=Follow>=1. ? 1. : Follow*Trust;
    const double Angle=FMath::Atan2(FVector::DotProduct(Axis,FVector::CrossProduct(Prior,Next)),Cos);
    const FVector Pole=FQuat(Axis,Angle*Weight).RotateVector(Prior);
    const double Along=(L1*L1-L2*L2+Distance*Distance)/(2.*Distance);
    const FVector Upper=Axis*Along+Pole*FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    const FVector NewNormal=FVector::CrossProduct(Axis,Pole).GetSafeNormal();
    auto Frame=[&](const FHinge& H)
    {
        const FQuat Swing=FQuat::FindBetweenNormals(H.Upper.GetSafeNormal(),Upper.GetSafeNormal());
        const FQuat Twist=FQuat::FindBetweenNormals(Swing.RotateVector(H.Normal),NewNormal);
        return (Twist*Swing*H.Rotation).GetNormalized();
    };
    // Both frames now share the same upper direction; remaining interpolation
    // is shoulder twist only and cannot move the solved elbow off its circle.
    Shoulder.SetRotation(FQuat::Slerp(Frame(P),Frame(N),Weight).GetNormalized());
    const FVector OldLower=Wrist.GetLocation()-Elbow.GetLocation();
    Elbow.SetLocation(Hip+Upper);
    Elbow.SetRotation((FQuat::FindBetweenNormals(OldLower.GetSafeNormal(),
        (Hip+Axis*Distance-Elbow.GetLocation()).GetSafeNormal())*Elbow.GetRotation()).GetNormalized());
    Wrist=Target;Wrist.SetLocation(Hip+Axis*Distance);
}

inline FQuat FollowTwist(const FQuat& Previous,const FQuat& Decoded,const FVector& LocalAxis,double Follow)
{
    if (Follow>=1.) return Decoded;
    const FVector Axis=LocalAxis.GetSafeNormal();
    const FQuat Carried=(FQuat::FindBetweenNormals(Previous.RotateVector(Axis),Decoded.RotateVector(Axis))*Previous).GetNormalized();
    return Follow<=0. ? Carried : FQuat::Slerp(Carried,Decoded,Follow).GetNormalized();
}
}
