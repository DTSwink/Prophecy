#include "ProphecyAgent.h"
#include "Components/CapsuleComponent.h"

namespace ProphecyRealisticMode
{
static double CapsuleBottom(const UCapsuleComponent& Capsule)
{
    float Radius,HalfHeight;Capsule.GetScaledCapsuleSize(Radius,HalfHeight);
    return Capsule.GetComponentLocation().Z-Radius
        -FMath::Max(0.f,HalfHeight-Radius)*FMath::Abs(Capsule.GetUpVector().Z);
}
static bool Above(double LeftZ,double RightZ,double Bottom,float Threshold)
{ return FMath::Min(LeftZ,RightZ)-Bottom>Threshold; }
}

bool AProphecyAgent::SetRealisticMode(bool Enabled,float FootThresholdCm)
{
    if(!IsInGameThread() || IsActorBeingDestroyed() || !FMath::IsFinite(FootThresholdCm) || FootThresholdCm<0)return false;
    bMonitorRealisticMode=Enabled;RealisticFootThresholdCm=FootThresholdCm;
    if(Enabled)UpdateRealisticMode();else SetRealisticModeActive(false);
    return true;
}
void AProphecyAgent::SetRealisticModeActive(bool Active)
{
    if(bRealisticModeActive==Active)return;
    // Commit before Blueprint dispatch; handlers can reconfigure or disable safely.
    bRealisticModeActive=Active;
    if(Active)OnStartRealistic();else OnEndRealistic();
}
void AProphecyAgent::ResetRealisticModeState() { SetRealisticModeActive(false); }
void AProphecyAgent::UpdateRealisticMode()
{
    if(!bMonitorRealisticMode || IsActorBeingDestroyed())return;
    const auto* PoseMesh=GetPoseReferenceMesh();
    if(!Capsule || !PoseMesh){SetRealisticModeActive(false);return;}
    static const FName Feet[]={TEXT("foot_l"),TEXT("foot_r")};
    double Z[2];
    for(int32 I=0;I<2;++I)
    {
        FTransform Pose;FVector V,W;bool Simulating=false;
        if(GetPhysicalBodyState(Feet[I],Pose,V,W,Simulating))Z[I]=Pose.GetLocation().Z;
        else if(PoseMesh->GetBoneIndex(Feet[I])!=INDEX_NONE)Z[I]=PoseMesh->GetSocketLocation(Feet[I]).Z;
        else {SetRealisticModeActive(false);return;}
        if(!FMath::IsFinite(Z[I])){SetRealisticModeActive(false);return;}
    }
    const double Bottom=ProphecyRealisticMode::CapsuleBottom(*Capsule);
    SetRealisticModeActive(FMath::IsFinite(Bottom)
        && ProphecyRealisticMode::Above(Z[0],Z[1],Bottom,RealisticFootThresholdCm));
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Misc/ScopeExit.h"
#include "ProphecyPhysicalProfileLibrary.h"
#include "ProphecyPhysicalContext.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRealisticModeTest,"Prophecy.Agent.RealisticMode.ThresholdAndOptIn",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRealisticModeTest::RunTest(const FString&)
{
    using namespace ProphecyRealisticMode;
    TestFalse(TEXT("One planted foot prevents entry"),Above(100,10,0,10));
    TestTrue(TEXT("Both feet above enters"),Above(11,100,0,10));
    TestFalse(TEXT("Equality exits"),Above(100,110,90,10));
    TestTrue(TEXT("Capsule-relative translation invariant"),Above(1011,1100,1000,10));
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!TestNotNull(TEXT("World"),World))return false;
    if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT{ProphecyPhysicalContext::Remove(Agent);World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);};
    if(!TestNotNull(TEXT("Agent"),Agent))return false;
    Agent->bAutoEnsureStandaloneNNManager=false;
    TestFalse(TEXT("Disabled by default"),Agent->bMonitorRealisticMode);
    TestFalse(TEXT("Inactive by default"),Agent->IsRealisticModeActive());
    for(FName Event:{FName(TEXT("OnStartRealistic")),FName(TEXT("OnEndRealistic"))})
    { const auto* F=Agent->FindFunction(Event);TestTrue(TEXT("Crossing event available to Blueprint"),F && F->HasAnyFunctionFlags(FUNC_BlueprintEvent)); }
    auto* Capsule=Agent->GetAgentCapsule();Capsule->SetCapsuleSize(20,80);
    Capsule->SetWorldLocation(FVector(0,0,100));
    TestEqual(TEXT("Upright capsule bottom"),CapsuleBottom(*Capsule),20.);
    Capsule->SetWorldRotation(FRotator(90,0,0));
    TestTrue(TEXT("Tilted capsule bottom uses shape support"),FMath::IsNearlyEqual(CapsuleBottom(*Capsule),80.,.001));
    UProphecyPhysicalProfileLibrary::SetMagnetizationMode(Agent,.7f);
    Agent->WorldMagnetizationLinearStrengthScale=.4f;
    Agent->bRealisticModeActive=true;
    TestFalse(TEXT("Invalid threshold rejected"),Agent->SetRealisticMode(true,-1));
    TestTrue(TEXT("Invalid input preserves state"),Agent->IsRealisticModeActive());
    TestTrue(TEXT("Disable succeeds"),Agent->SetRealisticMode(false,15));
    TestFalse(TEXT("Disable ends crossing"),Agent->IsRealisticModeActive());
    Agent->bMonitorRealisticMode=true;Agent->bRealisticModeActive=true;Agent->ResetRealisticModeState();
    TestTrue(TEXT("Reset keeps opt-in and threshold"),Agent->bMonitorRealisticMode && Agent->RealisticFootThresholdCm==15);
    TestFalse(TEXT("Reset ends crossing"),Agent->IsRealisticModeActive());
    TestEqual(TEXT("Events do not change magnetization mode"),UProphecyPhysicalProfileLibrary::GetMagnetizationMode(Agent),.7f);
    TestEqual(TEXT("Events do not change linear strength"),Agent->WorldMagnetizationLinearStrengthScale,.4f);
    return !HasAnyErrors();
}
#endif
