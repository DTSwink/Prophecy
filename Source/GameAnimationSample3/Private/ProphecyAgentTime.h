#pragma once
#include "CoreMinimal.h"

class AProphecyAgent;
class AProphecyNNLocomotionManager;

// Agent-local policy clocks. The trained step remains unchanged; only its wall
// cadence changes. No actor CustomTimeDilation, blend timer or physics-world dt.
namespace ProphecyAgentTime
{
struct FLane
{
    double Rate = 1., Phase = 0.;
    // A return to 1 finishes the current presentation interval at the next
    // shared boundary, then retires. This avoids jumping interpolation phases.
    double JoinRate = 1.;
    bool Joining = false;
    double EffectiveRate() const { return Joining ? JoinRate : Rate; }
};

struct FStep
{
    TBitArray<> Due, SamplePhysics;
    TArray<double> WorldIntervals;
    double ElapsedSeconds = 0., SourceTimeSeconds = 0.;
    bool SharedBoundary = false;
    FStep(int32 Count) : Due(false,Count), SamplePhysics(false,Count)
    { WorldIntervals.Init(0.,Count); }
};

// Plain clock math, independently testable without an NN or world.
struct FClocks
{
    TMap<int32,FLane> Lanes;
    double SharedPhase = 0.;
    void Set(int32 Index,double Rate);
    double Rate(int32 Index) const;
    double Alpha(int32 Index) const;
    void Advance(double DeltaSeconds,double PolicyStep,int32 Count,int32 MaxSteps,
        TFunctionRef<void(FStep&)> Step);
};

struct FContext
{
    const AProphecyNNLocomotionManager* Manager = nullptr;
    FStep* Step = nullptr;
};
const FContext* Context(const AProphecyNNLocomotionManager* Manager);
bool HasClocks(const AProphecyNNLocomotionManager* Manager);
void Set(AProphecyNNLocomotionManager* Manager,int32 Index,double Rate,float SharedAlpha);
float Rate(const AProphecyNNLocomotionManager* Manager,int32 Index);
float Alpha(const AProphecyNNLocomotionManager* Manager,int32 Index,float SharedAlpha);
void Reset(AProphecyNNLocomotionManager* Manager,int32 Index,float SharedAlpha);
void Remove(const AProphecyNNLocomotionManager* Manager);
void RemoveLane(const AProphecyNNLocomotionManager* Manager,int32 Index);
void Advance(AProphecyNNLocomotionManager* Manager,float DeltaSeconds,float PolicyStep,
    int32 Count,int32 MaxSteps,float& AccumulatedSeconds,double WorldTime,
    TFunctionRef<void(FStep&)> Step);
}
