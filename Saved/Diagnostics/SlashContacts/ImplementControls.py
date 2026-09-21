from pathlib import Path
base=Path('Source/GameAnimationSample3')
def read(p):return (base/p).read_text(encoding='utf-8')
def write(p,s):(base/p).write_text(s,encoding='utf-8')
p='Public/ProphecyAgent.h';s=read(p)
at='\t/** Author Headbutt arm preparation'
i=s.index(at)
s=s[:i]+'''\t/** Locomotion and half-attack legs: maximum hip-to-foot reach = rest leg length + leeway (cm). */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Locomotion")
	bool SetLocomotionFootClamp(bool bEnabled, float LeewayCm = 0.0f);

	/** Locomotion and half-attack legs: allowed calf length is rest length +/- leeway (cm). */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Locomotion")
	bool SetLocomotionCalfClamp(bool bEnabled, float LeewayCm = 0.0f);

	/** Locomotion hands: maximum elbow-to-hand reach = rest forearm length + leeway (cm). */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Locomotion")
	bool SetLocomotionHandClamp(bool bEnabled, float LeewayCm = 0.0f);

	bool bOverrideLocomotionFootClamp = false, bOverrideLocomotionCalfClamp = false, bOverrideLocomotionHandClamp = false;
	bool bLocomotionFootClamp = false, bLocomotionCalfClamp = false, bLocomotionHandClamp = false;
	float LocomotionFootClampLeewayCm = 0, LocomotionCalfClampLeewayCm = 0, LocomotionHandClampLeewayCm = 0;

	/** Last encoded locomotion root window in world space (cm): previous, current, then 8 future roots.
	 * Time offsets are relative to the current input root. False until the first policy input is built.
	 * During attacks this still reports the background locomotion policy, not the attack ghost. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Locomotion")
	bool GetLocomotionRootWindow(TArray<FTransform>& WorldRoots, TArray<float>& TimeOffsetsSeconds) const;

	/** Opt-in, unticked renderer of the previous pose encoded into the NN inputs.
	 * PreferAttack=true displays the attack ghost while attacking; false always displays locomotion.
	 * Returns the component immediately for Set Material. Disable destroys it and stops all debug pose work. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Debug")
	UPoseableMeshComponent* SetShowNNPreviousPoseDebugMesh(bool bEnabled, bool bPreferAttack = true);

	UPROPERTY(Transient, BlueprintReadOnly, Category="Prophecy|Agent|Debug")
	TObjectPtr<UPoseableMeshComponent> NNPreviousPoseDebugMesh;

'''+s[i:];write(p,s)
p='Private/ProphecyAgent.cpp';s=read(p);i=s.index('void AProphecyAgent::PublishManualFollowerSubstepTargets')
code=''
for part in ['Foot','Calf','Hand']:
 code+=f'''bool AProphecyAgent::SetLocomotion{part}Clamp(bool bEnabled, float LeewayCm)
{{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	bOverrideLocomotion{part}Clamp = true;
	bLocomotion{part}Clamp = bEnabled;
	Locomotion{part}ClampLeewayCm = LeewayCm;
	return true;
}}

'''
code+='''bool AProphecyAgent::GetLocomotionRootWindow(TArray<FTransform>& WorldRoots, TArray<float>& TimeOffsetsSeconds) const
{
	WorldRoots.Reset(); TimeOffsetsSeconds.Reset();
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionRootWindow(AgentHandle, WorldRoots, TimeOffsetsSeconds);
}

UPoseableMeshComponent* AProphecyAgent::SetShowNNPreviousPoseDebugMesh(bool bEnabled, bool bPreferAttack)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager ? Manager->SetAgentPreviousPoseDebug(AgentHandle, bEnabled, bPreferAttack) : nullptr;
}

''';s=s[:i]+code+s[i:];write(p,s)
p='Public/ProphecyNNLocomotionManager.h';s=read(p);i=s.index('\tbool StopAgentNNAttack(')
s=s[:i]+'''	bool GetAgentLocomotionRootWindow(FProphecyAgentHandle Handle, TArray<FTransform>& WorldRoots, TArray<float>& Times) const;
	UPoseableMeshComponent* SetAgentPreviousPoseDebug(FProphecyAgentHandle Handle, bool bEnabled, bool bPreferAttack);
	void UpdatePreviousPoseDebug(bool bAttack);
'''+s[i:];write(p,s)
p='Private/ProphecyNNLocomotionManager.cpp';s=read(p)
# Extract the existing decoder so optional input debugging uses the identical state interpretation, with presentation clamps disabled.
start=s.index('\tint32 CoreSlots[FullBodyBoneCount];',s.index('void AProphecyNNLocomotionManager::PublishAgentPose'))
end=s.index('\tFImpl::FAgent& Agent = Impl->Agents[AgentIndex];',start)
old=s[start:end];body=old[old.index('\t\tFVector3f Positions'):old.rindex('\n\t};')]
core=old[:old.index('\n\tauto BuildFullPoseTransforms')]
fn='''namespace
{
	struct FLocomotionClamps
	{
		bool bClampFoot = false, bClampCalf = false, bClampHand = false;
		float FootClampLengthMultiplier = 1, CalfClampLengthMultiplier = 1, HandClampLengthMultiplier = 1;
		float FootLeeway = 0, CalfLeeway = 0, HandLeeway = 0; // native metres
	};
	void DecodeLocomotionPose(const AProphecyNNLocomotionManager::FImpl* Impl,
		const float* PoseState, const float* UpperState, bool bPoseUsesWalkPolicy,
		TArrayView<FTransform> OutComponentTransforms, TArrayView<FTransform>* OutLocalTransforms,
		const FLocomotionClamps& C)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
'''+core+body+'''
	}
}

'''
for name in ['bClampFoot','bClampCalf','bClampHand','FootClampLengthMultiplier','CalfClampLengthMultiplier','HandClampLengthMultiplier']:
 # only body/core, not struct
 pos=fn.index('\tvoid DecodeLocomotionPose');fn=fn[:pos]+fn[pos:].replace(name,'C.'+name)
