#pragma once
#include "CoreMinimal.h"

/** Child body-local motor coordinates, rad/s and Nm. No world-space pose servo. */
struct FProphecyJoltRobotMotor
{
    FVector Velocity=FVector::ZeroVector;
    FVector TorqueLimit=FVector::ZeroVector;
    float Damping=0;
    bool bBall=false;
};

/** Compound drag tensor in native SI body-local coordinates. */
struct FProphecyJoltRobotDrag
{
    float Coefficient=0;
    FVector First=FVector::ZeroVector;
    FVector Second[3]={FVector::ZeroVector,FVector::ZeroVector,FVector::ZeroVector};
};
