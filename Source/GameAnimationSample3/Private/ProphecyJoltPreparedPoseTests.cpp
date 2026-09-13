#include "ProphecyJoltPose.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

namespace ProphecyJolt::PreparedPoseTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

FTransform RandomTransform(FRandomStream& Random, bool bRigid)
{
    const FQuat Rotation = FRotator(Random.FRandRange(-130.f, 130.f),
        Random.FRandRange(-130.f, 130.f), Random.FRandRange(-130.f, 130.f)).Quaternion();
    const FVector Translation(Random.FRandRange(-200.f, 200.f), Random.FRandRange(-200.f, 200.f), Random.FRandRange(-200.f, 200.f));
    const FVector Scale = bRigid ? FVector::OneVector
        : FVector(Random.FRandRange(.7f, 1.3f), Random.FRandRange(.7f, 1.3f), Random.FRandRange(.7f, 1.3f));
    return FTransform(Rotation, Translation, Scale);
}

bool ExactlySame(const FTransform& A, const FTransform& B)
{
    const FQuat X = A.GetRotation(), Y = B.GetRotation();
    return X.X == Y.X && X.Y == Y.Y && X.Z == Y.Z && X.W == Y.W
        && A.GetTranslation() == B.GetTranslation() && A.GetScale3D() == B.GetScale3D();
}

bool CompareArray(FAutomationTestBase& Test, TConstArrayView<FTransform> A,
    TConstArrayView<FTransform> B, const TCHAR* Label)
{
    if (!Test.TestEqual(Label, A.Num(), B.Num())) return false;
    for (int32 Index = 0; Index < A.Num(); ++Index)
        if (!ExactlySame(A[Index], B[Index]))
        {
            Test.AddError(FString::Printf(TEXT("%s: bone %d differs in an exact transform component."), Label, Index));
            return false;
        }
    return true;
}

bool ComparePose(FAutomationTestBase& Test, const FProphecyJoltComposedPose& A, const FProphecyJoltComposedPose& B)
{
    return CompareArray(Test, A.LocalTransforms, B.LocalTransforms, TEXT("All local transforms"))
        && CompareArray(Test, A.ComponentTransforms, B.ComponentTransforms, TEXT("All component transforms"))
        && CompareArray(Test, A.WorldTransforms, B.WorldTransforms, TEXT("All world transforms"));
}

void MakeLayout(TArray<int32>& Parents, TArray<FProphecyJoltPoseBodyMapping>& Mappings, bool bPhysicalRoot)
{
    Parents.Reset(); Mappings.Reset();
    for (int32 Index = 0; Index < 88; ++Index) Parents.Add(Index == 0 ? INDEX_NONE : (Index - 1) / 2);
    FRandomStream Random(92101);
    for (int32 Index = 0; Index < 22; ++Index)
    {
        FProphecyJoltPoseBodyMapping& Mapping = Mappings.AddDefaulted_GetRef();
        Mapping.BoneIndex = Index == 0 && bPhysicalRoot ? 0 : Index * 4 + 1;
        Mapping.BodyFromBoneRigid = RandomTransform(Random, true);
        // The original rigid check tolerates this small deviation: cached inverse must retain it exactly.
        if (Index == 7) Mapping.BodyFromBoneRigid.SetScale3D(FVector(1.0000002, .9999998, 1.0));
        Mapping.VisualScale = FVector(Random.FRandRange(.7f, 1.3f), Random.FRandRange(.7f, 1.3f), Random.FRandRange(.7f, 1.3f));
    }
    for (int32 Index = 0; Index < Mappings.Num() / 2; ++Index) Mappings.Swap(Index, Mappings.Num() - 1 - Index);
}

bool Empty(const FProphecyJoltComposedPose& Pose)
{
    return Pose.LocalTransforms.IsEmpty() && Pose.ComponentTransforms.IsEmpty() && Pose.WorldTransforms.IsEmpty();
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPreparedPoseExact,
    "Prophecy.Jolt.Pose.PreparedFullFrameMatchesLegacy", ProphecyJolt::PreparedPoseTests::Flags)
