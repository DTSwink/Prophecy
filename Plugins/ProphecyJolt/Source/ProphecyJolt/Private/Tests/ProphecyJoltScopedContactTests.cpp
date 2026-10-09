#include "ProphecyJoltWorldSubsystem.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
static bool VerifyScopedContacts()
{
    int32 Checks=0,Failures=0;
    auto Check=[&](bool Pass,const TCHAR* What){++Checks;if(!Pass){++Failures;UE_LOG(LogTemp,Error,TEXT("ScopedContacts: %s"),What);}};
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    for(int32 Mode=0;Mode<5;++Mode)for(bool Reverse:{false,true})
    {
        auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
        if(!W)return false;if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();
        FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;Settings.WorkerThreads=0;
        Check(S->InitializeSimulation(Settings).IsSuccess(),TEXT("Initialize"));
        FProphecyJoltBodyHandle D,A,D2,A2;
        auto Create=[&](FProphecyJoltBodyHandle& H,FVector Position){FProphecyJoltFixtureBodySettings B;B.PositionCm=Position;Check(S->CreateBox(FVector(10),.1,B,H).IsSuccess(),TEXT("Create"));};
        if(Reverse){Create(A,FVector(-25,5,0));Create(D,FVector::ZeroVector);}else{Create(D,FVector::ZeroVector);Create(A,FVector(-25,5,0));}
        Create(D2,FVector(0,100,0));Create(A2,FVector(-25,105,0));
        const FProphecyJoltBodyPair Pair{D,A};int Owner=1,OtherOwner=2;
        if(Mode==1)
        {
            Check(S->UpdateScopedContactRules(&Owner,MakeArrayView(&Pair,1),{}).IsSuccess(),TEXT("Suppress"));
            Check(S->UpdateScopedContactRules(&OtherOwner,MakeArrayView(&Pair,1),{}).IsSuccess(),TEXT("Shared suppression"));
            Check(S->UpdateScopedContactRules(&Owner,{},{}).IsSuccess(),TEXT("Remove one owner preserves other"));
        }
        if(Mode>=2)Check(S->UpdateScopedContactRules(&Owner,{},MakeArrayView(&Pair,1)).IsSuccess(),TEXT("Protect"));
        if(Mode==3)Check(S->UpdateScopedContactRules(&Owner,{},{}).IsSuccess(),TEXT("Protection exit"));
        S->SetBodyVelocity(A,FVector(400,0,0),FVector::ZeroVector,true);S->SetBodyVelocity(A2,FVector(400,0,0),FVector::ZeroVector,true);
        for(int32 Step=0;Step<20;++Step)
        {
            if(Mode==4 && Step==5)
            {
                Check(S->UpdateScopedContactRules(&Owner,{},{}).IsSuccess(),TEXT("Remove protection on a persistent contact"));
                S->SetBodyVelocity(A,FVector(400,0,0),FVector::ZeroVector,true);
            }
            Check(S->Step(1.f/60,1).IsSuccess(),TEXT("Step"));
        }
        FProphecyJoltBodyState DS,AS,DS2;S->ReadBody(D,DS);S->ReadBody(A,AS);S->ReadBody(D2,DS2);
        Check(DS2.PositionCm.X>1,TEXT("Unrelated agent pair still responds"));
        if(Mode==1 || Mode==2)
        {
            Check(DS.PositionCm.IsNearlyZero(1.e-5),TEXT("Protected/suppressed body not displaced"));
            Check(DS.CenterOfMassVelocityCmPerSecond.IsNearlyZero(1.e-5),TEXT("Zero linear contact reaction"));
            Check(DS.AngularVelocityRadiansPerSecond.IsNearlyZero(1.e-5) && DS.Rotation.Equals(FQuat::Identity,1.e-6),TEXT("Zero angular contact reaction"));
        }
        else Check(DS.PositionCm.X>1,TEXT("Ordinary response/restoration"));
        if(Mode==1)Check(AS.PositionCm.X>80,TEXT("Suppressed attacker passes through"));
        if(Mode==2)Check(AS.CenterOfMassVelocityCmPerSecond.X<390,TEXT("Other side still reacts"));
        S->DestroyBody(D);Check(S->UpdateScopedContactRules(&Owner,{},{}).IsSuccess(),TEXT("Cleanup after endpoint deletion"));
        Check(S->UpdateScopedContactRules(&OtherOwner,{},{}).IsSuccess(),TEXT("Shared owner cleanup"));
        S->ShutdownSimulation();W->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(W);W->MarkAsGarbage();
    }
    UE_LOG(LogTemp,Display,TEXT("ScopedContacts checks=%d failures=%d"),Checks,Failures);return Failures==0;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyScopedContactsTest,"Prophecy.Jolt.Contacts.ScopedDefense",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyScopedContactsTest::RunTest(const FString&){return TestTrue(TEXT("Scoped contact verification"),VerifyScopedContacts());}
static FAutoConsoleCommand VerifyScopedContactsCommand(TEXT("Prophecy.Jolt.VerifyScopedContacts"),TEXT("Verify pair contact response without entering global automation mode."),FConsoleCommandDelegate::CreateLambda([](){VerifyScopedContacts();}));

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySwordNoReactionTest,"Prophecy.Jolt.Contacts.SwordNoReaction",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySwordNoReactionTest::RunTest(const FString&)
{
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    for(bool Welded:{false,true})for(bool Reverse:{false,true})for(int Mode=0;Mode<7;++Mode)
    {
        auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
        if(!W)return false;if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();
        FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;Settings.WorkerThreads=0;
        TestTrue(TEXT("Initialize"),S->InitializeSimulation(Settings).IsSuccess());
        FProphecyJoltBodyHandle Hand,Sword,Other;
        const FVector Offset(0,30,0);
        auto Create=[&](FProphecyJoltBodyHandle& H,FVector P){FProphecyJoltFixtureBodySettings B;B.PositionCm=P;TestTrue(TEXT("Create"),S->CreateBox(FVector(5),.1f,B,H).IsSuccess());};
        // Mode 4 targets the actual hand: sword protection must not protect its carrier's own shape.
        const FVector OtherStart(-15,(Mode==4 && Welded)?0:30,2);
        if(Reverse)Create(Other,OtherStart);
        Create(Hand,FVector::ZeroVector);Create(Sword,Offset);
        if(!Reverse)Create(Other,OtherStart);
        if(Welded)TestTrue(TEXT("Weld"),S->WeldBodyShape(Hand,Sword,FTransform(Offset)).IsSuccess());
        if(Mode)TestTrue(TEXT("Enable no reaction"),S->SetBodyContactReactionEnabled(Sword,false).IsSuccess());
        if(Mode==2)TestTrue(TEXT("Disable before collision"),S->SetBodyContactReactionEnabled(Sword,true).IsSuccess());
        // Removing an unrelated scoped rule must retain the sword's rule.
        int Owner=0;FProphecyJoltBodyPair Pair{Sword,Other};
        TestTrue(TEXT("Additional scoped rule"),S->UpdateScopedContactRules(&Owner,{},MakeArrayView(&Pair,1)).IsSuccess());
        TestTrue(TEXT("Scoped rule removed"),S->UpdateScopedContactRules(&Owner,{},{}).IsSuccess());
        if(Mode>=5)TestTrue(TEXT("Fractional response"),S->SetBodyContactReactionScale(Sword,.5f).IsSuccess());
        if(Mode==6)TestTrue(TEXT("Scoped protection overrides fraction"),S->UpdateScopedContactRules(&Owner,{},MakeArrayView(&Pair,1)).IsSuccess());
        S->SetBodyVelocity(Other,FVector(400,0,0),{},true);
        for(int Step=0;Step<20;++Step)
        {
            if(Mode==3 && Step==5)
            {
                TestTrue(TEXT("Disable on existing contact"),S->SetBodyContactReactionEnabled(Sword,true).IsSuccess());
                S->SetBodyVelocity(Other,FVector(400,0,0),{},true);
            }
            TestTrue(TEXT("Step"),S->Step(1.f/60,1).IsSuccess());
        }
        FProphecyJoltBodyState Held,Victim;
        S->ReadBody(Welded?Hand:Sword,Held);S->ReadBody(Other,Victim);
        const bool Protected=Mode==1 || Mode==6 || (Mode==4 && !Welded);
        if(Protected)
        {
            TestTrue(TEXT("Zero contact translation"),Held.PositionCm.Equals(Welded?FVector::ZeroVector:Offset,1.e-5));
            TestTrue(TEXT("Zero linear/angular reaction"),Held.CenterOfMassVelocityCmPerSecond.IsNearlyZero(1.e-5) && Held.AngularVelocityRadiansPerSecond.IsNearlyZero(1.e-5));
            TestTrue(TEXT("Other body still responds"),Victim.CenterOfMassVelocityCmPerSecond.X<390);
        }
        else TestTrue(TEXT("Default/disabled/direct-hand contact responds"),Held.PositionCm.X>.1);
        TestTrue(TEXT("Destroy protected sword"),S->DestroyBody(Sword).IsSuccess());
        TestTrue(TEXT("Stale handle rejected"),!S->SetBodyContactReactionEnabled(Sword,false).IsSuccess());
        S->ShutdownSimulation();W->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(W);W->MarkAsGarbage();
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySwordReactionStrengthTest,"Prophecy.Jolt.Contacts.SwordReactionStrength",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySwordReactionStrengthTest::RunTest(const FString&)
{
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    for(bool Welded:{false,true})for(bool Reverse:{false,true})
    {
        double Speeds[3]{};int Index=0;
        for(float Scale:{1.f,.5f,0.f})
        {
            auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
            if(!W)return false;if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
            auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();
            FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;Settings.WorkerThreads=0;
            TestTrue(TEXT("Initialize fractional fixture"),S->InitializeSimulation(Settings).IsSuccess());
            FProphecyJoltBodyHandle Hand,Sword,Other;
            auto Create=[&](FProphecyJoltBodyHandle& H,FVector P){FProphecyJoltFixtureBodySettings B;B.PositionCm=P;B.Friction=0.f;TestTrue(TEXT("Create"),S->CreateBox(FVector(5),.1f,B,H).IsSuccess());};
            if(Reverse)Create(Other,FVector(45,0,0));
            Create(Hand,Welded?FVector::ZeroVector:FVector(0,100,0));Create(Sword,FVector(30,0,0));
            if(!Reverse)Create(Other,FVector(45,0,0));
            if(Welded)TestTrue(TEXT("Weld"),S->WeldBodyShape(Hand,Sword,FTransform(FVector(30,0,0))).IsSuccess());
            TestFalse(TEXT("Reject negative scale"),S->SetBodyContactReactionScale(Sword,-.1f).IsSuccess());
            TestFalse(TEXT("Reject excessive scale"),S->SetBodyContactReactionScale(Sword,1.1f).IsSuccess());
            TestTrue(TEXT("Set scale"),S->SetBodyContactReactionScale(Sword,Scale).IsSuccess());
            TestTrue(TEXT("Same scale is idempotent"),S->SetBodyContactReactionScale(Sword,Scale).IsSuccess());
            S->SetBodyVelocity(Other,FVector(-400,0,0),{},true);
            for(int Step=0;Step<8;++Step)TestTrue(TEXT("Step"),S->Step(1.f/60,1).IsSuccess());
            FProphecyJoltBodyState Held;S->ReadBody(Welded?Hand:Sword,Held);
            Speeds[Index++]=FMath::Abs(Held.CenterOfMassVelocityCmPerSecond.X);
            S->ShutdownSimulation();W->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(W);W->MarkAsGarbage();
        }
        TestTrue(TEXT("Half scale has less reaction than normal"),Speeds[1]>1. && Speeds[1]<Speeds[0]-.1);
        TestTrue(TEXT("Zero scale retains exact no reaction"),Speeds[2]<1.e-5);
    }
    return !HasAnyErrors();
}
#endif
