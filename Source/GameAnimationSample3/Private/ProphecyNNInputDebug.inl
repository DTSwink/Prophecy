// Optional renderer of encoded input history. Included after the pose decoder and Slash runtime.
#include "ProphecyContinuousRootWindow.h"

bool AProphecyNNLocomotionManager::SetAgentLocomotionRootWindowLocation(
	FProphecyAgentHandle Handle, FVector WorldLocation, bool bPreserveWorldPose)
{
	if (!IsInGameThread() || !Impl || !Impl->bInitialized || IsSimBridgeActive()
		|| WorldLocation.ContainsNaN()) return false;
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor || !Actor->bNNInferenceEnabled) return false;
	auto& Agent = Impl->Agents[Handle.Index];
	if (Agent.WindowStepSeconds <= 0
		|| (Agent.Slash.bActive && !Agent.Slash.bHalf)) return false;
	const FVector WorldDelta = WorldLocation - Actor->GetRootLowPoint();
	const FVector3f Delta = UnrealToTraining(WorldDelta);
	if (Delta.ContainsNaN() || (Agent.CurRootPos + Delta).ContainsNaN()) return false;
	if (WorldDelta.IsZero()) return true;
	// Deliberately unswept: a requested window translation must not collapse into
	// the normal collision-rebase path. Leave physical Jolt bodies to their solver.
	if (!Actor->SetActorLocation(Actor->GetActorLocation() + WorldDelta, false, nullptr, ETeleportType::None)) return false;
	if (Agent.DefensePose)
	{
		using namespace ProphecyDefense;
		auto& P=*Agent.DefensePose;
		if (bPreserveWorldPose)
		{
			auto Rebase=[&](float* Lower,float* Upper,FRootFrame& Root)
			{
				const FVector3f Old=Root.P;Root.P+=Delta;
				RebaseLower(Lower,Lower,Old,Root.R,Root.P,Root.R);
				RebaseUpper(Upper,Upper,Old,Root.R,Root.P,Root.R);
			};
			if (P.bDodge)
			{
				auto& S=static_cast<FProphecyLiveDodge&>(P).State;
				Rebase(S.PreviousLower,S.PreviousUpper,S.PreviousRoot);Rebase(S.CurrentLower,S.CurrentUpper,S.CurrentRoot);
			}
			else
			{
				auto& S=static_cast<FProphecyLiveParry&>(P).State;
				RebaseUpper(S.CurrentBaseline,S.CurrentBaseline,S.CurrentRoot.P,S.CurrentRoot.R,S.CurrentRoot.P+Delta,S.CurrentRoot.R);
				Rebase(S.PreviousLower,S.PreviousUpper,S.PreviousRoot);Rebase(S.CurrentLower,S.CurrentUpper,S.CurrentRoot);
			}
			const auto PrevCarrier=SlashComponentWorld(Actor,Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw);
			const auto Carrier=SlashComponentWorld(Actor,Agent.PublishedRoot,Agent.PublishedYaw);
			for (int32 I=0;I<25;++I)
			{
				P.PreviousComponent[I].AddToTranslation(-PrevCarrier.InverseTransformVector(WorldDelta));
				P.CurrentComponent[I].AddToTranslation(-Carrier.InverseTransformVector(WorldDelta));
			}
		}
		else if (P.bDodge)
		{
			// Move the episode origin with the defender. The external attacker does
			// not teleport, so its retained sweep endpoint needs the inverse shift.
			static_cast<FProphecyLiveDodge&>(P).WorldOrigin+=Delta;
			P.PreviousAttack.Center-=Delta;P.NextAttack.Center-=Delta;P.Context.TargetWorld-=Delta;
		}
		else
		{
			auto& Parry=static_cast<FProphecyLiveParry&>(P);
			Parry.State.PreviousRoot.P+=Delta;Parry.State.CurrentRoot.P+=Delta;
			for (int32 I=0;I<25;++I) { P.CurrentPose.P[I]+=Delta;Parry.Frozen.P[I]+=Delta; }
			for (int32 I=0;I<Impl->Defense->Contacts.Count;++I) P.PreviousBoxes[I].Center+=Delta;
		}
	}
	if (bPreserveWorldPose)
	{
		// Bounds recenter the carrier under the existing skeleton. Preserve BOTH
		// recurrence frames and publication endpoints, otherwise the next NN step
		// reintroduces a shifted pelvis target and the bounds chase it indefinitely.
		auto RebasePair = [&](TArray<float>& Lower, TArray<float>& Upper, float Yaw)
		{
			const FVector3f HeadingDelta = TransformRow(Delta, YawMatrix(Yaw));
			const FVector3f LowerDelta = TransformRow(HeadingDelta, Transpose(Impl->SeedRootRot));
			float* LowerState = StateSlice(Lower, Handle.Index);
			float* UpperState = UpperStateSlice(Upper, Handle.Index);
			// Translation only: don't normalize rotations or modify toe/clamp state.
			for (int32 Offset : {0, 9, 25})
				WriteStateVec3(LowerState, Offset, ReadStateVec3(LowerState, Offset) - LowerDelta);
			for (int32 Offset : {60, 75})
				WriteStateVec3(UpperState, Offset, ReadStateVec3(UpperState, Offset) - HeadingDelta);
		};
		RebasePair(Impl->PrevStateBuffer, Impl->UpperPreviousStateBuffer, Agent.PrevRootYaw);
		RebasePair(Impl->CurStateBuffer, Impl->UpperCurrentStateBuffer, Agent.CurRootYaw);
		RebasePair(Impl->PreviousPublishedStateBuffer, Impl->UpperPreviousPublishedStateBuffer, Agent.PreviousPublishedYaw);
		RebasePair(Impl->PublishedStateBuffer, Impl->UpperPublishedStateBuffer, Agent.PublishedYaw);
		if (Agent.bHasPhysicalSample)
			RebasePair(Impl->PreviousPhysicalStateBuffer, Impl->UpperPreviousPhysicalStateBuffer, Agent.CurRootYaw);
		BuildUpperBaseFromLower(StateSlice(Impl->CurStateBuffer, Handle.Index), *Impl,
			UpperStateSlice(Impl->UpperCurrentBaseBuffer, Handle.Index));
		LowerTransformToHeading(StateSlice(Impl->PrevStateBuffer, Handle.Index), 0, 3, *Impl,
			TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, Handle.Index));
		LowerTransformToHeading(StateSlice(Impl->CurStateBuffer, Handle.Index), 0, 3, *Impl,
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, Handle.Index));
	}
	Agent.PrevRootPos += Delta;
	Agent.CurRootPos += Delta;
	Agent.PreviousPublishedRoot += Delta;
	Agent.PublishedRoot += Delta;
	Agent.FedInputRoot += Delta;
	Agent.WindowPreviousRoot += Delta;
	for (auto& Root : Agent.FedFutureRootPositions) Root += Delta;
	Agent.MoverState.position.x += Delta.X;
	Agent.MoverState.position.z += Delta.Z;
	if (Agent.bHasBridgeActualRoot) Agent.LastBridgeActualRoot += Delta;
	// Encoded windows, recurrent poses and smoothing history are root-relative:
	// translating those again would change the trajectory/pose instead of its origin.
	// Half-attack presentation retains cached world poses between policy updates.
	if (!bPreserveWorldPose && Agent.Slash.bActive && Agent.Slash.bHalf)
	{
		for (auto& Bone : Agent.Slash.PreviousVisibleWorldPose) Bone.AddToTranslation(WorldDelta);
		for (auto& Bone : Agent.Slash.VisibleWorldPose) Bone.AddToTranslation(WorldDelta);
	}
	// The cached target is already in world coordinates. Bounds must leave it
	// (and Jolt's target history) untouched; ordinary explicit placement translates it.
	if (!bPreserveWorldPose)
		FProphecyNNPoseStore::TranslateAgentWorldPose(PoseStoreAgentBase + Handle.Index, WorldDelta);
	else if (Actor->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic)
		Actor->ApplyNNPoseKinematically(0.0f);
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentContinuousLocomotionRootWindow(
	FProphecyAgentHandle Handle, TArray<FTransform>& Roots, TArray<float>& Times) const
{
	Roots.Reset(); Times.Reset();
	const AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor || !Actor->bNNInferenceEnabled) return false;
	const auto& Agent = Impl->Agents[Handle.Index];
	if (Agent.Slash.bActive && !Agent.Slash.bHalf) return false;
	if (!GetAgentLocomotionRootWindow(Handle, Roots, Times)) return false;
	const FTransform AppliedRoot(FRotator(0, Actor->GetActorRotation().Yaw, 0), Actor->GetRootLowPoint());
	ProphecyContinuousRootWindow::Resample(Roots, Times, Impl->VisualPoseAlpha, Agent.WindowStepSeconds, AppliedRoot);
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentFootPinningDebug(FProphecyAgentHandle Handle, bool bEnabled)
{
	auto* Actor = ResolveAgent(Handle);
	if (!Actor) return false;
	if (!bEnabled) { Impl->PinningDebug.Remove(Handle.Index); return true; }
	auto& Debug = Impl->PinningDebug.FindOrAdd(Handle.Index);
	if (Debug.Owner.Get() != Actor) Debug = FImpl::FPinningDebug();
	Debug.Owner = Actor;
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentFootPinning(FProphecyAgentHandle Handle,
	bool bAttack, bool bFrozenStage, FProphecyFootPinningSample& Sample) const
{
	Sample = FProphecyFootPinningSample();
	const auto* Actor = ResolveAgent(Handle);
	if (!Actor) return false;
	const auto* Debug = Impl->PinningDebug.Find(Handle.Index);
	if (!Debug || Debug->Owner.Get() != Actor || !Actor->bNNInferenceEnabled) return false;
	const auto& Slash = Impl->Agents[Handle.Index].Slash;
	if (bAttack && (!Slash.bActive || !Slash.bHasPose)) return false;
	const auto& Cached = bAttack ? (bFrozenStage ? Debug->Frozen : Debug->Attack) : Debug->Locomotion;
	if (Cached.SampleTimeSeconds < 0) return false;
	Sample = Cached;
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentLocomotionRootWindow(
	FProphecyAgentHandle Handle, TArray<FTransform>& Roots, TArray<float>& Times) const
{
	Roots.Reset(); Times.Reset();
	if (!ResolveAgent(Handle)) return false;
	const auto& Agent = Impl->Agents[Handle.Index];
	if (Agent.WindowStepSeconds <= 0) return false;
	auto Add = [&](const FVector3f& Position, float Yaw, float Time)
	{
		Roots.Emplace(FRotator(0, -FMath::RadiansToDegrees(Yaw), 0), TrainingToUnreal(Position));
		Times.Add(Time);
	};
	Roots.Reserve(FutureWindow + 2); Times.Reserve(FutureWindow + 2);
	Add(Agent.WindowPreviousRoot, Agent.WindowPreviousYaw, -Agent.WindowStepSeconds);
	Add(Agent.FedInputRoot, Agent.FedInputYaw, 0);
	const float* Input = Impl->InputBuffer.GetData() + Handle.Index * InputDim + 120;
	for (int32 I = 1; I <= FutureWindow; ++I, Input += 4)
	{
		const float Scale = I * Impl->MaxSpeedScaleFinal;
		const FVector3f Local(Input[0] * Scale, Agent.WindowVerticalVelocity * I * Agent.WindowStepSeconds, Input[1] * Scale);
		Add(Agent.FedInputRoot + TransformRow(Local, Transpose(YawMatrix(Agent.FedInputYaw))),
			Agent.FedInputYaw + FMath::Atan2(Input[3], Input[2]), I * Agent.WindowStepSeconds);
	}
	return true;
}

UPoseableMeshComponent* AProphecyNNLocomotionManager::SetAgentPreviousPoseDebug(
	FProphecyAgentHandle Handle, bool bEnabled, bool bPreferAttack)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Actor) return nullptr;
	if (!bEnabled)
	{
		Impl->PreviousPoseDebugAgents.Remove(Handle.Index);
		if (IsValid(Actor->NNPreviousPoseDebugMesh))
		{
			Actor->RemoveInstanceComponent(Actor->NNPreviousPoseDebugMesh);
			Actor->NNPreviousPoseDebugMesh->DestroyComponent();
			Actor->NNPreviousPoseDebugMesh = nullptr;
		}
		return nullptr;
	}
	if (!IsValid(Actor->NNPreviousPoseDebugMesh))
	{
		const USkeletalMeshComponent* Reference = Actor->GetPoseReferenceMesh();
		if (!Reference || !Reference->GetSkeletalMeshAsset()) return nullptr;
		auto* Mesh = NewObject<UPoseableMeshComponent>(Actor, NAME_None, RF_Transient);
		Actor->AddInstanceComponent(Mesh);
		Mesh->SetSkinnedAssetAndUpdate(Reference->GetSkeletalMeshAsset(), false);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Mesh->SetGenerateOverlapEvents(false);
		Mesh->SetCanEverAffectNavigation(false);
		Mesh->SetCastShadow(false);
		Mesh->SetReceivesDecals(false);
		Mesh->SetAffectDistanceFieldLighting(false);
		Mesh->SetAffectDynamicIndirectLighting(false);
		Mesh->SetVisibleInRayTracing(false);
		Mesh->SetVisibility(false); // No reference-pose flash before the first captured input.
		Mesh->RegisterComponent();
		Mesh->SetComponentTickEnabled(false);
		Actor->NNPreviousPoseDebugMesh = Mesh;
	}
	Impl->PreviousPoseDebugAgents.Add(Handle.Index, bPreferAttack);
	return Actor->NNPreviousPoseDebugMesh;
}