bool FProphecyJoltPreparedPoseExact::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::PreparedPoseTests;
    for (const bool bPhysicalRoot : {false, true})
    {
        TArray<int32> Parents;
        TArray<FProphecyJoltPoseBodyMapping> Mappings;
        MakeLayout(Parents, Mappings, bPhysicalRoot);
        Pose::FPreparedLayout Layout;
        FString Error;
        if (!Layout.Build(88, Parents, Mappings, Error)) { AddError(Error); return false; }
        FProphecyJoltComposedPose Actual;
        const FTransform* LocalAllocation = nullptr;
        const FTransform* ComponentAllocation = nullptr;
        const FTransform* WorldAllocation = nullptr;
        for (int32 Frame = 0; Frame < 32; ++Frame)
        {
            FRandomStream Random(8001 + Frame);
            TArray<FTransform> Base, Bodies;
            for (int32 Index = 0; Index < 88; ++Index) Base.Add(RandomTransform(Random, false));
            for (int32 Index = 0; Index < 22; ++Index) Bodies.Add(RandomTransform(Random, true));
            FTransform World = RandomTransform(Random, true);
            if (Frame % 2 == 0) World.AddToTranslation(FVector(1.e8, -7.e7, 3.e7));
            if (Frame % 3 == 0) World.SetScale3D(FVector(.9999999, 1.0000001, 1.0));
            const TArray<FTransform> OriginalBase = Base, OriginalBodies = Bodies;
            FProphecyJoltComposedPose Expected;
            if (!Pose::ComposeCompletedPose(Base, Parents, Mappings, Bodies, World, Expected, Error)
                || !Layout.Compose(Base, Bodies, World, Actual, Error)) { AddError(Error); return false; }
            if (!ComparePose(*this, Actual, Expected)
                || !CompareArray(*this, Base, OriginalBase, TEXT("Base input unchanged"))
                || !CompareArray(*this, Bodies, OriginalBodies, TEXT("Body input unchanged"))) return false;
            if (Frame == 0)
            {
                LocalAllocation = Actual.LocalTransforms.GetData();
                ComponentAllocation = Actual.ComponentTransforms.GetData();
                WorldAllocation = Actual.WorldTransforms.GetData();
            }
            else if (!TestTrue(TEXT("All three output allocations are reused at constant layout"),
                LocalAllocation == Actual.LocalTransforms.GetData() && ComponentAllocation == Actual.ComponentTransforms.GetData()
                && WorldAllocation == Actual.WorldTransforms.GetData())) return false;
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPreparedPoseValidation,
    "Prophecy.Jolt.Pose.PreparedValidationAndRebuild", ProphecyJolt::PreparedPoseTests::Flags)
bool FProphecyJoltPreparedPoseValidation::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::PreparedPoseTests;
    TArray<int32> Parents;
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    MakeLayout(Parents, Mappings, false);
    TArray<FTransform> Base, Bodies;
    Base.Init(FTransform::Identity, 88); Bodies.Init(FTransform::Identity, 22);
    FTransform World = FTransform::Identity;
    Pose::FPreparedLayout Layout;
    FProphecyJoltComposedPose Output, Expected;
    FString Error, LegacyError;
    auto Rebuild = [&]() { return Layout.Build(Base.Num(), Parents, Mappings, Error); };
    if (!Rebuild()) { AddError(Error); return false; }
    auto RejectSame = [&]()
    {
        const bool Legacy = Pose::ComposeCompletedPose(Base, Parents, Mappings, Bodies, World, Expected, LegacyError);
        const bool Prepared = Layout.Compose(Base, Bodies, World, Output, Error);
        return TestFalse(TEXT("Legacy rejects invalid changing frame"), Legacy)
            && TestFalse(TEXT("Prepared rejects the same changing frame"), Prepared)
            && TestEqual(TEXT("Changing-input/output error reason is retained"), Error, LegacyError)
            && TestTrue(TEXT("Every prepared output is empty on failure"), Empty(Output));
    };
    if (!Layout.Compose(Base, Bodies, World, Output, Error)) { AddError(Error); return false; }
    Base[17].SetScale3D(FVector(-1, 1, 1));
    if (!RejectSame()) return false;
    Base[17] = FTransform::Identity;
    Bodies[3].SetRotation(FQuat(0, 0, 0, 2));
    if (!RejectSame()) return false;
    Bodies[3] = FTransform::Identity;
    World.SetScale3D(FVector(2, 1, 1));
    if (!RejectSame()) return false;
    World = FTransform::Identity;
    Bodies.Pop();
    if (!RejectSame()) return false;
    Bodies.Add(FTransform::Identity);
    Base[0].SetScale3D(FVector(1.e-200));
    Base[2].SetScale3D(FVector(1.e-200));
    if (!RejectSame()) return false; // Valid positive inputs can yield an invalid zero scale during composition.
    Base[0] = FTransform::Identity; Base[2] = FTransform::Identity;

    Parents[4] = 4;
    TestFalse(TEXT("Invalid topology rejected during preparation"), Rebuild());
    TestFalse(TEXT("Failed build leaves no usable stale layout"), Layout.IsValid());
    Parents[4] = 1;
    const int32 SavedBone = Mappings[1].BoneIndex;
    Mappings[1].BoneIndex = Mappings[0].BoneIndex;
    TestFalse(TEXT("Duplicate mapping rejected during preparation"), Rebuild());
    Mappings[1].BoneIndex = SavedBone;
    Mappings[1].VisualScale = FVector(1, -1, 1);
    TestFalse(TEXT("Nonpositive fixed visual scale rejected"), Rebuild());
    Mappings[1].VisualScale = FVector(1.1, .9, 1.2);
    Mappings[1].BodyFromBoneRigid.SetScale3D(FVector(1, 2, 1));
    TestFalse(TEXT("Scaled body offset rejected"), Rebuild());
    Mappings[1].BodyFromBoneRigid = FTransform(FRotator(12, 34, 56), FVector(11, -2, 8));
    Parents[4] = 0;
    if (!Rebuild() || !Layout.Compose(Base, Bodies, World, Output, Error)
        || !Pose::ComposeCompletedPose(Base, Parents, Mappings, Bodies, World, Expected, LegacyError))
    { AddError(Error + LegacyError); return false; }
    return ComparePose(*this, Output, Expected);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPreparedPoseBuffers,
    "Prophecy.Jolt.Pose.PreparedPublicationBufferLifetime", ProphecyJolt::PreparedPoseTests::Flags)
