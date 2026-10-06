#include "ProphecyDefenseControls.h"
#include "ProphecyAgent.h"
#include "ProphecyClampProfiles.h"
namespace ProphecyDefenseControls
{
namespace { struct FPair { FSettings Modes[2]; }; TMap<TWeakObjectPtr<const AProphecyAgent>,FPair> Settings; }
namespace { struct FHitDelays { int32 Parry=3,Dodge=3; }; TMap<TWeakObjectPtr<const AProphecyAgent>,FHitDelays> HitDelays; }
const FSettings* Find(const AProphecyAgent* Agent,bool bDodge)
{ const auto* Pair=Settings.Find(Agent);return Pair?&Pair->Modes[bDodge?1:0]:nullptr; }
bool Set(AProphecyAgent* Agent,bool bDodge,ELimb Limb,bool bEnabled,float LeewayCm)
{
    if (!IsInGameThread() || !IsValid(Agent) || !FMath::IsFinite(LeewayCm) || LeewayCm<0) return false;
    ProphecyClampProfiles::Cancel(Agent,bDodge?ProphecyClampProfiles::EMode::Dodge:ProphecyClampProfiles::EMode::Parry,int32(Limb));
    RestoreClamp(Agent,bDodge,Limb,{true,bEnabled,LeewayCm});return true;
}
void RestoreClamp(AProphecyAgent* Agent,bool bDodge,ELimb Limb,FClamp Value)
{
    auto& Mode=Settings.FindOrAdd(Agent).Modes[bDodge?1:0];
    auto& Clamp=Limb==ELimb::Foot?Mode.Foot:Mode.Calf;
    Clamp=Value;
}
bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{
    if (!IsInGameThread() || !IsValid(Agent) || Frames<0) return false;
    HitDelays.FindOrAdd(Agent).Dodge=Frames;
    return true;
}
int32 GetDodgeFramesAfterHit(const AProphecyAgent* Agent)
{ return GetFramesAfterHit(Agent,true); }
bool SetDefenseFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{
    if (!IsInGameThread() || !IsValid(Agent) || Frames<0) return false;
    if (Frames==3) HitDelays.Remove(Agent);else HitDelays.Add(Agent,{Frames,Frames});
    return true;
}
int32 GetFramesAfterHit(const AProphecyAgent* Agent,bool bDodge)
{ const auto* Delay=HitDelays.Find(Agent);return Delay?(bDodge?Delay->Dodge:Delay->Parry):3; }
void Remove(const AProphecyAgent* Agent) { Settings.Remove(Agent);HitDelays.Remove(Agent); }
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/World.h"
#include "ProphecyNNDefenseLibrary.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseHitDelayTest,"Prophecy.NN.Defense.HitDelayControls",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseHitDelayTest::RunTest(const FString&)
{
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A || !B) { if(W) W->DestroyWorld(false);return false; }
    auto Check=[&](AProphecyAgent* Agent,int32 Dodge,int32 Parry)
    {
        int32 D,P;UProphecyNNDefenseLibrary::GetDefenseFramesAfterHit(Agent,D,P);
        TestEqual(TEXT("Dodge delay"),D,Dodge);TestEqual(TEXT("Parry delay"),P,Parry);
    };
    Check(A,3,3);
    TestTrue(TEXT("Shared zero is accepted"),UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,0));Check(A,0,0);
    TestFalse(TEXT("Negative does not replace existing values"),UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,-1));Check(A,0,0);
    Check(B,3,3);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,7);Check(A,7,7);
    UProphecyNNDefenseLibrary::SetDodgeFramesAfterHit(A,1);Check(A,1,7);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,3);Check(A,3,3);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,9);
    ProphecyDefenseControls::Remove(A);Check(A,3,3);
    ProphecyDefenseControls::Remove(B);W->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
