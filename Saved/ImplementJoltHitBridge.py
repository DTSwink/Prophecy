from pathlib import Path
def edit(file,old,new):
 p=Path(file);s=p.read_text();assert s.count(old)==1,(file,old[:60],s.count(old));p.write_text(s.replace(old,new),newline='\n')
w='Plugins/ProphecyJolt/Source/ProphecyJolt/'
f=w+'Private/ProphecyJoltWorldSubsystem.cpp'
edit(f,'#include "HAL/PlatformTime.h"','#include "HAL/PlatformTime.h"\n#include "Misc/ScopeLock.h"\n#include "PhysicsPublic.h"\n#include "PhysicsEngine/BodyInstance.h"\n#include "GameFramework/Actor.h"')
edit(f,'    TWeakObjectPtr<UObject> AssociatedObject;','''    TWeakObjectPtr<UObject> AssociatedObject;
    FName HitBone;
    int32 HitBodyIndex = INDEX_NONE;
    bool bHitEvents = false;''')
edit(f,'class FProphecyJoltWorldState final','''struct FProphecyJoltPendingHit
{
    FProphecyJoltBodyHandle Body1, Body2;
    FVector Point1, Point2, Normal, Impulse;
};

class FProphecyJoltWorldState final : public JPH::ContactImpulseListener''')
edit(f,'    // Only the GT owner uses this before synchronous Update or after all its jobs joined.','''    // Registry mutations occur only on GT outside Update. Workers read native/plain data only.
    TArray<int32> NativeBodySlots;
    int32 HitEnabledBodies = 0;
    FCriticalSection HitMutex;
    TArray<FProphecyJoltPendingHit> PendingHits;
    uint64 DeliveredHits = 0;
    bool bDispatchingHits = false;

    const ProphecyJolt::WorldPrivate::FBodySlot* HitSlot(const JPH::Body& Body) const
    {
        const uint32 Index = Body.GetID().GetIndex();
        if (Index >= uint32(NativeBodySlots.Num())) return nullptr;
        const int32 SlotIndex = NativeBodySlots[Index];
        if (!Slots.IsValidIndex(SlotIndex)) return nullptr;
        const auto& Slot = Slots[SlotIndex];
        return Slot.Body == Body.GetID() ? &Slot : nullptr;
    }
    bool WantsContactImpulse(const JPH::Body& A, const JPH::Body& B) const override
    {
        const auto Wants = [this](const JPH::Body& Body)
        {
            const auto* Slot = HitSlot(Body);
            if (!Slot) return false;
            if (Slot->bHitEvents) return true;
            const auto* Source = Slot->Weld ? Find(Slot->Weld->SourceHandle) : nullptr;
            return Source && Source->bHitEvents;
        };
        return Wants(A) || Wants(B);
    }
    FProphecyJoltBodyHandle HitHandle(const JPH::Body& Body, const JPH::SubShapeID& Shape) const
    {
        const auto* Slot = HitSlot(Body);
        if (!Slot) return {};
        if (Slot->Weld && Slot->Weld->IsSource(Shape)) return Slot->Weld->SourceHandle;
        FProphecyJoltBodyHandle Handle;
        Handle.WorldLifetime = Lifetime;
        Handle.Slot = NativeBodySlots[Body.GetID().GetIndex()];
        Handle.Generation = Slot->Generation;
        return Handle;
    }
    void OnContactImpulse(const JPH::Body& A, const JPH::Body& B,
        const JPH::SubShapeID& ShapeA, const JPH::SubShapeID& ShapeB,
        JPH::RVec3Arg PointA, JPH::RVec3Arg PointB, JPH::Vec3Arg Normal, float Impulse) override
    {
        using namespace ProphecyJolt::Conversions;
        FProphecyJoltPendingHit Hit;
        Hit.Body1 = HitHandle(A, ShapeA); Hit.Body2 = HitHandle(B, ShapeB);
        const auto* Slot1 = Find(Hit.Body1); const auto* Slot2 = Find(Hit.Body2);
        if (!Slot1 || !Slot2 || (!Slot1->bHitEvents && !Slot2->bHitEvents)) return;
        Hit.Point1 = FromJoltPosition(PointA); Hit.Point2 = FromJoltPosition(PointB);
        Hit.Normal = FromJoltDirection(Normal);
        Hit.Impulse = Hit.Normal * (Impulse * MetersToCentimeters);
        FScopeLock Lock(&HitMutex);
        PendingHits.Add(Hit);
    }
    void SetHitEnabled(ProphecyJolt::WorldPrivate::FBodySlot& Slot, bool bEnabled)
    {
        if (Slot.bHitEvents == bEnabled) return;
        Slot.bHitEvents = bEnabled;
        HitEnabledBodies += bEnabled ? 1 : -1;
        Physics.SetContactImpulseListener(HitEnabledBodies ? this : nullptr);
    }

    // Only the GT owner uses this before synchronous Update or after all its jobs joined.''')
