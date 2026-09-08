// Included by the manager translation unit: one optional shared model, data-only per-agent history.
namespace
{
	FTransform SlashComponentWorld(const AProphecyAgent* Actor, const FVector3f& Root, float Yaw)
	{
		if (!Actor || !Actor->GetAgentCapsule() || !Actor->GetAgentMesh()) return FTransform::Identity;
		const FTransform CapsuleWorld(FRotator(0, -FMath::RadiansToDegrees(Yaw), 0),
			TrainingToUnreal(Root) + FVector::UpVector * Actor->GetAgentCapsule()->GetScaledCapsuleHalfHeight());
		const FTransform Relative = Actor->bManualNNPoseApplication
			? Actor->GetAgentMesh()->GetRelativeTransform() : Actor->GetAuthoredMeshRelativeTransform();
		return Relative * CapsuleWorld;
	}

	void EncodeSlashPose(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		TArrayView<const FTransform> Pose, float* Lower, float* Upper)
	{
		EncodeComponentPoseToNNStates(Impl, Agent, Pose, Lower, Upper);
		// Locomotion's hands are heading-relative. Slash native hands are root-relative.
		const FMat3f HeadingToRoot = Transpose(Impl.SeedRootRot);
		for (int32 Offset : {60, 75})
		{
			WriteStateVec3(Upper, Offset, TransformRow(ReadStateVec3(Upper, Offset), HeadingToRoot));
			WriteRot6(Multiply(MatrixFromRot6(Upper + Offset + 3), HeadingToRoot), Upper + Offset + 3);
			WriteRot6(Multiply(MatrixFromRot6(Upper + Offset + 9), HeadingToRoot), Upper + Offset + 9);
		}
	}

	void ResolveSlashTarget(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyAgent* Actor, int32 Index, FVector& EffectiveWorld, FVector& GhostWorld)
	{
		const auto& Agent = Impl.Agents[Index];
		const auto& Slash = Agent.Slash;
		EffectiveWorld = GhostWorld = Slash.TargetWorld;
		if (!Slash.bHalf || Slash.GhostPose.IsEmpty()) return;
		// Read the current lower publication directly; the optional debug mesh and
		// previous rendered frame must not become an authority for policy inputs.
		const float* Lower = StateSlice(Impl.PublishedStateBuffer, Index);
		const FTransform RealPelvis = FTransform(MatrixToQuat(MirrorYBasis(MatrixFromRot6(Lower + 3))),
			LocalTrainingToUnreal(ReadStateVec3(Lower, 0))) *
			SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
		const FVector Offset = Slash.TargetWorld - RealPelvis.GetLocation();
		const float Radius = AProphecyNNLocomotionManager::GetHalfAttackTargetRadius(Actor->GetWorld());
		EffectiveWorld = RealPelvis.GetLocation() + Offset.GetClampedToMaxSize(Radius);
		const FTransform GhostPelvis = Slash.GhostPose[0] * Slash.AnchorWorld;
		// Inverse of the existing ghost-upper -> real-pelvis presentation mapping.
		// Only the target changes. Lower ghost state, integration and latches do not.
		GhostWorld = GhostPelvis.TransformPosition(RealPelvis.InverseTransformPosition(EffectiveWorld));
	}

