#include "ProphecyAgentResetLibrary.h"
#include "ProphecyNNLocomotionManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "TimerManager.h"

namespace ProphecyAgentReset
{
struct FSession
{
    TArray<TWeakObjectPtr<AProphecyNNLocomotionManager>> Managers;
    int32 Count = 0;
    bool bPending = false;
};
static TMap<TWeakObjectPtr<UWorld>, FSession> Sessions;
static FDelegateHandle CleanupHandle;
static UWorld* World(const UObject* Context)
{
    return IsInGameThread() && GEngine ? GEngine->GetWorldFromContextObject(Context, EGetWorldErrorMode::ReturnNull) : nullptr;
}
}

bool UProphecyAgentResetLibrary::InitializeAgentReset(const UObject* Context, int32& AgentCount, FString& Error)
{
    using namespace ProphecyAgentReset;
    Error.Reset(); AgentCount = 0;
    UWorld* W = World(Context);
    if (!W || !W->IsGameWorld()) { Error = TEXT("Initialize Agent Reset requires a game world."); return false; }
    if (const auto* Existing = Sessions.Find(W)) { AgentCount = Existing->Count; return true; }
    FSession Session;
    for (TActorIterator<AProphecyNNLocomotionManager> It(W); It; ++It)
    {
        const int32 Count = It->CaptureInitialAgentResetState(Error);
        if (!Error.IsEmpty())
        {
            for (auto& M : Session.Managers) if (M.IsValid()) M->ClearInitialAgentResetState();
            return false;
        }
        if (Count > 0) { Session.Managers.Add(*It); Session.Count += Count; }
    }
    if (!Session.Count) { Error = TEXT("No initialized NN agents. Call Initialize Agent Reset after the manager is ready."); return false; }
    if (!CleanupHandle.IsValid())
        CleanupHandle = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* Ending, bool, bool)
        {
            if (auto* S = Sessions.Find(Ending))
                for (auto& M : S->Managers) if (M.IsValid()) M->ClearInitialAgentResetState();
            Sessions.Remove(Ending);
        });
    AgentCount = Session.Count;
    Sessions.Add(W, MoveTemp(Session));
    return true;
}

bool UProphecyAgentResetLibrary::ResetInitialAgents(const UObject* Context, FString& Error)
{
    using namespace ProphecyAgentReset;
    Error.Reset();
    UWorld* W = World(Context);
    FSession* Session = W ? Sessions.Find(W) : nullptr;
    if (!Session) { Error = TEXT("Call Initialize Agent Reset once before Reset Initial Agents."); return false; }
    if (Session->bPending) return true;
    Session->bPending = true;
    W->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateLambda([WeakWorld = TWeakObjectPtr<UWorld>(W)]
    {
        auto* S = Sessions.Find(WeakWorld);
        if (!WeakWorld.IsValid() || !S) return;
        // Copy weak owners before reset: animation callbacks may remove actors/worlds.
        const auto Managers = S->Managers;
        for (const auto& M : Managers)
        {
            if (!M.IsValid()) continue;
            FString Failure;
            const int32 ResetCount = M->RestoreInitialAgentResetState(Failure);
            if (!Failure.IsEmpty()) UE_LOG(LogTemp, Warning, TEXT("Agent reset (%d restored): %s"), ResetCount, *Failure);
        }
        if (auto* Current = Sessions.Find(WeakWorld)) Current->bPending = false;
    }));
    return true;
}
