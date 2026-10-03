from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp')
s=p.read_text()
s=s.replace('#include "ProphecyNNLegClamps.h"','#include "ProphecyNNLegClamps.h"\n#include "ProphecyNNPolicyBlend.h"',1)
s=s.replace('\t\tbool bUseWalkPolicy = false;\n\t\tFAnimationLayer', '\t\tbool bUseWalkPolicy = false;\n\t\tFProphecyNNPolicyBlend PolicyBlend;\n\t\tFAnimationLayer',1)
needle='Agent.bUseWalkPolicy = Agent.MoverIntent.mode != prophecy::sim::LocomotionMode::Run;'
# Initialize alongside seed state selection, including bridge admission.
s=s.replace(needle+'\n\t\tAgent.bPreviousPublishedUseWalkPolicy',needle+'\n\t\tAgent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\tAgent.bPreviousPublishedUseWalkPolicy',1)
s=s.replace(needle+'\n\t\t\tconst TArray<TArray<float>>& SeedStates',needle+'\n\t\t\tAgent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\t\tconst TArray<TArray<float>>& SeedStates',1)
s=s.replace(needle+'\n\t\tAgent.FedInputRoot',needle+'''
		if (Agent.Slash.bActive && !Agent.Slash.bHalf)
			Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);
		else if (Agent.PolicyBlend.IsActive() || Agent.PolicyBlend.bTargetWalk != Agent.bUseWalkPolicy)
			Agent.PolicyBlend.Step(Agent.bUseWalkPolicy,
				InputActor ? InputActor->LocomotionWalkToRunBlendSeconds : 0.f,
				InputActor ? InputActor->LocomotionRunToWalkBlendSeconds : 0.f, StepSeconds);
		Agent.FedInputRoot''',1)
s=s.replace('bNeedWalk |= Impl->Agents[AgentIndex].bUseWalkPolicy;','bNeedWalk |= Impl->Agents[AgentIndex].bUseWalkPolicy || Impl->Agents[AgentIndex].PolicyBlend.IsActive();',1)
s=s.replace('bNeedRun |= !Impl->Agents[AgentIndex].bUseWalkPolicy;','bNeedRun |= !Impl->Agents[AgentIndex].bUseWalkPolicy || Impl->Agents[AgentIndex].PolicyBlend.IsActive();',1)
s=s.replace('if (Impl->Agents[AgentIndex].bUseWalkPolicy)\n\t\t\t{','if (Impl->Agents[AgentIndex].bUseWalkPolicy && !Impl->Agents[AgentIndex].PolicyBlend.IsActive())\n\t\t\t{',1)
start=s.index('\t\tfor (int32 Index = 0; Index < StateDim; ++Index) Transition[Index] = CurrentState[Index] + Raw[Index];',s.index('void AProphecyNNLocomotionManager::ApplyOutputBatch'))
end=s.index('\n\t\tAgent.PreviousPublishedRoot',start)
body=s[start:end]
debugstart=body.index('\t\tauto* Debug =')
debugend=body.index('\t\tconst AProphecyAgent* PinActor',debugstart)
body=body[:debugstart]+'\t\tRawPin = FVector2f(Pin[0], Pin[1]);\n'+body[debugend:]
tail=body.index('\t\tAgent.PinProbability =')
body=body[:tail]+'\t\tEffectivePin = FVector2f(Pin[0], Pin[1]);\n'
body='\n'.join('\t'+line for line in body.splitlines())
new='''		// Correct each policy with its own pinning semantics before mixing the poses.
		// The ordinary single-policy path performs exactly one correction.
		auto CorrectPolicy = [&](const float* Raw, bool bWalkPolicy, float* Transition,
			FVector2f& RawPin, FVector2f& EffectivePin)
		{
'''+body+'''
		};
		FVector2f RawPin, EffectivePin;
		FVector2D RawDebug(Raw[41], Raw[42]);
		if (Agent.PolicyBlend.IsActive())
		{
			float WalkState[StateDim];
			FVector2f WalkRawPin, WalkEffectivePin;
			const float* WalkRaw = Impl->WalkOutputBuffer.GetData() + AgentIndex * PolicyOutputDim;
			CorrectPolicy(Raw, false, Transition, RawPin, EffectivePin);
			CorrectPolicy(WalkRaw, true, WalkState, WalkRawPin, WalkEffectivePin);
			const float W = Agent.PolicyBlend.WalkWeight;
			for (const int32 Offset : { 0, 9, 25 }) BlendStateVector(Transition, WalkState, Offset, W);
			for (const int32 Offset : { 3, 12, 18, 28, 34 }) BlendStateRotation(Transition, WalkState, Offset, W);
			for (const int32 Offset : { 24, 40 }) Transition[Offset] = FMath::Lerp(Transition[Offset], WalkState[Offset], W);
			RawPin = FMath::Lerp(RawPin, WalkRawPin, W);
			EffectivePin = FMath::Lerp(EffectivePin, WalkEffectivePin, W);
			RawDebug = FMath::Lerp(RawDebug, FVector2D(WalkRaw[41], WalkRaw[42]), double(W));
		}
		else CorrectPolicy(Raw, bWalkPolicy, Transition, RawPin, EffectivePin);
		Agent.PinProbability = EffectivePin;
		auto* Debug = Impl->PinningDebug.IsEmpty() ? nullptr : Impl->PinningDebug.Find(AgentIndex);
		if (Debug && Debug->Owner.Get() == AgentActors[AgentIndex])
		{
			Debug->Locomotion.RawNetworkOutput = RawDebug;
			Debug->Locomotion.RawPinning = FVector2D(RawPin);
			Debug->Locomotion.EffectivePinning = FVector2D(EffectivePin);
			Debug->Locomotion.SampleTimeSeconds = GetWorld()->GetTimeSeconds();
			Debug->Locomotion.bWalkPolicy = bWalkPolicy;
			Debug->Locomotion.bAppliesToVisibleFeet = !Agent.Slash.bActive || Agent.Slash.bHalf;
		}'''
s=s[:start]+new+s[end:]
p.write_text(s)
