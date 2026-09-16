// Included by the manager translation unit: one optional shared model, data-only per-agent history.
namespace
{
#if !UE_BUILD_SHIPPING
	TAutoConsoleVariable<int32> CVarSlashTraceAgent(TEXT("Prophecy.SlashTraceAgent"), -1,
		TEXT("Opt-in live Slash audit: owning manager agent index."));
	TAutoConsoleVariable<int32> CVarSlashTraceFrames(TEXT("Prophecy.SlashTraceFrames"), 0,
		TEXT("Remaining live Slash steps to record to Saved/Diagnostics/SlashContacts/live_steps.jsonl."));
	TAutoConsoleVariable<int32> CVarHalfTestUpperSource(TEXT("Prophecy.SlashTestHalfUpperSource"), -1,
		TEXT("Opt-in paired test: match current upper pose on half triggers, suppress automatic full triggers. No history/lower copying."));
	TAutoConsoleVariable<int32> CVarHalfTestRelativeTarget(TEXT("Prophecy.SlashTestHalfRelativeTarget"), 0,
		TEXT("Opt-in paired test world target producer: identical fixed-world (-30,50,35) cm pelvis offsets before normal half mapping."));
	void TraceSlashStep(AProphecyAgent* Actor, int32 Index, FName Family, int32 Frame,
		const FTransform& Anchor, const float* Input, const float* Output, bool bFoot, bool bCalf)
	{
		const int32 Remaining = CVarSlashTraceFrames.GetValueOnGameThread();
		const int32 Selected = CVarSlashTraceAgent.GetValueOnGameThread();
		if (Remaining <= 0 || (Selected != -2 && Selected != Index)) return;
		CVarSlashTraceFrames->Set(Remaining - 1, ECVF_SetByConsole);
		auto Row = MakeShared<FJsonObject>();
		Row->SetStringField(TEXT("actor"), Actor->GetName());
		Row->SetStringField(TEXT("family"), Family.ToString());
		Row->SetNumberField(TEXT("frame"), Frame);
		Row->SetNumberField(TEXT("time"), Actor->GetWorld()->GetTimeSeconds());
		Row->SetBoolField(TEXT("clamp_foot"), bFoot); Row->SetBoolField(TEXT("clamp_calf"), bCalf);
		auto Values = [&](const TCHAR* Name, const float* Data, int32 Count)
		{
			TArray<TSharedPtr<FJsonValue>> Items;
			for (int32 I=0; I<Count; ++I) Items.Add(MakeShared<FJsonValueNumber>(Data[I]));
			Row->SetArrayField(Name, Items);
		};
		Values(TEXT("input"), Input, SlashInputDim); Values(TEXT("output"), Output, SlashOutputDim);
		const FVector P=Anchor.GetTranslation(); const FQuat Q=Anchor.GetRotation();
		const float Transform[]={float(P.X),float(P.Y),float(P.Z),float(Q.X),float(Q.Y),float(Q.Z),float(Q.W)};
		Values(TEXT("anchor"),Transform,7);
		FString Text;
		FJsonSerializer::Serialize(Row,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));
		FFileHelper::SaveStringToFile(Text+TEXT("\n"),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SlashContacts/live_steps.jsonl")),
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
	}
#endif
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

	struct FHalfAttackGT
	{
		TArray<float> Lower[2];
		TArray<FTransform> Pose[2]; // Native contract bone order; centimetres, UE root axes.
	};
	// Shared immutable seed data, loaded only when a half attack is first requested.
	TMap<FName, FHalfAttackGT> HalfAttackGT;

