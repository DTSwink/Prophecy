#pragma once
#include "CoreMinimal.h"
#include "ProphecyJoltWorldSubsystem.h"
class FJsonObject;
class UWorld;

// Owns only the held visuals and standalone projectile bodies for one controller.
class FProphecyBodyflipProjectiles
{
public:
    FProphecyBodyflipProjectiles();
    ~FProphecyBodyflipProjectiles();
    bool Initialize(UWorld* World,const FTransform& Space,FString& Error);
    bool Update(const TSharedPtr<FJsonObject>& Result,double Time,FString& Error);
    bool CanSeek(const TSharedPtr<FJsonObject>& Result,double Time,FString& Error) const;
    bool Seek(const TSharedPtr<FJsonObject>& Result,double Time,FString& Error);
    void InvalidateHistory();
    void SetPaused(bool Paused);
    void Reset();
    struct FImpl;
private:
    TUniquePtr<FImpl> Impl;
};
namespace ProphecyBodyflip
{
// Called once by the existing shared-world coordinator; never creates/steps a world.
bool ProjectileStepSchedule(UWorld* World,FProphecyJoltStepSchedule& Out);
#if WITH_DEV_AUTOMATION_TESTS
// Read-only snapshots; the optional observer runs between existing shared steps.
// No samples are retained by production projectile state.
struct FProjectileDiagnostic
{
    FString Id,Kind;
    double Time=0,ReleaseTime=-1;
    FTransform Visual=FTransform::Identity,Space=FTransform::Identity;
    bool HasBody=false;
    FProphecyJoltBodyState Body;
    TSharedPtr<const FJsonObject> Launch;
};
void ReadProjectileDiagnostics(UWorld* World,TArray<FProjectileDiagnostic>& Out);
void SetProjectileDiagnosticObserver(UWorld* World,
    TFunction<void(const FProjectileDiagnostic&,const TCHAR*)> Observer);
#endif
}
