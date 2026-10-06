#include "ProphecyAttackNNFeedbackLibrary.h"
#include "ProphecyAttackNNFeedback.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyAttackNNFeedback
{
// Store only opt-outs. Untouched agents take the empty-map path and allocate nothing.
static TMap<TWeakObjectPtr<const AProphecyAgent>,uint8> Overrides,Baselines;
static FDelegateHandle Cleanup;
static void RefreshCleanup()
{
    if(!Cleanup.IsValid() && (!Overrides.IsEmpty() || !Baselines.IsEmpty()))
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for(auto* Map:{&Overrides,&Baselines})for(auto It=Map->CreateIterator();It;++It)
                if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
            RefreshCleanup();
        });
    if(Cleanup.IsValid() && Overrides.IsEmpty() && Baselines.IsEmpty())
    {FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
}
uint8 Mask(const AProphecyAgent* Agent)
{const auto* M=Overrides.IsEmpty()?nullptr:Overrides.Find(Agent);return M?*M:All;}
void CaptureReset(const AProphecyAgent* Agent)
{const uint8 M=Mask(Agent);if(M!=All)Baselines.Add(Agent,M);else Baselines.Remove(Agent);RefreshCleanup();}
void RestoreReset(const AProphecyAgent* Agent)
{if(const auto* M=Baselines.Find(Agent))Overrides.Add(Agent,*M);else Overrides.Remove(Agent);RefreshCleanup();}
void ForgetReset(const AProphecyAgent* Agent){Baselines.Remove(Agent);RefreshCleanup();}
}
bool UProphecyAttackNNFeedbackLibrary::SetAttackNNFeedback(AProphecyAgent* Agent,bool StartCoreInertia,
    bool StartHandInertia,bool HandInertia,bool ArmCone,bool LeftWristConstraint)
{
    using namespace ProphecyAttackNNFeedback;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)return false;
    const uint8 M=(StartCoreInertia?StartCore:0)|(StartHandInertia?StartHand:0)|(HandInertia?Hand:0)|(ArmCone?Cone:0)|(LeftWristConstraint?Wrist:0);
    if(M==All)Overrides.Remove(Agent);else Overrides.Add(Agent,M);
    RefreshCleanup();return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackNNFeedbackSettingsTest,"Prophecy.NN.AttackFeedback.DefaultsAndReset",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackNNFeedbackSettingsTest::RunTest(const FString&)
{
    using namespace ProphecyAttackNNFeedback;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TestEqual(TEXT("Untouched agent retains all old feedback"),Mask(A),uint8(All));
    for(uint8 M=0;M<=All;++M)
    {
        TestTrue(TEXT("Every combination accepted"),UProphecyAttackNNFeedbackLibrary::SetAttackNNFeedback(A,M&StartCore,M&StartHand,M&Hand,M&Cone,M&Wrist));
        TestEqual(TEXT("Independent bits round-trip"),Mask(A),M);
    }
    TestFalse(TEXT("All true needs no override storage"),Overrides.Contains(A));
    CaptureReset(A);UProphecyAttackNNFeedbackLibrary::SetAttackNNFeedback(A,false,false,false,false,false);RestoreReset(A);
    TestEqual(TEXT("Reset restores default"),Mask(A),uint8(All));
    UProphecyAttackNNFeedbackLibrary::SetAttackNNFeedback(A,false,true,false,true,false);CaptureReset(A);
    UProphecyAttackNNFeedbackLibrary::SetAttackNNFeedback(A);RestoreReset(A);
    TestEqual(TEXT("Reset restores configured opt-outs"),Mask(A),uint8(StartHand|Cone));
    World->DestroyWorld(false);World->MarkAsGarbage();
    TestFalse(TEXT("World cleanup removes overrides"),Overrides.Contains(A));
    TestFalse(TEXT("World cleanup removes saved values"),Baselines.Contains(A));
    return !HasAnyErrors();
}
#endif