	const FHalfAttackGT* FindHalfAttackGT(const AProphecyNNLocomotionManager::FImpl& Impl, FName Family)
	{
		if (HalfAttackGT.IsEmpty())
		{
			FString Text; TSharedPtr<FJsonObject> Json;
			if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectContentDir()/TEXT("locomotion/NN/prophecy_slash_half_gt.json"))) ||
				!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Json) ||
				Json->GetIntegerField(TEXT("schema")) != 1 ||
				Json->GetStringField(TEXT("checkpoint_sha256")) != TEXT("6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072")) return nullptr;
			const auto& Names = Json->GetArrayField(TEXT("bone_names"));
			if (Names.Num() != FullBodyBoneCount) return nullptr;
			for (int32 I=0; I<Names.Num(); ++I)
				if (FName(Names[I]->AsString()) != Impl.BodyNames[Impl.SlashBodyIndices[I]]) return nullptr;
			TMap<FName, FHalfAttackGT> Loaded;
			for (const auto& Pair : Json->GetObjectField(TEXT("families"))->Values)
			{
				const auto& Entry = Pair.Value->AsObject();
				if (Entry->GetIntegerField(TEXT("previous_frame")) + 1 != Entry->GetIntegerField(TEXT("armed_frame")) ||
					Entry->GetNumberField(TEXT("fps")) != 30) return nullptr;
				FHalfAttackGT Seed;
				for (int32 Frame=0; Frame<2; ++Frame)
				{
					JsonFloatArray(Entry->GetArrayField(Frame ? TEXT("lower_current") : TEXT("lower_previous")), Seed.Lower[Frame]);
					if (Seed.Lower[Frame].Num() != StateDim) return nullptr;
					for (float V : Seed.Lower[Frame]) if (!FMath::IsFinite(V)) return nullptr;
					const auto& Bones = Entry->GetArrayField(Frame ? TEXT("pose_current") : TEXT("pose_previous"));
					if (Bones.Num() != FullBodyBoneCount) return nullptr;
					for (const auto& Bone : Bones)
					{
						TArray<float> V; JsonFloatArray(Bone->AsArray(), V);
						if (V.Num()!=7) return nullptr;
						for (float X : V) if (!FMath::IsFinite(X)) return nullptr;
						FQuat Q(V[3],V[4],V[5],V[6]); if (Q.SizeSquared()<0.5) return nullptr;
						Seed.Pose[Frame].Emplace(Q.GetNormalized(),FVector(V[0],V[1],V[2]));
					}
				}
				Loaded.Add(FName(Pair.Key),MoveTemp(Seed));
			}
			for (const auto& Label : Impl.SlashLabels) if (!Loaded.Contains(Label.Key)) return nullptr;
			HalfAttackGT = MoveTemp(Loaded);
		}
		return HalfAttackGT.Find(Family);
	}

	void SeedHalfAttackGhost(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent, const FHalfAttackGT& GT,
		TArrayView<const FTransform> RealPose, TArray<float>& State, TArray<FTransform>& GhostPose)
	{
		TArray<FTransform, TInlineAllocator<FullBodyBoneCount>> SeedPose;
		SeedPose.SetNum(FullBodyBoneCount);
		const FTransform RealMount(GT.Pose[1][Impl.SlashBodyIndices.IndexOfByKey(0)].GetRotation(),
			RealPose[0].GetTranslation());
		float UnusedLower[StateDim];
		for (int32 Frame=0; Frame<2; ++Frame)
		{
			for (int32 I=0; I<FullBodyBoneCount; ++I) SeedPose[Impl.SlashBodyIndices[I]]=GT.Pose[Frame][I];
			for (int32 I=1; I<FullBodyBoneCount; ++I)
			{
				const FString Name=Impl.BodyNames[I].ToString();
				const bool bLower=Name.StartsWith(TEXT("thigh_")) || Name.StartsWith(TEXT("calf_")) ||
					Name.StartsWith(TEXT("foot_")) || Name.StartsWith(TEXT("ball_"));
				if (!bLower) SeedPose[I]=RealPose[I].GetRelativeTransform(RealMount)*SeedPose[0];
			}
			// The current upper pose supplies both frames: no running/physical lower
			// velocity leaks into hand history. GT pelvis transport is retained.
			EncodeSlashPose(Impl,Agent,MakeArrayView(SeedPose),UnusedLower,State.GetData()+82+90*Frame);
			FMemory::Memcpy(State.GetData()+41*Frame,GT.Lower[Frame].GetData(),StateDim*sizeof(float));
		}
		GhostPose.Reset(); GhostPose.Append(SeedPose);
	}

	void BeginHeadbuttPreparation(const AProphecyNNLocomotionManager::FImpl& Impl,
		AProphecyNNLocomotionManager::FImpl::FAgent& Agent, const AProphecyAgent* Actor, bool bEnabled)
	{
		auto& Slash = Agent.Slash;
		Slash.bHeadbuttPreparation = bEnabled;
		if (!bEnabled) return;
		Slash.PreparationBlendSeconds = FMath::IsFinite(Actor->HeadbuttPreparationBlendSeconds)
			? FMath::Clamp(Actor->HeadbuttPreparationBlendSeconds, 0.f, 1.f) : 0.1f;
		for (int32 I=0; I<2; ++I)
		{
			const int32 Hand = Impl.BodyNames.IndexOfByKey(FName(I ? TEXT("hand_r") : TEXT("hand_l")));
			const int32 Upper = Impl.BodyNames.IndexOfByKey(FName(I ? TEXT("upperarm_r") : TEXT("upperarm_l")));
			const FTransform HandLocal = Slash.GhostPose[Hand].GetRelativeTransform(Slash.GhostPose[0]);
			const FTransform UpperLocal = Slash.GhostPose[Upper].GetRelativeTransform(Slash.GhostPose[0]);
			auto& Entry = Slash.PreparationEntry.Arms[I];
			Entry.Position = LocalUnrealToTraining(HandLocal.GetTranslation());
			Entry.HandRotation = MatrixToQuat(MirrorYBasis(QuatToMatrix(HandLocal.GetRotation())));
			Entry.UpperArmRotation = MatrixToQuat(MirrorYBasis(QuatToMatrix(UpperLocal.GetRotation())));
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
		const FTransform RealMount(Slash.HalfMountWorldRotation,
			SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw).TransformPosition(
				LocalTrainingToUnreal(ReadStateVec3(Lower, 0))));
		FVector RequestedWorld = Slash.TargetWorld;
#if !UE_BUILD_SHIPPING
		if (CVarHalfTestRelativeTarget.GetValueOnGameThread() != 0)
			RequestedWorld = RealMount.GetLocation() + FVector(-30,50,35);
#endif
		const FVector Offset = RequestedWorld - RealMount.GetLocation();
		const float Radius = AProphecyNNLocomotionManager::GetHalfAttackTargetRadius(Actor->GetWorld());
		EffectiveWorld = RealMount.GetLocation() + Offset.GetClampedToMaxSize(Radius);
		const FTransform GhostPelvis = Slash.GhostPose[0] * Slash.AnchorWorld;
		// Inverse of presentation. The mount orientation is fixed at attack start:
		// real pelvis sway/turning cannot rotate the target seen by the ghost NN.
		GhostWorld = GhostPelvis.TransformPosition(RealMount.InverseTransformPosition(EffectiveWorld));
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
				LocalDelta, YawDelta);
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
			LocalPose, PreviousPose, Pose, PreviousCarrier, Carrier, Agent.PublishedPoseTimeSeconds,
			true, false, 0, FVector2D::ZeroVector, Agent.Slash.HandClamp);
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
#if !UE_BUILD_SHIPPING
	if (!bHalf && CVarHalfTestUpperSource.GetValueOnGameThread() >= 0) return false;
