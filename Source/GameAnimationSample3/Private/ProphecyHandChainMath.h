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

// Previous is the accepted arm carried into the new root frame. Blend a SOURCE
// chain, then transport its complete hinge frame to the final wrist, like legs.
// Wrist roll must not rotate the elbow around the shoulder-to-wrist axis.
inline void Resolve(const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,
    const FTransform& Target,const FVector& LocalUpper,const FVector& LocalPole,double Follow)
{
    const FVector Hip=Shoulder.GetLocation();
    const FQuat SourceRotation=FQuat::Slerp(PreviousShoulder.GetRotation(),Shoulder.GetRotation(),Follow).GetNormalized();
    const FVector SourceHip=FMath::Lerp(PreviousShoulder.GetLocation(),Hip,Follow);
    const FVector SourceUpper=SourceRotation.RotateVector(LocalUpper);
    const FVector SourceEnd=FMath::Lerp(PreviousWrist.GetLocation(),Wrist.GetLocation(),Follow);
    const FVector OldAxis=(SourceEnd-SourceHip).GetSafeNormal(1.e-12,SourceUpper.GetSafeNormal());
    const FVector OldPole=Plane(SourceUpper,OldAxis,SourceRotation.RotateVector(LocalPole));
    const double L1=LocalUpper.Length();
    // Honor the source's allowed forearm length; forcing rest length here made
    // unclamped NN arms change length abruptly when reconstruction switched off.
    const double L2=FMath::Lerp((PreviousWrist.GetLocation()-PreviousElbow.GetLocation()).Length(),
        (Wrist.GetLocation()-Elbow.GetLocation()).Length(),Follow);
    if (L1<1.e-6 || L2<1.e-6) { Wrist=Target;return; }
    const FVector Delta=Target.GetLocation()-Hip;
    const FVector Axis=Delta.GetSafeNormal(1.e-12,OldAxis);
    const double Distance=FMath::Clamp(Delta.Length(),FMath::Max(1.e-6,FMath::Abs(L1-L2)),L1+L2);
    const double Cos=FMath::Clamp(FVector::DotProduct(OldAxis,Axis),-1.,1.);
    // At the opposite-axis degeneracy retain the coherent hinge plane.
    const FVector Pole=Plane(Cos<-1.+1.e-6 ? -OldPole :
        OldPole-(OldAxis+Axis)*(FVector::DotProduct(OldPole,Axis)/(1.+Cos)),Axis,OldPole);
    const double Along=(L1*L1-L2*L2+Distance*Distance)/(2.*Distance);
    const FVector Upper=Axis*Along+Pole*FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    const FVector OldNormal=FVector::CrossProduct(OldAxis,OldPole).GetSafeNormal();
    const FVector NewNormal=FVector::CrossProduct(Axis,Pole).GetSafeNormal();
    const FQuat Swing=FQuat::FindBetweenNormals(SourceUpper.GetSafeNormal(),Upper.GetSafeNormal());
    const FQuat Twist=FQuat::FindBetweenNormals(Swing.RotateVector(OldNormal),NewNormal);
    Shoulder.SetRotation((Twist*Swing*SourceRotation).GetNormalized());
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
