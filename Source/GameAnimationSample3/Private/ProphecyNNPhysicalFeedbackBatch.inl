// Included in the manager's anonymous namespace after the native math helpers.
// The serial reference preserves the previous operation order and GT profiling.
bool CommitPhysicalSampleSerial(AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex,
    TConstArrayView<FTransform> ActualTransforms)
{
    using FImpl = AProphecyNNLocomotionManager::FImpl;
	float* Sample = StateSlice(Impl.PhysicalStateBuffer, AgentIndex);
	FImpl::FAgent& Agent = Impl.Agents[AgentIndex];
	const double RawEncodeStart = ProphecyJolt::CharacterProfiling::Timestamp();
	// Cache only this successful sample; no pose, tolerance, or recurrent state survives here.
	FSampledTrainingRotations TrainingRotations(ActualTransforms);
	EncodePhysicalLowerSample(Impl, Agent, ActualTransforms, TrainingRotations, Sample);
	ProphecyJolt::CharacterProfiling::RecordElapsed(ProphecyJolt::CharacterProfiling::EPhase::PhysicalRawEncode, RawEncodeStart);

	float* Previous = StateSlice(Impl.PrevStateBuffer, AgentIndex);
	float* Current = StateSlice(Impl.CurStateBuffer, AgentIndex);
	float* PreviousPhysical = StateSlice(Impl.PreviousPhysicalStateBuffer, AgentIndex);

	auto ApplyLinearStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		const FVector3f Kinematic = ReadStateVec3(Current, Offset);
		const FVector3f Simulated = ReadStateVec3(Sample, Offset);
		const FVector3f Error = Simulated - Kinematic;
		const float ErrorSize = Error.Size();
		const float ToleranceMeters = FMath::Max(0.0f, Tolerance.LinearCm) / MetersToCentimeters;
		if (ErrorSize <= ToleranceMeters || ErrorSize <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(Sample + Offset, Current + Offset, 3 * sizeof(float));
			return;
		}
		WriteStateVec3(Sample, Offset,
			Kinematic + Error * ((ErrorSize - ToleranceMeters) / ErrorSize));
	};

	auto ApplyRotationStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		FQuat Kinematic = MatrixToQuat(MatrixFromRot6(Current + Offset)).GetNormalized();
		FQuat Simulated = MatrixToQuat(MatrixFromRot6(Sample + Offset)).GetNormalized();
		float Dot = Kinematic | Simulated;
		if (Dot < 0.0f)
		{
			Simulated = Simulated * -1.0f;
			Dot = -Dot;
		}
		const float ErrorRadians = 2.0f * FMath::Acos(FMath::Clamp(Dot, 0.0f, 1.0f));
		const float ToleranceRadians = FMath::DegreesToRadians(
			FMath::Max(0.0f, Tolerance.AngularDegrees));
		if (ErrorRadians <= ToleranceRadians || ErrorRadians <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(Sample + Offset, Current + Offset, 6 * sizeof(float));
			return;
		}
		WriteRot6(
			QuatToMatrix(FQuat::Slerp(
				Kinematic,
				Simulated,
				(ErrorRadians - ToleranceRadians) / ErrorRadians).GetNormalized()),
			Sample + Offset);
	};

	auto ApplyToeStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		const float Error = Sample[Offset] - Current[Offset];
		const float ErrorDegrees = FMath::Abs(Error) * FMath::RadiansToDegrees(ToeAlphaRadians);
		const float ToleranceDegrees = FMath::Max(0.0f, Tolerance.AngularDegrees);
		if (ErrorDegrees <= ToleranceDegrees || ErrorDegrees <= UE_SMALL_NUMBER)
		{
			Sample[Offset] = Current[Offset];
			return;
		}
		Sample[Offset] = Current[Offset] +
			Error * ((ErrorDegrees - ToleranceDegrees) / ErrorDegrees);
	};

	const FPhysicalFeedbackTolerance& PelvisTolerance =
		FeedbackToleranceForBone(Agent, TEXT("pelvis"));
	ApplyLinearStateTolerance(0, PelvisTolerance);
	ApplyRotationStateTolerance(3, PelvisTolerance);

	const FPhysicalFeedbackTolerance& LeftThighTolerance = FeedbackToleranceForBone(Agent, TEXT("thigh_l"));
	const FPhysicalFeedbackTolerance& LeftFootTolerance = FeedbackToleranceForBone(Agent, TEXT("foot_l"));
	const FPhysicalFeedbackTolerance& LeftToeTolerance = FeedbackToleranceForBone(Agent, TEXT("ball_l"));
	ApplyRotationStateTolerance(18, LeftThighTolerance);
	ApplyLinearStateTolerance(9, LeftFootTolerance);
	ApplyRotationStateTolerance(12, LeftFootTolerance);
	ApplyToeStateTolerance(24, LeftToeTolerance);

	const FPhysicalFeedbackTolerance& RightThighTolerance = FeedbackToleranceForBone(Agent, TEXT("thigh_r"));
	const FPhysicalFeedbackTolerance& RightFootTolerance = FeedbackToleranceForBone(Agent, TEXT("foot_r"));
	const FPhysicalFeedbackTolerance& RightToeTolerance = FeedbackToleranceForBone(Agent, TEXT("ball_r"));
	ApplyRotationStateTolerance(34, RightThighTolerance);
	ApplyLinearStateTolerance(25, RightFootTolerance);
	ApplyRotationStateTolerance(28, RightFootTolerance);
	ApplyToeStateTolerance(40, RightToeTolerance);

	float* UpperSample = UpperStateSlice(Impl.UpperPhysicalStateBuffer, AgentIndex);
	float* UpperCurrent = UpperStateSlice(Impl.UpperCurrentStateBuffer, AgentIndex);
	float* UpperPrevious = UpperStateSlice(Impl.UpperPreviousStateBuffer, AgentIndex);
	float* UpperPreviousPhysical = UpperStateSlice(
		Impl.UpperPreviousPhysicalStateBuffer, AgentIndex);
	{
		ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::PhysicalRawEncode);
		EncodePhysicalUpperSample(Impl, ActualTransforms, TrainingRotations, UpperSample);
	}

	auto ApplyUpperLinearTolerance = [&](int32 Offset, FName BoneName)
	{
		const FPhysicalFeedbackTolerance& Tolerance = FeedbackToleranceForBone(Agent, BoneName);
		const FVector3f Kinematic = ReadStateVec3(UpperCurrent, Offset);
		const FVector3f Simulated = ReadStateVec3(UpperSample, Offset);
		const FVector3f Error = Simulated - Kinematic;
		const float ErrorSize = Error.Size();
		const float ToleranceMeters = FMath::Max(0.0f, Tolerance.LinearCm) / MetersToCentimeters;
		if (ErrorSize <= ToleranceMeters || ErrorSize <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(UpperSample + Offset, UpperCurrent + Offset, 3 * sizeof(float));
		}
		else
		{
			WriteStateVec3(UpperSample, Offset,
				Kinematic + Error * ((ErrorSize - ToleranceMeters) / ErrorSize));
		}
	};
	auto ApplyUpperAngularTolerance = [&](int32 Offset, FName BoneName)
	{
		const FPhysicalFeedbackTolerance& Tolerance = FeedbackToleranceForBone(Agent, BoneName);
		FQuat Kinematic = MatrixToQuat(MatrixFromRot6(UpperCurrent + Offset)).GetNormalized();
		FQuat Simulated = MatrixToQuat(MatrixFromRot6(UpperSample + Offset)).GetNormalized();
		float Dot = Kinematic | Simulated;
		if (Dot < 0.0f)
		{
			Simulated = Simulated * -1.0f;
			Dot = -Dot;
		}
		const float ErrorRadians = 2.0f * FMath::Acos(FMath::Clamp(Dot, 0.0f, 1.0f));
		const float ToleranceRadians = FMath::DegreesToRadians(
			FMath::Max(0.0f, Tolerance.AngularDegrees));
		if (ErrorRadians <= ToleranceRadians || ErrorRadians <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(UpperSample + Offset, UpperCurrent + Offset, 6 * sizeof(float));
		}
		else
		{
			WriteRot6(
				QuatToMatrix(FQuat::Slerp(
					Kinematic, Simulated,
					(ErrorRadians - ToleranceRadians) / ErrorRadians).GetNormalized()),
				UpperSample + Offset);
		}
	};
	for (int32 CoreIndex = 0; CoreIndex < Impl.UpperCoreBoneNames.Num(); ++CoreIndex)
	{
		ApplyUpperAngularTolerance(CoreIndex * 6, Impl.UpperCoreBoneNames[CoreIndex]);
	}
	for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
	{
		const int32 Offset = 60 + ArmIndex * 15;
		const FImpl::FUpperArm& Arm = Impl.UpperArms[ArmIndex];
		ApplyUpperLinearTolerance(Offset, Impl.BodyNames[Arm.End]);
		ApplyUpperAngularTolerance(Offset + 3, Impl.BodyNames[Arm.End]);
		ApplyUpperAngularTolerance(Offset + 9, Impl.BodyNames[Arm.Start]);
	}
	CleanUpperState(UpperSample);

	bool bMatchesKinematicState = true;
	for (int32 StateIndex = 0; StateIndex < StateDim; ++StateIndex)
	{
		if (Sample[StateIndex] != Current[StateIndex])
		{
			bMatchesKinematicState = false;
			break;
		}
	}
	bool bMatchesKinematicUpper = true;
	for (int32 StateIndex = 0; StateIndex < UpperStateDim; ++StateIndex)
	{
		if (UpperSample[StateIndex] != UpperCurrent[StateIndex])
		{
			bMatchesKinematicUpper = false;
			break;
		}
	}
	if (bMatchesKinematicState && bMatchesKinematicUpper)
	{
		// An all-kinematic result must leave the exact recurrent pair untouched.
		// Rebuilding it from the displayed publication changes root-relative
		// velocities and produces feet moving over a stationary capsule.
		FMemory::Memcpy(PreviousPhysical, Current, StateDim * sizeof(float));
		FMemory::Memcpy(UpperPreviousPhysical, UpperCurrent, UpperStateDim * sizeof(float));
		Agent.bHasPhysicalSample = true;
		return true;
	}

	if (!bMatchesKinematicState)
	{
		CleanState(Sample, Impl);
		FMemory::Memcpy(Previous, Agent.bHasPhysicalSample ? PreviousPhysical : Sample, StateDim * sizeof(float));
		FMemory::Memcpy(Current, Sample, StateDim * sizeof(float));
		FMemory::Memcpy(PreviousPhysical, Sample, StateDim * sizeof(float));
		BuildUpperBaseFromLower(
			Current,
			Impl,
			UpperStateSlice(Impl.UpperCurrentBaseBuffer, AgentIndex));
		LowerTransformToHeading(
			Previous, 0, 3, Impl,
			TransformStateSlice(Impl.PreviousPelvisHeadingBuffer, AgentIndex));
		LowerTransformToHeading(
			Current, 0, 3, Impl,
			TransformStateSlice(Impl.CurrentPelvisHeadingBuffer, AgentIndex));
	}
	else
	{
		FMemory::Memcpy(PreviousPhysical, Current, StateDim * sizeof(float));
	}
	if (!bMatchesKinematicUpper)
	{
		FMemory::Memcpy(
			UpperPrevious,
			Agent.bHasPhysicalSample ? UpperPreviousPhysical : UpperSample,
			UpperStateDim * sizeof(float));
		FMemory::Memcpy(UpperCurrent, UpperSample, UpperStateDim * sizeof(float));
		FMemory::Memcpy(UpperPreviousPhysical, UpperSample, UpperStateDim * sizeof(float));
	}
	else
	{
		FMemory::Memcpy(UpperPreviousPhysical, UpperCurrent, UpperStateDim * sizeof(float));
	}
	Agent.bHasPhysicalSample = true;
	return true;
}

