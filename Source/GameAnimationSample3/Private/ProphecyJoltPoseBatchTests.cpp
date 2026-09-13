#include "ProphecyJoltPoseBatch.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace ProphecyJolt::PoseBatchTests
{
bool Exact(const FTransform& A, const FTransform& B)
{
    const FQuat X = A.GetRotation(), Y = B.GetRotation();
    return X.X == Y.X && X.Y == Y.Y && X.Z == Y.Z && X.W == Y.W
        && A.GetTranslation() == B.GetTranslation() && A.GetScale3D() == B.GetScale3D();
}
bool SamePose(const FProphecyJoltComposedPose& A, const FProphecyJoltComposedPose& B)
{
    if (A.LocalTransforms.Num() != B.LocalTransforms.Num() || A.ComponentTransforms.Num() != B.ComponentTransforms.Num()
        || A.WorldTransforms.Num() != B.WorldTransforms.Num()) return false;
    for (int32 Index = 0; Index < A.LocalTransforms.Num(); ++Index)
        if (!Exact(A.LocalTransforms[Index], B.LocalTransforms[Index])
            || !Exact(A.ComponentTransforms[Index], B.ComponentTransforms[Index])
            || !Exact(A.WorldTransforms[Index], B.WorldTransforms[Index])) return false;
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPoseBatchTest,
    "Prophecy.Jolt.Pose.ParallelBatchMatchesSerialAndIsolatesErrors",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltPoseBatchTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::Pose;
    using namespace ProphecyJolt::PoseBatchTests;
    TArray<int32> Parents;
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    for (int32 Index = 0; Index < 88; ++Index) Parents.Add(Index == 0 ? INDEX_NONE : (Index - 1) / 2);
    for (int32 Index = 0; Index < 22; ++Index)
    {
        auto& Mapping = Mappings.AddDefaulted_GetRef();
        Mapping.BoneIndex = 85 - 4 * Index;
        Mapping.BodyFromBoneRigid = FTransform(FRotator(Index, -3 * Index, 2 * Index), FVector(4, -2, 7));
        Mapping.VisualScale = FVector(.9 + .005 * Index, 1.1, 1.0);
    }
    FPreparedLayout Layout;
    FString Error;
    if (!Layout.Build(88, Parents, Mappings, Error)) { AddError(Error); return false; }
    struct FInput { TArray<FTransform> Base, Bodies; FTransform Carrier; };
    TArray<FInput> Inputs;
    TArray<FProphecyJoltComposedPose> Serial, Parallel;
    TArray<FComposeBatchItem> Jobs;
    Inputs.SetNum(100); Serial.SetNum(100); Parallel.SetNum(100); Jobs.SetNum(100);
    for (int32 Index = 0; Index < 100; ++Index)
    {
        for (int32 Bone = 0; Bone < 88; ++Bone)
            Inputs[Index].Base.Add(FTransform(FRotator(.2 * Bone, -.3 * Index, .1 * Bone),
                FVector(.3 * Bone, 2, 3), FVector(1.0, 1.0 + .0005 * Bone, .95)));
        for (int32 Body = 0; Body < 22; ++Body)
            Inputs[Index].Bodies.Add(FTransform(FRotator(.3 * Index, 4 * Body, -7),
                FVector(1000 * Index + Body, 3 * Body - Index, 100 + 5 * Body)));
        Inputs[Index].Carrier = FTransform(FRotator(1, Index, -2), FVector(1000 * Index, -40, 10));
        auto& Job = Jobs[Index];
        Job.Layout = &Layout; Job.BaseLocal = Inputs[Index].Base; Job.BodyWorld = Inputs[Index].Bodies;
        Job.ComponentWorld = Inputs[Index].Carrier; Job.Output = &Parallel[Index];
        if (!Layout.Compose(Job.BaseLocal, Job.BodyWorld, Job.ComponentWorld, Serial[Index], Error))
        { AddError(Error); return false; }
    }
    ComposeBatch(Jobs);
    for (int32 Index = 0; Index < Jobs.Num(); ++Index)
        if (!TestTrue(TEXT("All 100 parallel full frames exactly match serial composition"),
            Jobs[Index].bSucceeded && Jobs[Index].Error.IsEmpty() && SamePose(Parallel[Index], Serial[Index]))) return false;

    const FTransform OriginalRoot = Inputs[37].Base[0];
    Inputs[37].Base[0].SetScale3D(FVector(-1, 1, 1));
    ComposeBatch(Jobs);
    for (int32 Index = 0; Index < Jobs.Num(); ++Index)
    {
        if (Index == 37)
        {
            TestFalse(TEXT("One invalid packet fails independently"), Jobs[Index].bSucceeded);
            TestTrue(TEXT("Invalid packet leaves no output and supplies a reason"),
                !Jobs[Index].Error.IsEmpty() && Parallel[Index].LocalTransforms.IsEmpty()
                && Parallel[Index].ComponentTransforms.IsEmpty() && Parallel[Index].WorldTransforms.IsEmpty());
        }
        else if (!TestTrue(TEXT("An invalid peer cannot change a valid completed packet"),
            Jobs[Index].bSucceeded && SamePose(Parallel[Index], Serial[Index]))) return false;
    }
    Inputs[37].Base[0] = OriginalRoot;
    ComposeBatch(Jobs, true);
    for (int32 Index = 0; Index < Jobs.Num(); ++Index)
        if (!TestTrue(TEXT("Single-thread fallback has the same full outputs"),
            Jobs[Index].bSucceeded && SamePose(Parallel[Index], Serial[Index]))) return false;
    return true;
}
#endif
