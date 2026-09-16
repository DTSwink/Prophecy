// Included after the native kernel under WITH_DEV_AUTOMATION_TESTS.
namespace PhysicalFeedbackBatchTests
{
using FImpl = AProphecyNNLocomotionManager::FImpl;
struct FBuffer
{
    const TCHAR* Name;
    TArray<float> FImpl::*Member;
    int32 Stride;
};
const FBuffer Buffers[] = {
    { TEXT("lower sample"), &FImpl::PhysicalStateBuffer, StateDim },
    { TEXT("lower previous"), &FImpl::PrevStateBuffer, StateDim },
    { TEXT("lower current"), &FImpl::CurStateBuffer, StateDim },
    { TEXT("lower prior physical"), &FImpl::PreviousPhysicalStateBuffer, StateDim },
    { TEXT("upper sample"), &FImpl::UpperPhysicalStateBuffer, UpperStateDim },
    { TEXT("upper current"), &FImpl::UpperCurrentStateBuffer, UpperStateDim },
    { TEXT("upper previous"), &FImpl::UpperPreviousStateBuffer, UpperStateDim },
    { TEXT("upper prior physical"), &FImpl::UpperPreviousPhysicalStateBuffer, UpperStateDim },
    { TEXT("upper lower-derived base"), &FImpl::UpperCurrentBaseBuffer, UpperStateDim },
    { TEXT("previous pelvis heading"), &FImpl::PreviousPelvisHeadingBuffer, 9 },
    { TEXT("current pelvis heading"), &FImpl::CurrentPelvisHeadingBuffer, 9 }
};

void FillPose(TArrayView<FTransform> Pose, int32 AgentIndex, int32 Pass)
{
    FRandomStream Random(17413 + AgentIndex * 37 + Pass * 7919);
    for (int32 Bone = 0; Bone < Pose.Num(); ++Bone)
    {
        FVector Axis(Random.FRandRange(-1, 1), Random.FRandRange(-1, 1), Random.FRandRange(-1, 1));
        Axis = Axis.GetSafeNormal();
        if (Axis.IsNearlyZero()) Axis = FVector::UpVector;
        FQuat Rotation(Axis, double(Random.FRandRange(-2.8f, 2.8f)));
        if ((AgentIndex + Bone + Pass) % 2) Rotation = Rotation * -1.0;
        if (AgentIndex % 17 == 0) Rotation = FQuat::Identity;
        if (AgentIndex % 19 == 0) Rotation = FQuat(Axis, 1.0e-9);
        if (AgentIndex % 23 == 0) Rotation = Rotation * 2.3;
        Pose[Bone] = FTransform(Rotation,
            FVector(Random.FRandRange(-350, 350), Random.FRandRange(-350, 350), Random.FRandRange(-350, 350)),
            FVector(0.3 + Bone * 0.03, 1.1, 2.7));
    }
}

void IdentityLower(float* State, const FImpl& Impl)
{
    FMemory::Memzero(State, StateDim * sizeof(float));
    for (const int32 Offset : { 3, 12, 18, 28, 34 })
    { State[Offset] = 1.0f; State[Offset + 4] = 1.0f; }
    CleanState(State, Impl);
}

void IdentityUpper(float* State)
{
    FMemory::Memzero(State, UpperStateDim * sizeof(float));
    for (int32 Offset = 0; Offset < 60; Offset += 6)
    { State[Offset] = 1.0f; State[Offset + 4] = 1.0f; }
    for (const int32 Offset : { 63, 69, 78, 84 })
    { State[Offset] = 1.0f; State[Offset + 4] = 1.0f; }
    CleanUpperState(State);
}

bool Initialize(FAutomationTestBase& Test, FImpl& Impl, int32 Count)
{
    if (!PhysicalRotationCacheTests::LoadLayout(Test, Impl) || Impl.UpperCoreBoneNames.Num() != 10) return false;
    Impl.RestOffsetsFromPelvis.SetNum(FullBodyBoneCount);
    for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
        Impl.RestOffsetsFromPelvis[Bone] = FVector3f(0.01f * Bone, 0.03f * Bone, -0.02f * Bone);
    Impl.Agents.SetNum(Count);
    Impl.PhysicalTransformBuffer.SetNum(Count * FullBodyBoneCount);
    Impl.PhysicalFeedbackWorkItems.SetNum(Count);
    Impl.PhysicalFeedbackIndices.Reserve(Count);
    int32 BufferIndex = 0;
    for (const FBuffer& Spec : Buffers)
    {
        auto& Values = Impl.*(Spec.Member);
        Values.SetNum(Count * Spec.Stride);
        for (int32 Index = 0; Index < Values.Num(); ++Index)
            Values[Index] = float(2000 + 17 * BufferIndex + Index) * 0.001f;
        ++BufferIndex;
    }
    const TSet<FName> LowerNames = { TEXT("pelvis"), TEXT("thigh_l"), TEXT("foot_l"), TEXT("ball_l"),
        TEXT("thigh_r"), TEXT("foot_r"), TEXT("ball_r") };
    for (int32 Index = 0; Index < Count; ++Index)
    {
        auto& Agent = Impl.Agents[Index];
        Agent.bUseWalkPolicy = (Index / 6) % 2 != 0;
        Agent.bHasPhysicalSample = Index % 3 != 0;
        FillPose(TransformSlice(Impl.PhysicalTransformBuffer, Index), Index, 0);
        const int32 Variant = Index % 6;
        if (Variant != 5) // Missing entries must resolve to the existing zero tolerance.
        {
            for (const FName Name : Impl.BodyNames)
            {
                auto& Tolerance = Agent.PhysicalFeedbackTolerances.FindOrAdd(Name);
                const bool bLarge = Variant == 0 || (Variant == 1 && LowerNames.Contains(Name))
                    || (Variant == 2 && !LowerNames.Contains(Name));
                Tolerance.LinearCm = bLarge ? 1.0e6f : Variant == 4 ? 2.5f : 0.0f;
                Tolerance.AngularDegrees = bLarge ? 360.0f : Variant == 4 ? 7.0f : 0.0f;
            }
        }
        IdentityLower(StateSlice(Impl.CurStateBuffer, Index), Impl);
        IdentityUpper(UpperStateSlice(Impl.UpperCurrentStateBuffer, Index));
    }
    return true;
}

bool Same(FAutomationTestBase& Test, const FImpl& Expected, const FImpl& Actual, const TCHAR* Mode, int32 Pass)
{
    for (const FBuffer& Spec : Buffers)
    {
        const auto& A = Expected.*(Spec.Member);
        const auto& B = Actual.*(Spec.Member);
        if (!Test.TestEqual(FString::Printf(TEXT("%s %s count"), Mode, Spec.Name), A.Num(), B.Num())) return false;
        for (int32 Index = 0; Index < A.Num(); ++Index)
        {
            if (!FMath::IsFinite(A[Index]) || !FMath::IsFinite(B[Index])
                || FMemory::Memcmp(A.GetData() + Index, B.GetData() + Index, sizeof(float)))
            {
                Test.AddError(FString::Printf(TEXT("%s pass %d %s float %d: legacy %.9g, prepared %.9g"),
                    Mode, Pass, Spec.Name, Index, double(A[Index]), double(B[Index])));
                return false;
            }
        }
    }
    for (int32 Index = 0; Index < Expected.Agents.Num(); ++Index)
    {
        if (Expected.Agents[Index].bHasPhysicalSample != Actual.Agents[Index].bHasPhysicalSample
            || Expected.Agents[Index].bUseWalkPolicy != Actual.Agents[Index].bUseWalkPolicy)
        {
            Test.AddError(FString::Printf(TEXT("%s pass %d agent %d flag mismatch"), Mode, Pass, Index));
            return false;
        }
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNPhysicalFeedbackBatchOracleTest,
    "Prophecy.NN.PhysicalFeedback.PreparedBatchFullState",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyNNPhysicalFeedbackBatchOracleTest::RunTest(const FString& Parameters)
{
    using namespace PhysicalFeedbackBatchTests;
    constexpr int32 Count = 102; // Includes untouched boundary lanes around the 100-agent fixture.
    const auto Legacy = MakeUnique<FImpl>();
    const auto Serial = MakeUnique<FImpl>();
    const auto Parallel = MakeUnique<FImpl>();
    if (!Initialize(*this, *Legacy, Count) || !Initialize(*this, *Serial, Count)
        || !Initialize(*this, *Parallel, Count)) return false;
    TestFalse(TEXT("Invalid negative preparation refused"), PreparePhysicalFeedbackWork(*Serial, -1));
    TestFalse(TEXT("Invalid past-end preparation refused"), PreparePhysicalFeedbackWork(*Parallel, Count));
    TArray<int32> Eligible;
    // Omitted indices represent failed captures and disabled/kinematic eligibility.
    // No UObject sampling is performed by this pure-state test.
    int32 BothUnchanged = 0, LowerOnlyUnchanged = 0, UpperOnlyUnchanged = 0, BothChanged = 0;
    for (int32 Pass = 0; Pass < 4; ++Pass)
    {
        Eligible.Reset();
        for (int32 Index = 1; Index < Count - 1; ++Index)
            if (Pass < 2 || (Index % 11 != 3 && Index % 11 != 4)) Eligible.Add(Index);
        for (const int32 Index : Eligible)
        {
            for (FImpl* Data : { Legacy.Get(), Serial.Get(), Parallel.Get() })
                FillPose(TransformSlice(Data->PhysicalTransformBuffer, Index), Index, Pass);
            if (!TestTrue(TEXT("Prepare serial item"), PreparePhysicalFeedbackWork(*Serial, Index))
                || !TestTrue(TEXT("Prepare parallel item"), PreparePhysicalFeedbackWork(*Parallel, Index))) return false;
        }
        // Deliberately alter source flags/maps after GT preparation. The kernel
        // must use its resolved input snapshot, never these mutable agent fields.
        for (FImpl* Data : { Serial.Get(), Parallel.Get() })
            for (const int32 Index : Eligible)
            {
                Data->Agents[Index].PhysicalFeedbackTolerances.Empty();
                Data->Agents[Index].bUseWalkPolicy = !Data->Agents[Index].bUseWalkPolicy;
                Data->Agents[Index].bHasPhysicalSample = !Data->Agents[Index].bHasPhysicalSample;
            }
        for (const int32 Index : Eligible)
        {
            float BeforeLower[StateDim], BeforeUpper[UpperStateDim];
            FMemory::Memcpy(BeforeLower, StateSlice(Legacy->CurStateBuffer, Index), sizeof(BeforeLower));
            FMemory::Memcpy(BeforeUpper, UpperStateSlice(Legacy->UpperCurrentStateBuffer, Index), sizeof(BeforeUpper));
            if (!CommitPhysicalSampleSerial(*Legacy, Index, TransformSlice(Legacy->PhysicalTransformBuffer, Index))) return false;
            const bool bLowerSame = !FMemory::Memcmp(BeforeLower, StateSlice(Legacy->CurStateBuffer, Index), sizeof(BeforeLower));
            const bool bUpperSame = !FMemory::Memcmp(BeforeUpper, UpperStateSlice(Legacy->UpperCurrentStateBuffer, Index), sizeof(BeforeUpper));
            if (bLowerSame && bUpperSame) ++BothUnchanged;
            else if (bLowerSame) ++LowerOnlyUnchanged;
            else if (bUpperSame) ++UpperOnlyUnchanged;
            else ++BothChanged;
        }
        ExecutePhysicalFeedbackBatch(*Serial, Serial->PhysicalFeedbackWorkItems, Eligible, true);
        ExecutePhysicalFeedbackBatch(*Parallel, Parallel->PhysicalFeedbackWorkItems, Eligible, false);
        for (FImpl* Data : { Serial.Get(), Parallel.Get() })
            for (const int32 Index : Eligible)
            {
                const auto& Work = Data->PhysicalFeedbackWorkItems[Index];
                if (!TestTrue(TEXT("Every dispatched kernel completed"), Work.bSucceeded)) return false;
                Data->Agents[Index].bHasPhysicalSample = Work.bHasPhysicalSample;
                Data->Agents[Index].bUseWalkPolicy = Legacy->Agents[Index].bUseWalkPolicy;
                Data->Agents[Index].PhysicalFeedbackTolerances = Legacy->Agents[Index].PhysicalFeedbackTolerances;
            }
        if (!Same(*this, *Legacy, *Serial, TEXT("prepared serial"), Pass)
            || !Same(*this, *Legacy, *Parallel, TEXT("prepared parallel"), Pass)) return false;
    }
    TestTrue(TEXT("Both recurrent states exactly unchanged branch exercised"), BothUnchanged > 0);
    TestTrue(TEXT("Only lower unchanged branch exercised"), LowerOnlyUnchanged > 0);
    TestTrue(TEXT("Only upper unchanged branch exercised"), UpperOnlyUnchanged > 0);
    TestTrue(TEXT("Both changed branch exercised"), BothChanged > 0);
    const TArray<int32> Empty;
    ExecutePhysicalFeedbackBatch(*Parallel, Parallel->PhysicalFeedbackWorkItems, Empty, false);
    return Same(*this, *Legacy, *Parallel, TEXT("empty batch preserves every lane"), 4);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNLowerFeedbackAlignmentTest,
    "Prophecy.NN.PhysicalFeedback.LowerTargetAlignment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyNNLowerFeedbackAlignmentTest::RunTest(const FString& Parameters)
{
    using namespace PhysicalFeedbackBatchTests;
    auto Serial = MakeUnique<FImpl>();
    auto Prepared = MakeUnique<FImpl>();
    if (!Initialize(*this, *Serial, 1) || !Initialize(*this, *Prepared, 1)) return false;
    float Authored[StateDim], Actual[StateDim], Aligned[StateDim], Original[StateDim];
    float* Current = StateSlice(Serial->CurStateBuffer, 0);
    FMemory::Memcpy(Original, Current, sizeof(Original));
    FMemory::Memcpy(Authored, Current, sizeof(Authored));
    // A completely different presentation frame/time must not count as contact.
    for (const int32 O : { 0, 9, 25 }) WriteStateVec3(Authored, O, FVector3f(7.1f, -3.2f, .9f));
    for (const int32 O : { 3, 12, 18, 28, 34 })
        WriteRot6(QuatToMatrix(FQuat(FVector(1,2,3).GetSafeNormal(), 1.7)), Authored + O);
    Authored[24] = .3f; Authored[40] = -.6f;
    ApplyLowerPhysicalDeviation(Authored, Authored, Current, Aligned);
    TestTrue(TEXT("Perfect follower preserves every recurrent float despite presentation movement"),
        FMemory::Memcmp(Aligned, Original, sizeof(Original)) == 0);

    FMemory::Memcpy(Actual, Authored, sizeof(Actual));
    WriteStateVec3(Actual, 9, ReadStateVec3(Authored, 9) + FVector3f(.05f, 0, 0));
    const FMat3f ContactRotation = QuatToMatrix(FQuat(FVector::UpVector, FMath::DegreesToRadians(20.0)));
    WriteRot6(Multiply(MatrixFromRot6(Authored + 18), ContactRotation), Actual + 18);
    Actual[24] += .1f;
    ApplyLowerPhysicalDeviation(Actual, Authored, Current, Aligned);
    TestTrue(TEXT("5 cm contact is retained independent of authored root"),
        ReadStateVec3(Aligned, 9).Equals(ReadStateVec3(Current, 9) + FVector3f(.05f, 0, 0), 1.e-6f));
    TestTrue(TEXT("World/component angular deviation transported onto current pose"),
        MatrixToQuat(MatrixFromRot6(Aligned + 18)).Equals(MatrixToQuat(ContactRotation), 1.e-6));
    TestTrue(TEXT("Toe feedback is an authored-relative deviation"), FMath::IsNearlyEqual(Aligned[24], .1f, 1.e-6f));
    for (FImpl* Data : { Serial.Get(), Prepared.Get() })
    {
        for (const FName Name : { FName("pelvis"), FName("thigh_l"), FName("foot_l"), FName("ball_l"),
            FName("thigh_r"), FName("foot_r"), FName("ball_r") })
        {
            auto& Tolerance = Data->Agents[0].PhysicalFeedbackTolerances.FindOrAdd(Name);
            Tolerance.LinearCm = 2.f; Tolerance.AngularDegrees = 5.f;
        }
    }
    PreparePhysicalFeedbackWork(*Prepared, 0);
    TestTrue(TEXT("Serial aligned commit succeeds"), CommitPhysicalSampleSerial(*Serial, 0,
        TransformSlice(Serial->PhysicalTransformBuffer, 0), Aligned));
    TestTrue(TEXT("Prepared aligned commit succeeds"), CommitPreparedPhysicalSample(*Prepared,
        Prepared->PhysicalFeedbackWorkItems[0], Aligned));
    Prepared->Agents[0].bHasPhysicalSample = Prepared->PhysicalFeedbackWorkItems[0].bHasPhysicalSample;
    TestTrue(TEXT("2 cm tolerance leaves 3 cm of a real 5 cm contact"),
        FMath::IsNearlyEqual(ReadStateVec3(StateSlice(Serial->CurStateBuffer, 0), 9).X, .03f, 1.e-6f));
    const FQuat Limited = MatrixToQuat(MatrixFromRot6(StateSlice(Serial->CurStateBuffer, 0) + 18));
    TestTrue(TEXT("5 degree tolerance leaves 15 degrees of real angular contact"),
        Limited.Equals(FQuat(FVector::UpVector, FMath::DegreesToRadians(15.0)), 1.e-5));
    return Same(*this, *Serial, *Prepared, TEXT("aligned serial/prepared"), 0);
}
