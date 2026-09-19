#pragma once
#include "CoreMinimal.h"
class UBodySetup;

// Geometry-only queries against authored simple collision. No body/world registration.
class PROPHECYJOLT_API FProphecyJoltContactShape
{
public:
    FProphecyJoltContactShape();
    ~FProphecyJoltContactShape();
    bool Build(const UBodySetup& Setup,const FVector& Scale,FString& Error);
    // On-demand diagnostic: deepest authored-shape overlap, in cm (zero when separate).
    float PenetrationCm(const FTransform& A,const FProphecyJoltContactShape& Other,const FTransform& B) const;
    // Rigid bone/component origins; scale is baked by Build. Fraction is in [0,1].
    bool Sweep(const FTransform& A0,const FTransform& A1,const FProphecyJoltContactShape& Other,
        const FTransform& B0,const FTransform& B1,float& Fraction) const;
private:
    struct FNative;
    TUniquePtr<FNative> Native;
};
