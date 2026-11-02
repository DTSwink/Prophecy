#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKLive.h"

class AProphecyAgent;

// The live inclined/slide owner advances root, contacts and recurrent NN in one
// canonical clock. It never initializes a recorded gait or a fixed-length course.
namespace ProphecyFootIKSurface
{
struct FPolicyHandoff
{
    ProphecyFootIKLive::FSourceSample Previous,Current;
    FVector VelocityWorld=FVector::ZeroVector;
    int32 Tick=0;
    bool WasSliding=false;
    FString Json;
};
bool Enable(AProphecyAgent* Agent,const FTransform& CourseWorld,
    const ProphecyFootIKLive::FSourceSample& PreviousActual30Hz,
    const ProphecyFootIKLive::FSourceSample& CurrentActual,
    const FString& SettingsJson,const FString& GeometryJson,
    const FString& LowerRuntimeContractPath,const FString& UpperRuntimeContractPath,FString& Error);
bool Active(const AProphecyAgent* Agent);
bool AnyActive();
void Remove(AProphecyAgent* Agent);
// Exactly one authored60Hz step. HeadingWindow is previous/current+8future
// controller headings, independent of the surface carrier's body tilt.
bool Tick(AProphecyAgent* Agent,const FVector& DesiredVelocityWorld,
    TConstArrayView<FTransform> HeadingWindow,uint64 GameTick,FString& Error);
bool UpdateGeometry(AProphecyAgent* Agent,const FString& GeometryJson,FString& Error);
bool Root(AProphecyAgent* Agent,FVector& Position,float& Yaw,FVector* Velocity=nullptr);
bool History(AProphecyAgent* Agent,FVector& Position,float& Yaw);
bool Apply(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    const FTransform& ComponentWorld);
FString Diagnostics(const AProphecyAgent* Agent);
double LastSeconds(const AProphecyAgent* Agent);
bool Status(const AProphecyAgent* Agent,FProphecyFootIKLiveState& Out);
// Read before Remove. This is clean locomotion history for recurrent NN reset,
// separate from the visible physical target pair supplied by Apply.
bool ReadPolicyHandoff(AProphecyAgent* Agent,FPolicyHandoff& Out,FString& Error);
}
