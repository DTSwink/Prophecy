#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyNNPresentation.h"
#include "ProphecyNNPoseTypes.h"
#include "Misc/AutomationTest.h"

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
