// Included by the constraint bridge. Reflection is confined to admission and
// event publication, never the physics-step depth check. A_Sword keeps its
// user-defined cut struct and authored acceptance/visual functions.
namespace SwordCuts
{
struct FState
{
    TWeakObjectPtr<AActor> Owner;
    double Length = 0, HalfWidth = 0, Side = 1, MinimumZ = 0, SideStop = 0;
    double LastStain = 0;
    int32 Type = 0, Matter = 0, StepsToCap = 0, Id = -1;
    bool WasCaptured = false;
    uint64 LastFrame = MAX_uint64;
};

FProperty* Field(UStruct* Struct, const TCHAR* Name)
{
    if (!Struct) return nullptr;
    const FString Prefix = FString(Name) + TEXT("_");
    for (TFieldIterator<FProperty> It(Struct); It; ++It)
        if (It->GetName() == Name || It->GetName().StartsWith(Prefix)) return *It;
    return nullptr;
}
double Number(FProperty* P, const void* Container, double Fallback = 0)
{
    auto* N = CastField<FNumericProperty>(P);
    if (!N || !Container) return Fallback;
    const void* V = N->ContainerPtrToValuePtr<void>(Container);
    return N->IsInteger() ? double(N->GetSignedIntPropertyValue(V)) : N->GetFloatingPointPropertyValue(V);
}
UObject* Object(FProperty* P, const void* Container)
{
    auto* O = CastField<FObjectPropertyBase>(P);
    return O && Container ? O->GetObjectPropertyValue_InContainer(Container) : nullptr;
}
void SetNumber(FProperty* P, void* Container, double Value)
{
    if (auto* N = CastField<FNumericProperty>(P))
    {
        void* V = N->ContainerPtrToValuePtr<void>(Container);
        if (N->IsInteger()) N->SetIntPropertyValue(V, int64(Value));
        else N->SetFloatingPointPropertyValue(V, Value);
    }
}
struct FRecords
{
    FArrayProperty* Array = nullptr;
    UScriptStruct* Struct = nullptr;
    FObjectPropertyBase* Constraint = nullptr;
    explicit FRecords(AActor* Owner)
    {
        Array = Owner ? FindFProperty<FArrayProperty>(Owner->GetClass(), TEXT("cuts")) : nullptr;
        auto* Inner = Array ? CastField<FStructProperty>(Array->Inner) : nullptr;
        Struct = Inner ? Inner->Struct : nullptr;
        Constraint = CastField<FObjectPropertyBase>(Field(Struct, TEXT("constraint")));
    }
    bool Valid() const { return Array && Struct && Constraint; }
    int32 Find(FScriptArrayHelper& Values, UPhysicsConstraintComponent* Joint) const
    {
        for (int32 I = 0; I < Values.Num(); ++I)
            if (Constraint->GetObjectPropertyValue_InContainer(Values.GetRawPtr(I)) == Joint) return I;
        return INDEX_NONE;
    }
};

void Limits(const FState& Cut, FProphecyJoltJointSettings& Settings)
{
    // Withdrawal is deliberately unbounded on the entering edge; the travel
    // monitor releases it there. Large finite open bounds avoid API infinities.
    constexpr double Open = 1.e8;
    Settings.bRadialTranslation = false;
    Settings.Translation[2] = {EProphecyJoltAxisMotion::Limited, Cut.MinimumZ, Open};
    if (Cut.Type != 0)
        Settings.Translation[1] = Cut.Side > 0
            ? FProphecyJoltAxisLimit{EProphecyJoltAxisMotion::Limited, Cut.SideStop, Open}
            : FProphecyJoltAxisLimit{EProphecyJoltAxisMotion::Limited, -Open, -Cut.SideStop};
}

bool DirectionalFriction(const FState& Cut, const FProphecyJoltBodyState& Sword,
    const FProphecyJoltBodyState& Victim, FProphecyJoltJointSettings& Settings)
{
    const FQuat FrameRotation = Sword.Rotation * Settings.FrameA.GetRotation();
    const FVector Wound = Victim.PositionCm + Victim.Rotation.RotateVector(Settings.FrameB.GetLocation());
    auto VelocityAt = [&](const FProphecyJoltBodyState& Body)
    {
        return Body.CenterOfMassVelocityCmPerSecond + FVector::CrossProduct(
            Body.AngularVelocityRadiansPerSecond, Wound - Body.CenterOfMassPositionCm);
    };
    // Rate of wound travel in the rotating blade frame, including both angular
    // lever arms. Positive means withdrawal. Reuse the bridge's existing body
    // reads; update motors only when direction changes, never rebuild the joint.
    const FVector Relative = FrameRotation.UnrotateVector(VelocityAt(Victim) - VelocityAt(Sword));
    bool Changed = false;
    for (int32 Axis = Cut.Type == 0 ? 2 : 1; Axis < 3; ++Axis)
    {
        auto& Drive = Settings.Drives[Axis];
        const double Speed = Relative[Axis] * (Axis == 1 ? Cut.Side : 1.);
        const bool Enabled = Speed > .1 ? false : (Speed < -.1 ? true : Drive.bVelocity);
        if (Drive.bVelocity != Enabled) { Drive.bVelocity = Enabled; Changed = true; }
    }
    return Changed;
}

void Stain(AActor* Owner, double Depth)
{
    if (!IsValid(Owner)) return;
    auto* Function = Owner->FindFunction(TEXT("Stain Blade"));
    if (!Function) return;
    FStructOnScope Params(Function);
    SetNumber(Field(Function, TEXT("Depth")), Params.GetStructMemory(), Depth);
    Owner->ProcessEvent(Function, Params.GetStructMemory());
}

void Release(AActor* Owner, UPhysicsConstraintComponent* Joint, int32 Id)
{
    if (!IsValid(Owner)) return;
    FRecords Records(Owner);
    if (!Records.Valid()) return;
    FScriptArrayHelper Values(Records.Array, Records.Array->ContainerPtrToValuePtr<void>(Owner));
    int32 Index = Joint ? Records.Find(Values, Joint) : INDEX_NONE;
    if (Index == INDEX_NONE && Id >= 0)
        for (int32 I = 0; I < Values.Num(); ++I)
            if (SwordCuts::Number(Field(Records.Struct, TEXT("id")), Values.GetRawPtr(I), -1) == Id) { Index = I; break; }
    if (Index == INDEX_NONE) return;
    FStructOnScope Record(Records.Struct);
    Records.Struct->CopyScriptStruct(Record.GetStructMemory(), Values.GetRawPtr(Index));
    const bool Flesh = Number(Field(Records.Struct, TEXT("typematter")), Record.GetStructMemory()) == 2;
    UObject* Victim = Object(Field(Records.Struct, TEXT("victim")), Record.GetStructMemory());
    Values.RemoveValues(Index);
    bool OtherFlesh = false, SameVictim = false;
    for (int32 I = 0; I < Values.Num(); ++I)
        if (Number(Field(Records.Struct, TEXT("typematter")), Values.GetRawPtr(I)) == 2)
        {
            OtherFlesh = true;
            SameVictim |= Object(Field(Records.Struct, TEXT("victim")), Values.GetRawPtr(I)) == Victim;
        }
    // Keep existing authored collision restoration. Do not re-enable a victim
    // while another cut still holds it, or destroy another cut's shared emitter.
    if (Flesh && !SameVictim && IsValid(Victim))
    {
        auto* Sword = Cast<UPrimitiveComponent>(Object(Field(Owner->GetClass(), TEXT("sword")), Owner));
        const auto PreviousType = Sword ? Sword->GetCollisionObjectType() : ECC_WorldDynamic;
        if (auto* Function = Owner->FindFunction(TEXT("change sword-skel collision and spawn NS")))
        {
            FStructOnScope Params(Function);
            if (auto* P = CastField<FObjectPropertyBase>(Field(Function, TEXT("skel"))); P && Victim->IsA(P->PropertyClass))
                P->SetObjectPropertyValue_InContainer(Params.GetStructMemory(), Victim);
            for (const TCHAR* Name : {TEXT("enable"), TEXT("do")})
                if (auto* P = CastField<FBoolProperty>(Field(Function, Name)))
                    P->SetPropertyValue_InContainer(Params.GetStructMemory(), true);
            if (auto* P = CastField<FStructProperty>(Field(Function, TEXT("cut"))); P && P->Struct == Records.Struct)
                P->CopyCompleteValue(P->ContainerPtrToValuePtr<void>(Params.GetStructMemory()), Record.GetStructMemory());
            Owner->ProcessEvent(Function, Params.GetStructMemory());
        }
        if (OtherFlesh && IsValid(Sword)) Sword->SetCollisionObjectType(PreviousType);
    }
    if (!OtherFlesh && IsValid(Owner))
        if (auto* P = FindFProperty<FObjectPropertyBase>(Owner->GetClass(), TEXT("wound NS")))
        {
            auto* Effect = Cast<UActorComponent>(P->GetObjectPropertyValue_InContainer(Owner));
            P->SetObjectPropertyValue_InContainer(Owner, nullptr);
            if (IsValid(Effect)) Effect->DestroyComponent();
        }
    if (IsValid(Joint)) Joint->DestroyComponent();
}
}