void AProphecyNNLocomotionManager::UpdatePreviousPoseDebug(bool bAttack)
{
	for (auto It = Impl->PreviousPoseDebugAgents.CreateIterator(); It; ++It)
	{
		const int32 Index = It.Key();
		AProphecyAgent* Actor = AgentActors.IsValidIndex(Index) ? AgentActors[Index] : nullptr;
		if (!IsValid(Actor) || !IsValid(Actor->NNPreviousPoseDebugMesh)) { It.RemoveCurrent(); continue; }
		if (!Actor->bNNInferenceEnabled) continue;
		const auto& Agent = Impl->Agents[Index];
		const auto& Slash = Agent.Slash;
		const bool bUseAttack = It.Value() && Slash.bActive && Slash.State.Num() == SlashInputDim;
		if (bUseAttack != bAttack) continue;
		FTransform Pose[FullBodyBoneCount];
		FTransform Carrier;
		if (bUseAttack)
		{
			// Outer Slash tensor: previous lower[0:41], previous upper[82:172].
			// Upper locomotion decoding expects heading coordinates; Slash stores root coordinates.
			float Upper[UpperStateDim];
			FMemory::Memcpy(Upper, Slash.State.GetData() + 82, sizeof(Upper));
			for (int32 Offset : {60, 75})
			{
				WriteStateVec3(Upper, Offset, TransformRow(ReadStateVec3(Upper, Offset), Impl->SeedRootRot));
				WriteRot6(Multiply(MatrixFromRot6(Upper + Offset + 3), Impl->SeedRootRot), Upper + Offset + 3);
				WriteRot6(Multiply(MatrixFromRot6(Upper + Offset + 9), Impl->SeedRootRot), Upper + Offset + 9);
			}
			DecodeLocomotionPose(Impl, Slash.State.GetData(), Upper, false, MakeArrayView(Pose), nullptr, {});
			Carrier = Slash.AnchorWorld;
		}
		else
		{
			// Read the tensors before the upper inference mutates its history.
			DecodeLocomotionPose(Impl, Impl->InputBuffer.GetData() + Index * InputDim + StateDim,
				Impl->UpperInputBuffer.GetData() + Index * UpperInputDim, Agent.bUseWalkPolicy,
				MakeArrayView(Pose), nullptr, {});
			Carrier = SlashComponentWorld(Actor, Agent.WindowPreviousRoot, Agent.WindowPreviousYaw);
		}
		auto* Mesh = Actor->NNPreviousPoseDebugMesh.Get();
		Mesh->SetWorldTransform(Carrier);
		const FReferenceSkeleton& Ref = Mesh->GetSkinnedAsset()->GetRefSkeleton();
		if (Mesh->BoneSpaceTransforms.Num() != Ref.GetNum()) continue;
		TArray<FTransform, TInlineAllocator<128>> ComponentPose;
		ComponentPose.SetNumUninitialized(Ref.GetNum());
		for (int32 Bone = 0; Bone < Ref.GetNum(); ++Bone)
		{
			const int32 Parent = Ref.GetParentIndex(Bone);
			const int32 Source = Impl->BodyNames.IndexOfByKey(Ref.GetBoneName(Bone));
			ComponentPose[Bone] = Source != INDEX_NONE ? Pose[Source]
				: Parent != INDEX_NONE ? Ref.GetRefBonePose()[Bone] * ComponentPose[Parent] : Ref.GetRefBonePose()[Bone];
			Mesh->BoneSpaceTransforms[Bone] = Parent == INDEX_NONE ? ComponentPose[Bone]
				: ComponentPose[Bone].GetRelativeTransform(ComponentPose[Parent]);
		}
		Mesh->RefreshBoneTransforms();
		Mesh->SetVisibility(true);
	}
}

