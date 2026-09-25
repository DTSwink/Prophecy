#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyNNPresentation.h"
#include "ProphecyNNPoseTypes.h"
#include "Misc/AutomationTest.h"
#include "ProphecyRecoveryLegLength.h"

bool RunAttackStartInertiaChecks(FAutomationTestBase& Test);
bool RunKneePopSmoothingChecks(FAutomationTestBase& Test);
#if WITH_EDITOR
bool RunCapturedKneeBendReturnChecks(FAutomationTestBase& Test);
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRecoveryCalfLengthTest,"Prophecy.NN.PhysicalTargets.RecoveryCalfLength",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FRecoveryCalfLengthTest::RunTest(const FString&)
{
    TestTrue(TEXT("Attack start pelvis inertia regression"),RunAttackStartInertiaChecks(*this));
    TestTrue(TEXT("Optional knee smoothing regression"),RunKneePopSmoothingChecks(*this));
#if WITH_EDITOR
    TestTrue(TEXT("Captured knee bend return regression"),RunCapturedKneeBendReturnChecks(*this));
#endif
    using namespace ProphecyRecoveryLegLength;
    for (double Length:{37.5,42.5,47.5})
    {
        FTransform Thigh(FQuat::Identity,FVector(0,0,75));
        FTransform Calf(FQuat::Identity,FVector(20,0,40));
        const FTransform Foot(FRotator(12,32,-8),FVector(0,0,5));
        const FTransform Saved=Foot;
        TestTrue(TEXT("Reachable compression/extension resolves"),Resolve(Thigh,Calf,Foot,42.5,Length));
        TestTrue(TEXT("Upper length preserved"),FMath::IsNearlyEqual((Calf.GetLocation()-Thigh.GetLocation()).Size(),42.5,1.e-6));
        TestTrue(TEXT("Calf length preserved including compression"),FMath::IsNearlyEqual((Foot.GetLocation()-Calf.GetLocation()).Size(),Length,1.e-6));
        TestTrue(TEXT("Foot position and rotation unchanged"),Foot.Equals(Saved,0));
        TestTrue(TEXT("Existing knee bend side preserved"),Calf.GetLocation().X>0);
        const FTransform Previous=Calf;
        Resolve(Thigh,Calf,Foot,42.5,Length);
        TestTrue(TEXT("Repeated presentation is idempotent"),Calf.Equals(Previous,1.e-6));
    }
    const int32 Id=-918;
    const TArray<FName> Names={TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r")};
    TArray<FTransform> Pose;
    for (int Side=0;Side<2;++Side)
    {
        Pose.Add(FTransform(FVector(0,Side*20,75)));Pose.Add(FTransform(FVector(20,Side*20,40)));Pose.Add(FTransform(FVector(0,Side*20,5)));
    }
    FProphecyNNPoseSnapshot Snapshot;Snapshot.BoneNames=Names;Snapshot.LocalTransforms=Pose;
    ProphecyNNPresentation::SetRecoveryCalfLengths(Id,FVector2D(42.5,42.5),FVector2D(47.5,37.5));
    FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
    TestTrue(TEXT("Both sides use independently published lengths"),
        FMath::IsNearlyEqual((Pose[2].GetLocation()-Pose[1].GetLocation()).Size(),47.5,1.e-6)
        && FMath::IsNearlyEqual((Pose[5].GetLocation()-Pose[4].GetLocation()).Size(),37.5,1.e-6));
    Snapshot.PreviousComponentTransforms=Pose;
    Snapshot.ComponentTransforms=Pose;
    Resolve(Snapshot.ComponentTransforms[0],Snapshot.ComponentTransforms[1],Snapshot.ComponentTransforms[2],42.5,43.5);
    Resolve(Snapshot.ComponentTransforms[3],Snapshot.ComponentTransforms[4],Snapshot.ComponentTransforms[5],42.5,41.5);
    for (float Alpha:{0.f,.25f,.5f,.75f,1.f})
    {
        for(int32 I=0;I<Pose.Num();++I) Pose[I].Blend(Snapshot.PreviousComponentTransforms[I],Snapshot.ComponentTransforms[I],Alpha);
        const auto Before=Pose;
        FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose,Alpha);
        for(int32 Side=0;Side<2;++Side)
        {
            const int32 I=Side*3;
            const double Expected=Side==0?FMath::Lerp(47.5,43.5,double(Alpha)):FMath::Lerp(37.5,41.5,double(Alpha));
            TestTrue(TEXT("Recovery length follows pose progress on both legs"),FMath::IsNearlyEqual((Pose[I+2].GetLocation()-Pose[I+1].GetLocation()).Size(),Expected,1.e-6));
            TestTrue(TEXT("Interpolated recovery preserves ankle and hip"),Pose[I+2].Equals(Before[I+2],0) && Pose[I].GetLocation().Equals(Before[I].GetLocation(),0));
        }
        const auto Once=Pose;
        ProphecyNNPresentation::SetRecoveryCalfLengths(Id,FVector2D(42.5,42.5),FVector2D(39,49));
        FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose,Alpha);
        TestTrue(TEXT("A newer live return tick cannot change the same presented sample"),Pose[1].Equals(Once[1],1.e-6) && Pose[4].Equals(Once[4],1.e-6));
    }
    FProphecyNNPoseStore::ClearAgentPose(Id);
    Pose[1].AddToTranslation(FVector(1,2,3));const auto Uncorrected=Pose;
    FProphecyNNPoseStore::ApplyRigidCalves(Id,Snapshot,Names,Pose);
    TestTrue(TEXT("Cleared/inactive return does no pose work"),Pose[1].Equals(Uncorrected[1],0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNPresentationCadence,
    "Prophecy.NN.Presentation.FrameCadence", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyNNPresentationCadence::RunTest(const FString&)
{
    const float Interval = 1.f / 30.f;
    auto Run = [this, Interval](const TArray<float>& Deltas, bool bExpectOldPause)
    {
        float Remainder = 0.f, OldAlpha = 0.f;
        int32 Completed = 0, OldPauses = 0;
        double Elapsed = 0.0, LastTime = -double(Interval), LastOldTime = LastTime;
        for (const float Dt : Deltas)
        {
            Remainder += Dt;
            int32 Steps = 0;
            while (Remainder >= Interval) { Remainder -= Interval; ++Steps; ++Completed; }
            Elapsed += Dt;
            const float Alpha = ProphecyNNPresentation::FromRemainder(Remainder, Interval);
            const float OldCandidate = Dt < Interval ? Remainder / Interval : 1.f;
            OldAlpha = Steps > 0 ? OldCandidate : FMath::Max(OldAlpha, OldCandidate);
            const double Presented = (double(Completed) - 1.0 + Alpha) * Interval;
            const double OldPresented = (double(Completed) - 1.0 + OldAlpha) * Interval;
            if (Dt > 0.f && FMath::Abs(OldPresented - LastOldTime) < 1.e-8) ++OldPauses;
            // Test distance/velocity, not merely nondecreasing time: a held endpoint
            // passed the old regression while still visibly stopping the character.
            TestTrue(TEXT("Constant-speed motion advances by the complete elapsed frame, including hitch recovery"),
                FMath::Abs(180.0 * (Presented - LastTime - double(Dt))) < .001);
            TestTrue(TEXT("Presentation keeps a constant one-policy-interval delay at every cadence"),
                FMath::Abs(Presented - (Elapsed - double(Interval))) < 1.e-6);
            LastTime = Presented;
            LastOldTime = OldPresented;
        }
        if (bExpectOldPause) TestTrue(TEXT("Recorded hitch fixture exposes the previous endpoint-hold defect"), OldPauses > 0);
    };
    TArray<float> Steady;
    Steady.Init(1.f / 60.f, 120);
    Run(Steady, false);
    Steady.Init(Interval, 60);
    Run(Steady, false);
    Steady.Init(.2f, 30);
    Run(Steady, false);
    Run({.04f, .016f, 0.f, .016f, .008f, .016f, .055998798f, .017114699f,
         .016f, .016f, .072077006f, .016729697f, .0166668f,
         .069286302f, .019374598f, .2f, .005f, .008f, .016f, .016f}, true);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNPresentationSharedReaders,
    "Prophecy.NN.Presentation.SharedReadersAndLifecycle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyNNPresentationSharedReaders::RunTest(const FString&)
{
    constexpr int32 Id = 198713;
    constexpr double Source = 4.0;
    const float Interval = 1.f / 30.f;
    FProphecyNNPoseStore::ClearAgentPose(Id);
    ProphecyNNPresentation::Publish(Id, Source, .25f);
    TestEqual(TEXT("Physical target reader shares root progress even on a slow frame"),
        ProphecyNNPresentation::Resolve(Id, Source, Source + Interval * .5, .072f, Interval, true), .25f);
    TestEqual(TEXT("Zero-time refresh shares root progress"),
        ProphecyNNPresentation::Resolve(Id, Source, Source + Interval * .5, 0.f, Interval, true), .25f);
    // A revision change within the same source interval must not change its clock.
    const TArray<FName> Names{TEXT("pelvis")};
    const TArray<FTransform> Local{FTransform::Identity};
    FProphecyNNPoseStore::SetAgentLocalPose(Id, Names, Local, Source);
    FProphecyNNPoseStore::SetAgentLocalPose(Id, Names, Local, Source);
    TestEqual(TEXT("Same-time re-publication retains progress"),
        ProphecyNNPresentation::Resolve(Id, Source, Source + Interval * .5, .016f, Interval, true), .25f);
    ProphecyNNPresentation::Publish(Id, Source, .75f);
    TestEqual(TEXT("Subsequent fast frame keeps advancing in the same interval"),
        ProphecyNNPresentation::Resolve(Id, Source, Source + Interval * .75, .016f, Interval, true), .75f);
    const double NextSource = Source + Interval;
    ProphecyNNPresentation::Publish(Id, NextSource, .25f);
    TestEqual(TEXT("New interval resumes forward interpolation"),
        ProphecyNNPresentation::Resolve(Id, NextSource, NextSource + Interval * .25, .016f, Interval, true), .25f);
    TestEqual(TEXT("Exact-pose option overrides fractional presentation"),
        ProphecyNNPresentation::Resolve(Id, NextSource, NextSource + Interval * .25, .016f, Interval, false), 1.f);
    // /fp:fast division can differ by a few float ULPs; stale .25/1 values cannot pass.
    TestEqual(TEXT("Mismatched source never consumes another interval's alpha"),
        ProphecyNNPresentation::Resolve(Id, Source, Source + Interval * .5, .016f, Interval, true), .5f, 1.e-6f);
    FProphecyNNPoseStore::ClearAgentPose(Id);
    TestEqual(TEXT("Unmanaged slow-frame timing does not snap to the endpoint"),
        ProphecyNNPresentation::Resolve(Id, NextSource, NextSource + Interval * .5, .072f, Interval, true), .5f, 1.e-6f);
    TestEqual(TEXT("Clearing/reusing a pose ID removes old presentation progress"),
        ProphecyNNPresentation::Resolve(Id, NextSource, NextSource + Interval * .5, .016f, Interval, true), .5f, 1.e-6f);
    return true;
}
#endif
