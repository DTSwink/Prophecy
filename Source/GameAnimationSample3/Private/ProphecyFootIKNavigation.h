#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

// Vertical navigation carrier for ordinary Foot IK locomotion. The manager's
// NN root/state remains virtual and flat; this layer follows actual root-only
// collision geometry without a second horizontal/velocity integration.
namespace ProphecyFootIKNavigation
{
struct FMove
{
    FVector VirtualRoot=FVector::ZeroVector,ActualRoot=FVector::ZeroVector;
    FVector PreviousVirtualRoot=FVector::ZeroVector,PreviousActualRoot=FVector::ZeroVector;
    FVector SupportNormal=FVector::UpVector;
    bool HasSupport=false;
};
// Caller owns eligibility (ordinary live layer, no surface/Bodyflip/action).
// All calls are game-thread only. Initial actual height is preserved.
void Begin(AProphecyAgent* Agent,double VirtualHeight,double MaximumInclineDegrees=80);
bool Active(const AProphecyAgent* Agent);
double Lift(const AProphecyAgent* Agent);
bool PrepareMove(AProphecyAgent* Agent,const FVector& DesiredVirtualRoot,FMove& Out);
// Call after the existing actual capsule sweep. Return this virtual root to
// collision rebasing; the support-height change must not enter NN recurrence.
FVector CommitMove(AProphecyAgent* Agent,const FMove& Move,const FVector& AppliedActualRoot);
// Exact source-time pair caching keeps repeated physical/render reads from
// resampling old history against a new floor height.
bool PublicationCarriers(AProphecyAgent* Agent,double SourceTime,
    const FVector& PreviousVirtualRoot,const FVector& CurrentVirtualRoot,
    FVector& PreviousActualRoot,FVector& CurrentActualRoot);
// Input starts at the actual displayed root; row0 stays exact. Future XY/yaw
// stay controller-authored, while support elevation is projected sequentially.
bool ProjectWindow(AProphecyAgent* Agent,TArray<FTransform>& WorldRoots);
// Before removal, the manager translates its virtual root origin by this lift
// once, preserving the actual character height and all root-local NN values.
double Remove(AProphecyAgent* Agent);
}
