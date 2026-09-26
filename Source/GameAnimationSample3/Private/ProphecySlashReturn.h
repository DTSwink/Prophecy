#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySlashReturn
{
bool IsSlash(FName Attack);
// 0 left / 1 right / INDEX_NONE excluded. Slashes always use the sword arm.
int32 ArmForAttack(FName Attack);
int32 ActiveArm(const AProphecyAgent* A);
// Bit0 left, bit1 right. Consume the shared clock once before applying any arm.
uint8 ActiveArmMask(const AProphecyAgent* A);
double AdvanceFrame(const AProphecyAgent* A);
bool Active(const AProphecyAgent* A);
bool UsesPelvisReference(const AProphecyAgent* A);
bool UsesControlledReference(const AProphecyAgent* A);
void FitNeutralArm(const FTransform& Shoulder,
    FTransform& NeutralShoulder,FTransform& NeutralElbow,FTransform& NeutralWrist);
void PelvisReferenceFrames(const AProphecyAgent* A,const FTransform& IdleTorso,const FTransform& IdlePelvis,
    const FTransform& Pelvis,const FTransform& PreviousPelvis,const FQuat& RootRotation,const FQuat& PreviousRootRotation,
    FTransform& Reference,FTransform& PreviousReference,
    const FTransform* TorsoOrigin=nullptr,const FTransform* PreviousTorsoOrigin=nullptr);
void Begin(const AProphecyAgent* A,FName Attack);
void Cancel(const AProphecyAgent* A);
void Remove(const AProphecyAgent* A);
void CaptureReset(const AProphecyAgent* A);
void RestoreReset(const AProphecyAgent* A);
void ForgetReset(const AProphecyAgent* A);
// Component-space transforms; the previous pose has already been root-rebased.
void ApplyPose(const AProphecyAgent* A,int32 ArmIndex,double FrameDelta,const FTransform& Torso,const FTransform& PreviousTorso,
    double HalfWidth,const FTransform& PreviousShoulder,const FTransform& PreviousElbow,
    const FTransform& PreviousWrist,const FTransform& NeutralShoulder,
    const FTransform& NeutralElbow,const FTransform& NeutralWrist,const FTransform& InitialNeutralWrist,
    FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,const FVector& LocalPole,
    const FTransform* Reference=nullptr,const FTransform* PreviousReference=nullptr);
}
