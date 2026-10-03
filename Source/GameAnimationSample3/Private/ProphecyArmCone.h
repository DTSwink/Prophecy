#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyArmCone
{
void BeginAttack(const AProphecyAgent* Agent,FName Attack);
// Release the attack hold without resetting the accepted pose or recoil state.
void Begin(const AProphecyAgent* Agent,FName Attack);
void Cancel(const AProphecyAgent* Agent);
extern bool bAnyActive;
FORCEINLINE bool AnyActive(){return bAnyActive;}
bool Active(const AProphecyAgent* Agent);
bool ApplyNNPose(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Pose,const FTransform& Carrier,float DeltaSeconds);
struct FPublicationFeedback
{
    uint8 Arms=0;
    FQuat WristRotation[2]={FQuat::Identity,FQuat::Identity}; // Component space, accepted cone correction.
};
// Return bit 0/1: visible left/right arm corrected. Feedback records the cone correction.
uint8 ApplyNNPublication(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,const FTransform& PreviousCarrier,
    const FTransform& Carrier,float DeltaSeconds,bool NewSample,FPublicationFeedback* Feedback=nullptr);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
