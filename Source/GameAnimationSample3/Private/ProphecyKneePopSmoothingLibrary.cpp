#include "ProphecyKneePopSmoothingLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPresentation.h"

bool UProphecyKneePopSmoothingLibrary::SetKneePopSmoothing(AProphecyAgent* Agent,bool Enabled,float SoftZoneCm)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !FMath::IsFinite(SoftZoneCm) || SoftZoneCm<0) return false;
    int32 Id;float Interval;bool Interpolate;
    if (!Agent->GetNNPoseDataSource(Id,Interval,Interpolate)) return false;
    ProphecyNNPresentation::SetKneePopSmoothing(Id,Enabled?SoftZoneCm:0.f);
    return true;
}