bool CommitPreparedPhysicalSample(const AProphecyNNLocomotionManager::FImpl& Impl,
    AProphecyNNLocomotionManager::FImpl::FPhysicalFeedbackWorkItem& Work)
{
    using FImpl = AProphecyNNLocomotionManager::FImpl;
    const TConstArrayView<FTransform> ActualTransforms = Work.ActualTransforms;
	float* Sample = Work.Sample;
	// Cache only this successful sample; no pose, tolerance, or recurrent state survives here.
	FSampledTrainingRotations TrainingRotations(ActualTransforms);
	EncodePhysicalLowerSample(Impl, Work.bUseWalkPolicy, ActualTransforms, TrainingRotations, Sample);

	float* Previous = Work.Previous;
	float* Current = Work.Current;
	float* PreviousPhysical = Work.PreviousPhysical;

	auto ApplyLinearStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		const FVector3f Kinematic = ReadStateVec3(Current, Offset);
		const FVector3f Simulated = ReadStateVec3(Sample, Offset);
		const FVector3f Error = Simulated - Kinematic;
		const float ErrorSize = Error.Size();
		const float ToleranceMeters = FMath::Max(0.0f, Tolerance.LinearCm) / MetersToCentimeters;
		if (ErrorSize <= ToleranceMeters || ErrorSize <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(Sample + Offset, Current + Offset, 3 * sizeof(float));
			return;
		}
		WriteStateVec3(Sample, Offset,
			Kinematic + Error * ((ErrorSize - ToleranceMeters) / ErrorSize));
	};

	auto ApplyRotationStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		FQuat Kinematic = MatrixToQuat(MatrixFromRot6(Current + Offset)).GetNormalized();
		FQuat Simulated = MatrixToQuat(MatrixFromRot6(Sample + Offset)).GetNormalized();
		float Dot = Kinematic | Simulated;
		if (Dot < 0.0f)
		{
			Simulated = Simulated * -1.0f;
			Dot = -Dot;
		}
		const float ErrorRadians = 2.0f * FMath::Acos(FMath::Clamp(Dot, 0.0f, 1.0f));
		const float ToleranceRadians = FMath::DegreesToRadians(
			FMath::Max(0.0f, Tolerance.AngularDegrees));
		if (ErrorRadians <= ToleranceRadians || ErrorRadians <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(Sample + Offset, Current + Offset, 6 * sizeof(float));
			return;
		}
		WriteRot6(
			QuatToMatrix(FQuat::Slerp(
				Kinematic,
				Simulated,
				(ErrorRadians - ToleranceRadians) / ErrorRadians).GetNormalized()),
			Sample + Offset);
	};

	auto ApplyToeStateTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		const float Error = Sample[Offset] - Current[Offset];
		const float ErrorDegrees = FMath::Abs(Error) * FMath::RadiansToDegrees(ToeAlphaRadians);
		const float ToleranceDegrees = FMath::Max(0.0f, Tolerance.AngularDegrees);
		if (ErrorDegrees <= ToleranceDegrees || ErrorDegrees <= UE_SMALL_NUMBER)
		{
			Sample[Offset] = Current[Offset];
			return;
		}
		Sample[Offset] = Current[Offset] +
			Error * ((ErrorDegrees - ToleranceDegrees) / ErrorDegrees);
	};

	const FPhysicalFeedbackTolerance& PelvisTolerance =
		Work.LowerTolerances[0];
	ApplyLinearStateTolerance(0, PelvisTolerance);
	ApplyRotationStateTolerance(3, PelvisTolerance);

	const FPhysicalFeedbackTolerance& LeftThighTolerance = Work.LowerTolerances[1];
	const FPhysicalFeedbackTolerance& LeftFootTolerance = Work.LowerTolerances[2];
	const FPhysicalFeedbackTolerance& LeftToeTolerance = Work.LowerTolerances[3];
	ApplyRotationStateTolerance(18, LeftThighTolerance);
	ApplyLinearStateTolerance(9, LeftFootTolerance);
	ApplyRotationStateTolerance(12, LeftFootTolerance);
	ApplyToeStateTolerance(24, LeftToeTolerance);

	const FPhysicalFeedbackTolerance& RightThighTolerance = Work.LowerTolerances[4];
	const FPhysicalFeedbackTolerance& RightFootTolerance = Work.LowerTolerances[5];
	const FPhysicalFeedbackTolerance& RightToeTolerance = Work.LowerTolerances[6];
	ApplyRotationStateTolerance(34, RightThighTolerance);
	ApplyLinearStateTolerance(25, RightFootTolerance);
	ApplyRotationStateTolerance(28, RightFootTolerance);
	ApplyToeStateTolerance(40, RightToeTolerance);

	float* UpperSample = Work.UpperSample;
	float* UpperCurrent = Work.UpperCurrent;
	float* UpperPrevious = Work.UpperPrevious;
	float* UpperPreviousPhysical = Work.UpperPreviousPhysical;
	{
		EncodePhysicalUpperSample(Impl, ActualTransforms, TrainingRotations, UpperSample);
	}

	auto ApplyUpperLinearTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		const FVector3f Kinematic = ReadStateVec3(UpperCurrent, Offset);
		const FVector3f Simulated = ReadStateVec3(UpperSample, Offset);
		const FVector3f Error = Simulated - Kinematic;
		const float ErrorSize = Error.Size();
		const float ToleranceMeters = FMath::Max(0.0f, Tolerance.LinearCm) / MetersToCentimeters;
		if (ErrorSize <= ToleranceMeters || ErrorSize <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(UpperSample + Offset, UpperCurrent + Offset, 3 * sizeof(float));
		}
		else
		{
			WriteStateVec3(UpperSample, Offset,
				Kinematic + Error * ((ErrorSize - ToleranceMeters) / ErrorSize));
		}
	};
	auto ApplyUpperAngularTolerance = [&](int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)
	{
		FQuat Kinematic = MatrixToQuat(MatrixFromRot6(UpperCurrent + Offset)).GetNormalized();
		FQuat Simulated = MatrixToQuat(MatrixFromRot6(UpperSample + Offset)).GetNormalized();
		float Dot = Kinematic | Simulated;
		if (Dot < 0.0f)
		{
			Simulated = Simulated * -1.0f;
			Dot = -Dot;
		}
		const float ErrorRadians = 2.0f * FMath::Acos(FMath::Clamp(Dot, 0.0f, 1.0f));
		const float ToleranceRadians = FMath::DegreesToRadians(
			FMath::Max(0.0f, Tolerance.AngularDegrees));
		if (ErrorRadians <= ToleranceRadians || ErrorRadians <= UE_SMALL_NUMBER)
		{
			FMemory::Memcpy(UpperSample + Offset, UpperCurrent + Offset, 6 * sizeof(float));
		}
		else
		{
			WriteRot6(
				QuatToMatrix(FQuat::Slerp(
					Kinematic, Simulated,
					(ErrorRadians - ToleranceRadians) / ErrorRadians).GetNormalized()),
				UpperSample + Offset);
		}
	};
	for (int32 CoreIndex = 0; CoreIndex < Impl.UpperCoreBoneNames.Num(); ++CoreIndex)
	{
		ApplyUpperAngularTolerance(CoreIndex * 6, Work.UpperCoreTolerances[CoreIndex]);
	}
	for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
	{
		const int32 Offset = 60 + ArmIndex * 15;
		ApplyUpperLinearTolerance(Offset, Work.UpperEndTolerances[ArmIndex]);
		ApplyUpperAngularTolerance(Offset + 3, Work.UpperEndTolerances[ArmIndex]);
		ApplyUpperAngularTolerance(Offset + 9, Work.UpperStartTolerances[ArmIndex]);
	}
	CleanUpperState(UpperSample);

	bool bMatchesKinematicState = true;
	for (int32 StateIndex = 0; StateIndex < StateDim; ++StateIndex)
	{
		if (Sample[StateIndex] != Current[StateIndex])
		{
			bMatchesKinematicState = false;
			break;
		}
	}
	bool bMatchesKinematicUpper = true;
	for (int32 StateIndex = 0; StateIndex < UpperStateDim; ++StateIndex)
	{
		if (UpperSample[StateIndex] != UpperCurrent[StateIndex])
		{
			bMatchesKinematicUpper = false;
			break;
		}
	}
	if (bMatchesKinematicState && bMatchesKinematicUpper)
	{
		// An all-kinematic result must leave the exact recurrent pair untouched.
		// Rebuilding it from the displayed publication changes root-relative
		// velocities and produces feet moving over a stationary capsule.
		FMemory::Memcpy(PreviousPhysical, Current, StateDim * sizeof(float));
		FMemory::Memcpy(UpperPreviousPhysical, UpperCurrent, UpperStateDim * sizeof(float));
		Work.bHasPhysicalSample = true;
		return true;
	}

	if (!bMatchesKinematicState)
	{
		CleanState(Sample, Impl);
		FMemory::Memcpy(Previous, Work.bHasPhysicalSample ? PreviousPhysical : Sample, StateDim * sizeof(float));
		FMemory::Memcpy(Current, Sample, StateDim * sizeof(float));
		FMemory::Memcpy(PreviousPhysical, Sample, StateDim * sizeof(float));
		BuildUpperBaseFromLower(
			Current,
			Impl,
			Work.UpperCurrentBase);
		LowerTransformToHeading(
			Previous, 0, 3, Impl,
			Work.PreviousPelvisHeading);
		LowerTransformToHeading(
			Current, 0, 3, Impl,
			Work.CurrentPelvisHeading);
	}
	else
	{
		FMemory::Memcpy(PreviousPhysical, Current, StateDim * sizeof(float));
	}
	if (!bMatchesKinematicUpper)
	{
		FMemory::Memcpy(
			UpperPrevious,
			Work.bHasPhysicalSample ? UpperPreviousPhysical : UpperSample,
			UpperStateDim * sizeof(float));
		FMemory::Memcpy(UpperCurrent, UpperSample, UpperStateDim * sizeof(float));
		FMemory::Memcpy(UpperPreviousPhysical, UpperSample, UpperStateDim * sizeof(float));
	}
	else
	{
		FMemory::Memcpy(UpperPreviousPhysical, UpperCurrent, UpperStateDim * sizeof(float));
	}
	Work.bHasPhysicalSample = true;
	return true;
}

