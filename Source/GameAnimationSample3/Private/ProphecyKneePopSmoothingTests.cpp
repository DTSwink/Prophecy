#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyKneePopSmoothing.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyNNPoseTypes.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FKneePopSmoothingTest,"Prophecy.NN.PhysicalTargets.KneePopSmoothing",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool RunKneePopSmoothingChecks(FAutomationTestBase& Test)
{
    // Exact possessed-agent PhysicalMesh capture, current scene frames 617..619.
    const FVector Points[3][3]={
        {{-4.4810198817,962.6419656775,83.1749359463},{-.445666841,984.5971947101,51.1364513855},{3.3160274127,1004.0797199908,12.3155296759}},
        {{-4.4369787574,966.3890544285,82.9259882216},{-.8905098618,986.1971570611,49.4619444223},{3.0111181998,1008.2915929549,12.1365450455}},
        {{-4.2385562736,970.1107731196,83.1113286561},{-.5893407879,993.2945011067,51.9026979174},{2.4815680679,1009.7098355033,11.7884183186}}};
    auto Bend=[](const FVector& H,const FVector& K,const FVector& F)
    { return FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct((K-H).GetSafeNormal(),(F-K).GetSafeNormal()),-1.,1.))); };
    double Before[3],After[3];
    for (int i=0;i<3;++i)
    {
        const FVector H=Points[i][0],K=Points[i][1],F=Points[i][2];
        FTransform Thigh(H),Calf(K),Foot(FRotator(11,22,33),F),Toe(F+FVector(10,0,0));
        const FTransform OldThigh=Thigh,OldCalf=Calf,OldFoot=Foot,OldToe=Toe;
        Test.TestFalse(TEXT("Zero zone bypass"),ProphecyKneePopSmoothing::Apply(Thigh,Calf,Foot,&Toe,0));
        Test.TestTrue(TEXT("Disabled transforms bit unchanged"),Thigh.Equals(OldThigh,0)&&Calf.Equals(OldCalf,0)&&Foot.Equals(OldFoot,0)&&Toe.Equals(OldToe,0));
        Test.TestTrue(TEXT("Captured full-extension approach softened"),ProphecyKneePopSmoothing::Apply(Thigh,Calf,Foot,&Toe,4));
        Before[i]=Bend(H,K,F);After[i]=Bend(H,Calf.GetLocation(),Foot.GetLocation());
        Test.TestTrue(TEXT("Hip fixed"),Thigh.GetLocation().Equals(H,0));
        Test.TestTrue(TEXT("Both segment lengths preserved"),FMath::IsNearlyEqual((Calf.GetLocation()-H).Size(),(K-H).Size(),1.e-6)
            &&FMath::IsNearlyEqual((Foot.GetLocation()-Calf.GetLocation()).Size(),(F-K).Size(),1.e-6));
        const FVector Shift=Foot.GetLocation()-F,Axis=(F-H).GetSafeNormal();
        Test.TestTrue(TEXT("Minimum radial displacement toward hip"),FVector::CrossProduct(Shift,Axis).Size()<1.e-6 && FVector::DotProduct(Shift,Axis)<0);
        Test.TestTrue(TEXT("Foot lifts with radial correction"),Shift.Z>0);
        Test.TestTrue(TEXT("Foot rotation and toe offset preserved"),Foot.GetRotation().Equals(OldFoot.GetRotation(),0)
            &&(Toe.GetLocation()-Foot.GetLocation()).Equals(OldToe.GetLocation()-F,1.e-6));
        const FVector OldPole=K-H-Axis*FVector::DotProduct(K-H,Axis),NewPole=Calf.GetLocation()-H-Axis*FVector::DotProduct(Calf.GetLocation()-H,Axis);
        Test.TestTrue(TEXT("Same bend side"),FVector::DotProduct(OldPole,NewPole)>0);
        const FTransform Frame(FRotator(23,67,12),FVector(100,-20,30));
        FTransform TH=OldThigh*Frame,TC=OldCalf*Frame,TF=OldFoot*Frame;
        ProphecyKneePopSmoothing::Apply(TH,TC,TF,nullptr,4);
        Test.TestTrue(TEXT("Independent of coordinate frame"),TC.Equals(Calf*Frame,1.e-6)&&TF.Equals(Foot*Frame,1.e-6));
    }
    Test.TestTrue(TEXT("Fixture reproduces collapse and rebound"),Before[1]<.1 && Before[2]-Before[1]>14);
    Test.TestTrue(TEXT("No full-extension collapse"),After[1]>20);
    Test.TestTrue(TEXT("Rebound reduced below 3 degrees"),FMath::Abs(After[2]-After[1])<3);

    FTransform H(FVector(0,0,80)),K(FVector(0,0,40)),F(FVector::ZeroVector);
    Test.TestTrue(TEXT("Vertical straight leg uses supplied bend, no floor restriction"),ProphecyKneePopSmoothing::Apply(H,K,F,nullptr,4,FVector(1,0,0)));
    Test.TestTrue(TEXT("Finite forward knee"),K.GetLocation().X>0&&!K.ContainsNaN()&&!F.ContainsNaN());
    H=FTransform(FVector(0,0,80));K=FTransform(FVector(-.1,0,40));F=FTransform(FVector::ZeroVector);
    Test.TestTrue(TEXT("Reversed near-straight pole corrected with reliable bend frame"),ProphecyKneePopSmoothing::Apply(H,K,F,nullptr,4,FVector(1,0,0)));
    Test.TestTrue(TEXT("Softening does not amplify backward knee"),K.GetLocation().X>0);
    const int32 Id=-190617;
    const TArray<FName> Names={TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l")};
    FProphecyNNPoseSnapshot Snapshot;Snapshot.BoneNames=Names;
    TArray<FTransform> Pose={FTransform(Points[1][0]),FTransform(Points[1][1]),FTransform(Points[1][2])};
    const auto Original=Pose;
    ProphecyNNPresentation::SetKneePopSmoothing(Id,4);
    FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
    Test.TestTrue(TEXT("Shared presentation applies correction without legacy calf clamp"),!Pose[2].Equals(Original[2],1.e-6));
    // All special publications share this existing classification, independent of clamps.
    for(const TCHAR* Mode:{TEXT("attack"),TEXT("parry"),TEXT("dodge")})
    {
        FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Original,Original,Original,
            FTransform::Identity,FTransform::Identity,1.,true,false);
        Pose=Original;FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
        Test.TestTrue(FString::Printf(TEXT("%s without entry inertia bypasses smoothing"),Mode),
            Pose[1].Equals(Original[1],0)&&Pose[2].Equals(Original[2],0));
    }
    FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Original,Original,Original,
        FTransform::Identity,FTransform::Identity,2.,false,false);
    Pose=Original;FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
    Test.TestTrue(TEXT("Locomotion resumes configured smoothing"),!Pose[2].Equals(Original[2],1.e-6));
    ProphecyNNPresentation::SetKneePopSmoothing(Id,0);Pose=Original;
    FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
    Test.TestTrue(TEXT("Disable removes settings and pose work"),!ProphecyNNPresentation::HasKneePopSmoothing(Id)&&Pose[1].Equals(Original[1],0)&&Pose[2].Equals(Original[2],0));
    ProphecyNNPresentation::SetKneePopSmoothing(Id,4);FProphecyNNPoseStore::ClearAgentPose(Id);
    Test.TestFalse(TEXT("Agent teardown clears settings"),ProphecyNNPresentation::HasKneePopSmoothing(Id));
    return !Test.HasAnyErrors();
}
bool FKneePopSmoothingTest::RunTest(const FString&) { return RunKneePopSmoothingChecks(*this); }
#endif
