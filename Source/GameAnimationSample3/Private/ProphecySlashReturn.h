#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySlashReturn
{
bool IsSlash(FName Attack);
bool Active(const AProphecyAgent* A);
void Begin(const AProphecyAgent* A,FName Attack);
void Cancel(const AProphecyAgent* A);
void Remove(const AProphecyAgent* A);
void CaptureReset(const AProphecyAgent* A);
void RestoreReset(const AProphecyAgent* A);
void ForgetReset(const AProphecyAgent* A);
// Component-space transforms; the previous pose has already been root-rebased.
void ApplyPose(const AProphecyAgent* A,const FTransform& Torso,const FTransform& PreviousTorso,
    double HalfWidth,const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,const FTransform& NeutralShoulder,
    const FTransform& NeutralElbow,const FTransform& NeutralWrist,const FTransform& InitialNeutralWrist,
    FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,const FVector& LocalPole);
}