bool FProphecyJoltPreparedPoseBuffers::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::PreparedPoseTests;
    TArray<int32> Parents;
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    MakeLayout(Parents, Mappings, false);
    TArray<FTransform> Base, Bodies;
    Base.Init(FTransform::Identity, 88); Bodies.Init(FTransform::Identity, 22);
    Pose::FPreparedLayout Layout;
    FString Error;
    if (!Layout.Build(88, Parents, Mappings, Error)) { AddError(Error); return false; }
    struct FPublicationState { FProphecyJoltComposedPose Completed, Scratch; };
    TUniquePtr<FPublicationState> State = MakeUnique<FPublicationState>();
    if (!Layout.Compose(Base, Bodies, FTransform::Identity, State->Completed, Error)) { AddError(Error); return false; }
    for (int32 Frame = 0; Frame < 8; ++Frame)
    {
        const FProphecyJoltComposedPose Previous = State->Completed;
        FProphecyJoltComposedPose InFlight = MoveTemp(State->Scratch);
        Bodies[0].AddToTranslation(FVector(1, 2, 3));
        if (!Layout.Compose(Base, Bodies, FTransform::Identity, InFlight, Error)) { AddError(Error); return false; }
        if (!ComparePose(*this, State->Completed, Previous)) return false;
        Swap(State->Completed, InFlight);
        State->Scratch = MoveTemp(InFlight);
        if (!ComparePose(*this, State->Scratch, Previous)) return false;
    }
    FProphecyJoltComposedPose InFlight = MoveTemp(State->Scratch);
    if (!Layout.Compose(Base, Bodies, FTransform::Identity, InFlight, Error)) { AddError(Error); return false; }
    const FProphecyJoltComposedPose Expected = InFlight;
    State.Reset(); // A publication callback may remove the bound state; the local frame still owns its storage.
    return ComparePose(*this, InFlight, Expected);
}

#endif
