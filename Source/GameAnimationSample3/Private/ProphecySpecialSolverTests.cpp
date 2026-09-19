#include "ProphecyAgent.h"
#include "ProphecySpecialSolver.h"
#include "ProphecyLimbCollision.h"
#include "Engine/World.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialSolverTest,"Prophecy.Jolt.SpecialSolver.Lifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySpecialSolverTest::RunTest(const FString&)
{
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    if (!World) return false;
    AProphecyAgent* Agent=World->SpawnActor<AProphecyAgent>();
    if (!Agent) { World->DestroyWorld(false);return false; }
    FString Error;
    auto Check=[&](int32 V,int32 P)
    {
        int32 ActualV,ActualP;Agent->GetJoltSolverIterations(ActualV,ActualP);
        TestEqual(TEXT("Effective velocity iterations"),ActualV,V);
        TestEqual(TEXT("Effective position iterations"),ActualP,P);
    };
    Agent->SetJoltSolverIterations(7,4,Error);Check(7,4);
    Agent->NotifySwordAttackState(true);Check(10,32);
    Agent->NotifySwordAttackState(true);Check(10,32);
    ProphecyLimbCollision::DefenseChanged(Agent,true);Check(10,32);
    Agent->NotifySwordAttackState(false);Check(10,32);
    Agent->SetJoltSolverIterations(9,6,Error);Check(10,32);
    ProphecyLimbCollision::DefenseChanged(Agent,false);Check(9,6);
    ProphecyLimbCollision::DefenseChanged(Agent,false);Check(9,6);
    // Both committed parry and dodge use this same activation/exit hook.
    ProphecyLimbCollision::DefenseChanged(Agent,true);Check(10,32);
    ProphecyLimbCollision::DefenseChanged(Agent,false);Check(9,6);
    Agent->SetJoltSolverIterations(0,0,Error);
    Agent->NotifySwordAttackState(true);Check(10,32);
    Agent->NotifySwordAttackState(false);Check(0,0);
    TestFalse(TEXT("No special entry remains in locomotion"),ProphecySpecialSolver::IsActive(Agent));
    ProphecyLimbCollision::Remove(Agent);
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
