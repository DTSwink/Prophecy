#include "ProphecyExplosionReceiverComponent.h"
#include "ProphecyExplosionLibrary.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UProphecyExplosionReceiverComponent::UProphecyExplosionReceiverComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

bool UProphecyExplosionReceiverComponent::TryAcceptImpact()
{
    if (RemainingTicks || !IsRegistered() || !IsValid(GetOwner())
        || GetOwner()->IsActorBeingDestroyed() || !OnExplosionImpact.IsBound()) return false;
    RemainingTicks = 30;
    CooldownHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &ThisClass::AdvanceCooldown);
    return true;
}

void UProphecyExplosionReceiverComponent::AdvanceCooldown(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (World != GetWorld() || !World || World->IsPaused() || TickType != LEVELTICK_All || DeltaSeconds <= 0) return;
    if (--RemainingTicks <= 0) StopCooldown();
}

void UProphecyExplosionReceiverComponent::StopCooldown()
{
    FWorldDelegates::OnWorldPreActorTick.Remove(CooldownHandle);
    CooldownHandle.Reset();
    RemainingTicks = 0;
}

void UProphecyExplosionReceiverComponent::OnUnregister()
{
    StopCooldown();
    Super::OnUnregister();
}

UProphecyExplosionReceiverComponent* UProphecyExplosionLibrary::BindExplosionImpact(AActor* Agent, FProphecyExplosionImpactCallback Event)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Event.IsBound()) return nullptr;
    auto* Receiver = Agent->FindComponentByClass<UProphecyExplosionReceiverComponent>();
    if (!Receiver)
    {
        Receiver = NewObject<UProphecyExplosionReceiverComponent>(Agent);
        Agent->AddInstanceComponent(Receiver);
        Receiver->RegisterComponent();
    }
    Receiver->OnExplosionImpact.AddUnique(Event);
    return Receiver;
}
