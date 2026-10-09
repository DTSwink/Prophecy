#pragma once
#include "CoreMinimal.h"
#include "ProphecyFKReturnMath.h"
class AProphecyAgent;
namespace ProphecyFKReturn
{
struct FProfile
{
    float Duration=.26f,Inertia=.51f,Easing=.12f;
    float InertiaHold=0.f,InertiaDecay=1.f,AngleTimeSeconds=0.f;
    bool WorldInertia=false;
    float UpperArmTwistRemoval=0.f;
    float Weights[GroupCount]={0.f,.19f,1.f,.63f,1.f,1.f,1.f};
};
bool Prepare(FCurve& Curve,const FProfile& Profile,float Coefficient,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,float SampleSeconds,TConstArrayView<FVector3f> AngularVelocity={});
// Cache only on handoff. Bones are mapped once, not during crowd updates.
void Begin(const AProphecyAgent* Agent,FName Attack,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks=0);
// PublishedAgeTicks is the policy scheduler's already-spent game-tick budget
// since Current was published, not a timestamp difference. Natural exits are
// one policy interval old; an explicit stop may occur between boundaries.
// SourceTime identifies publications only; it never measures elapsed return time.
// The shared clock advances exactly 1/60 per unpaused game tick.
bool Apply(const AProphecyAgent* Agent,double SourceTime,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    bool* NewSample=nullptr,const FQuat& Frame=FQuat::Identity);
bool IsActive(const AProphecyAgent* Agent);
void BeginParry(const AProphecyAgent* Agent,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks=0);
// Spend pending game ticks before deciding whether this step needs the upper NN.
bool NeedsInference(const AProphecyAgent* Agent);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