	void CatchUpFullAttackRoot(AProphecyNNLocomotionManager* Manager, AProphecyNNLocomotionManager::FImpl& Impl,
		AProphecyAgent* Actor, int32 Index)
	{
		auto& Agent = Impl.Agents[Index];
		const auto& Slash = Agent.Slash;
		FVector RootOffset;
		if (!SlashRootMinusStartPelvis.RemoveAndCopyValue(Actor, RootOffset) ||
			Slash.bHalf || !Slash.bHasPose || Slash.VisibleWorldPose.IsEmpty()) return;

		const FVector OldLowPoint = Actor->GetRootLowPoint();
		const FName DebugName(*FString::Printf(TEXT("KinematicDebugMesh_%d"), Index));
		UPoseableMeshComponent* DebugMesh = FindObjectFast<UPoseableMeshComponent>(Manager, DebugName);
		const FTransform OldDebugWorld = IsValid(DebugMesh)
			? DebugMesh->GetComponentTransform() : FTransform::Identity;
		USkeletalMeshComponent* KinematicMesh = Actor->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic
			? Actor->GetPoseReferenceMesh() : nullptr;
		if (KinematicMesh) KinematicMesh->HandleExistingParallelEvaluationTask(true, true);
		FVector DesiredLowPoint = Slash.VisibleWorldPose[0].GetTranslation() + RootOffset;
		DesiredLowPoint.Z = OldLowPoint.Z; // Attack bob/lean never lifts the capsule.
		const FVector ToTarget = (Slash.TargetWorld - Slash.VisibleWorldPose[0].GetTranslation()).GetSafeNormal2D();
		// The locomotion convention is +Y forward at zero yaw, not actor +X.
		// A coincident horizontal target has no heading: retain the current one.
		const float DesiredYaw = ToTarget.IsNearlyZero() ? Agent.CurRootYaw
			: float(FMath::Atan2(ToTarget.X, ToTarget.Y));
		const float YawDelta = WrapAngle(DesiredYaw - Agent.CurRootYaw);
		const FTransform OldCarrier = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
		const FTransform OldPreviousCarrier = SlashComponentWorld(Actor, Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
		FVector AppliedLowPoint, BlockingNormal;
		bool bWorldBlocked = false;
		Actor->SetManagedRootLowPoint(DesiredLowPoint, -FMath::RadiansToDegrees(DesiredYaw),
			AppliedLowPoint, BlockingNormal, bWorldBlocked);
		const FVector WorldDelta = AppliedLowPoint - OldLowPoint;
		if (IsValid(DebugMesh) && !DebugMesh->BoneSpaceTransforms.IsEmpty())
		{
			// The orange debug renderer has its own cached pose and no animation
			// tick. Preserve that pose across parent motion too, even when the BP
			// handoff happens AFTER the manager's debug update for this frame.
			DebugMesh->BoneSpaceTransforms[0] =
				(DebugMesh->BoneSpaceTransforms[0] * OldDebugWorld)
				.GetRelativeTransform(DebugMesh->GetComponentTransform());
			DebugMesh->RefreshBoneTransforms();
		}
		const FVector3f RootDelta = UnrealToTraining(WorldDelta);
		Agent.bPhysicalWorldBlockedPending |= bWorldBlocked;

		// This is a change of carrier coordinates, not movement of the skeleton.
		// Rebase BOTH recurrent frames and publication endpoints, preserving root
		// velocity/deltas rather than injecting the catch-up as linear/angular velocity.
		auto RebasePair = [&](TArray<float>& Lower, TArray<float>& Upper, float Yaw)
		{
			const FVector3f LocalDelta = TransformRow(RootDelta, YawMatrix(Yaw));
			RebaseStateRoot(StateSlice(Lower, Index), Impl, LocalDelta, YawDelta);
			RebaseUpperHeadingState(UpperStateSlice(Upper, Index),
				TransformRow(LocalDelta, Impl.SeedRootRot), YawDelta);
		};
		RebasePair(Impl.PrevStateBuffer, Impl.UpperPreviousStateBuffer, Agent.PrevRootYaw);
		RebasePair(Impl.CurStateBuffer, Impl.UpperCurrentStateBuffer, Agent.CurRootYaw);
		RebasePair(Impl.PreviousPublishedStateBuffer, Impl.UpperPreviousPublishedStateBuffer, Agent.PreviousPublishedYaw);
		RebasePair(Impl.PublishedStateBuffer, Impl.UpperPublishedStateBuffer, Agent.PublishedYaw);
		if (Agent.bHasPhysicalSample)
		{
			RebasePair(Impl.PreviousPhysicalStateBuffer, Impl.UpperPreviousPhysicalStateBuffer, Agent.CurRootYaw);
		}
		Agent.PrevRootPos += RootDelta;
		Agent.CurRootPos += RootDelta;
		Agent.PreviousPublishedRoot += RootDelta;
		Agent.PublishedRoot += RootDelta;
		Agent.PrevRootYaw = WrapAngle(Agent.PrevRootYaw + YawDelta);
		Agent.CurRootYaw = DesiredYaw;
		Agent.PreviousPublishedYaw = WrapAngle(Agent.PreviousPublishedYaw + YawDelta);
		Agent.PublishedYaw = WrapAngle(Agent.PublishedYaw + YawDelta);
		Agent.MoverState.position.x += RootDelta.X;
		Agent.MoverState.position.z += RootDelta.Z;
		Agent.MoverState.previous_yaw_radians += YawDelta;
		Agent.MoverState.yaw_radians = DesiredYaw;
		Agent.MoverIntent.orientation_yaw_radians = DesiredYaw;
		BuildUpperBaseFromLower(StateSlice(Impl.CurStateBuffer, Index), Impl,
			UpperStateSlice(Impl.UpperCurrentBaseBuffer, Index));
		LowerTransformToHeading(StateSlice(Impl.PrevStateBuffer, Index), 0, 3, Impl,
			TransformStateSlice(Impl.PreviousPelvisHeadingBuffer, Index));
		LowerTransformToHeading(StateSlice(Impl.CurStateBuffer, Index), 0, 3, Impl,
			TransformStateSlice(Impl.CurrentPelvisHeadingBuffer, Index));

		// Republish the exact cached bones in the new frame; no extra NN/FK pass,
		// animation step, presentation clamp, or change to the attack's world target.
		const FTransform Carrier = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
		const FTransform PreviousCarrier = SlashComponentWorld(Actor, Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
		auto Pose = TransformSlice(Impl.ComponentTransformBuffer, Index);
		auto PreviousPose = TransformSlice(Impl.PreviousComponentTransformBuffer, Index);
		auto LocalPose = TransformSlice(Impl.LocalTransformBuffer, Index);
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			Pose[Bone] = (Pose[Bone] * OldCarrier).GetRelativeTransform(Carrier);
			PreviousPose[Bone] = (PreviousPose[Bone] * OldPreviousCarrier).GetRelativeTransform(PreviousCarrier);
			if (Impl.Parents[Bone] == INDEX_NONE) LocalPose[Bone] = Pose[Bone];
		}
		FProphecyNNPoseStore::SetAgentLocalPose(PoseStoreAgentBase + Index, Impl.PublishedBoneNames,
			LocalPose, PreviousPose, Pose, PreviousCarrier, Carrier, Agent.PublishedPoseTimeSeconds, true);
		if (KinematicMesh)
		{
			// Moving the capsule also moves the already-evaluated component-space
			// bones. Consume the rebased publication synchronously in this same call;
			// waiting for the next mesh tick exposes a one-frame whole-body jump.
			const bool bSavedURO = KinematicMesh->bEnableUpdateRateOptimizations;
			KinematicMesh->bEnableUpdateRateOptimizations = false;
			Actor->ApplyNNPoseKinematically(0.0f);
			KinematicMesh->bEnableUpdateRateOptimizations = bSavedURO;
		}
	}
}

bool AProphecyNNLocomotionManager::InitializeSlashNNE()
{
	if (Impl->bSlashInitialized) return true;
	const FString Directory = FPaths::ProjectContentDir() / TEXT("locomotion/NN");
	FString Text;
	TSharedPtr<FJsonObject> Contract;
	if (!FFileHelper::LoadFileToString(Text, *(Directory / TEXT("prophecy_slash_runtime.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Contract) || !Contract.IsValid()) return false;
	if (Contract->GetStringField(TEXT("checkpoint_sha256")) != TEXT("6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072") ||
		Contract->GetIntegerField(TEXT("input_dim")) != SlashInputDim ||
		Contract->GetIntegerField(TEXT("output_dim")) != SlashOutputDim) return false;
	const int32 ModelBatch = 1;
	Impl->SlashBodyIndices.Reset();
	for (const auto& Name : Contract->GetArrayField(TEXT("bone_names")))
	{
		const int32 Index = Impl->BodyNames.IndexOfByKey(FName(Name->AsString()));
		if (Index == INDEX_NONE || Impl->SlashBodyIndices.Contains(Index)) return false;
		Impl->SlashBodyIndices.Add(Index);
	}
	if (Impl->SlashBodyIndices.Num() != FullBodyBoneCount) return false;
	if (!JsonVec3(Contract->GetArrayField(TEXT("root_position_m")), Impl->SlashRootPosition)) return false;
	const auto& Rows = Contract->GetArrayField(TEXT("root_rotation"));
	if (Rows.Num() != 3) return false;
	for (int32 Row = 0; Row < 3; ++Row)
		if (!JsonVec3(Rows[Row]->AsArray(), Impl->SlashRootRotation.Rows[Row])) return false;
	JsonFloatArray(Contract->GetArrayField(TEXT("seed_input")), Impl->SlashSeedInput);
	if (Impl->SlashSeedInput.Num() != SlashInputDim) return false;
	Impl->SlashLabels.Reset();
	Impl->SlashTailSteps.Reset();
	for (const auto& Pair : Contract->GetObjectField(TEXT("attack_labels"))->Values)
	{
		TArray<float> Label;
		JsonFloatArray(Pair.Value->AsArray(), Label);
		if (Label.Num() != 5) return false;
		Impl->SlashLabels.Add(FName(Pair.Key), MoveTemp(Label));
		Impl->SlashTailSteps.Add(FName(Pair.Key), Contract->GetObjectField(TEXT("post_hit_tail_steps"))->GetIntegerField(Pair.Key));
	}
	Impl->SlashModel = MakeUnique<FSlashNative>();
	if (!Impl->SlashModel->Initialize(Directory, Contract)) return false;
	Impl->SlashInputBuffer.SetNumUninitialized(ModelBatch * SlashInputDim);
	Impl->SlashOutputBuffer.SetNumZeroed(ModelBatch * SlashOutputDim);
	for (int32 Lane = 0; Lane < ModelBatch; ++Lane)
		FMemory::Memcpy(Impl->SlashInputBuffer.GetData() + Lane * SlashInputDim, Impl->SlashSeedInput.GetData(), SlashInputDim * sizeof(float));
	if (!Impl->SlashModel->Run(Impl->SlashInputBuffer, Impl->SlashOutputBuffer)) return false;
	const TArray<float>& Expected = Impl->SlashModel->StartupExpected;
	if (Expected.Num() != SlashOutputDim) return false;
	float Error = 0;
	for (int32 Index = 0; Index < SlashOutputDim; ++Index)
	{
		const float Value = Impl->SlashOutputBuffer[Index];
		if (!FMath::IsFinite(Value)) return false;
		Error = FMath::Max(Error, FMath::Abs(Value - Expected[Index]));
	}
	UE_LOG(LogProphecyNNLocomotion, Display, TEXT("Slash2 startup NNE parity max_abs=%.9g, lanes=%d"), Error, ModelBatch);
	if (Error > 0.001f)
	{
		auto Diagnostic=MakeShared<FJsonObject>(); TArray<TSharedPtr<FJsonValue>> Actual;
		for (float V:Impl->SlashOutputBuffer) Actual.Add(MakeShared<FJsonValueNumber>(V));
		Diagnostic->SetArrayField(TEXT("actual"),Actual);
		for (int32 I=0; I<3; ++I)
		{
			TArray<TSharedPtr<FJsonValue>> Values;
			for (float V:Impl->SlashModel->NetworkInputs[I]) Values.Add(MakeShared<FJsonValueNumber>(V));
			Diagnostic->SetArrayField(FString::Printf(TEXT("network_input_%d"),I),Values);
		}
		FJsonSerializer::Serialize(Diagnostic,TJsonWriterFactory<>::Create(&Text));
		FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("SlashParity/native_startup_error.json")));
		return false;
	}
	Impl->bSlashInitialized = true;
	return true;
}

bool AProphecyNNLocomotionManager::TriggerAgentNNAttack(FProphecyAgentHandle Handle, FName Attack, FVector TargetWorld, bool bHalf)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor || !Actor->bNNInferenceEnabled || TargetWorld.ContainsNaN() || !InitializeSlashNNE()) return false;
	const TArray<float>* Labels = Impl->SlashLabels.Find(Attack);
	if (!Labels || (bHalf && (Attack == TEXT("kickl") || Attack == TEXT("kickr")))) return false;
	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	const FTransform Carrier = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
	const auto Current = TransformSlice(Impl->ComponentTransformBuffer, Handle.Index);
	const FVector Pelvis = Carrier.TransformPosition(Current[0].GetTranslation());
	if (FVector::DistSquared2D(Pelvis, TargetWorld) < 0.0001) return false;
	// Validate the replacement first; an invalid request must not end the old attack.
	const bool bContinueFullHistory = Agent.Slash.bActive && Agent.Slash.bHasPose &&
		!Agent.Slash.bHalf && !bHalf;
	if (Agent.Slash.bActive) StopAgentNNAttack(Handle);
	const FTransform StartCarrier = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
	auto& Slash = Agent.Slash;
	if (bContinueFullHistory)
	{
		// Match the continuous rollout: retain both raw recurrent frames and their
		// fixed world anchor. The presentation-only hand fix must not feed back.
		Slash.Family = Attack;
		Slash.TargetWorld = TargetWorld;
		Slash.TailSteps = Impl->SlashTailSteps[Attack];
		Slash.Frame = 1;
		Slash.HitFrame = INDEX_NONE;
		FMemory::Memcpy(Slash.State.GetData() + 265, Labels->GetData(), 5 * sizeof(float));
		Slash.State[270] = Slash.State[271] = 0;
		Slash.bActive = true;
		Actor->BeginAttackFists(Attack);
		SlashRootMinusStartPelvis.Add(Actor,
			Actor->GetRootLowPoint() - Slash.VisibleWorldPose[0].GetTranslation());
		return true;
	}
	Slash = FImpl::FAgent::FSlashAttack{};
	Slash.Family = Attack; Slash.TargetWorld = TargetWorld; Slash.bHalf = bHalf;
	Slash.AnchorWorld = StartCarrier; Slash.TailSteps = Impl->SlashTailSteps[Attack];
	Slash.State = Impl->SlashSeedInput;
	TArray<FTransform> Previous;
	Previous.Append(TransformSlice(Impl->PreviousComponentTransformBuffer, Handle.Index));
	const FTransform PreviousWorld = SlashComponentWorld(Actor, Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
	for (FTransform& Bone : Previous) Bone = (Bone * PreviousWorld).GetRelativeTransform(StartCarrier);
	EncodeSlashPose(*Impl, Agent, Previous, Slash.State.GetData(), Slash.State.GetData() + 82);
	EncodeSlashPose(*Impl, Agent, Current, Slash.State.GetData() + 41, Slash.State.GetData() + 172);
	FMemory::Memcpy(Slash.State.GetData() + 265, Labels->GetData(), 5 * sizeof(float));
	Slash.State[270] = Slash.State[271] = 0;
	Slash.GhostPose.Append(Current);
	for (const auto& Bone : Current) Slash.VisibleWorldPose.Add(Bone * StartCarrier);
	Slash.PreviousVisibleWorldPose = Slash.VisibleWorldPose;
	if (!bHalf) SlashRootMinusStartPelvis.Add(Actor,
		Actor->GetRootLowPoint() - Slash.VisibleWorldPose[0].GetTranslation());
	Slash.bActive = true;
	Actor->BeginAttackFists(Attack);
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentNNHalfAttack(FProphecyAgentHandle Handle, bool bHalf)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor) return false;
	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	auto& Slash = Agent.Slash;
	if (!Slash.bActive || (bHalf && (Slash.Family == TEXT("kickl") || Slash.Family == TEXT("kickr")))) return false;
	if (Slash.bHalf && !bHalf)
	{
		// Rejoin at the current locomotion carrier without teleporting the visible
		// body back to the attack's origin. Native ghost history/latches stay intact.
		Slash.AnchorWorld = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
		SlashRootMinusStartPelvis.Add(Actor, Actor->GetRootLowPoint() -
			(Slash.GhostPose[0] * Slash.AnchorWorld).GetTranslation());
	}
	if (bHalf) SlashRootMinusStartPelvis.Remove(Actor);
	Slash.bHalf = bHalf;
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentNNAttackTarget(FProphecyAgentHandle Handle, FVector TargetWorld)
{
	if (!ResolveAgent(Handle) || TargetWorld.ContainsNaN()) return false;
	auto& Slash = Impl->Agents[Handle.Index].Slash;
	if (!Slash.bActive) return false;
	Slash.TargetWorld = TargetWorld;
	return true;
}

bool AProphecyNNLocomotionManager::StopAgentNNAttack(FProphecyAgentHandle Handle)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor) return false;
	auto& Slash = Impl->Agents[Handle.Index].Slash;
	if (!Slash.bActive) return false;
	CatchUpFullAttackRoot(this, *Impl, Actor, Handle.Index);
	Slash.bActive = false;
	Actor->EndAttackFists();
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentNNAttackState(FProphecyAgentHandle Handle, FName& Attack, bool& bHalf, bool& bArmed, bool& bHit, int32& Frame) const
{
	if (!ResolveAgent(Handle)) return false;
	const auto& Slash = Impl->Agents[Handle.Index].Slash;
	Attack = Slash.Family; bHalf = Slash.bHalf; Frame = Slash.Frame;
	bArmed = Slash.State.Num() == SlashInputDim && Slash.State[270] > 0.5f;
	bHit = Slash.State.Num() == SlashInputDim && Slash.State[271] > 0.5f;
	return Slash.bActive;
}

bool AProphecyNNLocomotionManager::GetAgentNNAttackTarget(FProphecyAgentHandle Handle,
	FVector& Requested, FVector& Effective, FVector& Ghost) const
{
	Requested = Effective = Ghost = FVector::ZeroVector;
	const AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor || !Impl->Agents[Handle.Index].Slash.bActive) return false;
	Requested = Impl->Agents[Handle.Index].Slash.TargetWorld;
	ResolveSlashTarget(*Impl, Actor, Handle.Index, Effective, Ghost);
	return true;
}

