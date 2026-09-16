// Included after the encoders; only plain arrays cross the parallel feedback boundary.
struct FAlignedLowerFeedback
{
    float State[StateDim] = {};
    bool bAligned = false;
};
TMap<TWeakObjectPtr<AProphecyNNLocomotionManager>, TArray<FAlignedLowerFeedback>> AlignedLowerFeedbackBatches;

#if !UE_BUILD_SHIPPING
// Diagnostic A/B switch only; the corrected path remains the production default.
static TAutoConsoleVariable<int32> CVarLowerFeedbackAlignment(
    TEXT("Prophecy.NNLowerFeedbackAlignment"), 1,
    TEXT("1: aligned lower physical deviation (default). 0: legacy absolute physical sample. Restart PIE between comparisons."));
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

void PrepareAlignedLowerFeedback(const AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex,
    AProphecyAgent& Actor, FAlignedLowerFeedback& Out)
{
    Out.bAligned = false;
#if !UE_BUILD_SHIPPING
    if (CVarLowerFeedbackAlignment.GetValueOnGameThread() == 0) return;
#endif
    auto* Character = Actor.GetJoltCharacterComponent();
    if (!Character || !Character->IsJoltPhysical()) return;
    const auto& Agent = Impl.Agents[AgentIndex];
    const float* Current = StateSlice(Impl.CurStateBuffer, AgentIndex);
    // While a new binding has no paired completed target, retain recurrence.
    // Never fall back to the mismatched absolute physical pose for one frame.
    Out.bAligned = true;
    FMemory::Memcpy(Out.State, Current, sizeof(Out.State));
    const auto* Mesh = Actor.GetAgentMesh();
    const auto* Capsule = Actor.GetAgentCapsule();
    if (!Mesh || !Capsule) return;
    const FTransform Root(FRotator(0, -FMath::RadiansToDegrees(Agent.CurRootYaw), 0),
        TrainingToUnreal(Agent.CurRootPos) + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight());
    const FTransform Reference = (Actor.bManualNNPoseApplication ? Mesh->GetRelativeTransform()
        : Actor.GetAuthoredMeshRelativeTransform()) * Root;
    const auto& Left = Agent.bUseWalkPolicy ? Impl.WalkLimbs[0] : Impl.Limbs[0];
    const auto& Right = Agent.bUseWalkPolicy ? Impl.WalkLimbs[1] : Impl.Limbs[1];
    const int32 Indices[] = { 0, Left.Start, Left.End, Left.Toe, Right.Start, Right.End, Right.Toe };
    FName Names[7];
    for (int32 I = 0; I < 7; ++I) Names[I] = Impl.BodyNames[Indices[I]];
    FTransform Actual[7], Authored[7];
    if (!Character->SampleCompletedLowerFeedbackPose(Names, Reference, Actual, Authored)) return;
    FTransform ActualPose[FullBodyBoneCount], AuthoredPose[FullBodyBoneCount];
    for (int32 I = 0; I < 7; ++I)
    {
        ActualPose[Indices[I]] = Actual[I];
        AuthoredPose[Indices[I]] = Authored[I];
    }
    float ActualState[StateDim], AuthoredState[StateDim];
    FSampledTrainingRotations ActualRotations(ActualPose), AuthoredRotations(AuthoredPose);
    EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, ActualPose, ActualRotations, ActualState);
    EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, AuthoredPose, AuthoredRotations, AuthoredState);
    ApplyLowerPhysicalDeviation(ActualState, AuthoredState, Current, Out.State);
}
