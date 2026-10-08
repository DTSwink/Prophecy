#include "ProphecyHalfAttackMount.h"
#include "Misc/AutomationTest.h"
#include "ProphecyHalfAttackCompensation.h"
#include "ProphecyGhostAttackLibrary.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHalfAttackMountTest,"Prophecy.NN.HalfAttack.PelvisMount",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHalfAttackMountTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyHalfAttackMount;
    // A pelvis-rooted chain plus a leg and a separate root child. Only spine descendants qualify.
    TArray<int32> Parents{INDEX_NONE,0,1,2,0,4,0};
    for (int32 I=0;I<Parents.Num();++I)
        TestEqual(TEXT("Exactly spine subtree"),IsUpper(I,1,Parents),I>=1 && I<=3);
    TestFalse(TEXT("Missing spine selects nothing"),IsUpper(2,INDEX_NONE,Parents));
    const FTransform GhostPelvis(FRotator(13,35,-11),FVector(30,20,95));
    const FTransform SpineLocal(FRotator(4,8,3),FVector(0,0,12));
    const FTransform GhostSpine=SpineLocal*GhostPelvis;
    const FTransform HandLocal(FRotator(-12,27,5),FVector(60,-25,25));
    const FTransform GhostHand=HandLocal*GhostPelvis;
    for (double Yaw:{0.,90.,179.,-179.,-90.})
    {
        const FTransform RealPelvis(FRotator(-19,Yaw,16),FVector(100,-50,110));
        const FTransform Mounted=Mount(GhostSpine,GhostPelvis,RealPelvis);
        TestTrue(TEXT("Spine local rotation/position retained through pelvis turn"),Mounted.GetRelativeTransform(RealPelvis).Equals(SpineLocal,1.e-6));
        const FTransform Hand=Mount(GhostHand,GhostPelvis,RealPelvis);
        TestTrue(TEXT("Ghost target inverse hits mounted hand"),Target(Hand.GetLocation(),RealPelvis,GhostPelvis).Equals(GhostHand.GetLocation(),1.e-6));
        TestTrue(TEXT("Hand local rotation retained"),Hand.GetRelativeTransform(RealPelvis).GetRotation().Equals(HandLocal.GetRotation(),1.e-6));
        const FTransform Seed=Mount(Hand,RealPelvis,GhostPelvis);
        TestTrue(TEXT("Half seeding and graft are inverses"),Seed.Equals(GhostHand,1.e-6));
        // Show the old translation-only mount violates the invariant as real pelvis turns.
        const FTransform OldMount(GhostPelvis.GetRotation(),RealPelvis.GetLocation());
        const double OldError=FMath::RadiansToDegrees(Mount(GhostSpine,GhostPelvis,OldMount)
            .GetRelativeTransform(RealPelvis).GetRotation().AngularDistance(SpineLocal.GetRotation()));
        if (Yaw==179.) TestTrue(TEXT("Old fixed-world orientation reproduces reversed torso"),OldError>100.);
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHalfAttackSpineCompensationTest,"Prophecy.NN.HalfAttack.SpineCompensation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHalfAttackSpineCompensationTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyHalfAttackMount;
    const FTransform GhostPelvis(FRotator(13,35,-11),FVector(30,20,95));
    const FTransform GhostSpine=FTransform(FRotator(4,8,3),FVector(0,0,12))*GhostPelvis;
    const FTransform GhostHand=FTransform(FRotator(-12,27,5),FVector(60,-25,25))*GhostSpine;
    const FTransform Anchor(FRotator(7,-57,12),FVector(-300,420,50));
    for (double Yaw:{0.,90.,179.,-179.,-90.}) for(double CarrierYaw:{-110.,60.})
    {
        const FTransform Carrier(FRotator(-3,CarrierYaw,9),FVector(100,-800,35));
        const FTransform RealPelvis(FRotator(-19,Yaw,16),FVector(100,-50,110));
        const auto Spine=CompensatedSpine(GhostSpine,GhostPelvis,RealPelvis,Anchor,Carrier);
        const auto Hand=GhostHand.GetRelativeTransform(GhostSpine)*Spine;
        TestTrue(TEXT("Spine attachment does not move"),Spine.GetLocation().Equals(Mount(GhostSpine,GhostPelvis,RealPelvis).GetLocation(),1.e-6));
        TestTrue(TEXT("Spine world orientation follows ghost, independent of real pelvis/carrier"),
            (Spine*Carrier).GetRotation().Equals((GhostSpine*Anchor).GetRotation(),1.e-6));
        TestTrue(TEXT("Hand world orientation follows ghost"),(Hand*Carrier).GetRotation().Equals((GhostHand*Anchor).GetRotation(),1.e-6));
        TestTrue(TEXT("Upper articulation is unchanged"),Hand.GetRelativeTransform(Spine).Equals(GhostHand.GetRelativeTransform(GhostSpine),1.e-6));
        TestTrue(TEXT("Aim vector from spine equals ghost in world space"),
            ((Hand*Carrier).GetLocation()-(Spine*Carrier).GetLocation()).Equals(
                (GhostHand*Anchor).GetLocation()-(GhostSpine*Anchor).GetLocation(),1.e-6));
        const FTransform MatchedPelvis=(GhostPelvis*Anchor).GetRelativeTransform(Carrier);
        TestTrue(TEXT("Matching pelvis rotations require no compensation"),
            CompensatedSpine(GhostSpine,GhostPelvis,MatchedPelvis,Anchor,Carrier).Equals(Mount(GhostSpine,GhostPelvis,MatchedPelvis),1.e-6));
        TArray<FTransform> Ghost{GhostPelvis};
        for(int32 I=0;I<5;++I) Ghost.Add(FTransform(FRotator(3+I,-8+I,2),FVector(1,0,10))*Ghost.Last());
        Ghost.Add(FTransform(FRotator(-12,27,5),FVector(60,-25,25))*Ghost.Last());
        Ghost.Add(FTransform(FRotator(20,7,-9),FVector(-30,0,-60))*GhostPelvis);
        const TArray<int32> Parents{INDEX_NONE,0,1,2,3,4,5,0};
        const int32 Spines[]={1,2,3,4,5};
        TArray<FTransform> DistributedPose;
        for(const auto& Bone:Ghost) DistributedPose.Add(Mount(Bone,GhostPelvis,RealPelvis));
        const auto Original=DistributedPose;
        TestTrue(TEXT("Distributed mount accepted"),MountDistributed(Ghost,DistributedPose,Parents,MakeArrayView(Spines),RealPelvis,Anchor,Carrier));
        const FQuat Counter=PelvisCounterRotation(GhostPelvis,RealPelvis,Anchor,Carrier);
        for(int32 I=1;I<=5;++I)
        {
            const FQuat Applied=(DistributedPose[I].GetRotation()*Original[I].GetRotation().Inverse()).GetNormalized();
            TestTrue(TEXT("Each spine adds exactly one fifth of the counter-rotation"),Applied.Equals(FQuat::Slerp(FQuat::Identity,Counter,I/5.).GetNormalized(),1.e-6));
            TestTrue(TEXT("Distributed joints preserve local attachment and length"),
                DistributedPose[I].GetRelativeTransform(DistributedPose[I-1]).GetLocation().Equals(Ghost[I].GetRelativeTransform(Ghost[I-1]).GetLocation(),1.e-6));
        }
        TestTrue(TEXT("Distributed chest reaches full ghost orientation"),(DistributedPose[5]*Carrier).GetRotation().Equals((Ghost[5]*Anchor).GetRotation(),1.e-6));
        TestTrue(TEXT("Distributed hand follows corrected chest"),(DistributedPose[6]*Carrier).GetRotation().Equals((Ghost[6]*Anchor).GetRotation(),1.e-6));
        TestTrue(TEXT("Distributed pelvis unchanged"),DistributedPose[0].Equals(Original[0],0));
        TestTrue(TEXT("Distributed leg unchanged"),DistributedPose[7].Equals(Original[7],0));
    }
    TestFalse(TEXT("Null toggle rejected"),UProphecyGhostAttackLibrary::EnableSpine01CompensationHalfAttack(nullptr,true));
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if(!TestNotNull(TEXT("Toggle fixture world"),World))return false;
    AProphecyAgent* A=World->SpawnActor<AProphecyAgent>();
    if(TestNotNull(TEXT("Toggle fixture agent"),A))
    {
        using namespace ProphecyHalfAttackCompensation;
        TestFalse(TEXT("Default disabled"),Enabled(A));
        CaptureReset(A);
        TestTrue(TEXT("Enable accepted"),UProphecyGhostAttackLibrary::EnableSpine01CompensationHalfAttack(A,true));
        TestTrue(TEXT("Enabled for this agent"),Enabled(A));
        RestoreReset(A);TestFalse(TEXT("Reset restores disabled baseline"),Enabled(A));
        TestFalse(TEXT("Distributed defaults off"),Distributed(A));
        TestFalse(TEXT("Position defaults off"),Position(A));
        UProphecyGhostAttackLibrary::EnableSpine01CompensationHalfAttack(A,true,true,true);CaptureReset(A);
        TestTrue(TEXT("Distribution enabled"),Distributed(A));
        TestTrue(TEXT("Position enabled"),Position(A));
        UProphecyGhostAttackLibrary::EnableSpine01CompensationHalfAttack(A,false,true,true);
        TestFalse(TEXT("Disable removes active state"),Enabled(A));
        TestFalse(TEXT("Disable removes distribution state too"),Distributed(A));
        TestFalse(TEXT("Disable removes position state too"),Position(A));
        RestoreReset(A);TestTrue(TEXT("Reset restores enabled baseline"),Enabled(A));
        TestTrue(TEXT("Reset restores distributed baseline"),Distributed(A));
        TestTrue(TEXT("Reset restores position baseline"),Position(A));
        Remove(A);TestFalse(TEXT("Removal retires state"),Enabled(A));
        TestFalse(TEXT("Removal retires distribution"),Distributed(A));
        TestFalse(TEXT("Removal retires position"),Position(A));
    }
    World->DestroyWorld(false);World->MarkAsGarbage();
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHalfAttackPositionCompensationTest,"Prophecy.NN.HalfAttack.PositionCompensation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHalfAttackPositionCompensationTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyHalfAttackMount;
    for(bool Distributed:{false,true})for(double Yaw:{0.,90.,179.,-179.})
    {
        FTransform Ghost[6];Ghost[0]=FTransform(FRotator(13,35,-11),FVector(30,20,95));
        for(int32 I=1;I<=5;++I)Ghost[I]=FTransform(FRotator(2,-3,1),FVector(1,0,7))*Ghost[I-1];
        const FTransform RealPelvis(FRotator(-19,Yaw,16),FVector(100,-50,110));
        const FVector Target(130,20,155);
        const auto Virtual=ReachTarget(Ghost,RealPelvis,Target,Distributed);
        FTransform RealPivot;int32 Pivot;
        if(Distributed)
        {
            const int32 Spines[]={1,2,3,4,5};FTransform Corrected[5];
            BuildDistributedSpines(MakeArrayView(Ghost),MakeArrayView(Spines),RealPelvis,
                Ghost[0].GetRotation()*RealPelvis.GetRotation().Inverse(),Corrected);
            RealPivot=Corrected[4];Pivot=5;
        }
        else {RealPivot=CompensatedSpine(Ghost[1],Ghost[0],RealPelvis,FTransform::Identity,FTransform::Identity);Pivot=1;}
        TestTrue(TEXT("Virtual target maps exactly to actual target, including reach"),
            RealPivot.TransformPosition(Ghost[Pivot].InverseTransformPosition(Virtual)).Equals(Target,1.e-6));
        TestTrue(TEXT("Identical torso-target distance in both frames"),
            FMath::IsNearlyEqual(FVector::Dist(Virtual,Ghost[Pivot].GetLocation()),FVector::Dist(Target,RealPivot.GetLocation()),1.e-6));
        const FVector Shift(150,-80,12);FTransform Moved=RealPelvis;Moved.AddToTranslation(Shift);
        TestTrue(TEXT("Attacker and target moving together do not stretch the attack"),
            ReachTarget(Ghost,Moved,Target+Shift,Distributed).Equals(Virtual,1.e-6));
        TestTrue(TEXT("Matching pelvis leaves target unchanged"),ReachTarget(Ghost,Ghost[0],Target,Distributed).Equals(Target,1.e-6));
        const FTransform Frame(FRotator(10,65,-20),FVector(250,-100,85));
        FTransform RotatedGhost[6];for(int32 I=0;I<6;++I)RotatedGhost[I]=Ghost[I]*Frame;
        TestTrue(TEXT("Coordinate-frame rotation and translation are covariant"),
            ReachTarget(RotatedGhost,RealPelvis*Frame,Frame.TransformPosition(Target),Distributed).Equals(Frame.TransformPosition(Virtual),1.e-6));
    }
    return !HasAnyErrors();
}
#endif
