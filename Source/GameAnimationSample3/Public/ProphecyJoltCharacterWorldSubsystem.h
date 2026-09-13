#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyJoltCharacterWorldSubsystem.generated.h"

class AActor;
class UActorComponent;
class IProphecyJoltStepClient;
class UProphecyJoltCharacterComponent;
class UProphecyJoltCharacterWorldSubsystem;

DECLARE_DELEGATE_OneParam(FProphecyJoltClientAdmissionCallback, const FGuid&);

USTRUCT()
struct FProphecyJoltCharacterWorldTickFunction : public FTickFunction
{
    GENERATED_BODY()

    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> Target;
    virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
        const FGraphEventRef& MyCompletionGraphEvent) override;
    virtual FString DiagnosticMessage() override;
    virtual FName DiagnosticContext(bool bDetailed) override;
};

template<>
struct TStructOpsTypeTraits<FProphecyJoltCharacterWorldTickFunction>
    : public TStructOpsTypeTraitsBase2<FProphecyJoltCharacterWorldTickFunction>
{
    enum { WithCopy = false };
};

struct FProphecyJoltStepClientRegistration
{
    TWeakObjectPtr<UActorComponent> Client;
    TWeakObjectPtr<AActor> PublishingActor;
    FGuid RegistrationId;
};

struct FProphecyJoltClientPendingAdmission
{
    TWeakObjectPtr<UActorComponent> Client;
    FGuid AdmissionId;
    FProphecyJoltClientAdmissionCallback Complete;
    FProphecyJoltClientAdmissionCallback Cancel;
};

/** One shared explicit physics step after registered publishers, followed by all completed poses.
 * Historical class name retained for API compatibility. Never initializes Jolt or creates geometry.
 */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJoltCharacterWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void OnWorldEndPlay(UWorld& InWorld) override;
    virtual void PreDeinitialize() override;
    virtual void Deinitialize() override;

    // Native callbacks must be weak-bound to Client (CreateUObject or CreateWeakLambda), and recheck
    // the supplied token. Immediate admission returns false/invalid deferred outputs; caller enables now.
    // Deferred admission creates no native state. Teardown invokes Cancel; explicit cancellation only
    // removes the token because the calling client already owns its local cancellation.
    bool RequestClientAdmission(UActorComponent& Client, const FProphecyJoltClientAdmissionCallback& Complete,
        const FProphecyJoltClientAdmissionCallback& Cancel, bool& bOutDeferred, FGuid& OutAdmissionId, FString& OutError);
    bool CancelClientAdmission(UActorComponent& Client, const FGuid& AdmissionId);
    bool CanRegisterStepClient(const UActorComponent& Client, FString& OutError);
    // Client must already own and have primed its native binding. Publisher is optional; passive props
    // do not need an enabled Actor tick. Every client using one publisher shares its prerequisite.
    bool RegisterStepClient(UActorComponent& Client, AActor* PublishingActor, FGuid& OutRegistrationId, FString& OutError);
    bool UnregisterStepClient(UActorComponent& Client, const FGuid& RegistrationId);
    bool IsStepClientRegistered(const UActorComponent& Client, const FGuid& RegistrationId) const;
    int32 GetRegisteredStepClientCount() const;
    bool StepExplicit(UActorComponent& Requester, const FGuid& RegistrationId, float DeltaSeconds, FString& OutError);

    // Existing character APIs remain adapters to the same registry/admission/step owner.
    bool RequestEnable(UProphecyJoltCharacterComponent& Character, bool& bOutDeferred, FString& OutError);
    void CancelPendingEnable(UProphecyJoltCharacterComponent& Character);
    bool CanRegisterCharacter(const UProphecyJoltCharacterComponent& Character, FString& OutError);
    bool RegisterCharacter(UProphecyJoltCharacterComponent& Character, FString& OutError);
    void UnregisterCharacter(UProphecyJoltCharacterComponent& Character);
    bool StepExplicit(UProphecyJoltCharacterComponent& Requester, float DeltaSeconds, FString& OutError);
    int32 GetRegisteredCharacterCount() const;

    // OR of explicit active client requests; native body counts never imply automatic stepping.
    bool HasAutomaticStepOwners() const;
    bool IsSteppingStopped() const { return bStopped; }
    const FString& GetLastError() const { return LastError; }
    // Startup-only experiment: default PrePhysics, opt-in -ProphecyJoltDuringPhysics.
    // These are native, read-only provenance; explicit Step callers retain their own cadence.
    ETickingGroup GetAutomaticTickGroup() const { return StepTick.TickGroup; }
    ETickingGroup GetLastAutomaticTickGroup() const { return LastAutomaticTickGroup; }
    ETickingGroup GetLastAutomaticEndTickGroup() const { return LastAutomaticEndTickGroup; }
    ETickingGroup GetLastAutomaticWorldTickGroup() const { return LastAutomaticWorldTickGroup; }
    uint64 GetLastAutomaticStepEngineFrame() const { return LastAutomaticStepEngineFrame; }
    uint64 GetAutomaticStepCount() const { return AutomaticStepCount; }

protected:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
    friend struct FProphecyJoltCharacterWorldTickFunction;
    void TickAutomatic(float DeltaSeconds);
    bool StepRegisteredClients(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError);
    bool StopWithError(FString& OutError, const FString& Error);
    void PruneRegistrations();
    void RemoveRegistrationPrerequisite(const FProphecyJoltStepClientRegistration& Registration);
    IProphecyJoltStepClient* ResolveClient(const FProphecyJoltStepClientRegistration& Registration) const;
    void RefreshTickEnabled();
    void StopForWorldTeardown();
    bool CanRequestAdmission(const UActorComponent& Client, FString& OutError);
    bool CanAdmitImmediately() const;
    void OnWorldTickStart(UWorld* World, ELevelTick TickType, float DeltaSeconds);
    void OnWorldPreActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
    void OnWorldTickEnd(UWorld* World, ELevelTick TickType, float DeltaSeconds);

    UPROPERTY(Transient)
    FProphecyJoltCharacterWorldTickFunction StepTick;
    TArray<FProphecyJoltStepClientRegistration> RegisteredClients;
    // Exact identity lookup avoids an O(N^2) scan when validating every client during a crowd frame.
    TMap<FGuid, TWeakObjectPtr<UActorComponent>> RegistrationOwners;
    TArray<FProphecyJoltClientPendingAdmission> PendingAdmissions;
    FDelegateHandle TickStartHandle;
    FDelegateHandle PreActorTickHandle;
    FDelegateHandle TickEndHandle;
    FGuid StepWorldLifetime;
    uint64 ExpectedWorldSteps = 0;
    uint64 LastStepEngineFrame = MAX_uint64;
    ETickingGroup LastAutomaticTickGroup = TG_MAX;
    ETickingGroup LastAutomaticEndTickGroup = TG_MAX;
    ETickingGroup LastAutomaticWorldTickGroup = TG_MAX;
    uint64 LastAutomaticStepEngineFrame = MAX_uint64;
    uint64 AutomaticStepCount = 0;
    bool bExecutingStep = false;
    bool bEnding = false;
    bool bStopped = false;
    bool bWorldTickInProgress = false;
    bool bAdmissionWindowOpen = false;
    FString LastError;
};
