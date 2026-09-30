#include "ProphecyNNPoseTypes.h"
#include "ProphecyFixedArmPhysics.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNFixedArmTest,"Prophecy.NN.PhysicalTargets.FixedForearms",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyNNFixedArmTest::RunTest(const FString&)
{
    constexpr int32 Id=1900000042;
    const TArray<FName> Names={TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("lowerarm_r"),TEXT("hand_r")};
    FProphecyNNFixedArms Geometry;Geometry.ForearmOffsets[0]=FVector(30,0,0);Geometry.ForearmOffsets[1]=FVector(-27,0,0);
    TArray<FTransform> Local={FTransform::Identity,FTransform(Geometry.ForearmOffsets[0]),FTransform::Identity,FTransform(Geometry.ForearmOffsets[1])};
    TArray<FTransform> Previous=Local,Current=Local;
    for(int S=0;S<2;++S)
    {
        Previous[S*2]=FTransform(FRotator(10,-60,20),FVector(S*60,0,100));
        Current[S*2]=FTransform(FRotator(-10,60,-20),FVector(S*60,20,105));
        Previous[S*2+1]=FTransform(FRotator(20,30,40),Previous[S*2].TransformPosition(Geometry.ForearmOffsets[S]));
        Current[S*2+1]=FTransform(FRotator(-20,10,50),Current[S*2].TransformPosition(Geometry.ForearmOffsets[S])+FVector(10,15,-5));
    }
    for(bool Special:{false,true})for(bool Half:{false,true})
    {
        FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Previous,Current,FTransform::Identity,FTransform::Identity,
            0,Special,false,0,FVector2D::ZeroVector,Geometry,Half);
        FProphecyNNPoseSnapshot Snapshot;FProphecyNNPoseStore::GetAgentLocalPose(Id,Snapshot);
        TestEqual(TEXT("Special ownership does not control arm attachment"),FProphecyNNPoseStore::UsesAttackPresentation(Id),Special);
        TestEqual(TEXT("Half attacks retain locomotion legs"),FProphecyNNPoseStore::UsesLowerSpecialPresentation(Id),Special && !Half);
        for(int Step=0;Step<=20;++Step)
        {
            TArray<FTransform> Pose=Current;const double Alpha=Step/20.;
            for(int B=0;B<4;++B)Pose[B].Blend(Snapshot.PreviousComponentTransforms[B],Snapshot.ComponentTransforms[B],Alpha);
            const auto Before=Pose;
            FProphecyNNPoseStore::ApplyRigidForearms(Id,Snapshot,Names,Pose);
            for(int S=0;S<2;++S)
            {
                const int E=2*S,H=E+1;
                TestTrue(TEXT("Every interpolation sample retains anatomical attachment"),Pose[H].GetLocation().Equals(Pose[E].TransformPosition(Geometry.ForearmOffsets[S]),1.e-8));
                TestTrue(TEXT("Neither arm can compress or stretch"),FMath::IsNearlyEqual(FVector::Distance(Pose[E].GetLocation(),Pose[H].GetLocation()),Geometry.ForearmOffsets[S].Length(),1.e-8));
                TestTrue(TEXT("Wrist rotation and forearm transform are unchanged"),Pose[H].GetRotation().Equals(Before[H].GetRotation(),1.e-8) && Pose[E].Equals(Before[E],1.e-8));
            }
        }
    }
    FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Previous,Current,FTransform::Identity,FTransform::Identity,
        2,false,false,0,FVector2D::ZeroVector,Geometry,false,false);
    FProphecyNNPoseSnapshot Free;FProphecyNNPoseStore::GetAgentLocalPose(Id,Free);
    auto Unconstrained=Current;
    FProphecyNNPoseStore::ApplyRigidForearms(Id,Free,Names,Unconstrained);
    for(int S=0;S<2;++S)
    {
        TestTrue(TEXT("Free-position publication retains raw NN endpoint"),Free.ComponentTransforms[S*2+1].Equals(Current[S*2+1]));
        TestTrue(TEXT("Free-position interpolation adds no attachment clamp"),Unconstrained[S*2+1].Equals(Current[S*2+1]));
    }
    FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,Previous,Current,FTransform::Identity,FTransform::Identity,
        3,false,false,0,FVector2D::ZeroVector,Geometry,false,true);
    FProphecyNNPoseSnapshot Restored;FProphecyNNPoseStore::GetAgentLocalPose(Id,Restored);
    for(int S=0;S<2;++S)TestTrue(TEXT("Toggling freedom off restores anatomical attachment"),Restored.ComponentTransforms[S*2+1].GetLocation().Equals(Restored.ComponentTransforms[S*2].TransformPosition(Geometry.ForearmOffsets[S]),1.e-8));
    FProphecyNNPoseStore::ClearAgentPose(Id);
    // Simple animation/fixture publishers cannot alter length after establishing geometry.
    FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,0);
    Local[1].SetLocation(FVector(70,0,0));Local[3].SetLocation(FVector(-4,0,0));
    FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Local,1);
    FProphecyNNPoseSnapshot Snapshot;FProphecyNNPoseStore::GetAgentLocalPose(Id,Snapshot);
    TestTrue(TEXT("Local-only publishers preserve both fixed offsets"),Snapshot.LocalTransforms[1].GetLocation()==Geometry.ForearmOffsets[0] && Snapshot.LocalTransforms[3].GetLocation()==Geometry.ForearmOffsets[1]);
    FProphecyNNPoseStore::ClearAgentPose(Id);
    return !HasAnyErrors();
}
#endif
