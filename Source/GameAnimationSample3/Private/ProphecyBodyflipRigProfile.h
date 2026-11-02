#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
struct FProphecyJoltRigSnapshot;
struct FProphecyJoltRigJoint;
class FProphecyJoltPreparedRig;
namespace ProphecyBodyflip
{
bool CaptureRigProfile(AProphecyAgent* Agent,FString& Json,FString& Error);
// Capture-time serialization is independent of pose and does not mutate a rig.
bool SerializeRigProfile(const FProphecyJoltRigSnapshot& Snapshot,const FProphecyJoltPreparedRig& Prepared,FString& Json,FString& Error);
bool RefreshRigProfile(const FString& Original,TConstArrayView<FProphecyJoltRigJoint> Joints,float FootTrimCm,FString& Json,FString& Error);
}
