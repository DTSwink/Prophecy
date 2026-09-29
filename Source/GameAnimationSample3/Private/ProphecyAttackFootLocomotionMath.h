#pragma once
#include "ProphecyAttackStartInertiaMath.h"

namespace ProphecyAttackFootLocomotion
{
inline FVector FootLocalPole(const FTransform* Leg)
{
    const FVector Axis=(Leg[2].GetLocation()-Leg[0].GetLocation()).GetSafeNormal();
    const FVector Upper=Leg[1].GetLocation()-Leg[0].GetLocation();
    FVector Pole=(Upper-Axis*FVector::DotProduct(Upper,Axis)).GetSafeNormal();
    if(Pole.IsNearlyZero())
    {
        FVector Reference=Leg[0].GetRotation().GetAxisY();
        if(FMath::Abs(FVector::DotProduct(Reference,Axis))>.95)Reference=Leg[0].GetRotation().GetAxisZ();
        Pole=(Reference-Axis*FVector::DotProduct(Reference,Axis)).GetSafeNormal();
    }
    return Leg[2].GetRotation().UnrotateVector(Pole);
}
inline FVector BlendFootLocalPoles(const FVector& Loco,const FVector& Attack,const FVector& LocoAxis,float Alpha)
{
    if(Alpha<=0)return Loco;if(Alpha>=1)return Attack;
    FQuat Delta=FQuat::FindBetweenNormals(Loco,Attack);
    // Opposite poles have no unique shortest arc. Use the source leg axis in
    // foot coordinates, so the midpoint stays on its knee circle, not straight.
    if(FVector::DotProduct(Loco,Attack)<-1.+1.e-6)
    {
        const FVector Axis=(LocoAxis-Loco*FVector::DotProduct(LocoAxis,Loco)).GetSafeNormal();
        if(!Axis.IsNearlyZero())Delta=FQuat(Axis,UE_DOUBLE_PI);
    }
    return FQuat::Slerp(FQuat::Identity,Delta,Alpha).RotateVector(Loco);
}
inline void ApplyFootLocalPole(FTransform* Leg,const FVector& Local)
{
    const FVector Hip=Leg[0].GetLocation(),Axis=(Leg[2].GetLocation()-Hip).GetSafeNormal();
    const FVector Upper=Leg[1].GetLocation()-Hip;
    const FVector From=(Upper-Axis*FVector::DotProduct(Upper,Axis)).GetSafeNormal();
    const FVector Desired=Leg[2].GetRotation().RotateVector(Local);
    const FVector To=(Desired-Axis*FVector::DotProduct(Desired,Axis)).GetSafeNormal();
    // A straight knee or a pole parallel to the leg has no defined steering.
    if(From.IsNearlyZero() || To.IsNearlyZero())return;
    const double Angle=FMath::Atan2(FVector::DotProduct(Axis,FVector::CrossProduct(From,To)),
        FMath::Clamp(FVector::DotProduct(From,To),-1.,1.));
    const FQuat Turn(Axis,Angle);
    Leg[0].SetRotation((Turn*Leg[0].GetRotation()).GetNormalized());
    Leg[1].SetRotation((Turn*Leg[1].GetRotation()).GetNormalized());
    Leg[1].SetLocation(Hip+Turn.RotateVector(Upper));
}
// Four component-space transforms: thigh, calf, ankle, toe. Only active drag
// calls this; the default endpoint follows the original copy-and-connect path.
inline void AuthorLeg(FTransform* Attack,const FTransform* Loco,float Weight,float RotationAlpha,float PoleAttackAlpha=-1.f)
{
    if(Weight<=0)return;
    const FVector Hip=Attack[0].GetLocation();
    if(Weight>=1 && RotationAlpha>=1 && PoleAttackAlpha<0)
    {
        for(int32 B=0;B<4;++B)Attack[B]=Loco[B];
        ProphecyAttackStartInertia::MoveHip(Attack[0],Attack[1],Attack[2],&Attack[3],Hip);
        return;
    }
    FVector AttackPole=FVector::ZeroVector,LocoPole=FVector::ZeroVector,LocoAxis=FVector::ZeroVector;
    if(PoleAttackAlpha>=0)
    {
        AttackPole=FootLocalPole(Attack);
        if(PoleAttackAlpha<1)
        {
            LocoPole=FootLocalPole(Loco);
            LocoAxis=Loco[2].GetRotation().UnrotateVector((Loco[2].GetLocation()-Loco[0].GetLocation()).GetSafeNormal());
        }
    }
    FTransform Connected[4];for(int32 B=0;B<4;++B)Connected[B]=Loco[B];
    ProphecyAttackStartInertia::MoveHip(Connected[0],Connected[1],Connected[2],&Connected[3],Hip);
    const float R=Weight*RotationAlpha;
    const FQuat FootRotation=R<=0 ? Attack[2].GetRotation()
        : FQuat::Slerp(Attack[2].GetRotation(),Connected[2].GetRotation(),R).GetNormalized();
    FTransform ToeLocal=Attack[3].GetRelativeTransform(Attack[2]);
    if(R>0)ToeLocal.Blend(ToeLocal,Connected[3].GetRelativeTransform(Connected[2]),R);
    if(Weight>=1)for(int32 B=0;B<3;++B)Attack[B]=Connected[B];
    else
    {
        const FVector Ankle=FMath::Lerp(Attack[2].GetLocation(),Connected[2].GetLocation(),double(Weight));
        // Blend local segment frames, preserving interpolated segment lengths.
        // A final existing two-bone solve reaches the blended ankle from the fixed hip.
        FTransform Calf=Attack[1].GetRelativeTransform(Attack[0]);
        FTransform Foot=Attack[2].GetRelativeTransform(Attack[1]);
        const FTransform LocoCalf=Connected[1].GetRelativeTransform(Connected[0]);
        const FTransform LocoFoot=Connected[2].GetRelativeTransform(Connected[1]);
        const double UpperLength=FMath::Lerp(Calf.GetLocation().Length(),LocoCalf.GetLocation().Length(),double(Weight));
        const double LowerLength=FMath::Lerp(Foot.GetLocation().Length(),LocoFoot.GetLocation().Length(),double(Weight));
        Calf.Blend(Calf,LocoCalf,Weight);Foot.Blend(Foot,LocoFoot,Weight);
        Calf.SetLocation(Calf.GetLocation().GetSafeNormal()*UpperLength);
        Foot.SetLocation(Foot.GetLocation().GetSafeNormal()*LowerLength);
        Attack[0].Blend(Attack[0],Connected[0],Weight);
        Attack[1]=Calf*Attack[0];Attack[2]=Foot*Attack[1];
        const FVector Shift=Ankle-Attack[2].GetLocation();
        for(int32 B=0;B<3;++B)Attack[B].AddToTranslation(Shift);
        ProphecyAttackStartInertia::MoveHip(Attack[0],Attack[1],Attack[2],nullptr,Hip);
    }
    Attack[2].SetRotation(FootRotation);Attack[3]=ToeLocal*Attack[2];
    // The positional handoff also converges to the attack pole if it completes
    // before the independent pole clock, avoiding a second jump at ownership exit.
    if(PoleAttackAlpha>=0)ApplyFootLocalPole(Attack,PoleAttackAlpha>=1?AttackPole:
        BlendFootLocalPoles(LocoPole,AttackPole,LocoAxis,1.f-Weight*(1.f-PoleAttackAlpha)));
}
}
