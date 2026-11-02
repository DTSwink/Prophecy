#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKNavigation.h"
#include "ProphecyAgent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKNavigationCarrierTest,"Prophecy.FootIK.Live.NavigationCarrier",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKNavigationCarrierTest::RunTest(const FString&)
{
    using namespace ProphecyFootIKNavigation;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if(!World){AddError(TEXT("Cannot create navigation query world"));return false;}
    auto Box=[&](const FVector& Center,const FVector& Extent,const FQuat& Q,FName Tag,bool Feet=false)
    {
        auto* Actor=World->SpawnActor<AActor>();auto* C=NewObject<UBoxComponent>(Actor);Actor->SetRootComponent(C);
        C->SetBoxExtent(Extent);C->SetCollisionEnabled(ECollisionEnabled::QueryOnly);C->SetCollisionObjectType(ECC_WorldStatic);C->SetCollisionResponseToAllChannels(ECR_Block);
        if(Feet){C->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);C->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Ignore);}
        if(!Tag.IsNone())C->ComponentTags.Add(Tag);C->RegisterComponent();Actor->SetActorLocationAndRotation(Center,Q);return Actor;
    };
    Box(FVector(-150,0,-20),FVector(350,180,20),FQuat::Identity,NAME_None);
    Box(FVector(1310,0,148),FVector(690,180,20),FQuat::Identity,NAME_None);
    const FQuat RampQ=FRotator(FMath::RadiansToDegrees(FMath::Atan(.4)),0,0).Quaternion();
    Box(FVector(410,0,84)-RampQ.GetAxisZ()*5,FVector(FMath::Sqrt(420.*420+168.*168)/2,180,5),RampQ,TEXT("FootIKRoot"));
    for(int32 I=0;I<12;++I)Box(FVector(217.5+35*I,0,14*(I+1)-3),FVector(17.5,180,3),FQuat::Identity,TEXT("FootIKFeet"),true);
    auto* Agent=World->SpawnActor<AProphecyAgent>();Agent->TeleportManagedRootLowPoint(FVector::ZeroVector,0);
    Begin(Agent,0);TestTrue(TEXT("Navigation owns a separate carrier"),Active(Agent));
    double LargestVirtualZ=0,MaxStep=0;FVector Previous=Agent->GetRootLowPoint();bool Complete=true;
    auto MoveTo=[&](double X)
    {
        FMove Move;if(!PrepareMove(Agent,FVector(X,0,0),Move)){Complete=false;return;}
        if(!Move.HasSupport){Complete=false;AddError(FString::Printf(TEXT("Lost connected ramp support at %.3f cm"),X));return;}
        FVector Applied,Normal;bool Blocked=false;Agent->SetManagedRootLowPoint(Move.ActualRoot,0,Applied,Normal,Blocked);
        const FVector Virtual=CommitMove(Agent,Move,Applied);LargestVirtualZ=FMath::Max(LargestVirtualZ,FMath::Abs(Virtual.Z));
        MaxStep=FMath::Max(MaxStep,FVector::Distance(Previous,Applied));Previous=Applied;
        if(FMath::Abs(Applied.X-X)>.2)
        {
            Complete=false;
            AddError(FString::Printf(TEXT("Capsule stalls: previous=%s desired=%s applied=%s supportNormal=%s movementNormal=%s blocked=%d requestedX=%.3f"),
                *Move.PreviousActualRoot.ToString(),*Move.ActualRoot.ToString(),*Applied.ToString(),*Move.SupportNormal.ToString(),*Normal.ToString(),Blocked?1:0,X));
        }
    };
    MoveTo(2);
    TestTrue(TEXT("First horizontal move escapes exact floor contact"),Complete&&FMath::Abs(Agent->GetRootLowPoint().X-2)<.2);
    const FVector FirstSupported=Agent->GetRootLowPoint();
    TestTrue(TEXT("Collision skin is positive and below two millimetres"),FirstSupported.Z>0&&FirstSupported.Z<.2);
    for(int32 I=0;I<20&&Complete;++I)MoveTo(2);
    TestTrue(TEXT("Stationary support does not accumulate the collision skin"),Agent->GetRootLowPoint().Equals(FirstSupported,1.e-6));
    for(int32 I=2;I<=375&&Complete;++I)MoveTo(I*2.);
    TestTrue(TEXT("Actual capsule ascends finite navigation ramp"),Complete);
    TestTrue(TEXT("Top plateau height is counted once"),FMath::Abs(Agent->GetRootLowPoint().Z-168)<.2);
    TestEqual(TEXT("Slope never changes virtual NN root height"),LargestVirtualZ,0.);
    TestTrue(TEXT("Capsule edge support is continuous"),MaxStep<5.);
    const FVector PreviousVirtual(745,0,0),CurrentVirtual(750,0,0);FVector A,B,A2,B2;
    TestTrue(TEXT("Publication carrier pair resolves"),PublicationCarriers(Agent,1,PreviousVirtual,CurrentVirtual,A,B));
    TestTrue(TEXT("Repeated source timestamp resolves"),PublicationCarriers(Agent,1,PreviousVirtual,CurrentVirtual,A2,B2));
    TestTrue(TEXT("Published history stays exact"),A==A2&&B==B2);
    TestTrue(TEXT("Both plateau carriers have actual support elevation"),FMath::Abs(A.Z-168)<.2&&FMath::Abs(B.Z-168)<.2);
    TArray<FTransform> Roots;for(int32 I=0;I<9;++I)Roots.Add(FTransform(FRotator(0,I*7,0),FVector(750-I*25,0,168)));
    const FTransform First=Roots[0];TestTrue(TEXT("Future navigation elevation resolves"),ProjectWindow(Agent,Roots));
    TestTrue(TEXT("Actual first root is unchanged"),Roots[0].Equals(First,0));
    TestTrue(TEXT("Upcoming downhill root descends"),Roots.Last().GetLocation().Z<160);
    for(int32 I=0;I<Roots.Num();++I)
    {
        TestEqual(TEXT("Future horizontal path remains controller-authored"),Roots[I].GetLocation().X,750-I*25.);
        TestTrue(TEXT("Future headings remain controller-authored"),Roots[I].GetRotation().AngularDistance(FRotator(0,I*7,0).Quaternion())<1.e-7);
    }
    for(int32 I=374;I>=0&&Complete;--I)MoveTo(I*2.);
    TestTrue(TEXT("Actual capsule descends navigation ramp"),Complete);
    TestTrue(TEXT("Bottom plateau returns to original height"),FMath::Abs(Agent->GetRootLowPoint().Z)<.2);
    const FVector BeforeDisable=Agent->GetRootLowPoint();const double LastLift=Remove(Agent);
    TestTrue(TEXT("Disable removes carrier state"),!Active(Agent));
    TestTrue(TEXT("Remove never teleports actual agent"),Agent->GetRootLowPoint()==BeforeDisable);
    TestTrue(TEXT("Returned lift is the origin rebase needed by manager"),FMath::Abs(LastLift-BeforeDisable.Z)<1.e-8);
    World->DestroyWorld(false);return true;
}
#endif
