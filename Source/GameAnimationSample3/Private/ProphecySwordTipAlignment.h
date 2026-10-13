#pragma once
#include "CoreMinimal.h"

// Same grip-centred, holster-local path as SwordHolsterLab/tipalign.js.
struct FProphecySwordTipAlignment
{
    FVector From,To,TipOffset,TargetTip;
    FQuat FromRotation,ToRotation;
    int32 Start=0,Ticks=1;
    double Scale=1,Insertion=0,TranslationTicks=0,RotationTicks=0;

    void Begin(const FTransform& Holster,const FTransform& Full,const FTransform& Blade,
        const FVector& TipLocal,const FVector& BaseLocal,const FVector& Mouth,const FVector& Hand,double InScale,
        int32 Tick,double Tolerance,double ReachSpeed,double RotationSpeed)
    {
        const FVector Tip=Blade.TransformPosition(TipLocal);
        TipOffset=Blade.GetRotation().UnrotateVector(Tip-Hand);
        From=Holster.GetRotation().UnrotateVector(Hand-Holster.GetLocation());
        FromRotation=(Holster.GetRotation().Inverse()*Blade.GetRotation()).GetNormalized();
        const FQuat Aim=(FQuat::FindBetweenVectors(Tip-Hand,Mouth-Hand)*Blade.GetRotation()).GetNormalized();
        const double Error=FMath::RadiansToDegrees(Full.GetRotation().AngularDistance(Aim));
        const FQuat End=FQuat::Slerp(Full.GetRotation(),Aim,Error>Tolerance?Tolerance/Error:1.).GetNormalized();
        ToRotation=(Holster.GetRotation().Inverse()*End).GetNormalized();
        const FVector Axis=Full.GetRotation().GetAxisZ(),ZeroHand=Mouth-End.RotateVector(TipOffset);
        const double Depth=FVector::DotProduct(Hand-ZeroHand,Axis);
        const double Span=FVector::DotProduct(Full.GetRotation().RotateVector(Blade.GetScale3D()*(TipLocal-BaseLocal)),Axis);
        Insertion=Depth/FMath::Max(Span,1.e-8);
        To=Holster.GetRotation().UnrotateVector(ZeroHand+Axis*Depth-Holster.GetLocation());
        TargetTip=Holster.GetRotation().UnrotateVector(Mouth+Axis*Depth-Holster.GetLocation());
        TranslationTicks=FVector::Distance(From,To)/ReachSpeed*60;
        RotationTicks=FMath::RadiansToDegrees(FromRotation.AngularDistance(ToRotation))/RotationSpeed*60;
        Start=Tick;Ticks=FMath::Max(1,FMath::CeilToInt(FMath::Max(TranslationTicks,RotationTicks)));Scale=InScale;
    }
    void Sample(const FTransform& Holster,double Tick,FVector& Tip,FQuat& Rotation) const
    {
        const double Elapsed=FMath::Max(0.,Tick-Start);
        const auto Fraction=[Elapsed](double Duration){return Duration>0?FMath::Clamp(Elapsed/Duration,0.,1.):Elapsed>0?1.:0.;};
        Rotation=(Holster.GetRotation()*FQuat::Slerp(FromRotation,ToRotation,Fraction(RotationTicks))).GetNormalized();
        const FVector Hand=Holster.GetLocation()+Holster.GetRotation().RotateVector(FMath::Lerp(From,To,Fraction(TranslationTicks)));
        Tip=Hand+Rotation.RotateVector(TipOffset);
    }
};
