#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyArmCone
{
void BeginAttack(const AProphecyAgent* Agent,FName Attack);
// Release the attack hold without resetting the accepted pose or recoil state.
void Begin(const AProphecyAgent* Agent,FName Attack);
void Cancel(const AProphecyAgent* Agent);
bool Active(const AProphecyAgent* Agent);
// Decode the authored idle only once per agent, and only when wrist recovery needs it.
bool NeedsWristIdleReference(const AProphecyAgent* Agent);
void SetWristIdleReference(const AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<FTransform> Idle);
bool ApplyNNPose(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Pose,const FTransform& Carrier,float DeltaSeconds);
struct FPublicationFeedback
{
    uint8 Arms=0;
    FQuat WristRotation[2]={FQuat::Identity,FQuat::Identity}; // Component space, before wrist recoil.
};
// Return bit 0/1: visible left/right arm corrected. Feedback excludes wrist recoil.
uint8 ApplyNNPublication(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,const FTransform& PreviousCarrier,
    const FTransform& Carrier,float DeltaSeconds,bool NewSample,FPublicationFeedback* Feedback=nullptr);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
