#include "ProphecyHalfAttackMount.h"
#include "Misc/AutomationTest.h"
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
#endif