#endif
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor || !Actor->bNNInferenceEnabled || TargetWorld.ContainsNaN() || !InitializeSlashNNE()) return false;
	const TArray<float>* Labels = Impl->SlashLabels.Find(Attack);
	if (!Labels || (bHalf && (Attack == TEXT("kickl") || Attack == TEXT("kickr")))) return false;
	const bool bPreparation = Attack == TEXT("headbutt") && Actor->bUseGTHeadbuttPreparation;
	if (bPreparation && !Impl->SlashModel->LoadHeadbuttPreparation(FPaths::ProjectContentDir()/TEXT("locomotion/NN")))
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Headbutt refused: missing/invalid GT preparation track."));
		return false;
	}
	const FHalfAttackGT* HalfGT = bHalf ? FindHalfAttackGT(*Impl, Attack) : nullptr;
	if (bHalf && !HalfGT)
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Half attack %s refused: missing/invalid GT Armed seed."), *Attack.ToString());
		return false;
	}
	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	const FTransform Carrier = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
	const auto Current = TransformSlice(Impl->ComponentTransformBuffer, Handle.Index);
#if !UE_BUILD_SHIPPING
	const int32 UpperSource = CVarHalfTestUpperSource.GetValueOnGameThread();
	if (bHalf && UpperSource >= 0 && UpperSource != Handle.Index && Impl->Agents.IsValidIndex(UpperSource))
	{
		const auto SourcePose = TransformSlice(Impl->ComponentTransformBuffer, UpperSource);
		const AProphecyAgent* SourceActor = AgentActors[UpperSource];
		const auto& SourceAgent = Impl->Agents[UpperSource];
		const FTransform SourceCarrier = SlashComponentWorld(SourceActor, SourceAgent.PublishedRoot, SourceAgent.PublishedYaw);
		const FVector SourcePelvis = SourceCarrier.TransformPosition(SourcePose[0].GetTranslation());
		const FVector DestinationPelvis = Carrier.TransformPosition(Current[0].GetTranslation());
		for (int32 I=1; I<FullBodyBoneCount; ++I)
		{
			const FString Name=Impl->BodyNames[I].ToString();
			if (!Name.StartsWith(TEXT("thigh_")) && !Name.StartsWith(TEXT("calf_")) &&
				!Name.StartsWith(TEXT("foot_")) && !Name.StartsWith(TEXT("ball_")))
			{
				FTransform WorldUpper = SourcePose[I] * SourceCarrier;
				WorldUpper.AddToTranslation(DestinationPelvis - SourcePelvis);
				Current[I] = WorldUpper.GetRelativeTransform(Carrier);
			}
		}
	}