void AProphecyNNLocomotionManager::AdvanceSlashAttacks()
{
	if (!Impl->bSlashInitialized) return;
	TArray<int32, TInlineAllocator<BatchSize>> Active;
	for (int32 Index = 0; Index < CrowdSize; ++Index)
	{
		auto& Agent = Impl->Agents[Index];
		auto& Slash = Agent.Slash;
		if (!Slash.bActive || !AgentActors[Index]->bNNInferenceEnabled) continue;
		// The ghost performs the attack in its own fixed root frame. Moving the
		// real locomotion capsule must not feed running translation into that NN.
		FVector EffectiveTarget, GhostTarget;
		ResolveSlashTarget(*Impl, AgentActors[Index], Index, EffectiveTarget, GhostTarget);
		FVector3f TargetLocal = LocalUnrealToTraining(Slash.AnchorWorld.InverseTransformPosition(GhostTarget));
		const FVector3f Target = TransformRow(TargetLocal, Impl->SlashRootRotation) + Impl->SlashRootPosition;
		const FVector3f Pelvis = TransformRow(ReadStateVec3(Slash.State.GetData() + 41, 0), Impl->SlashRootRotation) + Impl->SlashRootPosition;
		if (FMath::Square(Target.X - Pelvis.X) + FMath::Square(Target.Z - Pelvis.Z) < 1.0e-10f)
		{
			UE_LOG(LogProphecyNNLocomotion, Warning, TEXT("Slash2 stopped: pelvis and target have coincident horizontal positions."));
			Slash.bActive = false;
			AgentActors[Index]->EndAttackFists();
			continue;
		}
		WriteStateVec3(Slash.State.GetData(), 262, Target);
		Active.Add(Index);
	}
	if (Active.IsEmpty()) return;
	// A single call per neural stage, packed with active attackers only. Dynamic
	// CPU batch shapes change only when the active count changes (not per frame).
	const int32 Width = FMath::Min(BatchSize,Active.Num());
	if (Impl->SlashModel->InputBatchSize!=Width)
	{
		if (!Impl->SlashModel->SetBatch(Width))
		{
			for (int32 Index:Active)
			{
				Impl->Agents[Index].Slash.bActive=false;
				AgentActors[Index]->EndAttackFists();
			}
			return;
		}
		Impl->SlashInputBuffer.SetNumUninitialized(Width*SlashInputDim);
		Impl->SlashOutputBuffer.SetNumUninitialized(Width*SlashOutputDim);
	}
	for (int32 Start = 0; Start < Active.Num(); Start += Width)
	{
		const int32 Count = FMath::Min(Width, Active.Num() - Start);
		for (int32 Lane = 0; Lane < Width; ++Lane)
		{
			const float* Source = Lane < Count ? Impl->Agents[Active[Start + Lane]].Slash.State.GetData() : Impl->SlashSeedInput.GetData();
			FMemory::Memcpy(Impl->SlashInputBuffer.GetData() + Lane * SlashInputDim, Source, SlashInputDim * sizeof(float));
		}
		if (!Impl->SlashModel->Run(Impl->SlashInputBuffer, Impl->SlashOutputBuffer))
		{
			UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash2 NNE inference failed."));
			for (int32 Lane = 0; Lane < Count; ++Lane)
			{
				const int32 Index = Active[Start + Lane];
				Impl->Agents[Index].Slash.bActive = false;
				AgentActors[Index]->EndAttackFists();
			}
			continue;
		}
		for (int32 Lane = 0; Lane < Count; ++Lane)
		{
			const int32 Index = Active[Start + Lane];
			auto& Slash = Impl->Agents[Index].Slash;
			const float* Output = Impl->SlashOutputBuffer.GetData() + Lane * SlashOutputDim;
			bool bFinite = true;
			for (int32 Value = 0; Value < SlashOutputDim; ++Value) bFinite &= FMath::IsFinite(Output[Value]);
			if (!bFinite)
			{
				Slash.bActive = false;
				AgentActors[Index]->EndAttackFists();
				UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash2 rejected non-finite output for agent %d."), Index);
				continue;
			}
			for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
			{
				const FVector3f Position = TransformRow(ReadStateVec3(Output, 131 + Bone * 3) - Impl->SlashRootPosition, Transpose(Impl->SlashRootRotation));
				FMat3f Rotation;
				for (int32 Row = 0; Row < 3; ++Row) Rotation.Rows[Row] = ReadStateVec3(Output, 206 + Bone * 9 + Row * 3);
				Rotation = Multiply(Rotation, Transpose(Impl->SlashRootRotation));
				Slash.GhostPose[Impl->SlashBodyIndices[Bone]] = FTransform(MatrixToQuat(MirrorYBasis(Rotation)), LocalTrainingToUnreal(Position));
			}
			FMemory::Memmove(Slash.State.GetData(), Slash.State.GetData() + 41, 41 * sizeof(float));
			FMemory::Memcpy(Slash.State.GetData() + 41, Output, 41 * sizeof(float));
			FMemory::Memmove(Slash.State.GetData() + 82, Slash.State.GetData() + 172, 90 * sizeof(float));
			FMemory::Memcpy(Slash.State.GetData() + 172, Output + 41, 90 * sizeof(float));
			Slash.State[270] = Output[431]; Slash.State[271] = Output[432];
			++Slash.Frame;
			if (Slash.HitFrame == INDEX_NONE && Output[432] > 0.5f) Slash.HitFrame = Slash.Frame;
			Slash.bHasPose = Slash.bNeedsFeedback = true;
			// Decode/publish at every 30 Hz step, including catch-up steps. This commits
			// coherent locomotion history before the next step, never on a render-only tick.
			PublishAgentPose(Index, Impl->Agents[Index].PublishedPoseTimeSeconds);
		}
	}
}

