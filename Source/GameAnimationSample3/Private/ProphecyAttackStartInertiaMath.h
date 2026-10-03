#pragma once
#include "ProphecyPelvisInertiaMath.h"
namespace ProphecyAttackStartInertia
{
inline double Weight(int32 Frame,int32 Window,double Strength)
{
    return Window>1 && Frame<Window ? Strength*(1.-double(FMath::Max(1,Frame)-1)/(Window-1)) : 0.;
}
inline FTransform Step(const FTransform& Previous,const FTransform& Authored,
    const FVector& EntryDelta,const FVector& EntryAngularDelta,double LinearWeight,double AngularWeight)
{
    using namespace ProphecyPelvisInertia;
    FTransform Result=Authored;
    if (LinearWeight!=0) Result.SetLocation(Previous.GetLocation()+FMath::Lerp(
        Authored.GetLocation()-Previous.GetLocation(),EntryDelta,LinearWeight));
    if (AngularWeight!=0) Result.SetRotation((RotationIncrement(FMath::Lerp(
        RotationVector(Authored.GetRotation()*Previous.GetRotation().Inverse()),EntryAngularDelta,AngularWeight))
        *Previous.GetRotation()).GetNormalized());
    return Result;
}
// Carry the authored bend frame rather than selecting a new knee-plane branch.
// Preserve reachable ankle targets and both segment lengths/rolls. Only an
// unreachable endpoint is projected to the new hip's reach shell.
inline void MoveHip(FTransform& Thigh,FTransform& Calf,FTransform& Foot,FTransform* Toe,const FVector& Hip,
    const FVector& ReliablePole=FVector::ZeroVector)
{
    const FVector OldHip=Thigh.GetLocation(),OldKnee=Calf.GetLocation(),OldFoot=Foot.GetLocation();
    if(Hip.Equals(OldHip,1.e-10))return;
    const FVector Upper=OldKnee-OldHip,Lower=OldFoot-OldKnee;
    const double L1=Upper.Length(),L2=Lower.Length();
    if (L1<1.e-5 || L2<1.e-5) return;
    const FVector OldAxis=(OldFoot-OldHip).GetSafeNormal(UE_SMALL_NUMBER,Upper.GetSafeNormal());
    const FVector Radial=Upper-OldAxis*FVector::DotProduct(Upper,OldAxis);
    FVector Pole=Radial.GetSafeNormal();
    if (Pole.IsNearlyZero())
    {
        // At exact extension retain a thigh-authored transverse axis.
        FVector Reference=Thigh.GetRotation().GetAxisY();
        if (FMath::Abs(FVector::DotProduct(Reference,OldAxis))>.95) Reference=Thigh.GetRotation().GetAxisZ();
        Pole=(Reference-OldAxis*FVector::DotProduct(Reference,OldAxis)).GetSafeNormal();
    }
    const FVector Delta=OldFoot-Hip;
    const FVector Axis=Delta.GetSafeNormal(UE_SMALL_NUMBER,OldAxis);
    const double D=FMath::Clamp(Delta.Length(),FMath::Abs(L1-L2)+1.e-5,L1+L2-1.e-5);
    const double Along=(L1*L1-L2*L2+D*D)/(2.*D);
    const double Radius=FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    // Re-bending an almost straight source must not amplify its ill-conditioned
    // point-derived pole. Carry the entry bend in thigh space until the source
    // itself supplies enough radius. No timer, reader history or NN feedback.
    const FVector Reference=(ReliablePole-OldAxis*FVector::DotProduct(ReliablePole,OldAxis)).GetSafeNormal();
    if(!Reference.IsNearlyZero() && Radius>Radial.Length())
    {
        const double X=FMath::Clamp(Radial.Length()/Radius,0.,1.);
        const double Follow=X*X*(3.-2.*X);
        const double Angle=FMath::Atan2(FVector::DotProduct(OldAxis,FVector::CrossProduct(Reference,Pole)),
            FMath::Clamp(FVector::DotProduct(Reference,Pole),-1.,1.));
        Pole=FQuat(OldAxis,Angle*Follow).RotateVector(Reference);
    }
    const double Cos=FVector::DotProduct(OldAxis,Axis);
    const FVector Transport=Cos < -1.+1.e-6 ? -Pole
        : Pole-(OldAxis+Axis)*(FVector::DotProduct(Pole,Axis)/FMath::Max(1.e-6,1.+Cos));
    const FVector NewPole=(Transport-Axis*FVector::DotProduct(Transport,Axis)).GetSafeNormal();
    const FVector NewUpper=Axis*Along+NewPole*Radius;
    const FVector End=Hip+Axis*D,Knee=Hip+NewUpper;
    Thigh.SetLocation(Hip);
    Thigh.SetRotation((FQuat::FindBetweenNormals(Upper/L1,NewUpper.GetSafeNormal())*Thigh.GetRotation()).GetNormalized());
    Calf.SetLocation(Knee);
    Calf.SetRotation((FQuat::FindBetweenNormals(Lower/L2,(End-Knee).GetSafeNormal())*Calf.GetRotation()).GetNormalized());
    Foot.SetLocation(End);if (Toe) Toe->AddToTranslation(End-OldFoot);
}
}