#if !UE_BUILD_SHIPPING
static TAutoConsoleVariable<int32> CVarNNInputTraceFrames(TEXT("Prophecy.NNInputTraceFrames"), 0,
	TEXT("Opt-in input/output capture to Saved/Diagnostics/SlashContacts/nn_inputs.jsonl; step budget."));
#endif
void AProphecyNNLocomotionManager::TraceNNHandoff()
{
#if !UE_BUILD_SHIPPING
	const int32 Remaining = CVarNNInputTraceFrames.GetValueOnGameThread();
	if (Remaining <= 0) return;
	CVarNNInputTraceFrames->Set(Remaining - 1, ECVF_SetByConsole);
	for (int32 I = 0; I < AgentActors.Num(); ++I)
	{
		if (!IsValid(AgentActors[I]) || !AgentActors[I]->bNNInferenceEnabled) continue;
		const auto& A = Impl->Agents[I];
		auto Row = MakeShared<FJsonObject>();
		Row->SetStringField(TEXT("actor"), AgentActors[I]->GetName());
		Row->SetNumberField(TEXT("time"), GetWorld()->GetTimeSeconds());
		Row->SetBoolField(TEXT("attack"), A.Slash.bActive);
		Row->SetBoolField(TEXT("half"), A.Slash.bHalf);
		auto Add = [&](const TCHAR* Name, const float* Data, int32 Count)
		{
			TArray<TSharedPtr<FJsonValue>> Items;
			for (int32 J = 0; J < Count; ++J) Items.Add(MakeShared<FJsonValueNumber>(Data[J]));
			Row->SetArrayField(Name, Items);
		};
		Add(TEXT("lower_input"), Impl->InputBuffer.GetData() + I * InputDim, InputDim);
		Add(TEXT("upper_input"), Impl->UpperInputBuffer.GetData() + I * UpperInputDim, UpperInputDim);
		Add(TEXT("upper_delta"), Impl->UpperOutputBuffer.GetData() + I * UpperStateDim, UpperStateDim);
		Add(TEXT("published_lower"), StateSlice(Impl->PublishedStateBuffer, I), StateDim);
		Add(TEXT("previous_upper"), UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer, I), UpperStateDim);
		const float Root[] = {A.PrevRootPos.X,A.PrevRootPos.Y,A.PrevRootPos.Z,A.PrevRootYaw,
			A.CurRootPos.X,A.CurRootPos.Y,A.CurRootPos.Z,A.CurRootYaw,A.PublishedRoot.X,A.PublishedRoot.Y,A.PublishedRoot.Z,A.PublishedYaw};
		Add(TEXT("roots"), Root, UE_ARRAY_COUNT(Root));
		FString Text;
		FJsonSerializer::Serialize(Row,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));
		FFileHelper::SaveStringToFile(Text+TEXT("\n"),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SlashContacts/nn_inputs.jsonl")),
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
	}
