#include "ProphecyBloodNiagaraCallbacks.h"
#include "ProphecyFoliageDecalGridComponent.h"
#include "NiagaraComponent.h"
#include "NiagaraDataInterfaceExport.h"
#include "NiagaraSystem.h"
#include "Async/Async.h"
#include "Containers/Queue.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "EngineUtils.h"
#include "UObject/UObjectArray.h"
#include "UObject/UObjectIterator.h"
#include <atomic>

namespace ProphecyBloodCallbacks
{
const FName CallbackName(TEXT("User.decal_callback"));
TMap<TWeakObjectPtr<UWorld>, TWeakObjectPtr<AActor>> Managers;
TSet<TWeakObjectPtr<UNiagaraComponent>> Pending;
FDelegateHandle Cleanup, ActorsReady, LevelReady;
UProphecyBloodNiagaraCallbacks* Receiver = nullptr;
bool Running = false;

bool ValidCallback(UObject* Object, UWorld* World)
{
	return IsValid(Object) && !Object->IsTemplate() &&
		Object->GetClass()->ImplementsInterface(UNiagaraParticleCallbackHandler::StaticClass()) &&
		(!Object->GetWorld() || Object->GetWorld() == World);
}

AActor* FindManager(UWorld* World)
{
	if (auto* Cached = Managers.Find(World))
		if (ValidCallback(Cached->Get(), World)) return Cached->Get();
	AActor* Found = nullptr;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (!ValidCallback(*It, World) || !It->FindComponentByClass<UProphecyFoliageDecalGridComponent>()) continue;
		if (Found) return nullptr; // Ambiguous worlds require an explicit callback.
		Found = *It;
	}
	if (Found) Managers.Add(World, Found);
	return Found;
}

void Assign(UNiagaraComponent* Component)
{
	UWorld* World = Component->GetWorld();
	UNiagaraSystem* System = Component->GetAsset();
	if (!World || !World->IsGameWorld() || World->bIsTearingDown || !System) return;
	TArray<FNiagaraVariable> Variables;
	System->GetExposedParameters().GetParameters(Variables);
	const FNiagaraVariable* Callback = Variables.FindByPredicate([](const FNiagaraVariable& V)
		{ return V.GetName() == CallbackName && V.IsUObject(); });
	if (!Callback) { Pending.Remove(Component); return; }
	auto& Parameters = Component->GetOverrideParameters();
	UObject* Existing = Parameters.IndexOf(*Callback) != INDEX_NONE ? Parameters.GetUObject(*Callback).Get() : nullptr;
	if (ValidCallback(Existing, World)) { Pending.Remove(Component); return; }
	AActor* Manager = FindManager(World);
	if (!Manager || !Manager->IsA(Callback->GetType().GetClass()))
	{
		Pending.Add(Component);
		return;
	}
	Component->SetVariableObject(CallbackName, Manager);
	Pending.Remove(Component);
}

void Observe(UNiagaraComponent* Component)
{
	if (!IsValid(Component) || Component->IsTemplate() ||
		Component->HasAnyFlags(RF_NeedLoad | RF_NeedPostLoad | RF_NeedInitialization)) return;
	Component->OnComponentActivated.AddUniqueDynamic(Receiver, &UProphecyBloodNiagaraCallbacks::OnActivated);
	// A spawn helper can activate within the same construction call. Catch up
	// once when its construction notification reaches the game thread.
	if (Component->IsActive()) Assign(Component);
}

void ObserveLevel(ULevel* Level)
{
	if (!Level) return;
	for (AActor* Actor : Level->Actors)
	{
		if (!IsValid(Actor)) continue;
		TInlineComponentArray<UNiagaraComponent*> Components;
		Actor->GetComponents(Components);
		for (auto* Component : Components) Observe(Component);
	}
}

void RetryPending(UWorld* World = nullptr)
{
	TArray<TWeakObjectPtr<UNiagaraComponent>> Copy = Pending.Array();
	for (auto Weak : Copy)
	{
		auto* Component = Weak.Get();
		if (!Component) Pending.Remove(Weak);
		else if (!World || Component->GetWorld() == World) Assign(Component);
	}
}

// Runtime UObject notifications also cover components added to existing actors.
// Never inspect/mutate a component while its constructor is still executing.
class FCreated final : public FUObjectArray::FUObjectCreateListener
{
public:
	const UClass* NiagaraClass = nullptr;
	const UClass* ActorClass = nullptr;
	const UClass* CallbackInterface = nullptr;
	TQueue<FWeakObjectPtr, EQueueMode::Mpsc> Queue;
	std::atomic<bool> Scheduled{false};
	std::atomic<bool> Enabled{false};

