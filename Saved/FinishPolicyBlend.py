from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp');s=p.read_text()
s=s.replace('FProphecyNNPolicyBlend PolicyBlend;','FProphecyNNPolicyBlend PolicyBlend;\n\t\tfloat PublishedWalkWeight = 1.f, PreviousPublishedWalkWeight = 1.f;',1)
s=s.replace('Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\tAgent.bPrevious', 'Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\tAgent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;\n\t\tAgent.bPrevious',1)
s=s.replace('Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\t\tconst TArray', 'Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);\n\t\t\tAgent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;\n\t\t\tconst TArray',1)
s=s.replace('Agent.bPreviousPublishedUseWalkPolicy = Agent.bPublishedUseWalkPolicy;','Agent.bPreviousPublishedUseWalkPolicy = Agent.bPublishedUseWalkPolicy;\n\t\tAgent.PreviousPublishedWalkWeight = Agent.PublishedWalkWeight;')
s=s.replace('Agent.bPublishedUseWalkPolicy = bWalkPolicy;', 'Agent.bPublishedUseWalkPolicy = bWalkPolicy;\n\t\tAgent.PublishedWalkWeight = Agent.PolicyBlend.WalkWeight;',1)
# The two checkpoint contracts also have different calf hinge calibration.
# Decode with a continuous calibration weight rather than toggling it on the request frame.
a=s.index('\tvoid DecodeLocomotionPose(');b=s.index('\nvoid AProphecyNNLocomotionManager::PublishAgentPose',a)
t=s[a:b];t=t.replace('bool bPoseUsesWalkPolicy','float WalkWeight',1)
t=t.replace('const FImpl::FLimb& Limb = bPoseUsesWalkPolicy\n\t\t\t\t\t? Impl->WalkLimbs[LimbIndex]\n\t\t\t\t\t: Impl->Limbs[LimbIndex];','''FImpl::FLimb MixedLimb;
				const FImpl::FLimb* SelectedLimb = WalkWeight >= 1.f ? &Impl->WalkLimbs[LimbIndex] : &Impl->Limbs[LimbIndex];
				if (WalkWeight > 0.f && WalkWeight < 1.f)
				{
					MixedLimb = Impl->Limbs[LimbIndex];
					const auto& WalkLimb = Impl->WalkLimbs[LimbIndex];
					for (int32 Axis = 0; Axis < 2; ++Axis)
						MixedLimb.LocalPoleAxes[Axis] = SafeNormal(FMath::Lerp(MixedLimb.LocalPoleAxes[Axis], WalkLimb.LocalPoleAxes[Axis], WalkWeight));
					MixedLimb.ToeOffset = FMath::Lerp(MixedLimb.ToeOffset, WalkLimb.ToeOffset, WalkWeight);
					MixedLimb.ToeAxis = SafeNormal(FMath::Lerp(MixedLimb.ToeAxis, WalkLimb.ToeAxis, WalkWeight));
					SelectedLimb = &MixedLimb;
				}
				const FImpl::FLimb& Limb = *SelectedLimb;''',1)
assert 'bPoseUsesWalkPolicy' not in t
s=s[:a]+t+s[b:]
s=s.replace('const float* Lower, const float* Upper, bool bWalk,','const float* Lower, const float* Upper, float WalkWeight,',1)
s=s.replace('DecodeLocomotionPose(Impl, Lower, Upper, bWalk,','DecodeLocomotionPose(Impl, Lower, Upper, WalkWeight,',1)
s=s.replace('Agent.bPreviousPublishedUseWalkPolicy,\n\t\tPreviousComponentTransforms','Agent.PreviousPublishedWalkWeight,\n\t\tPreviousComponentTransforms',1)
s=s.replace('Agent.bPublishedUseWalkPolicy,\n\t\tComponentTransforms','Agent.PublishedWalkWeight,\n\t\tComponentTransforms',1)
p.write_text(s)
