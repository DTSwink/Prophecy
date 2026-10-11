#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

// Game-thread only. Four slots share one unpaused tick clock per active world.
namespace ProphecySwordHolsterSchedule
{
inline uint64 NextSlot(uint64 Tick,int32 Slot) { return Tick+((uint64(Slot)-Tick)&3); }
struct FSlots
{
    int32 Load[4]={};
    int32 Starts[4]={};uint64 LastBookingTick=0;
    uint64 BookStart(uint64 Tick)
    {
        // A four-tick rolling window; completed/cancelled bookings expire
        // naturally. No retained request list or scans when booking a start.
        for(uint64 T=LastBookingTick;T<FMath::Min(Tick,LastBookingTick+4);++T)Starts[T&3]=0;
        LastBookingTick=Tick;int32 Best=int32(Tick&3);
        for(int32 I=1;I<4;++I){const int32 Slot=int32((Tick+I)&3);if(Starts[Slot]<Starts[Best])Best=Slot;}
        ++Starts[Best];return NextSlot(Tick,Best);
    }
    int32 Acquire(uint64 Tick)
    {
        int32 Best=int32(Tick&3);
        for(int32 I=1;I<4;++I){const int32 Slot=int32((Tick+I)&3);if(Load[Slot]<Load[Best])Best=Slot;}
        ++Load[Best];return Best;
    }
    void Release(int32 Slot) { check(Load[Slot]>0);--Load[Slot]; }
};
void Reserve(const AProphecyAgent* Agent);
bool Ready(const AProphecyAgent* Agent);
int32 Slot(const AProphecyAgent* Agent);
uint64 Tick(const AProphecyAgent* Agent);
void LeaveReach(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
