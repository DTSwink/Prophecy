#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Components/StaticMeshComponent.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNativeReachTest,"Prophecy.Reach.NativeKernel",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyNativeReachTest::RunTest(const FString&)
{
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Reach reference mesh"),Mesh)) return false;
    const auto& Ref=Mesh->GetRefSkeleton();TArray<FTransform> CS,Base;
    for (int I=0;I<Ref.GetNum();++I) { int P=Ref.GetParentIndex(I);CS.Add(P<0?Ref.GetRefBonePose()[I]:Ref.GetRefBonePose()[I]*CS[P]); }
    const auto Names=ProphecyNativeReach::BoneNames();
    for (FName N:Names) { int I=Ref.FindBoneIndex(N);if (!TestTrue(TEXT("Skeleton joint exists"),I>=0)) return false;Base.Add(CS[I]); }
    const int Hands[]={Names.IndexOfByKey(TEXT("hand_l")),Names.IndexOfByKey(TEXT("hand_r"))};
    FVector Targets[2]={Base[Hands[0]].GetLocation()+FVector(0,15,10),Base[Hands[1]].GetLocation()+FVector(0,15,10)};
    const float Speeds[2]={120,90};double WorstLength=0;
    for (auto Mode:{EProphecyDoubleReachMode::Left,EProphecyDoubleReachMode::Right,EProphecyDoubleReachMode::Both})
    {
        ProphecyNativeReach::FState State;TArray<FTransform> Output;
        for (int Tick=0;Tick<90;++Tick)
        {
            auto Previous=State;
            TestTrue(TEXT("Native solve succeeds"),ProphecyNativeReach::Step(Base,Mode,Targets,Speeds,State,Output,1./60.));
            for (const auto& T:Output) TestFalse(TEXT("Finite normalized output"),T.ContainsNaN()||!T.GetRotation().IsNormalized());
            for (int K=0;K<2;++K) if (State.Active[K]&&Tick>0)
                TestTrue(TEXT("Requested hand trajectory obeys per-hand tick speed"),FVector::Distance(State.Targets[K],Previous.Targets[K])*100<=Speeds[K]/60.+1.e-6);
            for (const TCHAR* Side:{TEXT("l"),TEXT("r")})
            {
                int A=Names.IndexOfByKey(FName(*FString::Printf(TEXT("upperarm_%s"),Side))),B=Names.IndexOfByKey(FName(*FString::Printf(TEXT("lowerarm_%s"),Side))),C=Names.IndexOfByKey(FName(*FString::Printf(TEXT("hand_%s"),Side)));
                for (auto Pair:{FIntPoint(A,B),FIntPoint(B,C)}) WorstLength=FMath::Max(WorstLength,FMath::Abs(FVector::Distance(Output[Pair.X].GetLocation(),Output[Pair.Y].GetLocation())-FVector::Distance(Base[Pair.X].GetLocation(),Base[Pair.Y].GetLocation())));
            }
        }
    }
    TestTrue(TEXT("Arm lengths preserved"),WorstLength<1.e-6);
    FString CSV=TEXT("agents,repeat,mean_ms,peak_ms\n");
    for (int Count:{1,10,100}) for (int Repeat=0;Repeat<3;++Repeat)
    {
        TArray<ProphecyNativeReach::FState> Crowd;Crowd.SetNum(Count);TArray<FTransform> Output;
        double Total=0,Peak=0;
        for (int Tick=0;Tick<180;++Tick)
        {
            double Start=FPlatformTime::Seconds();for (auto& S:Crowd) ProphecyNativeReach::Step(Base,EProphecyDoubleReachMode::Both,Targets,Speeds,S,Output,1./60.);
            const double Ms=(FPlatformTime::Seconds()-Start)*1000;if (Tick>=30) {Total+=Ms;Peak=FMath::Max(Peak,Ms);}
        }
        CSV+=FString::Printf(TEXT("%d,%d,%.9f,%.9f\n"),Count,Repeat,Total/150,Peak);
    }
    FFileHelper::SaveStringToFile(CSV,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachGrasp20261012/native-performance.csv")));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGrabGeometryTest,"Prophecy.Reach.GrabGeometry",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyGrabGeometryTest::RunTest(const FString&)
{
    using namespace ProphecyReach;
    auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    auto* Clip=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/_mygame/closed_fist.closed_fist"));
    if(!TestNotNull(TEXT("Hand reference"),Mesh)||!TestNotNull(TEXT("Fist reference"),Clip))return false;
    auto* Component=NewObject<UStaticMeshComponent>();auto* Shape=NewObject<UBodySetup>();
    FKSphereElem Sphere;Sphere.Radius=6;Shape->AggGeom.SphereElems.Add(Sphere);
    double BuildMs=0,FitMs=0;int Trials=0;
    for(int Side=0;Side<2;++Side)for(int Trial=0;Trial<30;++Trial)
    {
        FHand H;double Start=FPlatformTime::Seconds();TestTrue(TEXT("Reference finger conversion"),BuildFingers(Mesh,Clip,Side,H));BuildMs+=(FPlatformTime::Seconds()-Start)*1000;
        H.Component=Component;H.Collider=Shape;H.Target=FTransform::Identity;
        Component->SetWorldLocation(H.Palm+(Side==0?-FVector::RightVector:FVector::RightVector)*6.35);
        H.Point=Component->GetComponentTransform().InverseTransformPosition(H.Palm);
        Start=FPlatformTime::Seconds();FitFingers(H);FitMs+=(FPlatformTime::Seconds()-Start)*1000;++Trials;
        TestTrue(TEXT("Fingers fitted once"),H.Fitted);
        for(const auto& B:H.Fingers)TestTrue(TEXT("Finite bounded curl"),FMath::IsFinite(B.Curl)&&B.Curl>=0&&B.Curl<=1);
        // Durable points follow component motion and rotation, without a world-space recapture.
        const FVector Local=H.Point;const FTransform Moved(FRotator(25,40,10),FVector(130,-40,95));
        Component->SetWorldTransform(Moved);
        TestTrue(TEXT("Surface point stays component local"),TargetFrame(H).TransformPosition(H.Point).Equals(Moved.TransformPosition(Local),1.e-6));
    }
    FString Perf=FString::Printf(TEXT("finger_reference_mean_ms=%.9f\nfinger_fit_mean_ms=%.9f\n"),BuildMs/Trials,FitMs/Trials);
    FFileHelper::SaveStringToFile(Perf,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ReachGrasp20261012/finger-performance.txt")));
    TestFalse(TEXT("Invalid side fails"),UProphecyReachLibrary::ReachTarget(nullptr,static_cast<EProphecyReachHand>(255),FTransform::Identity));
    TestFalse(TEXT("Missing target fails"),UProphecyReachLibrary::GrabObject(nullptr,EProphecyReachHand::Right,nullptr));
    return !HasAnyErrors();
}
#endif
