#pragma once

#include "CoreMinimal.h"

// Shared presentation only; policy cadence and recurrent state are unchanged.
namespace ProphecyNNPresentation
{
inline float FromRemainder(float AccumulatedSeconds, float PoseIntervalSeconds)
{
    // Keep the same one-interval presentation delay across every render cadence.
    // Snapping to the endpoint on a hitch spends the interpolation buffer and
    // forces either a rewind or a hold when the next frame has no new NN pose.
    return FMath::Clamp(AccumulatedSeconds / PoseIntervalSeconds, 0.0f, 1.0f);
}

// Manager publication, consumed on the game thread before animation evaluation.
// Stored separately so Live Coding never changes existing snapshot/proxy layouts.
void Publish(int32 AgentId, double SourceTimeSeconds, float Alpha);
// Game-thread publication; animation workers consume a locked, value-only copy.
// Reference offsets are the actual unstretched foot offsets in calf space (cm).
void SetKickFootExtension(int32 AgentId,float LeewayCm,const FVector& LeftReference,const FVector& RightReference);
void SetKickFootReturn(int32 AgentId,bool Returning,const FVector2D& ExtensionCm);
bool ApplyKickFootExtension(int32 AgentId,TConstArrayView<FName> BoneNames,TArrayView<FTransform> Transforms);
float Resolve(int32 AgentId, double SourceTimeSeconds, double WorldTimeSeconds,
    float FrameDeltaSeconds, float PoseIntervalSeconds, bool bInterpolate);
}