bool PreparePhysicalFeedbackWork(AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex)
{
    check(IsInGameThread());
    if (!Impl.Agents.IsValidIndex(AgentIndex) || !Impl.PhysicalFeedbackWorkItems.IsValidIndex(AgentIndex)
        || Impl.UpperCoreBoneNames.Num() != 10) return false;
    auto& Work = Impl.PhysicalFeedbackWorkItems[AgentIndex];
    const auto& Agent = Impl.Agents[AgentIndex];
    Work = {};
    Work.ActualTransforms = TransformSlice(Impl.PhysicalTransformBuffer, AgentIndex);
    Work.Sample = StateSlice(Impl.PhysicalStateBuffer, AgentIndex);
    Work.Previous = StateSlice(Impl.PrevStateBuffer, AgentIndex);
    Work.Current = StateSlice(Impl.CurStateBuffer, AgentIndex);
    Work.PreviousPhysical = StateSlice(Impl.PreviousPhysicalStateBuffer, AgentIndex);
    Work.UpperSample = UpperStateSlice(Impl.UpperPhysicalStateBuffer, AgentIndex);
    Work.UpperCurrent = UpperStateSlice(Impl.UpperCurrentStateBuffer, AgentIndex);
    Work.UpperPrevious = UpperStateSlice(Impl.UpperPreviousStateBuffer, AgentIndex);
    Work.UpperPreviousPhysical = UpperStateSlice(Impl.UpperPreviousPhysicalStateBuffer, AgentIndex);
    Work.UpperCurrentBase = UpperStateSlice(Impl.UpperCurrentBaseBuffer, AgentIndex);
    Work.PreviousPelvisHeading = TransformStateSlice(Impl.PreviousPelvisHeadingBuffer, AgentIndex);
    Work.CurrentPelvisHeading = TransformStateSlice(Impl.CurrentPelvisHeadingBuffer, AgentIndex);
    const FName LowerNames[] = { TEXT("pelvis"), TEXT("thigh_l"), TEXT("foot_l"), TEXT("ball_l"),
        TEXT("thigh_r"), TEXT("foot_r"), TEXT("ball_r") };
    for (int32 Index = 0; Index < 7; ++Index)
        Work.LowerTolerances[Index] = FeedbackToleranceForBone(Agent, LowerNames[Index]);
    for (int32 Index = 0; Index < 10; ++Index)
        Work.UpperCoreTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.UpperCoreBoneNames[Index]);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        Work.UpperEndTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.BodyNames[Impl.UpperArms[Index].End]);
        Work.UpperStartTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.BodyNames[Impl.UpperArms[Index].Start]);
    }
    Work.bUseWalkPolicy = Agent.bUseWalkPolicy;
    Work.bHasPhysicalSample = Agent.bHasPhysicalSample;
    return true;
}

void ExecutePhysicalFeedbackBatch(const AProphecyNNLocomotionManager::FImpl& ReadOnlyLayout,
    TArrayView<AProphecyNNLocomotionManager::FImpl::FPhysicalFeedbackWorkItem> WorkItems,
    TConstArrayView<int32> Indices, bool bForceSerial)
{
    check(IsInGameThread());
    ParallelFor(TEXT("ProphecyNN.PhysicalFeedback"), Indices.Num(), 4,
        [&ReadOnlyLayout, WorkItems, Indices](int32 ItemIndex)
        {
            auto& Work = WorkItems[Indices[ItemIndex]];
            Work.bSucceeded = CommitPreparedPhysicalSample(ReadOnlyLayout, Work);
        }, bForceSerial ? EParallelForFlags::ForceSingleThread : EParallelForFlags::None);
}