edit(f,'        Physics.SetContactListener(nullptr);','        Physics.SetContactListener(nullptr);\n        Physics.SetContactImpulseListener(nullptr);')
edit(f,'        Slot.Body = Body;','''        Slot.Body = Body;
        const int32 OldNum = NativeBodySlots.Num();
        if (Body.GetIndex() >= uint32(OldNum))
        {
            NativeBodySlots.SetNum(int32(Body.GetIndex()) + 1);
            for (int32 I = OldNum; I < NativeBodySlots.Num(); ++I) NativeBodySlots[I] = INDEX_NONE;
        }
        NativeBodySlots[Body.GetIndex()] = SlotIndex;''')
edit(f,'        Bodies.DestroyBody(Slot.Body);','''        SetHitEnabled(Slot, false);
        NativeBodySlots[Slot.Body.GetIndex()] = INDEX_NONE;
        Slot.HitBone = NAME_None; Slot.HitBodyIndex = INDEX_NONE;
        Bodies.DestroyBody(Slot.Body);''')
edit(f,'        Rig.Handles.Add(Handle);','''        Native->Slots[Handle.Slot].HitBone = Snapshot.Bodies[Index].BodyName;
        Native->Slots[Handle.Slot].HitBodyIndex = Index;
        Rig.Handles.Add(Handle);''')
edit(f,'    TGuardValue<bool> Guard(bStepInProgress, true);','''    if (Native->bDispatchingHits)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Cannot recursively step from a hit callback."));
    Native->PendingHits.Reset();
    TGuardValue<bool> Guard(bStepInProgress, true);''')
code='''
FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyHitEvents(
    const FProphecyJoltBodyHandle& Handle, bool bEnabled)
{
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Native->Find(Handle)) return ProphecyJolt::WorldPrivate::Fail(
        EProphecyJoltWorldResult::InvalidHandle, TEXT("Hit event body is stale."));
    Native->SetHitEnabled(Native->Slots[Handle.Slot], bEnabled);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigHitEvents(
    const FProphecyJoltRigHandle& Handle, UPrimitiveComponent* Receiver, bool bEnabled)
{
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Rig = Native->FindRig(Handle);
    if (!Rig || !IsValid(Receiver) || Receiver->GetWorld() != GetWorld())
        return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Hit event rig/receiver is unavailable."));
    for (const auto& Body : Rig->Handles)
    {
        auto& Slot = Native->Slots[Body.Slot];
        Slot.AssociatedObject = Receiver;
        Native->SetHitEnabled(Slot, bEnabled);
    }
    return {};
}

uint64 UProphecyJoltWorldSubsystem::GetDeliveredHitEventCount() const
{
    return IsInGameThread() && Native ? Native->DeliveredHits : 0;
}

void UProphecyJoltWorldSubsystem::DispatchPendingHitEvents()
{
    if (!ValidateReady().IsSuccess() || Native->bDispatchingHits || Native->PendingHits.IsEmpty()) return;
    const FGuid Lifetime = Native->Lifetime;
    Native->bDispatchingHits = true;
    TArray<FProphecyJoltPendingHit> Hits;
    Swap(Hits, Native->PendingHits);
    // Worker scheduling must not determine callback order. Aggregate subshapes/substeps per body pair.
    for (auto& Hit : Hits)
        if (Hit.Body1.Slot > Hit.Body2.Slot)
        {
            Swap(Hit.Body1, Hit.Body2); Swap(Hit.Point1, Hit.Point2);
            Hit.Normal = -Hit.Normal; Hit.Impulse = -Hit.Impulse;
        }
    Hits.Sort([](const auto& A, const auto& B) {
        if (A.Body1.Slot != B.Body1.Slot) return A.Body1.Slot < B.Body1.Slot;
        if (A.Body2.Slot != B.Body2.Slot) return A.Body2.Slot < B.Body2.Slot;
        if (A.Point1.X != B.Point1.X) return A.Point1.X < B.Point1.X;
        if (A.Point1.Y != B.Point1.Y) return A.Point1.Y < B.Point1.Y;
        return A.Point1.Z < B.Point1.Z;
    });
    for (int32 I = 0; I < Hits.Num(); ++I)
    {
        auto& Hit = Hits[I];
        while (I + 1 < Hits.Num() && Hit.Body1.Slot == Hits[I+1].Body1.Slot && Hit.Body2.Slot == Hits[I+1].Body2.Slot)
            Hit.Impulse += Hits[++I].Impulse;
        for (int32 Side = 0; Side < 2; ++Side)
        {
            // A previous delegate may destroy a body, disable notifications or shut down the world.
            if (!Native || Native->Lifetime != Lifetime || !ValidateReady().IsSuccess()) return;
            const auto* Mine = Native->Find(Side ? Hit.Body2 : Hit.Body1);
            const auto* Other = Native->Find(Side ? Hit.Body1 : Hit.Body2);
            if (!Mine || !Other || !Mine->bHitEvents) continue;
            auto* MyComp = Cast<UPrimitiveComponent>(Mine->AssociatedObject.Get());
            auto* OtherComp = Cast<UPrimitiveComponent>(Other->AssociatedObject.Get());
            AActor* Actor = MyComp ? MyComp->GetOwner() : nullptr;
            if (!IsValid(MyComp) || !IsValid(OtherComp) || !IsValid(Actor) || Actor->IsActorBeingDestroyed()) continue;
            FRigidBodyCollisionInfo MyInfo, OtherInfo;
            MyInfo.Component = MyComp; MyInfo.Actor = Actor;
            MyInfo.BoneName = Mine->HitBone; MyInfo.BodyIndex = Mine->HitBodyIndex;
            OtherInfo.Component = OtherComp; OtherInfo.Actor = OtherComp->GetOwner();
            OtherInfo.BoneName = Other->HitBone; OtherInfo.BodyIndex = Other->HitBodyIndex;
            FCollisionImpactData Impact;
            Impact.TotalNormalImpulse = Side ? Hit.Impulse : -Hit.Impulse;
            const auto* MyBody = MyComp->GetBodyInstance(Mine->HitBone);
            const auto* OtherBody = OtherComp->GetBodyInstance(Other->HitBone);
            Impact.ContactInfos.Emplace(Side ? Hit.Point1 : Hit.Point2, Side ? Hit.Normal : -Hit.Normal,
                float(FMath::Max(0.0, FVector::DotProduct(Hit.Point1 - Hit.Point2, Hit.Normal))), false,
                MyBody ? MyBody->GetSimplePhysicalMaterial() : nullptr,
                OtherBody ? OtherBody->GetSimplePhysicalMaterial() : nullptr);
            ++Native->DeliveredHits;
            Actor->DispatchPhysicsCollisionHit(MyInfo, OtherInfo, Impact);
        }
    }
    if (Native && Native->Lifetime == Lifetime)
    {
        Native->bDispatchingHits = false;
        Hits.Reset(); Swap(Hits, Native->PendingHits);
    }
}

'''
edit(f,'void UProphecyJoltWorldSubsystem::RefreshDiagnostics()',code+'void UProphecyJoltWorldSubsystem::RefreshDiagnostics()')
h=w+'Public/ProphecyJoltWorldSubsystem.h'
edit(h,'    // Module ShutdownModule should verify zero before unregistering global Jolt types.','''    // Optional solved-contact notifications. Delivery is GT-only after completed poses are published.
    FProphecyJoltWorldStatus SetRigHitEvents(const FProphecyJoltRigHandle& Rig, UPrimitiveComponent* Receiver, bool bEnabled);
    FProphecyJoltWorldStatus SetBodyHitEvents(const FProphecyJoltBodyHandle& Body, bool bEnabled);
    void DispatchPendingHitEvents();
    uint64 GetDeliveredHitEventCount() const;

    // Module ShutdownModule should verify zero before unregistering global Jolt types.''')
