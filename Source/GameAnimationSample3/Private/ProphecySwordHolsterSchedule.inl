// Included once by the pose controller; no per-agent tick loop or task queue.
namespace ProphecySwordHolsterSchedule
{
struct FWorldClock { FSlots Slots;uint64 Tick=0;int32 Users=0; };
struct FReservation { TWeakObjectPtr<const UWorld> World;uint64 Due=0;int32 Slot=0;bool Reaching=true; };
static TMap<TWeakObjectPtr<const UWorld>,FWorldClock> Worlds;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReservation> Reservations;
static FDelegateHandle TickHandle,CleanupHandle;
static void RetireCallbacks()
{
    if(!Worlds.IsEmpty())return;
    FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
    FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();
}
static void AdvanceClock(UWorld* World,ELevelTick Type,float Delta)
{
    if(!World||World->IsPaused()||Type!=LEVELTICK_All||Delta<=0)return;
    if(auto* Clock=Worlds.Find(World))++Clock->Tick;
}
void Reserve(const AProphecyAgent* Agent)
{
    if(!Agent||Agent->IsPlayerControlled()||Reservations.Contains(Agent))return;
    auto* World=Agent->GetWorld();if(!World)return;
    auto& Clock=Worlds.FindOrAdd(World);const int32 Slot=Clock.Slots.Acquire(Clock.Tick);++Clock.Users;
    Reservations.Add(Agent,{World,Clock.Slots.BookStart(Clock.Tick),Slot,true});
    if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&AdvanceClock);
    if(!CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){
        for(auto It=Reservations.CreateIterator();It;++It)if(It.Value().World==W)It.RemoveCurrent();
        Worlds.Remove(W);RetireCallbacks();
    });
}
bool Ready(const AProphecyAgent* Agent)
{
    const auto* R=Reservations.Find(Agent);if(!R)return true;
    const auto* Clock=Worlds.Find(R->World);return Clock&&Clock->Tick>=R->Due;
}
int32 Slot(const AProphecyAgent* Agent)
{const auto* R=Reservations.Find(Agent);return R?R->Slot:INDEX_NONE;}
uint64 Tick(const AProphecyAgent* Agent)
{const auto* Clock=Agent?Worlds.Find(Agent->GetWorld()):nullptr;return Clock?Clock->Tick:0;}
void LeaveReach(const AProphecyAgent* Agent)
{
    if(auto* R=Reservations.Find(Agent))if(R->Reaching){
        if(auto* Clock=Worlds.Find(R->World))Clock->Slots.Release(R->Slot);
        R->Reaching=false;
    }
}
void Remove(const AProphecyAgent* Agent)
{
    FReservation R;if(!Reservations.RemoveAndCopyValue(Agent,R))return;
    if(auto* Clock=Worlds.Find(R.World)){
        if(R.Reaching)Clock->Slots.Release(R.Slot);
        if(--Clock->Users==0)Worlds.Remove(R.World);
    }
    RetireCallbacks();
}
}
