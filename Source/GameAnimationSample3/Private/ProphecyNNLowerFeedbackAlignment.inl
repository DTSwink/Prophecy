// Included after the encoders; only plain arrays cross the parallel feedback boundary.
struct FAlignedPhysicalFeedback
{
    float State[StateDim] = {};
    bool bAligned = false;
    float Upper[UpperStateDim] = {};
    bool bUpperAligned = false;
};
TMap<TWeakObjectPtr<AProphecyNNLocomotionManager>, TArray<FAlignedPhysicalFeedback>> AlignedPhysicalFeedbackBatches;

#if !UE_BUILD_SHIPPING
// Diagnostic A/B switch only; the corrected path remains the production default.
static TAutoConsoleVariable<int32> CVarLowerFeedbackAlignment(
    TEXT("Prophecy.NNLowerFeedbackAlignment"), 1,
    TEXT("1: aligned lower physical deviation (default). 0: legacy absolute physical sample. Restart PIE between comparisons."));
static TAutoConsoleVariable<int32> CVarUpperFeedbackAlignment(
    TEXT("Prophecy.NNUpperFeedbackAlignment"), 1,
    TEXT("1: completed-target upper physical deviation (default). 0: legacy absolute sample, diagnostic comparisons only."));
#endif

void ApplyLowerPhysicalDeviation(const float* Actual, const float* Authored,
    const float* Current, float* Out)
{
    FMemory::Memcpy(Out, Current, StateDim * sizeof(float));
    for (const int32 Offset : { 0, 9, 25 })
    {
        const FVector3f Error = ReadStateVec3(Actual, Offset) - ReadStateVec3(Authored, Offset);
        // Numerical transform noise only (one micrometre), not a gameplay dead zone.
        if (Error.SizeSquared() > 1.e-12f)
            WriteStateVec3(Out, Offset, ReadStateVec3(Current, Offset) + Error);
    }
    for (const int32 Offset : { 3, 12, 18, 28, 34 })
    {
        // Row-vector convention: R_actual = R_authored * R_error.
        const FMat3f Error = Multiply(Transpose(MatrixFromRot6(Authored + Offset)), MatrixFromRot6(Actual + Offset));
        FQuat RotationError = MatrixToQuat(Error).GetNormalized();
        if (RotationError.W < 0) RotationError = RotationError * -1.0;
        if (!RotationError.Equals(FQuat::Identity, 1.e-6))
            WriteRot6(Multiply(MatrixFromRot6(Current + Offset), Error), Out + Offset);
    }
    for (const int32 Offset : { 24, 40 })
    {
        const float Error = Actual[Offset] - Authored[Offset];
        if (FMath::Abs(Error) > 1.e-6f) Out[Offset] = FMath::Clamp(Current[Offset] + Error, -1.f, 1.f);
    }
}

// Upper feedback measures the deviation from the target of the same completed
// physics step. Presentation interpolation and fixed arm length are not impacts.
void ApplyUpperPhysicalDeviation(const float* Actual, const float* Authored,
    const float* Current, float* Out)
{
    FMemory::Memcpy(Out, Current, UpperStateDim * sizeof(float));
    for (const int32 Offset : { 60, 75 })
    {
        const FVector3f Error = ReadStateVec3(Actual, Offset) - ReadStateVec3(Authored, Offset);
        if (Error.SizeSquared() > 1.e-12f)
            WriteStateVec3(Out, Offset, ReadStateVec3(Current, Offset) + Error);
    }
    auto Rotation = [&](int32 Offset)
    {
        const FMat3f Error = Multiply(Transpose(MatrixFromRot6(Authored + Offset)), MatrixFromRot6(Actual + Offset));
        FQuat Q = MatrixToQuat(Error).GetNormalized();
        if (Q.W < 0) Q = Q * -1.0;
        if (!Q.Equals(FQuat::Identity, 1.e-6))
            WriteRot6(Multiply(MatrixFromRot6(Current + Offset), Error), Out + Offset);
    };
    for (int32 Offset = 0; Offset < 60; Offset += 6) Rotation(Offset);
    for (const int32 Offset : { 63, 69, 78, 84 }) Rotation(Offset);
}

void PrepareAlignedPhysicalFeedback(const AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex,
    AProphecyAgent& Actor, FAlignedPhysicalFeedback& Out, bool RetainNNUpper)
{
    Out.bAligned = Out.bUpperAligned = false;
    auto* Character = Actor.GetJoltCharacterComponent();
    if (!Character || !Character->IsJoltPhysical()) return;
    const auto& Agent = Impl.Agents[AgentIndex];
    const float* Current = StateSlice(Impl.CurStateBuffer, AgentIndex);
    const float* Upper = UpperStateSlice(Impl.UpperCurrentStateBuffer, AgentIndex);
    // A new binding has no completed target pair yet. Retain recurrence until
    // it does; never inject one frame of unaligned feedback at a transition.
    Out.bAligned = true;
#if !UE_BUILD_SHIPPING
    Out.bAligned = CVarLowerFeedbackAlignment.GetValueOnGameThread() != 0;
#endif
    Out.bUpperAligned = !RetainNNUpper;
#if !UE_BUILD_SHIPPING
    Out.bUpperAligned &= CVarUpperFeedbackAlignment.GetValueOnGameThread() != 0;
#endif
    FMemory::Memcpy(Out.State, Current, sizeof(Out.State));
    if (Out.bUpperAligned) FMemory::Memcpy(Out.Upper, Upper, sizeof(Out.Upper));
    const auto* Mesh = Actor.GetAgentMesh();
    const auto* Capsule = Actor.GetAgentCapsule();
    if (!Mesh || !Capsule) return;
    const FTransform Root(FRotator(0, -FMath::RadiansToDegrees(Agent.CurRootYaw), 0),
        TrainingToUnreal(Agent.CurRootPos) + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight());
    const FTransform Reference = (Actor.bManualNNPoseApplication ? Mesh->GetRelativeTransform()
        : Actor.GetAuthoredMeshRelativeTransform()) * Root;
    // Reuse the existing revision-paired target capture for the whole skeleton.
    // One fixed name set avoids rebinding it when D/S ownership changes.
    FTransform Actual[FullBodyBoneCount], Authored[FullBodyBoneCount];
    if (!Character->SampleCompletedLowerFeedbackPose(Impl.BodyNames, Reference, Actual, Authored)) return;
    FSampledTrainingRotations ActualRotations(Actual), AuthoredRotations(Authored);
    if (Out.bAligned)
    {
        float ActualState[StateDim], AuthoredState[StateDim];
        EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, Actual, ActualRotations, ActualState);
        EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, Authored, AuthoredRotations, AuthoredState);
        ApplyLowerPhysicalDeviation(ActualState, AuthoredState, Current, Out.State);
    }
    if (Out.bUpperAligned)
    {
        float ActualState[UpperStateDim], AuthoredState[UpperStateDim];
        EncodePhysicalUpperSample(Impl, Actual, ActualRotations, ActualState);
        EncodePhysicalUpperSample(Impl, Authored, AuthoredRotations, AuthoredState);
        ApplyUpperPhysicalDeviation(ActualState, AuthoredState, Upper, Out.Upper);
    }
}