void AProphecyNNLocomotionManager::ApplySlashPose(int32 AgentIndex, TArrayView<FTransform> PreviousPose, TArrayView<FTransform> Pose)
{
	auto& Agent = Impl->Agents[AgentIndex];
	auto& Slash = Agent.Slash;
	if (!Slash.bActive || !Slash.bHasPose) return;
	const FTransform Carrier = SlashComponentWorld(AgentActors[AgentIndex], Agent.PublishedRoot, Agent.PublishedYaw);
	const FTransform PreviousCarrier = SlashComponentWorld(AgentActors[AgentIndex], Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
	if (Slash.bNeedsFeedback)
	{
		Slash.PreviousVisibleWorldPose = Slash.VisibleWorldPose;
		const FTransform RealPelvis = Pose[0];
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			// Bone selection uses the shared named skeleton, not assumptions about ordering.
			const FName Name = Impl->BodyNames[Bone];
			const bool bLower = Bone == 0 || Name.ToString().StartsWith(TEXT("thigh_")) ||
				Name.ToString().StartsWith(TEXT("calf_")) || Name.ToString().StartsWith(TEXT("foot_")) || Name.ToString().StartsWith(TEXT("ball_"));
			if (!Slash.bHalf) Pose[Bone] = (Slash.GhostPose[Bone] * Slash.AnchorWorld).GetRelativeTransform(Carrier);
			else if (!bLower) Pose[Bone] = Slash.GhostPose[Bone].GetRelativeTransform(Slash.GhostPose[0]) * RealPelvis;
		}
		// Same final pass as the reference animation: each hand's parent-local
		// translation is the skeleton rest offset. Rotations and raw Slash history
		// are untouched; both shortening and stretching are removed.
		const USkeletalMeshComponent* Mesh = AgentActors[AgentIndex]->GetPoseReferenceMesh();
		const USkeletalMesh* SkeletonMesh = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
		if (SkeletonMesh)
		{
			const FReferenceSkeleton& Skeleton = SkeletonMesh->GetRefSkeleton();
			for (const FImpl::FUpperArm& Arm : Impl->UpperArms)
			{
				const int32 HandIndex = Skeleton.FindBoneIndex(Impl->BodyNames[Arm.End]);
				if (HandIndex != INDEX_NONE)
				{
					Pose[Arm.End].SetTranslation(Pose[Arm.Mid].TransformPosition(
						Skeleton.GetRefBonePose()[HandIndex].GetTranslation()));
				}
			}
		}
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
			Slash.VisibleWorldPose[Bone] = Pose[Bone] * Carrier;
		// Half mode does not re-encode or feed presentation clamps back into the
		// real lower policy. Its exact vanilla locomotion recurrence stays intact.
		float UnusedLower[StateDim];
		float* Lower = Slash.bHalf ? UnusedLower : StateSlice(Impl->PublishedStateBuffer, AgentIndex);
		float* Upper = UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex);
		EncodeComponentPoseToNNStates(*Impl, Agent, Pose, Lower, Upper);
		float* Current = StateSlice(Impl->CurStateBuffer, AgentIndex);
		if (!Slash.bHalf)
		{
			FMemory::Memcpy(Current, Lower, StateDim * sizeof(float));
			const FVector3f Delta = TransformRow(Agent.CurRootPos - Agent.PublishedRoot, YawMatrix(Agent.PublishedYaw));
			RebaseStateRoot(Current, *Impl, Delta, WrapAngle(Agent.CurRootYaw - Agent.PublishedYaw));
		}
		FMemory::Memcpy(UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex), Upper, UpperStateDim * sizeof(float));
		BuildUpperBaseFromLower(Current, *Impl, UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex));
		LowerTransformToHeading(Current, 0, 3, *Impl, TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex));
		Slash.bNeedsFeedback = false;
	}
	for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
	{
		Pose[Bone] = Slash.VisibleWorldPose[Bone].GetRelativeTransform(Carrier);
		PreviousPose[Bone] = Slash.PreviousVisibleWorldPose[Bone].GetRelativeTransform(PreviousCarrier);
	}
}

