#include "ProphecySpecialRollLibrary.h"
#include "ProphecySpecialRoll.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecySpecialRoll
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> DisabledForearms,DisabledCalves;
static FDelegateHandle Cleanup;
bool Forearms(const AProphecyAgent* A) { return DisabledForearms.IsEmpty() || !DisabledForearms.Contains(A); }
bool Calves(const AProphecyAgent* A) { return DisabledCalves.IsEmpty() || !DisabledCalves.Contains(A); }
static bool Set(AProphecyAgent* A,bool Enabled,bool Forearm)
{
    if (!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    auto& Values=Forearm?DisabledForearms:DisabledCalves;
    if (Enabled) Values.Remove(A);else Values.Add(A);
    if (!Cleanup.IsValid() && (!DisabledForearms.IsEmpty() || !DisabledCalves.IsEmpty()))
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
        {
            for (auto* S:{&DisabledForearms,&DisabledCalves}) for (auto It=S->CreateIterator();It;++It)
                if (!It->IsValid() || It->Get()->GetWorld()==W) It.RemoveCurrent();
        });
    if (Cleanup.IsValid() && DisabledForearms.IsEmpty() && DisabledCalves.IsEmpty())
    { FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset(); }
    return true;
}
}
bool UProphecySpecialRollLibrary::SetSpecialForearmRollCorrection(AProphecyAgent* A,bool Enabled)
{ return ProphecySpecialRoll::Set(A,Enabled,true); }
bool UProphecySpecialRollLibrary::SetSpecialCalfRollCorrection(AProphecyAgent* A,bool Enabled)
{ return ProphecySpecialRoll::Set(A,Enabled,false); }
