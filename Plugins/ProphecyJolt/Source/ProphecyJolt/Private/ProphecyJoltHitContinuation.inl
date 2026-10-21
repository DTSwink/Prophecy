// GT-only opt-in state. No extra solver pass, world query, or mass override.
namespace ProphecyJolt::HitContinuation
{
struct FState
{
    FProphecyJoltBodyHandle Handle;
    FProphecyJoltBodyState Start;
    uint64 Step = 0;
    double Dt = 0.;
    bool Ready = false;
    bool Consumed = false;
};
using FComponents = TMap<TWeakObjectPtr<UPrimitiveComponent>, FState>;
static TMap<TWeakObjectPtr<UWorld>, FComponents> Worlds;

static void Prepare(UProphecyJoltWorldSubsystem& Owner, FProphecyJoltWorldState& Native,
                    double Dt, int32 Substeps, uint64 NextStep)
{
    auto* Components = Worlds.Find(Owner.GetWorld());
    if (!Components) return;
    for (auto It = Components->CreateIterator(); It; ++It)
    {
        auto* Component = It.Key().Get();
        if (!IsValid(Component) || !IsValid(Component->GetOwner()) || Component->GetOwner()->IsActorBeingDestroyed())
        { It.RemoveCurrent(); continue; }
        auto& State = It.Value();
        State.Ready = State.Consumed = false;
        const auto* Slot = Native.Find(State.Handle);
        if (!Slot)
        {
            // Only initial admission/replacement resolves the association. Normal frames use the handle.
            for (int32 I = 0; I < Native.Slots.Num(); ++I)
                if (!Native.Slots[I].Body.IsInvalid() && Native.Slots[I].AssociatedObject.Get() == Component
                    && !Native.Slots[I].OwnerRig.IsSet())
                {
                    State.Handle.WorldLifetime = Native.Lifetime;
                    State.Handle.Slot = I;
                    State.Handle.Generation = Native.Slots[I].Generation;
                    Slot = &Native.Slots[I]; break;
                }
        }
        if (!Slot || Slot->AssociatedObject.Get() != Component || Slot->WeldParent.IsSet()
            || Slot->Weld || Slot->OwnerRig.IsSet() || !Slot->bHitEvents
            || !Slot->IncidentJoints.IsEmpty() || Substeps != 1) continue;
        State.Ready = Owner.ReadBody(State.Handle, State.Start).IsSuccess() && State.Start.bDynamic;
        State.Dt = Dt;
        State.Step = NextStep;
    }
    if (Components->IsEmpty()) Worlds.Remove(Owner.GetWorld());
}

static bool Accept(UProphecyJoltWorldSubsystem& Owner, FProphecyJoltWorldState& Native,
    UPrimitiveComponent& Component, const FProphecyJoltBodyHandle& Mine,
    const FProphecyJoltBodyHandle& Other, const HitImpact::FComponentMotion& Incoming,
    const TArray<FProphecyJoltPendingHit>& Hits, FString& Reason)
{
    auto Fail = [&](const TCHAR* Message) { Reason = Message; return false; };
    auto* Components = Worlds.Find(Owner.GetWorld());
    auto* State = Components ? Components->Find(&Component) : nullptr;
    FProphecyJoltWorldDiagnostics D;
    const auto* Slot = Native.Find(Mine);
    if (!State || !State->Ready || !Incoming.Valid || !Slot
        || !WorldPrivate::SameBody(State->Handle, Mine)
        || !Owner.GetDiagnostics(D).IsSuccess() || D.CompletedSteps != State->Step)
        return Fail(TEXT("No valid continuation capture: enable before the step; standalone dynamic body, one collision substep, no existing joint required."));
    if (State->Consumed) { Reason.Reset(); return true; }
    if (Slot->WeldParent.IsSet() || Slot->Weld || !Slot->IncidentJoints.IsEmpty())
        return Fail(TEXT("Call Accept Pike Hit before creating the cut joint; joined/welded bodies are not restored."));
    for (const auto& H : Hits)
    {
        const bool A = WorldPrivate::SameBody(H.Body1, Mine), B = WorldPrivate::SameBody(H.Body2, Mine);
        if ((A || B) && !WorldPrivate::SameBody(A ? H.Body2 : H.Body1, Other))
            return Fail(TEXT("Another solved collision involves this sword in the same frame; it was preserved."));
    }
    FProphecyJoltBodyState CurrentBody;
    if (!Owner.ReadBody(Mine, CurrentBody).IsSuccess() || !CurrentBody.bDynamic)
        return Fail(TEXT("The receiving body is no longer dynamic."));

    // The existing incoming getter rewinds the component origin, including its
    // COM lever arm. Recover COM velocity from that exact representation.
    const FTransform StartBody(State->Start.Rotation, State->Start.PositionCm);
    const FTransform StartComponent = Slot->ComponentToBodyOrigin * StartBody;
    const FVector ComponentCOM = StartComponent.InverseTransformPosition(State->Start.CenterOfMassPositionCm);
    const FVector V = Incoming.Velocity + FVector::CrossProduct(Incoming.AngularVelocityRad,
        Incoming.Rotation.RotateVector(ComponentCOM));
    const FVector W = Incoming.AngularVelocityRad;
    const double Angle = W.Size() * State->Dt;
    const FQuat Rotation = (Angle > 1.e-6 ? FQuat(W.GetSafeNormal(), Angle) * State->Start.Rotation
                                         : State->Start.Rotation).GetNormalized();
    const FVector Center = State->Start.CenterOfMassPositionCm + V * State->Dt;
    const FVector OriginOffset = State->Start.Rotation.UnrotateVector(
        State->Start.PositionCm - State->Start.CenterOfMassPositionCm);
    const FTransform BodyTarget(Rotation, Center + Rotation.RotateVector(OriginOffset));
    FTransform ComponentTarget = Slot->ComponentToBodyOrigin * BodyTarget;
    ComponentTarget.SetScale3D(Component.GetComponentScale());
    if (V.ContainsNaN() || W.ContainsNaN() || BodyTarget.ContainsNaN() || ComponentTarget.ContainsNaN())
        return Fail(TEXT("Incoming continuation is nonfinite."));
    auto Result = Owner.SetBodyPose(Mine, BodyTarget);
    if (!Result.IsSuccess()) { Reason = Result.Message; return false; }
    Result = Owner.SetBodyVelocity(Mine, V, W, true);
    if (!Result.IsSuccess()) { Reason = Result.Message; return false; }
    State->Consumed = true;
    // The existing adapter transform callback updates the native/query bridge.
    // This is synchronous inside the hit, before a rendered frame can see it.
    Component.SetWorldTransform(ComponentTarget, false, nullptr, ETeleportType::TeleportPhysics);
    if (IsValid(&Component))
        Component.ComponentVelocity = V + FVector::CrossProduct(W, ComponentTarget.GetLocation() - Center);
    Reason.Reset();
    return true;
}
}

void UProphecyJoltHitImpactLibrary::EnableCleanHitContinuation(UPrimitiveComponent* Component, bool Enabled)
{
    if (!IsInGameThread() || !IsValid(Component) || !Component->GetWorld() || !Component->GetWorld()->IsGameWorld()) return;
    using namespace ProphecyJolt::HitContinuation;
    if (Enabled) Worlds.FindOrAdd(Component->GetWorld()).FindOrAdd(Component);
    else if (auto* Components = Worlds.Find(Component->GetWorld()))
    {
        Components->Remove(Component);
        if (Components->IsEmpty()) Worlds.Remove(Component->GetWorld());
    }
}

bool UProphecyJoltHitImpactLibrary::AcceptPikeHit(const UObject* HitReceiver, FString& Reason)
{
    const auto* Hit = ProphecyJolt::HitImpact::Current;
    if (!IsInGameThread() || !Hit || !IsValid(HitReceiver) || !IsValid(Hit->Mine)
        || (HitReceiver != Hit->Mine && HitReceiver != Hit->Mine->GetOwner()) || !Hit->Continue)
    { Reason = TEXT("Accept Pike Hit must run synchronously in the receiving object's Jolt Event Hit."); return false; }
    return Hit->Continue(Reason);
}
