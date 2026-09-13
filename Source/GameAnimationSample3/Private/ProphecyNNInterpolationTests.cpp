#include "ProphecyNNInterpolation.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace
{
constexpr int32 TestAgent = 910071;
FProphecyNNPoseSnapshot Publish(double Time, const FTransform& A, const FTransform& B,
    const FTransform& Carrier = FTransform::Identity)
{
    const FName Names[] = {TEXT("pelvis")};
    const FTransform Previous[] = {A.GetRelativeTransform(Carrier)};
    const FTransform Current[] = {B.GetRelativeTransform(Carrier)};
    FProphecyNNPoseStore::SetAgentLocalPose(TestAgent, Names, Current, Previous, Current, Carrier, Carrier, Time);
    FProphecyNNPoseSnapshot Pose;
    FProphecyNNPoseStore::GetAgentLocalPose(TestAgent, Pose);
    return Pose;
}
FTransform Point(double X, double Yaw = 0)
{
    return FTransform(FRotator(0,Yaw,0), FVector(X,0,100));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNNInterpolationModeTest, "Prophecy.NN.Interpolation.ModeAndEndpoints",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNNInterpolationModeTest::RunTest(const FString& Parameters)
{
    FProphecyNNPoseStore::ClearAgentPose(TestAgent);
    auto Pose = Publish(0, Point(0), Point(10,90));
    TestTrue(TEXT("Default is the existing interpolation"), Pose.InterpolationMode == EProphecyNNInterpolationMode::Current);
    TestTrue(TEXT("Default allocates no tangent arrays"), Pose.InterpolationStartTangents.IsEmpty() && Pose.InterpolationEndTangents.IsEmpty());
    FProphecyNNPoseStore::SetInterpolationMode(TestAgent, EProphecyNNInterpolationMode::HermiteSlerp);
    FProphecyNNPoseStore::GetAgentLocalPose(TestAgent, Pose);
    TestTrue(TEXT("Mode changes wait for a publication"), Pose.InterpolationMode == EProphecyNNInterpolationMode::Current);
    Pose = Publish(1./30, Point(0), Point(10,90));
    TestTrue(TEXT("Next publication enables the requested mode"), Pose.InterpolationMode == EProphecyNNInterpolationMode::HermiteSlerp);
    TestTrue(TEXT("Exact start"), ProphecyNNInterpolation::Sample(Pose,0,Point(0),Point(10,90),0).Equals(Point(0),1.e-9));
    TestTrue(TEXT("Exact end"), ProphecyNNInterpolation::Sample(Pose,0,Point(0),Point(10,90),1).Equals(Point(10,90),1.e-9));
    const auto Quarter = ProphecyNNInterpolation::Sample(Pose,0,Point(0),Point(10,90),.25f);
    TestTrue(TEXT("Cold history uses a straight position segment"), Quarter.GetLocation().Equals(FVector(2.5,0,100),1.e-8));
    TestTrue(TEXT("SLERP has uniform angular progress"), Quarter.GetRotation().Equals(Point(0,22.5).GetRotation(),1.e-6));
    TestEqual(TEXT("Source clock unchanged"), Pose.SourceTimeSeconds, 1./30);
    FProphecyNNPoseStore::SetInterpolationMode(TestAgent,EProphecyNNInterpolationMode::Current);
    Pose=Publish(2./30,Point(10),Point(20));
    TestTrue(TEXT("Switching back frees tangent storage"), Pose.InterpolationMode == EProphecyNNInterpolationMode::Current
        && Pose.InterpolationStartTangents.Max()==0 && Pose.InterpolationEndTangents.Max()==0);
    FProphecyNNPoseStore::ClearAgentPose(TestAgent);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNNInterpolationHistoryTest, "Prophecy.NN.Interpolation.HistoryPinningAndRebase",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNNInterpolationHistoryTest::RunTest(const FString& Parameters)
{
    FProphecyNNPoseStore::ClearAgentPose(TestAgent);
    FProphecyNNPoseStore::SetInterpolationMode(TestAgent,EProphecyNNInterpolationMode::HermiteSlerp);
    Publish(0,Point(0),Point(10));
    Publish(1./30,Point(10),Point(20));
    auto Pose=Publish(2./30,Point(20),Point(40));
    const auto Mid=ProphecyNNInterpolation::Sample(Pose,0,Point(20),Point(40),.5f);
    TestTrue(TEXT("Warm history produces a cubic position curve"), !FMath::IsNearlyEqual(Mid.GetLocation().X,30.,1.e-5));
    const FVector EndTangent=Pose.InterpolationEndTangents[0];
    Pose=Publish(3./30,Point(40),Point(65));
    TestTrue(TEXT("Ordinary intervals share boundary velocity"), Pose.InterpolationStartTangents[0].Equals(EndTangent,1.e-7));
    const FVector Start=Pose.InterpolationStartTangents[0], End=Pose.InterpolationEndTangents[0];
    Pose=Publish(3./30,Point(40),Point(65),FTransform(FRotator(0,75,0),FVector(170,230,0)));
    TestTrue(TEXT("Same-time world-preserving root rebase retains curve"), Pose.InterpolationStartTangents[0].Equals(Start,1.e-7)
        && Pose.InterpolationEndTangents[0].Equals(End,1.e-7));
    Pose=Publish(4./30,Point(65),Point(65));
    for (int32 I=0;I<=20;++I)
        TestTrue(TEXT("Stationary pinned point cannot drift"), ProphecyNNInterpolation::Sample(Pose,0,Point(65),Point(65),I/20.f).GetLocation().Equals(Point(65).GetLocation(),1.e-9));
    Pose=Publish(5./30,Point(65),Point(-20));
    for (int32 I=0;I<=50;++I)
    {
        const FVector P=ProphecyNNInterpolation::Sample(Pose,0,Point(65),Point(-20),I/50.f).GetLocation();
        TestTrue(TEXT("Reversal remains inside endpoint bounds"), P.X>=-20.-1.e-8 && P.X<=65.+1.e-8 && FMath::IsNearlyEqual(P.Z,100.));
    }
    Pose=Publish(6./30,Point(900),Point(1000));
    TestTrue(TEXT("Discontinuous pose resets old tangents"), ProphecyNNInterpolation::Sample(Pose,0,Point(900),Point(1000),.5f).GetLocation().Equals(Point(950).GetLocation(),1.e-8));
    FProphecyNNPoseStore::ClearAgentPose(TestAgent);
    Pose=Publish(7./30,Point(0),Point(1));
    TestTrue(TEXT("Clearing an agent clears its override"), Pose.InterpolationMode==EProphecyNNInterpolationMode::Current);
    FProphecyNNPoseStore::ClearAgentPose(TestAgent);
    return true;
}
#endif