// Opt-in long-chain audit. Never used by the gameplay tick; no pose resets at
// segment boundaries, only the target, family and learned phase latches change.
static bool AuditSlashChain(FSlashNative& Model, const FString& Directory)
{
	FString Text;
	TSharedPtr<FJsonObject> Fixture;
	if (!FFileHelper::LoadFileToString(Text, *(Directory / TEXT("chain_audit.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Fixture)) return false;
	if (!Model.SetBatch(1)) return false;
	const auto& Inputs = Fixture->GetArrayField(TEXT("inputs"));
	const auto& Expected = Fixture->GetArrayField(TEXT("expected"));
	const auto& Oracle = Fixture->GetArrayField(TEXT("four_step_oracle"));
	TSet<int32> Starts;
	for (const auto& S : Fixture->GetArrayField(TEXT("segments"))) Starts.Add(S->AsObject()->GetIntegerField(TEXT("startFrame")));
	TArray<float> State, Output, TeacherInput, TeacherOutput;
	JsonFloatArray(Inputs[0]->AsArray(), State);
	TArray<TSharedPtr<FJsonValue>> Rows, Poses, TeacherPoses;
	double SourceMax = 0, OracleMax = 0, TeacherMax = 0, MatrixMax = 0;
	bool bSourceLatches = true, bOracleLatches = true;
	for (int32 I = 0; I < Inputs.Num(); ++I)
	{
		JsonFloatArray(Inputs[I]->AsArray(), TeacherInput);
		FMemory::Memcpy(State.GetData()+262, TeacherInput.GetData()+262, 8*sizeof(float));
		if (Starts.Contains(I+2)) State[270] = State[271] = 0;
		if (!Model.Run(State, Output) || !Model.Run(TeacherInput, TeacherOutput)) return false;
		const auto& E = Expected[I]->AsArray(); const auto& O = Oracle[I]->AsArray();
		double SourceError = 0, OracleError = 0, TeacherError = 0, MatrixError = 0;
		for (int32 Bone = 0; Bone < 25; ++Bone)
		{
			FVector3f DS, DO, DT;
			for (int32 A = 0; A < 3; ++A)
			{
				const int32 J = 131 + Bone*3 + A;
				DS[A] = Output[J]-E[J]->AsNumber(); DO[A] = Output[J]-O[J]->AsNumber();
				DT[A] = TeacherOutput[J]-E[J]->AsNumber();
			}
			SourceError = FMath::Max(SourceError, double(DS.Size()));
			OracleError = FMath::Max(OracleError, double(DO.Size()));
			TeacherError = FMath::Max(TeacherError, double(DT.Size()));
		}
		for (int32 J = 206; J < 431; ++J) MatrixError = FMath::Max(MatrixError, FMath::Abs(Output[J]-O[J]->AsNumber()));
		SourceMax = FMath::Max(SourceMax, SourceError); OracleMax = FMath::Max(OracleMax, OracleError);
		TeacherMax = FMath::Max(TeacherMax, TeacherError); MatrixMax = FMath::Max(MatrixMax, MatrixError);
		const bool bSL = Output[431]==E[431]->AsNumber() && Output[432]==E[432]->AsNumber();
		const bool bOL = Output[431]==O[431]->AsNumber() && Output[432]==O[432]->AsNumber();
		bSourceLatches &= bSL; bOracleLatches &= bOL;
		auto Row = MakeShared<FJsonObject>();
		Row->SetNumberField(TEXT("frame"), I+2);
		Row->SetNumberField(TEXT("source_error_mm"), SourceError*1000);
		Row->SetNumberField(TEXT("four_step_error_mm"), OracleError*1000);
		Row->SetNumberField(TEXT("teacher_source_error_mm"), TeacherError*1000);
		Row->SetNumberField(TEXT("four_step_matrix_error"), MatrixError);
		Row->SetBoolField(TEXT("source_latches_match"), bSL); Row->SetBoolField(TEXT("four_step_latches_match"), bOL);
		Rows.Add(MakeShared<FJsonValueObject>(Row));
		TArray<TSharedPtr<FJsonValue>> Values;
		for (float V : Output) { if (!FMath::IsFinite(V)) return false; Values.Add(MakeShared<FJsonValueNumber>(V)); }
		Poses.Add(MakeShared<FJsonValueArray>(Values));
		Values.Reset();
		for (float V : TeacherOutput) Values.Add(MakeShared<FJsonValueNumber>(V));
		TeacherPoses.Add(MakeShared<FJsonValueArray>(Values));
		FMemory::Memmove(State.GetData(), State.GetData()+41, 41*sizeof(float));
		FMemory::Memcpy(State.GetData()+41, Output.GetData(), 41*sizeof(float));
		FMemory::Memmove(State.GetData()+82, State.GetData()+172, 90*sizeof(float));
		FMemory::Memcpy(State.GetData()+172, Output.GetData()+41, 90*sizeof(float));
		State[270]=Output[431]; State[271]=Output[432];
	}
	auto Report = MakeShared<FJsonObject>();
	Report->SetNumberField(TEXT("source_max_mm"), SourceMax*1000);
	Report->SetNumberField(TEXT("four_step_max_mm"), OracleMax*1000);
	Report->SetNumberField(TEXT("teacher_source_max_mm"), TeacherMax*1000);
	Report->SetNumberField(TEXT("four_step_matrix_max"), MatrixMax);
	Report->SetBoolField(TEXT("source_latches_match"), bSourceLatches);
	Report->SetBoolField(TEXT("four_step_latches_match"), bOracleLatches);
	Report->SetArrayField(TEXT("frames"), Rows); Report->SetArrayField(TEXT("outputs"), Poses);
	Report->SetArrayField(TEXT("teacher_outputs"), TeacherPoses);
	const bool bPassed = OracleMax < 0.0001 && MatrixMax < 0.001 && bOracleLatches;
	Report->SetBoolField(TEXT("passed"), bPassed);
	FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
	FFileHelper::SaveStringToFile(Text, *(Directory / TEXT("unreal_chain_audit.json")));
	UE_LOG(LogProphecyNNLocomotion, Display, TEXT("Slash chain: %d steps source %.6f mm, four-step %.6f mm, teacher %.6f mm, latches %d/%d"),
		Inputs.Num(), SourceMax*1000, OracleMax*1000, TeacherMax*1000, bSourceLatches, bOracleLatches);
	return bPassed;
}

bool AProphecyNNLocomotionManager::AuditSlashReference(const FString& ReferenceDirectory)
{
	if (!GetWorld() || GetWorld()->IsGameWorld()) return false;
	if (Impl->BodyNames.IsEmpty() && !LoadRuntimeContract())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash audit: cannot load lower contract %s."), *RuntimeContractPath);
		return false;
	}
	if (!InitializeSlashNNE())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash audit: model initialization failed."));
		return false;
	}
	FString Text;
	TSharedPtr<FJsonObject> Reference;
	if (FPaths::FileExists(ReferenceDirectory / TEXT("chain_audit.json")))
	{
		// The immutable corpus has its own stationary carrier coordinate frame.
		// Use that frame for this isolated audit, never overwrite gameplay assets.
		FSlashNative ReferenceModel;
		TSharedPtr<FJsonObject> Contract;
		const FString Directory = FPaths::ProjectContentDir()/TEXT("locomotion/NN");
		if (!FFileHelper::LoadFileToString(Text, *(Directory/TEXT("prophecy_slash_runtime.json"))) ||
			!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Contract) ||
			!ReferenceModel.Initialize(Directory, Contract, false, ReferenceDirectory/TEXT("source_native_geometry.json"))) return false;
		return AuditSlashChain(ReferenceModel, ReferenceDirectory);
	}
	if (!FFileHelper::LoadFileToString(Text, *(ReferenceDirectory / TEXT("rollout_unreal.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Reference) || !Reference.IsValid()) return false;
	TArray<float> State = Impl->SlashSeedInput;
	TArray<TSharedPtr<FJsonValue>> NativeReference;
	if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectSavedDir()/TEXT("SlashParity/native_geometry_reference.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), NativeReference)) return false;
	TArray<TSharedPtr<FJsonValue>> Frames;
	const auto& ExpectedFrames = Reference->GetArrayField(TEXT("frames"));
	// Exercise the same world/component/root codec used by TriggerNNAttack,
	// independently of the exported NN's seeded parity test.
	if (!LoadWalkRuntimeContract() || !LoadUpperRuntimeContract()) return false;
	FImpl::FAgent CodecAgent;
	CodecAgent.bUseWalkPolicy = true;
	double MaximumSeedCodecError = 0;
	for (int32 Frame = 0; Frame < 2; ++Frame)
	{
		TArray<FTransform> ComponentPose;
		ComponentPose.SetNum(FullBodyBoneCount);
		const auto& Expected = ExpectedFrames[Frame]->AsObject();
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			FVector3f Position;
			JsonVec3(Expected->GetArrayField(TEXT("globalJointPositionsM"))[Bone]->AsArray(), Position);
			FMat3f Rotation;
			for (int32 Row = 0; Row < 3; ++Row)
				JsonVec3(Expected->GetArrayField(TEXT("globalJointRotations3x3"))[Bone]->AsArray()[Row]->AsArray(), Rotation.Rows[Row]);
			Position = TransformRow(Position - Impl->SlashRootPosition, Transpose(Impl->SlashRootRotation));
			Rotation = Multiply(Rotation, Transpose(Impl->SlashRootRotation));
			ComponentPose[Impl->SlashBodyIndices[Bone]] = FTransform(MatrixToQuat(MirrorYBasis(Rotation)), LocalTrainingToUnreal(Position));
		}
		float Lower[StateDim], Upper[UpperStateDim];
		EncodeSlashPose(*Impl, CodecAgent, ComponentPose, Lower, Upper);
		for (int32 Value = 0; Value < StateDim; ++Value)
			MaximumSeedCodecError = FMath::Max(MaximumSeedCodecError, double(FMath::Abs(Lower[Value] - State[Frame * 41 + Value])));
		for (int32 Value = 0; Value < UpperStateDim; ++Value)
			MaximumSeedCodecError = FMath::Max(MaximumSeedCodecError, double(FMath::Abs(Upper[Value] - State[82 + Frame * 90 + Value])));
	}
	double MaximumPositionError = 0, MaximumRotationError = 0;
	double MaximumFourStepPositionError = 0, MaximumFourStepRotationError = 0;
	double InferenceSeconds = 0;
	bool bLatchesMatch = true;
	for (int32 Frame = 0; Frame < ExpectedFrames.Num(); ++Frame)
	{
		const auto& Expected = ExpectedFrames[Frame]->AsObject();
		if (Frame < 2)
		{
			Frames.Add(ExpectedFrames[Frame]);
			continue;
		}
		for (int32 Lane = 0; Lane < Impl->SlashModel->InputBatchSize; ++Lane)
			FMemory::Memcpy(Impl->SlashInputBuffer.GetData() + Lane * SlashInputDim, State.GetData(), SlashInputDim * sizeof(float));
		const double InferenceStart = FPlatformTime::Seconds();
		if (!Impl->SlashModel->Run(Impl->SlashInputBuffer, Impl->SlashOutputBuffer)) return false;
		InferenceSeconds += FPlatformTime::Seconds() - InferenceStart;
		const float* Output = Impl->SlashOutputBuffer.GetData();
		const auto& FourStep=NativeReference[Frame-2]->AsObject()->GetArrayField(TEXT("output"));
		for (int32 Bone=0; Bone<FullBodyBoneCount; ++Bone)
		{
			FVector3f Delta;
			for (int32 Axis=0; Axis<3; ++Axis) Delta[Axis]=Output[131+Bone*3+Axis]-FourStep[131+Bone*3+Axis]->AsNumber();
			MaximumFourStepPositionError=FMath::Max(MaximumFourStepPositionError,double(Delta.Size()));
		}
		for (int32 I=206; I<431; ++I) MaximumFourStepRotationError=FMath::Max(MaximumFourStepRotationError,FMath::Abs(Output[I]-FourStep[I]->AsNumber()));
		for (int32 Value = 0; Value < SlashOutputDim; ++Value) if (!FMath::IsFinite(Output[Value])) return false;
		TArray<TSharedPtr<FJsonValue>> Positions, Rotations;
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			FVector3f ExpectedPosition;
			JsonVec3(Expected->GetArrayField(TEXT("globalJointPositionsM"))[Bone]->AsArray(), ExpectedPosition);
			const FVector3f Position = ReadStateVec3(Output, 131 + Bone * 3);
			MaximumPositionError = FMath::Max(MaximumPositionError, double((ExpectedPosition - Position).Size()));
			TArray<TSharedPtr<FJsonValue>> XYZ, Rows;
			for (int32 Axis = 0; Axis < 3; ++Axis) XYZ.Add(MakeShared<FJsonValueNumber>(Position[Axis]));
			Positions.Add(MakeShared<FJsonValueArray>(XYZ));
			for (int32 Row = 0; Row < 3; ++Row)
			{
				TArray<TSharedPtr<FJsonValue>> Columns;
				const auto& ExpectedRow = Expected->GetArrayField(TEXT("globalJointRotations3x3"))[Bone]->AsArray()[Row]->AsArray();
				for (int32 Column = 0; Column < 3; ++Column)
				{
					const float Value = Output[206 + Bone * 9 + Row * 3 + Column];
					MaximumRotationError = FMath::Max(MaximumRotationError, FMath::Abs(Value - ExpectedRow[Column]->AsNumber()));
					Columns.Add(MakeShared<FJsonValueNumber>(Value));
				}
				Rows.Add(MakeShared<FJsonValueArray>(Columns));
			}
			Rotations.Add(MakeShared<FJsonValueArray>(Rows));
		}
		bLatchesMatch &= Output[431] == Expected->GetNumberField(TEXT("armedLatch")) && Output[432] == Expected->GetNumberField(TEXT("hitLatch"));
		auto Result = MakeShared<FJsonObject>();
		Result->SetNumberField(TEXT("frame"), Frame);
		Result->SetArrayField(TEXT("globalJointPositionsM"), Positions);
		Result->SetArrayField(TEXT("globalJointRotations3x3"), Rotations);
		Result->SetNumberField(TEXT("armedLatch"), Output[431]);
		Result->SetNumberField(TEXT("hitLatch"), Output[432]);
		Frames.Add(MakeShared<FJsonValueObject>(Result));
		FMemory::Memmove(State.GetData(), State.GetData() + 41, 41 * sizeof(float));
		FMemory::Memcpy(State.GetData() + 41, Output, 41 * sizeof(float));
		FMemory::Memmove(State.GetData() + 82, State.GetData() + 172, 90 * sizeof(float));
		FMemory::Memcpy(State.GetData() + 172, Output + 41, 90 * sizeof(float));
		State[270] = Output[431]; State[271] = Output[432];
	}
	auto Report = MakeShared<FJsonObject>();
	Report->SetNumberField(TEXT("maximum_position_error_m"), MaximumPositionError);
	Report->SetNumberField(TEXT("maximum_rotation_matrix_error"), MaximumRotationError);
	Report->SetNumberField(TEXT("maximum_seed_pose_codec_error"), MaximumSeedCodecError);
	Report->SetNumberField(TEXT("maximum_four_step_position_error_m"), MaximumFourStepPositionError);
	Report->SetNumberField(TEXT("maximum_four_step_rotation_matrix_error"), MaximumFourStepRotationError);
	Report->SetNumberField(TEXT("mean_native_inference_ms"), InferenceSeconds * 1000.0 / FMath::Max(1, ExpectedFrames.Num() - 2));
	Report->SetNumberField(TEXT("batch_size"), Impl->SlashModel->InputBatchSize);
	Report->SetBoolField(TEXT("latches_match"), bLatchesMatch);
	Report->SetArrayField(TEXT("frames"), Frames);
	const bool bPassed = MaximumFourStepPositionError < 0.0001 && MaximumFourStepRotationError < 0.001 && MaximumSeedCodecError < 0.001 && bLatchesMatch;
	Report->SetBoolField(TEXT("passed"), bPassed);
	FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
	FFileHelper::SaveStringToFile(Text, *(FPaths::ProjectSavedDir() / TEXT("SlashParity/unreal_nne_rollout.json")));
	UE_LOG(LogProphecyNNLocomotion, Display, TEXT("Slash reference parity passed=%d max_position=%.6f mm max_matrix=%.9g latches=%d seed_codec=%.9g"),
		bPassed, MaximumPositionError * 1000, MaximumRotationError, bLatchesMatch, MaximumSeedCodecError);
	return bPassed;
}

bool AProphecyNNLocomotionManager::BenchmarkSlashRuntime(bool bGpu, int32 AgentCount)
{
	if (!GetWorld() || GetWorld()->IsGameWorld() || AgentCount<1 || AgentCount>100) return false;
	const FString Directory=FPaths::ProjectContentDir()/TEXT("locomotion/NN");
	FString Text; TSharedPtr<FJsonObject> Contract;
	TArray<TSharedPtr<FJsonValue>> Reference;
	if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("prophecy_slash_runtime.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Contract)) return false;
	if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("SlashParity/native_geometry_reference.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Reference)) return false;
	FSlashNative Model; Model.InputBatchSize=AgentCount;
	if (!Model.Initialize(Directory,Contract,bGpu)) return false;
	TArray<TArray<float>> Inputs; Inputs.SetNum(Reference.Num());
	for (int32 Frame=0; Frame<Reference.Num(); ++Frame)
	{
		Inputs[Frame].SetNumUninitialized(AgentCount*272);
		for (int32 Lane=0; Lane<AgentCount; ++Lane)
		{
			const auto& Row=Reference[(Frame+Lane)%Reference.Num()]->AsObject()->GetArrayField(TEXT("state"));
			for (int32 I=0; I<272; ++I) Inputs[Frame][Lane*272+I]=Row[I]->AsNumber();
		}
	}
	TArray<float> Output; TArray<double> Samples; double MaximumError=0;
	for (int32 Iter=0; Iter<220; ++Iter)
	{
		const int32 Frame=Iter%Reference.Num(); const double Begin=FPlatformTime::Seconds();
		if (!Model.Run(Inputs[Frame],Output)) return false;
		const double Milliseconds=(FPlatformTime::Seconds()-Begin)*1000;
		if (Iter>=20) Samples.Add(Milliseconds);
		if (Iter<Reference.Num())
		{
			for (int32 Lane=0; Lane<AgentCount; ++Lane)
			{
				const auto& Expected=Reference[(Frame+Lane)%Reference.Num()]->AsObject()->GetArrayField(TEXT("output"));
				for (int32 I=0; I<437; ++I)
				{
					if (!FMath::IsFinite(Output[Lane*437+I])) return false;
					MaximumError=FMath::Max(MaximumError,FMath::Abs(Output[Lane*437+I]-Expected[I]->AsNumber()));
				}
			}
		}
	}
	double ResizeError=0, ResizeMilliseconds=0;
	if (AgentCount==1)
	{
		for (int32 Count : {100,4,32,1})
		{
			const double Start=FPlatformTime::Seconds();
			if (!Model.SetBatch(Count)) return false;
			ResizeMilliseconds=FMath::Max(ResizeMilliseconds,(FPlatformTime::Seconds()-Start)*1000);
			TArray<float> Batch; Batch.SetNumUninitialized(Count*272);
			for (int32 Lane=0; Lane<Count; ++Lane)
			{
				const auto& Row=Reference[Lane%Reference.Num()]->AsObject()->GetArrayField(TEXT("state"));
				for (int32 I=0; I<272; ++I) Batch[Lane*272+I]=Row[I]->AsNumber();
			}
			if (!Model.Run(Batch,Output)) return false;
			for (int32 Lane=0; Lane<Count; ++Lane)
			{
				const auto& Row=Reference[Lane%Reference.Num()]->AsObject()->GetArrayField(TEXT("output"));
				for (int32 I=0; I<437; ++I) ResizeError=FMath::Max(ResizeError,FMath::Abs(Output[Lane*437+I]-Row[I]->AsNumber()));
			}
		}
	}
	Samples.Sort(); auto Report=MakeShared<FJsonObject>();
	Report->SetStringField(TEXT("backend"),bGpu?TEXT("NNE DirectML GPU"):TEXT("NNE ORT CPU"));
	Report->SetNumberField(TEXT("agents"),AgentCount);
	Report->SetNumberField(TEXT("median_whole_step_ms"),Samples[Samples.Num()/2]);
	Report->SetNumberField(TEXT("p95_whole_step_ms"),Samples[FMath::FloorToInt(Samples.Num()*0.95)]);
	Report->SetNumberField(TEXT("max_single_step_parity_error"),MaximumError);
	Report->SetNumberField(TEXT("max_batch_resize_ms"),ResizeMilliseconds);
	Report->SetNumberField(TEXT("max_batch_resize_parity_error"),ResizeError);
	Report->SetBoolField(TEXT("passed"),MaximumError<0.001 && ResizeError<0.001);
	Report->SetBoolField(TEXT("includes_geometry_and_gpu_transfers"),true);
	FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));
	FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/FString::Printf(TEXT("SlashParity/native_%s_b%d.json"),bGpu?TEXT("gpu"):TEXT("cpu"),AgentCount)));
	UE_LOG(LogProphecyNNLocomotion,Display,TEXT("Slash whole-step benchmark: %s"),*Text);
	return MaximumError<0.001 && ResizeError<0.001;
}

namespace
{
#if WITH_EDITOR
	FAutoConsoleCommandWithWorldAndArgs SlashAuditInput(TEXT("Prophecy.SlashAuditInput"),
		TEXT("PIE-only input for the Slash regression: key name and 1=press/0=release. Does not change input bindings."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (!World || !World->IsGameWorld() || Args.Num() != 2) return;
			if (APlayerController* PC = World->GetFirstPlayerController())
			{
				const bool bPressed = Args[1] == TEXT("1");
				PC->InputKey(FInputKeyEventArgs(nullptr, INPUTDEVICEID_NONE, FKey(*Args[0]),
					bPressed ? IE_Pressed : IE_Released, bPressed ? 1.0f : 0.0f, false, 0));
			}
		}));
	FAutoConsoleCommandWithWorld SlashAuditCamera(TEXT("Prophecy.SlashAuditCamera"),
		TEXT("PIE-only: bind a script-created test camera on old Blueprint instances with no inherited camera."),
		FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
		{
			if (!World || !World->IsGameWorld()) return;
			for (TActorIterator<AProphecyAgent> It(World); It; ++It)
			{
				if (It->GetAgentCamera()) continue;
				if (FObjectPropertyBase* Property = FindFProperty<FObjectPropertyBase>(It->GetClass(), TEXT("Camera")))
					Property->SetObjectPropertyValue_InContainer(*It, It->FindComponentByClass<UCameraComponent>());
			}
		}));
	FAutoConsoleCommandWithWorld RefreshSlashVisuals(TEXT("Prophecy.RefreshSlashVisuals"),
		TEXT("Refresh transient paused Slash parity meshes in the editor (they do not tick)."),
		FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
		{
			if (!World || World->IsGameWorld()) return;
			for (TActorIterator<AActor> It(World); It; ++It)
			{
				if (!It->GetActorLabel().StartsWith(TEXT("SlashVisual"))) continue;
				if (UPoseableMeshComponent* Component = It->FindComponentByClass<UPoseableMeshComponent>())
				{
					Component->RefreshBoneTransforms();
					Component->UpdateBounds();
				}
			}
		}));
#endif
}