p=Path(h);s=p.read_text();anchor=next(l for l in s.splitlines() if l.startswith('class ') and ';' in l)
edit(h,anchor,anchor+'\nclass UPrimitiveComponent;')
c='Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp'
edit(c,'    Pending->bOwnsRig = true;','''    Pending->bOwnsRig = true;
    Owner->SetRigHitEvents(Pending->RigHandle, Mesh, Agent->bGeneratePhysicalHitEvents);''')
edit(c,'bool UProphecyJoltCharacterComponent::GetBodyHandle(','''void UProphecyJoltCharacterComponent::SetHitEventsEnabled(bool bEnabled)
{
    if (State && State->WorldOwner.IsValid() && State->Mesh.IsValid())
        State->WorldOwner->SetRigHitEvents(State->RigHandle, State->Mesh.Get(), bEnabled);
}

bool UProphecyJoltCharacterComponent::GetBodyHandle(''')
edit('Source/GameAnimationSample3/Public/ProphecyJoltCharacterComponent.h','    bool GetBodyHandle(FName BoneName, FProphecyJoltBodyHandle& OutHandle) const;', '    bool GetBodyHandle(FName BoneName, FProphecyJoltBodyHandle& OutHandle) const;\n    void SetHitEventsEnabled(bool bEnabled);')
edit('Source/GameAnimationSample3/Private/ProphecyAgent.cpp','\tbGeneratePhysicalHitEvents = bEnabled;', '\tbGeneratePhysicalHitEvents = bEnabled;\n\tif (JoltCharacter) JoltCharacter->SetHitEventsEnabled(bEnabled);')
c='Source/GameAnimationSample3/Private/ProphecyJoltCharacterWorldSubsystem.cpp'
edit(c,'    LastError.Reset();\n    return true;\n}\n\nvoid UProphecyJoltCharacterWorldSubsystem::TickAutomatic', '    LastError.Reset();\n    PhysicsOwner->DispatchPendingHitEvents();\n    return true;\n}\n\nvoid UProphecyJoltCharacterWorldSubsystem::TickAutomatic')
print('Hit bridge added.')
