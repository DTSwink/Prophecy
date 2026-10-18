// Owned by the native world, with no separate tick/delegate/timer or global lifetime map.
namespace ProphecyExplosion
{
struct FNotification
{
    TWeakObjectPtr<UProphecyExplosionReceiverComponent> Receiver;
    FProphecyExplosionImpact Impact;
};
using FNotifications = TArray<FNotification, TInlineAllocator<8>>;
// Called under body locks: gather data only, never execute Blueprint here.
void Collect(const FProphecyJoltWorldState& State, const JPH::Body& Body,
    JPH::Vec3Arg Impulse, JPH::RVec3Arg Origin, FNotifications& Events)
{
    const auto* Slot = State.HitSlot(Body);
    auto* Component = Slot ? Cast<UPrimitiveComponent>(Slot->AssociatedObject.Get()) : nullptr;
    auto* Actor = IsValid(Component) ? Component->GetOwner() : nullptr;
    auto* Receiver = IsValid(Actor) ? Actor->FindComponentByClass<UProphecyExplosionReceiverComponent>() : nullptr;
    if (!Receiver || !Receiver->TryAcceptImpact()) return;
    auto& Event = Events.AddDefaulted_GetRef();
    Event.Receiver = Receiver;
    Event.Impact.ExplosionOrigin = ProphecyJolt::Conversions::FromJoltPosition(Origin);
    Event.Impact.ImpactLocation = ProphecyJolt::Conversions::FromJoltPosition(Body.GetCenterOfMassPosition());
    Event.Impact.Impulse = FVector(Impulse.GetX(), Impulse.GetY(), Impulse.GetZ()) * 100.;
    Event.Impact.BoneName = Slot->HitBone;
    Event.Impact.HitComponent = Component;
}
// All bodies, wave cursors and activation are finished before user code can mutate them.
void Dispatch(const FNotifications& Events)
{
    for (const auto& Event : Events)
    {
        auto* Receiver = Event.Receiver.Get();
        if (IsValid(Receiver) && Receiver->IsRegistered() && IsValid(Receiver->GetOwner())
            && !Receiver->GetOwner()->IsActorBeingDestroyed() && IsValid(Event.Impact.HitComponent))
            Receiver->OnExplosionImpact.Broadcast(Event.Impact);
    }
}
uint64 Generation(const FProphecyJoltWorldState& State,const JPH::Body& Body)
{
    const auto* Slot=State.HitSlot(Body);
    if(!Slot) return 0;
    const auto* Component=Cast<UPrimitiveComponent>(Slot->AssociatedObject.Get());
    return Component && Component->bIgnoreRadialImpulse ? 0 : Slot->Generation;
}
FNotifications Advance(FProphecyJoltWorldState& State,double Now)
{
    FNotifications Events;
    State.Explosions.Advance(State.Physics,Now,[&State](const JPH::Body& Body){return Generation(State,Body);},
        [&](const JPH::Body& Body, JPH::Vec3Arg Impulse, JPH::RVec3Arg Origin){ Collect(State,Body,Impulse,Origin,Events); });
    return Events;
}
}

int32 UProphecyExplosionLibrary::StartExplosion(const UObject* Context,FVector Location,float Intensity,float Radius,float FalloffExponent,float ExplosionVelocity)
{
    if (!IsInGameThread() || !IsValid(Context) || Location.ContainsNaN()
        || !FMath::IsFinite(Intensity) || Intensity<=0 || !FMath::IsFinite(Radius) || Radius<=0
        || !FMath::IsFinite(FalloffExponent) || FalloffExponent<0
        || !FMath::IsFinite(ExplosionVelocity) || ExplosionVelocity<0) return 0;
    UWorld* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    auto* Owner=World?World->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;
    if (!Owner || !Owner->ValidateReady().IsSuccess()) return 0;
    auto& State=*Owner->Native;
    ProphecyExplosion::FWave Wave;
    if(ExplosionVelocity>0)
    {
        Wave.Origin=ProphecyJolt::Conversions::ToJoltPosition(Location);
        Wave.RadiusMetres=Radius*.01f;Wave.VelocityMetresPerSecond=ExplosionVelocity*.01f;
        if(!(Wave.VelocityMetresPerSecond>0) || !(Wave.RadiusMetres>0) || !std::isfinite(JPH::Vec3(Wave.Origin).LengthSq()))return 0;
        Wave.StartSeconds=Owner->Diagnostics.SimulatedSeconds;
        Wave.EndSeconds=Wave.StartSeconds+double(Wave.RadiusMetres)/Wave.VelocityMetresPerSecond;
    }
    // Static broadphase layer is excluded before traversal. Dynamic/kinematic are distinguished per body.
    class FMovingLayer final : public JPH::BroadPhaseLayerFilter
    { public: bool ShouldCollide(JPH::BroadPhaseLayer L) const override {return L.GetValue()!=0;} } Filter;
    ProphecyExplosion::FNotifications Events;
    const auto Result=ProphecyExplosion::Apply(State.Physics,ProphecyJolt::Conversions::ToJoltPosition(Location),
        Radius*.01f,Intensity,FalloffExponent,[&State](const JPH::Body& Body)
        { return ProphecyExplosion::Generation(State,Body); },Filter,ExplosionVelocity>0?&Wave:nullptr,
        [&](const JPH::Body& Body, JPH::Vec3Arg Impulse, JPH::RVec3Arg Origin){ ProphecyExplosion::Collect(State,Body,Impulse,Origin,Events); });
    if(ExplosionVelocity>0)State.Explosions.Add(std::move(Wave));
    ProphecyExplosion::Dispatch(Events);
    return Result.Affected;
}

int32 UProphecyExplosionLibrary::DrawExplosionWavefronts(const UObject* Context,FLinearColor Color,float Thickness)
{
#if !UE_BUILD_SHIPPING
    if(!IsInGameThread() || !IsValid(Context) || !FMath::IsFinite(Thickness) || Thickness<0
        || !FMath::IsFinite(Color.R) || !FMath::IsFinite(Color.G) || !FMath::IsFinite(Color.B) || !FMath::IsFinite(Color.A))return 0;
    UWorld* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    auto* Owner=World?World->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;
    if(!Owner || !Owner->ValidateReady().IsSuccess())return 0;
    const auto& Waves=Owner->Native->Explosions.Waves;
    for(const auto& Wave:Waves)
    {
        const FVector Origin=ProphecyJolt::Conversions::FromJoltPosition(Wave.Origin);
        const double Radius=Wave.RadiusAt(Owner->Diagnostics.SimulatedSeconds)*100;
        const FColor Tint=Color.ToFColor(true);
        // Three great circles, 96 short-lived world-depth lines; never drawn through foreground objects.
        DrawDebugCircle(World,Origin,Radius,32,Tint,false,-1,0,Thickness,FVector::ForwardVector,FVector::RightVector,false);
        DrawDebugCircle(World,Origin,Radius,32,Tint,false,-1,0,Thickness,FVector::ForwardVector,FVector::UpVector,false);
        DrawDebugCircle(World,Origin,Radius,32,Tint,false,-1,0,Thickness,FVector::RightVector,FVector::UpVector,false);
    }
    return int32(Waves.size());
#else
    return 0;
#endif
}
