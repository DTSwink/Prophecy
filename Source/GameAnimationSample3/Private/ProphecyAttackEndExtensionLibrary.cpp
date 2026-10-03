#include "ProphecyAttackEndExtensionLibrary.h"
#include "ProphecyAttackEndExtension.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyAttackEndExtension
{
struct FSettings { bool Enabled=true; float Slash=50.688107f,Hook=50.688107f,Over=50.688107f; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;
static FDelegateHandle Cleanup;
bool Threshold(const AProphecyAgent* Agent,FName Attack,float& Degrees,bool& Sword,bool& Left)
{
    static const FName Slashes[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU")};
    const FSettings Defaults;
    const auto* Value=Settings.IsEmpty()?nullptr:Settings.Find(Agent);
    const auto& S=Value?*Value:Defaults;
    if (!S.Enabled) return false;
    Sword=false; Left=false;
    for (FName Name:Slashes) if (Attack==Name) { Sword=true;Degrees=S.Slash;return Degrees<180; }
    if (Attack==TEXT("hookL") || Attack==TEXT("hookR"))
    { Left=Attack==TEXT("hookL");Degrees=S.Hook;return Degrees<180; }
    if (Attack==TEXT("overL") || Attack==TEXT("overR"))
    { Left=Attack==TEXT("overL");Degrees=S.Over;return Degrees<180; }
    return false;
}
}
bool UProphecyAttackEndExtensionLibrary::SetAttackEndExtension(AProphecyAgent* Agent,bool Enabled,
    float SlashThresholdDegrees,float HookThresholdDegrees,float OverThresholdDegrees)
{
    using namespace ProphecyAttackEndExtension;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    for (float V:{SlashThresholdDegrees,HookThresholdDegrees,OverThresholdDegrees})
        if (!FMath::IsFinite(V) || V<0 || V>180) return false;
    Settings.Add(Agent,{Enabled,SlashThresholdDegrees,HookThresholdDegrees,OverThresholdDegrees});
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Settings.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        if (Settings.IsEmpty()) { FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset(); }
    });
    return true;
}