#endif
	const FVector Pelvis = Carrier.TransformPosition(Current[0].GetTranslation());
	if (FVector::DistSquared2D(Pelvis, TargetWorld) < 0.0001) return false;
	// Validate the replacement first; an invalid request must not end the old attack.
	const bool bContinueFullHistory = Agent.Slash.bActive && Agent.Slash.bHasPose &&
		!Agent.Slash.bHalf && !bHalf;
	if (Agent.DefensePose) StopAgentNNDefense(Handle);
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
		BeginHeadbuttPreparation(*Impl, Agent, Actor, bPreparation);
		Actor->BeginAttackFists(Attack);
		Actor->NotifySwordAttackState(true);
		SlashRootMinusStartPelvis.Add(Actor,
			Actor->GetRootLowPoint() - Slash.VisibleWorldPose[0].GetTranslation());
		ProphecyAttackCamera::Update(this, Actor, true);
		return true;
	}
	Slash = FImpl::FAgent::FSlashAttack{};
	Slash.Family = Attack; Slash.TargetWorld = TargetWorld; Slash.bHalf = bHalf;
	Slash.AnchorWorld = StartCarrier; Slash.TailSteps = Impl->SlashTailSteps[Attack];
	Slash.State = Impl->SlashSeedInput;
	FMemory::Memcpy(Slash.State.GetData() + 265, Labels->GetData(), 5 * sizeof(float));
	Slash.State[270] = Slash.State[271] = 0;
	if (HalfGT)
	{
		// A target-facing ghost frame also removes the real root's INITIAL heading
		// from conditioning. Equal upper world poses and pelvis-relative world
		// targets must seed identically even when one lower body faces elsewhere.
		const FVector Direction = (TargetWorld - Pelvis).GetSafeNormal2D();
		const FQuat Heading(FRotator(0, FMath::RadiansToDegrees(FMath::Atan2(-Direction.X, Direction.Y)), 0));
		const FTransform& GTPelvis = HalfGT->Pose[1][Impl->SlashBodyIndices.IndexOfByKey(0)];
		Slash.AnchorWorld = FTransform(Heading, Pelvis - Heading.RotateVector(GTPelvis.GetTranslation()));
		TArray<FTransform, TInlineAllocator<FullBodyBoneCount>> InGhostFrame;
		for (const FTransform& Bone : Current)
			InGhostFrame.Add((Bone * StartCarrier).GetRelativeTransform(Slash.AnchorWorld));
		SeedHalfAttackGhost(*Impl, Agent, *HalfGT, MakeArrayView(InGhostFrame), Slash.State, Slash.GhostPose);
		Slash.HalfMountWorldRotation = (Slash.GhostPose[0] * Slash.AnchorWorld).GetRotation();
		Slash.bHasPose = Slash.bNeedsFeedback = true;
	}
	else
	{
		TArray<FTransform, TInlineAllocator<FullBodyBoneCount>> Previous;
		Previous.Append(TransformSlice(Impl->PreviousComponentTransformBuffer, Handle.Index));
		const FTransform PreviousWorld = SlashComponentWorld(Actor, Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
		for (FTransform& Bone : Previous) Bone = (Bone * PreviousWorld).GetRelativeTransform(StartCarrier);
		EncodeSlashPose(*Impl, Agent, MakeArrayView(Previous), Slash.State.GetData(), Slash.State.GetData() + 82);
		EncodeSlashPose(*Impl, Agent, Current, Slash.State.GetData() + 41, Slash.State.GetData() + 172);
		Slash.GhostPose.Append(Current);
	}
	for (const auto& Bone : Current) Slash.VisibleWorldPose.Add(Bone * StartCarrier);
	Slash.PreviousVisibleWorldPose = Slash.VisibleWorldPose;
	if (!bHalf) SlashRootMinusStartPelvis.Add(Actor,
		Actor->GetRootLowPoint() - Slash.VisibleWorldPose[0].GetTranslation());
	Slash.bActive = true;
	BeginHeadbuttPreparation(*Impl, Agent, Actor, bPreparation);
	Actor->BeginAttackFists(Attack);
	Actor->NotifySwordAttackState(true);
	ProphecyAttackCamera::Update(this, Actor, !bHalf);
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentNNHalfAttack(FProphecyAgentHandle Handle, bool bHalf)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor) return false;
	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	auto& Slash = Agent.Slash;
	if (!Slash.bActive || (bHalf && (Slash.Family == TEXT("kickl") || Slash.Family == TEXT("kickr")))) return false;
	if (Slash.bHalf == bHalf) return true;
	if (Slash.bHalf && !bHalf)
	{
		// Retain the existing full-mode rejoin contract: use the current ground-
		// aligned locomotion carrier, keeping native history/latches. Matching a
		// tilted ghost pelvis here would tilt the full attack's floor frame too.
		Slash.AnchorWorld = SlashComponentWorld(Actor, Agent.PublishedRoot, Agent.PublishedYaw);
		SlashRootMinusStartPelvis.Add(Actor, Actor->GetRootLowPoint() -
			(Slash.GhostPose[0] * Slash.AnchorWorld).GetTranslation());
	}
	if (bHalf)
	{
		// A running full attack keeps its pose/history. Freeze its current upper
		// mounting orientation rather than reseeding an already-running attack.
		Slash.HalfMountWorldRotation = (Slash.GhostPose[0] * Slash.AnchorWorld).GetRotation();
		SlashRootMinusStartPelvis.Remove(Actor);
	}
	Slash.bHalf = bHalf;
	Slash.bNeedsFeedback = true;
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
	Actor->NotifySwordAttackState(false);
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
			AgentActors[Index]->NotifySwordAttackState(false);
			continue;
		}
		WriteStateVec3(Slash.State.GetData(), 262, Target);
		Active.Add(Index);
	}
	if (Active.IsEmpty()) return;
	if (!Impl->PreviousPoseDebugAgents.IsEmpty()) UpdatePreviousPoseDebug(true);
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
				AgentActors[Index]->NotifySwordAttackState(false);
			}
			return;
		}
		Impl->SlashInputBuffer.SetNumUninitialized(Width*SlashInputDim);
		Impl->SlashOutputBuffer.SetNumUninitialized(Width*SlashOutputDim);
	}
	for (int32 Start = 0; Start < Active.Num(); Start += Width)
	{
		const int32 Count = FMath::Min(Width, Active.Num() - Start);
		TArray<FSlashNative::FStepSettings, TInlineAllocator<BatchSize>> Settings;
		// Construct contexts only for active inertia; inline capacity keeps pointers
		// stable through this call and avoids per-step heap allocation.
		TArray<FPelvisInertiaStepContext, TInlineAllocator<BatchSize>> InertiaContexts;
		Settings.SetNum(Width);
		for (int32 Lane = 0; Lane < Width; ++Lane)
		{
			const float* Source = Lane < Count ? Impl->Agents[Active[Start + Lane]].Slash.State.GetData() : Impl->SlashSeedInput.GetData();
			FMemory::Memcpy(Impl->SlashInputBuffer.GetData() + Lane * SlashInputDim, Source, SlashInputDim * sizeof(float));
			Settings[Lane].FrozenPinIterations = 4;
			if (Lane < Count)
			{
				const int32 Index = Active[Start + Lane];
				const AProphecyAgent* Actor = AgentActors[Index];
				const auto& Slash = Impl->Agents[Index].Slash;
				auto& Option = Settings[Lane];
				Option.FrozenPinIterations = Actor->AttackFootPinningIterations;
				if (!Slash.bHalf && ProphecyPelvisInertia::HasTarget(Actor))
				{
					auto& Context=InertiaContexts.AddDefaulted_GetRef();
					Context.Actor=Actor;
					Context.Carrier=Slash.AnchorWorld;
					Context.Step=1./NNUpdateHz;
					Context.Time=double(GetWorld()->GetTimeSeconds())-Impl->AccumulatedStepSeconds+Context.Step;
					Option.PelvisInertia=&Context;
				}
				if (Slash.bHeadbuttPreparation && Actor->bUseGTHeadbuttPreparation && Source[270] < 0.5f)
				{
					Option.PreparationFrame = Slash.Frame;
					Option.EntryPose = &Slash.PreparationEntry;
					const float T = Slash.PreparationBlendSeconds > 0
						? FMath::Clamp(Slash.Frame / (30.f * Slash.PreparationBlendSeconds), 0.f, 1.f) : 1.f;
					Option.PreparationWeight = T*T*(3-2*T);
				}
			}
		}
		if (!Impl->SlashModel->Run(Impl->SlashInputBuffer, Impl->SlashOutputBuffer, MakeArrayView(Settings)))
		{
			UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash2 NNE inference failed."));
			for (int32 Lane = 0; Lane < Count; ++Lane)
			{
				const int32 Index = Active[Start + Lane];
				Impl->Agents[Index].Slash.bActive = false;
				AgentActors[Index]->EndAttackFists();
				AgentActors[Index]->NotifySwordAttackState(false);
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
				AgentActors[Index]->NotifySwordAttackState(false);
				UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Slash2 rejected non-finite output for agent %d."), Index);
				continue;
			}
			if (!Impl->PinningDebug.IsEmpty())
			{
				if (auto* Debug = Impl->PinningDebug.Find(Index); Debug && Debug->Owner.Get() == AgentActors[Index])
				{
					const float* Frozen = Impl->SlashModel->NetworkOutputs[0].GetData() + Lane*43;
					const float* Learned = Impl->SlashModel->NetworkOutputs[1].GetData() + Lane*43;
					const bool Both = Frozen[41]<0 && Frozen[42]<0;
					Debug->Frozen.RawNetworkOutput = FVector2D(Frozen[41],Frozen[42]);
					Debug->Frozen.RawPinning = FVector2D(Both || Frozen[41]<=Frozen[42] ? 1 : 0, Both || Frozen[42]<Frozen[41] ? 1 : 0);
					Debug->Frozen.EffectivePinning = Debug->Frozen.RawPinning;
					Debug->Frozen.SampleTimeSeconds = GetWorld()->GetTimeSeconds();
					Debug->Frozen.bWalkPolicy = true;
					Debug->Frozen.bAppliesToVisibleFeet = false; // Intermediate baseline, not the final feet.
					Debug->Attack.RawNetworkOutput = FVector2D(Learned[41],Learned[42]);
					Debug->Attack.RawPinning = FVector2D(Output[435],Output[436]);
					Debug->Attack.EffectivePinning = Debug->Attack.RawPinning;
					Debug->Attack.SampleTimeSeconds = GetWorld()->GetTimeSeconds();
					Debug->Attack.bAppliesToVisibleFeet = !Slash.bHalf;
				}
			}
#if !UE_BUILD_SHIPPING
			TraceSlashStep(AgentActors[Index], Index, Slash.Family, Slash.Frame + 1, Slash.AnchorWorld,
				Impl->SlashInputBuffer.GetData() + Lane * SlashInputDim, Output, bClampFoot, bClampCalf);
#endif
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
		FTransform HalfMount;
		if (Slash.bHalf) HalfMount = FTransform(Slash.HalfMountWorldRotation,
			Carrier.TransformPosition(Pose[0].GetTranslation())).GetRelativeTransform(Carrier);
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			// Bone selection uses the shared named skeleton, not assumptions about ordering.
			const FName Name = Impl->BodyNames[Bone];
			const bool bLower = Bone == 0 || Name.ToString().StartsWith(TEXT("thigh_")) ||
				Name.ToString().StartsWith(TEXT("calf_")) || Name.ToString().StartsWith(TEXT("foot_")) || Name.ToString().StartsWith(TEXT("ball_"));
			if (!Slash.bHalf) Pose[Bone] = (Slash.GhostPose[Bone] * Slash.AnchorWorld).GetRelativeTransform(Carrier);
			else if (!bLower) Pose[Bone] = Slash.GhostPose[Bone].GetRelativeTransform(Slash.GhostPose[0]) * HalfMount;
		}
		// Default matches the reference animation's exact wrist attachment. Optional
		// per-agent leeway or disabling only changes presentation, not raw Slash history.
		Slash.HandClamp.bEnabled = AgentActors[AgentIndex]->bAttackHandClamp;
		Slash.HandClamp.LeewayCm = AgentActors[AgentIndex]->AttackHandClampLeewayCm;
		const USkeletalMeshComponent* Mesh = AgentActors[AgentIndex]->GetPoseReferenceMesh();
		const USkeletalMesh* SkeletonMesh = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
		if (SkeletonMesh)
		{
			const FReferenceSkeleton& Skeleton = SkeletonMesh->GetRefSkeleton();
			const AProphecyAgent* ClampActor = AgentActors[AgentIndex];
			const bool bFootClamp = ClampActor->bOverrideAttackFootClamp ? ClampActor->bAttackFootClamp : bClampFoot;
			const bool bCalfClamp = ClampActor->bOverrideAttackCalfClamp ? ClampActor->bAttackCalfClamp : bClampCalf;
			const float FootMultiplier = ClampActor->bOverrideAttackFootClamp ? 1.f : FootClampLengthMultiplier;
			const float CalfMultiplier = ClampActor->bOverrideAttackCalfClamp ? 1.f : CalfClampLengthMultiplier;
			const float FootLeeway = ClampActor->bOverrideAttackFootClamp ? ClampActor->AttackFootClampLeewayCm : 0.f;
			const float CalfLeeway = ClampActor->bOverrideAttackCalfClamp ? ClampActor->AttackCalfClampLeewayCm : 0.f;
			Slash.CalfClampLengths = FVector2D::ZeroVector;
			// Full attacks replace the already-clamped locomotion legs. Apply the controls
			// to that replacement before publishing/encoding the visible pose, just as for hands.
			if (!Slash.bHalf && (bFootClamp || bCalfClamp))
			{
				for (const FImpl::FLimb& Leg : Impl->Limbs)
				{
					const int32 CalfIndex = Skeleton.FindBoneIndex(Impl->BodyNames[Leg.Mid]);
					const int32 FootIndex = Skeleton.FindBoneIndex(Impl->BodyNames[Leg.End]);
					if (CalfIndex != INDEX_NONE && FootIndex != INDEX_NONE)
					{
						const FVector Reference = Skeleton.GetRefBonePose()[FootIndex].GetTranslation();
						Slash.CalfClampLengths[Impl->BodyNames[Leg.End] == TEXT("foot_l") ? 0 : 1] = Reference.Length()*FMath::Max(0.f,CalfMultiplier);
						ProphecyNNLegClamps::Apply(Pose[Leg.Start].GetTranslation(), Pose[Leg.Mid],
							Pose[Leg.End], Pose[Leg.Toe], Skeleton.GetRefBonePose()[FootIndex].GetTranslation(),
							Skeleton.GetRefBonePose()[CalfIndex].GetTranslation().Length(),
							bFootClamp, FootMultiplier, bCalfClamp, CalfMultiplier, FootLeeway, CalfLeeway);
					}
				}
			}
			for (const FImpl::FUpperArm& Arm : Impl->UpperArms)
			{
				const int32 HandIndex = Skeleton.FindBoneIndex(Impl->BodyNames[Arm.End]);
				if (HandIndex != INDEX_NONE)
				{
					const FVector Offset = Skeleton.GetRefBonePose()[HandIndex].GetTranslation();
					Slash.HandClamp.ReferenceOffsets[Impl->BodyNames[Arm.End] == TEXT("hand_l") ? 0 : 1] = Offset;
					if (Slash.HandClamp.bEnabled)
						Pose[Arm.End].SetTranslation(FProphecyNNAttackHandClamp::ClampPosition(
							Pose[Arm.End].GetTranslation(), Pose[Arm.Mid].TransformPosition(Offset), Slash.HandClamp.LeewayCm));
				}
			}
		}
		if (ProphecyHandInertia::IsActive(AgentActors[AgentIndex],Agent.PublishedWalkWeight,true))
		{
			const FTransform Root=HandInertiaRoot(Agent.PublishedRoot,Agent.PublishedYaw);
			const FTransform PrevRoot=HandInertiaRoot(Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw);
			const double Dt=1./NNUpdateHz;
			const double Time=double(GetWorld()->GetTimeSeconds())-Impl->AccumulatedStepSeconds+Dt;
			for (int32 I=0; I<2; ++I)
			{
				const auto& Arm=Impl->UpperArms[I];
				if (CorrectInertiaArm(*Impl,AgentActors[AgentIndex],I,Agent.PublishedWalkWeight,true,Time,Dt,
					PrevRoot,Root,Slash.PreviousVisibleWorldPose[Arm.End],Carrier,Pose))
				{
					for (int32 Bone:{Arm.Start,Arm.Mid,Arm.End})
					{
						const FTransform World=Pose[Bone]*Carrier;
						Slash.GhostPose[Bone]=Slash.bHalf ? World.GetRelativeTransform(HalfMount*Carrier)*Slash.GhostPose[0]
							: World.GetRelativeTransform(Slash.AnchorWorld);
					}
					StoreInertiaArm(*Impl,I,Slash.GhostPose,FMat3f(),Slash.State.GetData()+172);
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
		float* CurrentUpper = UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex);
		FMemory::Memcpy(CurrentUpper, Upper, UpperStateDim * sizeof(float));
		// Published bones use the old carrier, while the recurrent lower/base already
		// uses the predicted next carrier. Upper history must describe that same frame.
		const FVector3f UpperDelta = TransformRow(Agent.CurRootPos - Agent.PublishedRoot, YawMatrix(Agent.PublishedYaw));
		RebaseUpperHeadingState(CurrentUpper, UpperDelta, WrapAngle(Agent.CurRootYaw - Agent.PublishedYaw));
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
	if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SlashContacts/benchmark_reference.json"))) ||
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
