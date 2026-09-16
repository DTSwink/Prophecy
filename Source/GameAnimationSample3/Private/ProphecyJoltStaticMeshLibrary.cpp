#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltBodyComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"

namespace ProphecyJolt::StaticMeshLibrary
{
// Event-only tracking for adapters created by this library. Never scan the world during a tick.
static TMap<TWeakObjectPtr<UStaticMeshComponent>, TWeakObjectPtr<UProphecyJoltBodyComponent>> Owned;
static FDelegateHandle DestroyHandle;
static FDelegateHandle WorldHandle;
static void RefreshHooks();
static void Retire(UStaticMeshComponent* Mesh)
{
    TWeakObjectPtr<UProphecyJoltBodyComponent> Adapter;
    if (Owned.RemoveAndCopyValue(Mesh, Adapter) && Adapter.IsValid()) Adapter->DestroyComponent();
    RefreshHooks();
}
static void RefreshHooks()
{
    if (Owned.IsEmpty())
    {
        UActorComponent::GlobalDestroyPhysicsDelegate.Remove(DestroyHandle); DestroyHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(WorldHandle); WorldHandle.Reset();
    }
    else if (!DestroyHandle.IsValid())
    {
        DestroyHandle = UActorComponent::GlobalDestroyPhysicsDelegate.AddLambda([](UActorComponent* Source)
        {
            // Query-proxy recreation during handoff is intentional; only actual destruction retires it.
            if (Source && Source->IsBeingDestroyed())
                if (auto* Mesh = Cast<UStaticMeshComponent>(Source)) Retire(Mesh);
        });
        WorldHandle = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
        {
            TArray<TWeakObjectPtr<UStaticMeshComponent>> Keys;
            for (const auto& Pair : Owned)
                if (!Pair.Key.IsValid() || Pair.Key->GetWorld() == World) Keys.Add(Pair.Key);
            for (const auto& Key : Keys)
            {
                TWeakObjectPtr<UProphecyJoltBodyComponent> Adapter;
                if (Owned.RemoveAndCopyValue(Key, Adapter) && Adapter.IsValid()) Adapter->DestroyComponent();
            }
            RefreshHooks();
        });
    }
}
}

bool UProphecyJoltStaticMeshLibrary::EnableJoltStaticMeshPhysics(UStaticMeshComponent* Mesh, FString& OutError)
{
    using namespace ProphecyJolt::StaticMeshLibrary;
    OutError.Reset();
    if (!IsInGameThread() || !IsValid(Mesh) || Mesh->IsBeingDestroyed() || !Mesh->IsRegistered()
        || !IsValid(Mesh->GetOwner()) || Mesh->GetOwner()->IsActorBeingDestroyed())
    { OutError = TEXT("Supply a live registered Static Mesh Component on the game thread."); return false; }
    if (auto* Existing = Owned.Find(Mesh))
    {
        if (Existing->IsValid()) return Existing->Get()->EnableBody(*Mesh, OutError);
        Owned.Remove(Mesh);
    }
    TInlineComponentArray<UProphecyJoltBodyComponent*> Adapters(Mesh->GetOwner());
    for (auto* Adapter : Adapters)
        if (Adapter->GetSourceComponent() == Mesh && (Adapter->IsJoltBody() || Adapter->IsEnablePending())) return true;
    auto* Adapter = NewObject<UProphecyJoltBodyComponent>(Mesh->GetOwner(), NAME_None, RF_Transient);
    Mesh->GetOwner()->AddInstanceComponent(Adapter);
    Adapter->RegisterComponent();
    if (!Adapter->EnableBody(*Mesh, OutError)) { Adapter->DestroyComponent(); return false; }
    Owned.Add(Mesh, Adapter);
    RefreshHooks();
    if (Adapter->IsEnablePending() && !Adapter->FreezePendingLaunch(*Mesh, OutError))
    { Retire(Mesh); return false; }
    return true;
}

void UProphecyJoltStaticMeshLibrary::DisableJoltStaticMeshPhysics(UStaticMeshComponent* Mesh)
{
    if (IsInGameThread()) ProphecyJolt::StaticMeshLibrary::Retire(Mesh);
}

bool UProphecyJoltStaticMeshLibrary::IsJoltStaticMeshPhysicsEnabled(UStaticMeshComponent* Mesh)
{
    if (!IsInGameThread() || !IsValid(Mesh)) return false;
    TInlineComponentArray<UProphecyJoltBodyComponent*> Adapters(Mesh->GetOwner());
    for (auto* Adapter : Adapters)
        if (Adapter->GetSourceComponent() == Mesh && Adapter->IsJoltBody()) return true;
    return false;
}