	void Drain()
	{
		check(IsInGameThread());
		Scheduled.store(false);
		FWeakObjectPtr Weak;
		bool ManagerCreated = false;
		while (Queue.Dequeue(Weak))
		{
			if (!Running) continue;
			if (auto* Component = Cast<UNiagaraComponent>(Weak.Get())) Observe(Component);
			else if (auto* Actor = Cast<AActor>(Weak.Get()); Actor && !Actor->IsTemplate())
			{
				Managers.Remove(Actor->GetWorld());
				ManagerCreated = true;
			}
		}
		if (Running && ManagerCreated) RetryPending();
	}
	virtual void NotifyUObjectCreated(const UObjectBase* Object, int32) override
	{
		const UClass* Class = Object->GetClass();
		if (!Enabled.load() || !Class ||
			(!Class->IsChildOf(NiagaraClass) &&
			 !(Class->IsChildOf(ActorClass) && Class->ImplementsInterface(CallbackInterface)))) return;
		Queue.Enqueue(FWeakObjectPtr(static_cast<const UObject*>(Object)));
		if (!Scheduled.exchange(true))
			AsyncTask(ENamedThreads::GameThread, [this]() { Drain(); });
	}
	virtual void OnUObjectArrayShutdown() override
	{
		Enabled.store(false);
		GUObjectArray.RemoveUObjectCreateListener(this);
	}
} Created;
}

void UProphecyBloodNiagaraCallbacks::OnActivated(UActorComponent* Component, bool)
{
	if (ProphecyBloodCallbacks::Running)
		if (auto* Niagara = Cast<UNiagaraComponent>(Component)) ProphecyBloodCallbacks::Assign(Niagara);
}

void UProphecyBloodNiagaraCallbacks::Startup()
{
	using namespace ProphecyBloodCallbacks;
	if (Running) return;
	Receiver = GetMutableDefault<UProphecyBloodNiagaraCallbacks>();
	Created.NiagaraClass = UNiagaraComponent::StaticClass();
	Created.ActorClass = AActor::StaticClass();
	Created.CallbackInterface = UNiagaraParticleCallbackHandler::StaticClass();
	Running = true;
	Created.Enabled.store(true);
	GUObjectArray.AddUObjectCreateListener(&Created);
	// One startup catch-up; future components arrive through creation events.
	for (TObjectIterator<UNiagaraComponent> It; It; ++It) Observe(*It);
	ActorsReady = FWorldDelegates::OnWorldInitializedActors.AddLambda([](const UWorld::FActorsInitializedParams& P)
	{
		Created.Drain();
		for (ULevel* Level : P.World->GetLevels()) ObserveLevel(Level);
		Managers.Remove(P.World);
		RetryPending(P.World);
	});
	LevelReady = FWorldDelegates::LevelAddedToWorld.AddLambda([](ULevel* Level, UWorld* World)
	{
		ObserveLevel(Level);
		Managers.Remove(World);
		RetryPending(World);
	});
	Cleanup = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
	{
		Managers.Remove(World);
		for (TObjectIterator<UNiagaraComponent> It; It; ++It)
		{
			auto* Component = *It;
			if (Component->GetWorld() == World)
			{
				Component->OnComponentActivated.RemoveDynamic(Receiver, &UProphecyBloodNiagaraCallbacks::OnActivated);
				Pending.Remove(Component);
			}
		}
		for (auto It = Pending.CreateIterator(); It; ++It) if (!It->IsValid()) It.RemoveCurrent();
	});
}

void UProphecyBloodNiagaraCallbacks::Shutdown()
{
	using namespace ProphecyBloodCallbacks;
	if (!Running) return;
	Running = false;
	// UObject shutdown may already have removed this listener. Only touch live
	// components when module shutdown happens first (for example a module unload).
	if (Created.Enabled.exchange(false))
	{
		GUObjectArray.RemoveUObjectCreateListener(&Created);
		for (TObjectIterator<UNiagaraComponent> It; It; ++It)
			It->OnComponentActivated.RemoveDynamic(Receiver, &UProphecyBloodNiagaraCallbacks::OnActivated);
	}
	FWorldDelegates::OnWorldInitializedActors.Remove(ActorsReady);
	FWorldDelegates::LevelAddedToWorld.Remove(LevelReady);
	FWorldDelegates::OnWorldCleanup.Remove(Cleanup);
	Pending.Reset(); Managers.Reset();
	Created.Drain();
	Receiver = nullptr;
}