fn=fn.replace('Arm.Lengths.Y * HandLengthMultiplier - 1.0e-5f','Arm.Lengths.Y * HandLengthMultiplier + C.HandLeeway')
fn=fn.replace('FMath::Max(0.0f, C.FootClampLengthMultiplier);','FMath::Max(0.0f, C.FootClampLengthMultiplier) + C.FootLeeway;')
fn=fn.replace('End = Positions[Limb.Mid] + Delta * (Length / Delta.Size());','const float Distance = Delta.Size();\n\t\t\t\t\t\tconst float Allowed = FMath::Clamp(Distance, FMath::Max(0.f, Length - C.CalfLeeway), Length + C.CalfLeeway);\n\t\t\t\t\t\tEnd = Positions[Limb.Mid] + Delta * (Allowed / Distance);')
replacement='''	const AProphecyAgent* Controls = AgentActors[AgentIndex];
	FLocomotionClamps C;
'''
for part in ['Foot','Calf','Hand']:
 replacement+=f'''	C.bClamp{part} = Controls->bOverrideLocomotion{part}Clamp ? Controls->bLocomotion{part}Clamp : bClamp{part};
	C.{part}ClampLengthMultiplier = Controls->bOverrideLocomotion{part}Clamp ? 1.f : {part}ClampLengthMultiplier;
	C.{part}Leeway = Controls->bOverrideLocomotion{part}Clamp ? Controls->Locomotion{part}ClampLeewayCm / 100.f : 0.f;
'''
replacement+='''	auto BuildFullPoseTransforms = [&](const float* Lower, const float* Upper, bool bWalk,
		TArrayView<FTransform> Out, TArrayView<FTransform>* Local)
	{
		DecodeLocomotionPose(Impl.Get(), Lower, Upper, bWalk, Out, Local, C);
	};
'''
s=s[:start]+replacement+s[end:]
idx=s.index('void AProphecyNNLocomotionManager::PublishAgentPose');s=s[:idx]+fn+s[idx:]
s=s.replace('bCalfOverride ? ClampActor->bAttackCalfClamp : bClampCalf && CalfClampLengthMultiplier > 0.0f,','bCalfOverride ? ClampActor->bAttackCalfClamp : (bFullAttack ? bClampCalf && CalfClampLengthMultiplier > 0.f : C.bClampCalf && C.CalfClampLengthMultiplier > 0.f),')
s=s.replace('bCalfOverride ? ClampActor->AttackCalfClampLeewayCm : 0.f,','bCalfOverride ? ClampActor->AttackCalfClampLeewayCm : (bFullAttack ? 0.f : C.CalfLeeway * 100.f),')
s=s.replace('bFullAttack ? Agent.Slash.CalfClampLengths : FVector2D::ZeroVector);','bFullAttack ? Agent.Slash.CalfClampLengths : FVector2D(\n\t\t\tImpl->LocalOffsets[Impl->Limbs[0].End].Size() * 100.f * C.CalfClampLengthMultiplier,\n\t\t\tImpl->LocalOffsets[Impl->Limbs[1].End].Size() * 100.f * C.CalfClampLengthMultiplier));')
# Root tensors already retained. Store only their reference frame/time, decode the window on demand.
s=s.replace('float FedInputYaw = 0.0f;','float FedInputYaw = 0.0f;\n\t\tFVector3f WindowPreviousRoot = FVector3f::ZeroVector;\n\t\tfloat WindowPreviousYaw = 0, WindowStepSeconds = 0;')
needle='\t\tconst float* CurrentState = StateSlice(Impl->CurStateBuffer, AgentIndex);'
pos=s.index(needle,s.index('void AProphecyNNLocomotionManager::BuildInputBatch'))
s=s[:pos]+'''		Agent.FedInputRoot = Agent.CurRootPos;
		Agent.FedInputYaw = Agent.CurRootYaw;
		Agent.WindowPreviousRoot = Agent.PrevRootPos;
		Agent.WindowPreviousYaw = Agent.PrevRootYaw;
		Agent.WindowStepSeconds = StepSeconds;
'''+s[pos:]
# Sparse list: no pose allocation, object lookup, or skeleton processing when disabled.
s=s.replace('\tTArray<float> PrevStateBuffer;', '\tTMap<int32, bool> PreviousPoseDebugAgents; // value: prefer active attack input\n\tTArray<float> PrevStateBuffer;')
assert 'PreviousPoseDebugAgents;' in s
s=s.replace('\tBuildUpperInputBatch();','\tBuildUpperInputBatch();\n\tif (!Impl->PreviousPoseDebugAgents.IsEmpty()) UpdatePreviousPoseDebug(false);',1)
# Correct the same heading-vs-root translation mistake in blocked-root rebases.
for name in ['PreviousStateRootDelta','CurrentStateRootDelta','PublishedStateRootDelta','PreviousPublishedStateRootDelta']:
 s=s.replace('TransformRow('+name+', Impl->SeedRootRot),',name+',')
write(p,s)