#endif
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNCarrierRebaseTest, "Prophecy.NN.Handoff.CarrierCoordinates",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyNNCarrierRebaseTest::RunTest(const FString& Parameters)
{
	auto Data = MakeUnique<AProphecyNNLocomotionManager::FImpl>();
	Data->SeedRootRot.Rows[0] = FVector3f(1,0,0);
	Data->SeedRootRot.Rows[1] = FVector3f(0,0,-1);
	Data->SeedRootRot.Rows[2] = FVector3f(0,1,0);
	const FVector3f OriginalRootPoint(.3f,.6f,1.2f);
	const FVector3f OriginalHeadingPoint = TransformRow(OriginalRootPoint, Data->SeedRootRot);
	for (float Angle : {0.f, .45f, -1.1f, 2.7f})
	{
		float Lower[StateDim]{}, Upper[UpperStateDim]{};
		for (int32 Offset : {0,9,25}) WriteStateVec3(Lower, Offset, OriginalRootPoint);
		for (int32 Offset : {3,12,18,28,34}) WriteRot6(FMat3f(), Lower + Offset);
		for (int32 Offset : {60,75})
		{
			WriteStateVec3(Upper, Offset, OriginalHeadingPoint);
			WriteRot6(Data->SeedRootRot, Upper + Offset + 3);
			WriteRot6(Data->SeedRootRot, Upper + Offset + 9);
		}
		const FVector3f Delta(.35f,0,-.42f);
		RebaseStateRoot(Lower, *Data, Delta, Angle);
		RebaseUpperHeadingState(Upper, Delta, Angle);
		const FVector3f LowerHeading = TransformRow(ReadStateVec3(Lower, 0), Data->SeedRootRot);
		const FVector3f UpperHeading = ReadStateVec3(Upper, 60);
		TestTrue(TEXT("Upper and lower retain the same point through carrier translation/yaw"), LowerHeading.Equals(UpperHeading, 1.e-5f));
		const FVector3f World = TransformRow(UpperHeading, YawMatrix(-Angle)) + Delta;
		TestTrue(TEXT("World-space point is invariant under carrier change"), World.Equals(OriginalHeadingPoint, 1.e-5f));
		TestTrue(TEXT("Horizontal carrier motion cannot change hand height"), FMath::IsNearlyEqual(UpperHeading.Y, OriginalHeadingPoint.Y, 1.e-5f));
	}
	return true;
}
#endif
