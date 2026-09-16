#include "ProphecyPelvisInertiaMath.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyPelvisInertia.h"
#include "ProphecyPelvisInertiaLibrary.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "Misc/ScopeExit.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPelvisInertiaMathTest,
    "Prophecy.NN.PelvisInertia.WorldMotion", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyPelvisInertiaMathTest::RunTest(const FString&)
{
    using namespace ProphecyPelvisInertia;
    const double Dt = 1./30.;
    const FTransform Initial(FRotator(30,70,-20), FVector(100,200,80));
    const FVector Velocity(20,-10,5), Spin(.2,-.3,.4);
    const FTransform Next(RotationIncrement(Spin*Dt)*Initial.GetRotation(),
        Initial.GetLocation()+Velocity*Dt);
    FMotion Coast;
    Coast.Seed(Initial,Next,Dt);
    for (int32 I=1; I<=120; ++I)
    {
        // Arbitrary incoming target/root motion must not drag a world-space coast.
        const FTransform Incoming(FRotator(I*5,I*-7,I*3), FVector(I*50,I*-60,I*10));
        const FTransform Result = Coast.Step(Incoming,FVector::ZeroVector,FVector::ZeroVector,Dt);
        const FTransform Expected(RotationIncrement(Spin*(I*Dt))*Initial.GetRotation(),
            Initial.GetLocation()+Velocity*(I*Dt));
        TestTrue(TEXT("Constant world linear velocity"),Coast.LinearVelocity.Equals(Velocity,1e-10));
        TestTrue(TEXT("Constant world angular velocity"),Coast.AngularVelocity.Equals(Spin,1e-10));
        TestTrue(TEXT("World-space coast independent of incoming target"),Result.Equals(Expected,1e-8));
    }
    FMotion Split;
    Split.Seed(Initial,Next,Dt);
    const FTransform Target(FRotator(-40,120,15),FVector(-500,300,90));
    const FTransform Result = Split.Step(Target,FVector(0,0,1),FVector(1,1,0),Dt);
    TestTrue(TEXT("Horizontal coast"), FMath::IsNearlyEqual(Result.GetLocation().X,Next.GetLocation().X,1e-9)
        && FMath::IsNearlyEqual(Result.GetLocation().Y,Next.GetLocation().Y,1e-9));
    TestEqual(TEXT("Vertical exact target"),Result.GetLocation().Z,Target.GetLocation().Z);
    TestTrue(TEXT("World yaw angular velocity retained independently"),FMath::IsNearlyEqual(Split.AngularVelocity.Z,Spin.Z,1e-10));
    const FTransform Follow = Split.Step(Target,FVector::OneVector,FVector::OneVector,Dt);
    TestTrue(TEXT("All-one exact position"),Follow.GetLocation()==Target.GetLocation());
    TestTrue(TEXT("All-one exact rotation"),Follow.GetRotation()==Target.GetRotation());
    TestTrue(TEXT("All-one exact scale"),Follow.GetScale3D()==Target.GetScale3D());
    // Quaternion sign and crossing +/-180 degrees must not create an angular spike.
    TestTrue(TEXT("Antipodal quaternion has zero angular difference"),
        RotationVector(Target.GetRotation()*-1. *Target.GetRotation().Inverse()).IsNearlyZero(1e-10));
    const FVector AcrossWrap=RotationVector(FRotator(0,-179,0).Quaternion()*FRotator(0,179,0).Quaternion().Inverse());
    TestTrue(TEXT("Yaw wrap uses two degrees"),FMath::IsNearlyEqual(AcrossWrap.Length(),FMath::DegreesToRadians(2.),1e-10));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPelvisInertiaPublicationTest,
    "Prophecy.NN.PelvisInertia.Publication", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPelvisInertiaPublicationTest::RunTest(const FString&)
{
    using namespace ProphecyPelvisInertia;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!TestNotNull(TEXT("Test world"),World)) return false;
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT { Remove(Agent); World->DestroyWorld(false); World->MarkAsGarbage(); };
    if (!TestNotNull(TEXT("Test agent"),Agent)) return false;
    Agent->bAutoEnsureStandaloneNNManager=false;
    constexpr double Dt=1./30.;
    const FTransform Start(FRotator(0,20,0),FVector(0,0,100));
    const FTransform Next(FRotator(0,21,0),FVector(1,0,100));
    FTransform A=Start,B=Next;
    TestFalse(TEXT("Default bypass"),ApplyTarget(Agent,1,Dt,FTransform::Identity,FTransform::Identity,A,B));
    TestTrue(TEXT("Enable exact-follow bypass"),UProphecyPelvisInertiaLibrary::SetPelvisInertia(Agent,true));
    TestFalse(TEXT("All-one bypass"),ApplyTarget(Agent,1,Dt,FTransform::Identity,FTransform::Identity,A,B));
    TestTrue(TEXT("Bypass is bit-identical"),A.Equals(Start,0) && B.Equals(Next,0));
    TestTrue(TEXT("Configure coast"),UProphecyPelvisInertiaLibrary::SetPelvisInertia(Agent,true,0,0,0,0));
    TestTrue(TEXT("First publication seeds velocity"),ApplyTarget(Agent,1,Dt,FTransform::Identity,FTransform::Identity,A,B));
    TestTrue(TEXT("Seed matches current target"),B.Equals(Next,1.e-8));
    const FTransform Carrier(FRotator(30,100,20),FVector(500,-800,40));
    A=Next.GetRelativeTransform(Carrier); B=FTransform::Identity;
    ApplyTarget(Agent,1+Dt,Dt,Carrier,Carrier,A,B);
    const FTransform Expected(FRotator(0,22,0),FVector(2,0,100));
    TestTrue(TEXT("Carrier movement cannot drag coasting pelvis"),(B*Carrier).Equals(Expected,1.e-7));
    TestTrue(TEXT("Previous endpoint remains previous filtered world pose"),(A*Carrier).Equals(Next,1.e-7));
    A=Start; B=Next;
    ApplyTarget(Agent,1+Dt,Dt,FTransform::Identity,FTransform::Identity,A,B);
    TestTrue(TEXT("Repeated timestamp does not integrate twice"),B.Equals(Expected,1.e-7));
    TestFalse(TEXT("Invalid input rejected"),UProphecyPelvisInertiaLibrary::SetPelvisInertia(Agent,true,-1,1,1,1));
    bool Enabled,Physical; float H,V,Y,PR;
    UProphecyPelvisInertiaLibrary::GetPelvisInertia(Agent,Enabled,H,V,Y,PR,Physical);
    TestTrue(TEXT("Rejected input preserves prior settings"),Enabled && H==0 && V==0 && Y==0 && PR==0);
    UProphecyPelvisInertiaLibrary::SetPelvisInertia(Agent,false,0,0,0,0);
    A=Start; B=Next;
    TestFalse(TEXT("Disable bypass"),ApplyTarget(Agent,2,Dt,Carrier,Carrier,A,B));
    TestTrue(TEXT("Disable preserves original endpoints exactly"),A.Equals(Start,0) && B.Equals(Next,0));
    UProphecyPelvisInertiaLibrary::SetPelvisInertia(Agent,true,0,0,0,0,true);
    TestTrue(TEXT("Kinematic still filters target with simulated-body option"),
        ApplyTarget(Agent,2,Dt,FTransform::Identity,FTransform::Identity,A,B));
    Remove(Agent);
    TestFalse(TEXT("Removal leaves no processing"),ApplyTarget(Agent,3,Dt,Carrier,Carrier,A,B));
    return true;
}
#endif
