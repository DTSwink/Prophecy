namespace ProphecyJolt::ArmMotorSettings
{
struct FArms { bool Left = false, Right = false; };
static TMap<TWeakObjectPtr<AActor>, FArms> Preferences;
static TSet<TWeakObjectPtr<AActor>> AttackWindows;
static TSet<TWeakObjectPtr<AActor>> GetUpWindows;
struct FHold { FArms Restore; uint64 Remaining = 0; };
static TMap<TWeakObjectPtr<AActor>, FHold> Holds;
static FDelegateHandle HoldTick;
static void RefreshHoldTick();
static void AdvanceHolds(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0) return;
    TArray<TPair<TWeakObjectPtr<AActor>,FArms>,TInlineAllocator<8>> Due;
    for (auto It=Holds.CreateIterator();It;++It)
    {
        const auto* Agent=It.Key().Get();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (Agent->GetWorld()==World && --It.Value().Remaining==0)
        { Due.Emplace(It.Key(),It.Value().Restore);It.RemoveCurrent(); }
    }
    for (const auto& Entry:Due)
        if (auto* Agent=Entry.Key.Get())
            UProphecyJoltBodyDriveLibrary::SetArmsAntiJiggle(Agent,Entry.Value.Left,Entry.Value.Right);
    RefreshHoldTick();
}
static void RefreshHoldTick()
{
    if (Holds.IsEmpty())
    { FWorldDelegates::OnWorldPreActorTick.Remove(HoldTick);HoldTick.Reset(); }
    else if (!HoldTick.IsValid()) HoldTick=FWorldDelegates::OnWorldPreActorTick.AddStatic(&AdvanceHolds);
}
static bool Wants(const FArms& Arms, FName Bone)
{
    static const FName Left[] = {TEXT("upperarm_l"), TEXT("lowerarm_l"), TEXT("hand_l")};
    static const FName Right[] = {TEXT("upperarm_r"), TEXT("lowerarm_r"), TEXT("hand_r")};
    for (int I=0; I<3; ++I)
        if ((Arms.Left && Bone == Left[I]) || (Arms.Right && Bone == Right[I])) return true;
    return false;
}
static const FArms* Effective(AActor* Agent)
{
    static const FArms Both{true,true};
    return GetUpWindows.Contains(Agent) ? &Both : AttackWindows.Contains(Agent) ? nullptr : Preferences.Find(Agent);
}
static void Apply(FProphecyJoltWorldState& Native, const WorldPrivate::FRigRecord& Rig, AActor* Agent)
{
    const auto* Arms = Effective(Agent);
    for (const auto& Handle : Rig.Handles)
    {
        const auto& Slot = Native.Slots[Handle.Slot];
        ArmMotors::Set(Native.Physics, Slot.Body, Arms && Wants(*Arms, Slot.HitBone));
    }
}
static void ApplyAgent(FProphecyJoltWorldState* Native,AActor* Agent)
{
    if (!Native) return;
    for (const auto& RigSlot:Native->Rigs)
    {
        if (!RigSlot.Record || RigSlot.Record->Handles.IsEmpty()) continue;
        const auto& Slot=Native->Slots[RigSlot.Record->Handles[0].Slot];
        const auto* Component=Cast<UPrimitiveComponent>(Slot.AssociatedObject.Get());
        if (Component && Component->GetOwner()==Agent) Apply(*Native,*RigSlot.Record,Agent);
    }
}
static void ForgetWorld(UWorld* World)
{
    for (auto It=GetUpWindows.CreateIterator();It;++It)
        if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    for (auto It=AttackWindows.CreateIterator();It;++It)
        if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    for (auto It=Holds.CreateIterator();It;++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    RefreshHoldTick();
    for (auto It=Preferences.CreateIterator(); It; ++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
}
}

bool UProphecyJoltBodyDriveLibrary::SetArmsAntiJiggle(AActor* Agent, bool LeftArm, bool RightArm)
{
    if (!IsInGameThread() || !IsValid(Agent)) return false;
    auto* World = Agent->GetWorld();
    auto* Owner = World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || Owner->bWorldEnding) return false;
    using namespace ProphecyJolt::ArmMotorSettings;
    if (Holds.Remove(Agent)) RefreshHoldTick();
    if (LeftArm || RightArm) Preferences.Add(Agent, {LeftArm, RightArm});
    else Preferences.Remove(Agent);
    ApplyAgent(Owner->Native.Get(),Agent);
    return true;
}

void UProphecyJoltBodyDriveLibrary::NotifyArmsAntiJiggleAttackWindow(AActor* Agent,bool Active)
{
    if (!IsInGameThread() || !IsValid(Agent)) return;
    auto* World=Agent->GetWorld();
    auto* Owner=World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || Owner->bWorldEnding) return;
    using namespace ProphecyJolt::ArmMotorSettings;
    if (AttackWindows.Contains(Agent)==Active) return;
    if (Active) AttackWindows.Add(Agent); else AttackWindows.Remove(Agent);
    // Holds have already removed preferences/motors. Unconfigured agents need no rig scan.
    if (Preferences.Contains(Agent)) ApplyAgent(Owner->Native.Get(),Agent);
}

bool UProphecyJoltBodyDriveLibrary::DisableArmsAntiJiggleForDuration(AActor* Agent, float DurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds<0) return false;
    auto* World=Agent->GetWorld();
    auto* Owner=World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || Owner->bWorldEnding) return false;
    using namespace ProphecyJolt::ArmMotorSettings;
    const auto* Existing=Holds.Find(Agent);
    const FArms Restore=Existing ? Existing->Restore : Preferences.FindRef(Agent);
    if (DurationSeconds==0) return SetArmsAntiJiggle(Agent,Restore.Left,Restore.Right);
    if (!SetArmsAntiJiggle(Agent,false,false)) return false;
    if (Restore.Left || Restore.Right)
    {
        const uint64 Ticks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(DurationSeconds)*60.,9.e15)-1.e-5)));
        Holds.Add(Agent,{Restore,Ticks});RefreshHoldTick();
    }
    return true;
}

void UProphecyJoltBodyDriveLibrary::NotifyArmsAntiJiggleGetUpWindow(AActor* Agent,bool Active)
{
    if (!IsInGameThread() || !IsValid(Agent)) return;
    auto* World=Agent->GetWorld();
    auto* Owner=World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || Owner->bWorldEnding) return;
    using namespace ProphecyJolt::ArmMotorSettings;
    if (GetUpWindows.Contains(Agent)==Active) return;
    if (Active) GetUpWindows.Add(Agent); else GetUpWindows.Remove(Agent);
    ApplyAgent(Owner->Native.Get(),Agent);
}
