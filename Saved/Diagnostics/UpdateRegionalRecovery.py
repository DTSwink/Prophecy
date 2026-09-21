from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp'
s=p.read_text(encoding='utf-8-sig')
def sub(a,b):
    global s
    assert a in s,a
    s=s.replace(a,b)
sub('float PublishedWalkWeight = 1.f, PreviousPublishedWalkWeight = 1.f;',
    'float PublishedWalkWeight = 1.f, PreviousPublishedWalkWeight = 1.f;\n\t\tProphecyAttackRecovery::FWeights RecoveryWeights;\n\t\tFVector2f PublishedLegWalkWeights=FVector2f(1,1), PreviousPublishedLegWalkWeights=FVector2f(1,1);')
sub('Agent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;',
    'Agent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;\n\t\tAgent.RecoveryWeights=ProphecyAttackRecovery::FWeights(Agent.PolicyBlend.WalkWeight);\n\t\tAgent.PublishedLegWalkWeights=Agent.PreviousPublishedLegWalkWeights=Agent.RecoveryWeights.Legs();')
sub('const bool bAttackRecovery = ProphecyAttackRecovery::Step(\n\t\t\tInputActor, Agent.PolicyBlend, Agent.bUseWalkPolicy, StepSeconds);\n\t\tif (!bAttackRecovery && Agent.Slash.bActive && !Agent.Slash.bHalf)',
    'if (Agent.Slash.bActive && !Agent.Slash.bHalf)')
sub('else if (!bAttackRecovery && (Agent.PolicyBlend.IsActive() || Agent.PolicyBlend.bTargetWalk != Agent.bUseWalkPolicy))',
    'else if (Agent.PolicyBlend.IsActive() || Agent.PolicyBlend.bTargetWalk != Agent.bUseWalkPolicy)')
sub('if (!Agent.PolicyBlend.IsActive()) ProphecyBlendClock::Stop(InputActor,ProphecyBlendClock::EKind::Policy);\n\t\t}',
    'if (!Agent.PolicyBlend.IsActive()) ProphecyBlendClock::Stop(InputActor,ProphecyBlendClock::EKind::Policy);\n\t\t}\n\t\tProphecyAttackRecovery::Step(InputActor,Agent.PolicyBlend.WalkWeight,Agent.RecoveryWeights);')
sub('Impl->Agents[AgentIndex].bUseWalkPolicy || Impl->Agents[AgentIndex].PolicyBlend.IsActive()', 'Impl->Agents[AgentIndex].RecoveryWeights.NeedsWalk()')
# Previous replacement can consume a substring of the ! expression.
s=s.replace('!Impl->Agents[AgentIndex].RecoveryWeights.NeedsWalk()', 'Impl->Agents[AgentIndex].RecoveryWeights.NeedsRun()')
sub('Impl->Agents[AgentIndex].bUseWalkPolicy && !Impl->Agents[AgentIndex].PolicyBlend.IsActive()', '!Impl->Agents[AgentIndex].RecoveryWeights.NeedsRun()')
sub('const bool bWalkPolicy = Agent.bUseWalkPolicy;', 'const bool bWalkPolicy = !Agent.RecoveryWeights.NeedsRun();')
sub('Agent.PreviousPublishedWalkWeight = Agent.PublishedWalkWeight;',
    'Agent.PreviousPublishedWalkWeight = Agent.PublishedWalkWeight;\n\t\tAgent.PreviousPublishedLegWalkWeights=Agent.PublishedLegWalkWeights;')
sub('if (Agent.PolicyBlend.IsActive())\n\t\t{\n\t\t\tfloat WalkState[StateDim];',
    'FVector3f LegSourcePelvis[2];\n\t\tFMat3f LegSourcePelvisRotation[2];\n\t\tconst bool bRegional=Agent.RecoveryWeights.Left!=Agent.RecoveryWeights.Pelvis || Agent.RecoveryWeights.Right!=Agent.RecoveryWeights.Pelvis;\n\t\tif (Agent.RecoveryWeights.NeedsBoth())\n\t\t{\n\t\t\tfloat WalkState[StateDim];')
a='''\t\t\tconst float W = Agent.PolicyBlend.WalkWeight;
\t\t\tfor (const int32 Offset : { 0, 9, 25 }) BlendStateVector(Transition, WalkState, Offset, W);
\t\t\tfor (const int32 Offset : { 3, 12, 18, 28, 34 }) BlendStateRotation(Transition, WalkState, Offset, W);
\t\t\tfor (const int32 Offset : { 24, 40 }) Transition[Offset] = FMath::Lerp(Transition[Offset], WalkState[Offset], W);
\t\t\tRawPin = FMath::Lerp(RawPin, WalkRawPin, W);
\t\t\tEffectivePin = FMath::Lerp(EffectivePin, WalkEffectivePin, W);
\t\t\tRawDebug = FMath::Lerp(RawDebug, FVector2D(WalkRaw[41], WalkRaw[42]), double(W));'''
b='''\t\t\tfor (int32 I=0;I<2;++I)
\t\t\t{
\t\t\t\tconst float W=I==0 ? Agent.RecoveryWeights.Left : Agent.RecoveryWeights.Right;
\t\t\t\tif (bRegional)
\t\t\t\t{
\t\t\t\t\tfloat SourcePelvis[9];FMemory::Memcpy(SourcePelvis,Transition,sizeof(SourcePelvis));
\t\t\t\t\tBlendStateVector(SourcePelvis,WalkState,0,W);BlendStateRotation(SourcePelvis,WalkState,3,W);
\t\t\t\t\tLegSourcePelvis[I]=ReadStateVec3(SourcePelvis,0);LegSourcePelvisRotation[I]=MatrixFromRot6(SourcePelvis+3);
\t\t\t\t}
\t\t\t\tconst int32 O=9+16*I;
\t\t\t\tBlendStateVector(Transition,WalkState,O,W);
\t\t\t\tBlendStateRotation(Transition,WalkState,O+3,W);BlendStateRotation(Transition,WalkState,O+9,W);
\t\t\t\tTransition[O+15]=FMath::Lerp(Transition[O+15],WalkState[O+15],W);
\t\t\t\tRawPin[I]=FMath::Lerp(RawPin[I],WalkRawPin[I],W);
\t\t\t\tEffectivePin[I]=FMath::Lerp(EffectivePin[I],WalkEffectivePin[I],W);
\t\t\t\tRawDebug[I]=FMath::Lerp(RawDebug[I],double(WalkRaw[41+I]),double(W));
\t\t\t}
\t\t\tBlendStateVector(Transition,WalkState,0,Agent.RecoveryWeights.Pelvis);
\t\t\tBlendStateRotation(Transition,WalkState,3,Agent.RecoveryWeights.Pelvis);'''
sub(a,b)
sub('if (bReconstructTemperedLegs)\n\t\t{',
    'if (bReconstructTemperedLegs || (bRegional && !Tempering && ProphecyLegChainDebug::IsEnabled(AgentActors[AgentIndex])))\n\t\t{')
sub('const float W = Agent.PolicyBlend.WalkWeight;\n\t\t\tfor (int32 I = 0; I < 2; ++I)\n\t\t\t{',
    'for (int32 I = 0; I < 2; ++I)\n\t\t\t{\n\t\t\t\tconst float W=I==0 ? Agent.RecoveryWeights.Left : Agent.RecoveryWeights.Right;')
sub('ResolveTemperedLeg(*Tempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),',
    'if (bReconstructTemperedLegs) ResolveTemperedLeg(*Tempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),')
sub('FMath::Max(.15f,FMath::Abs(G.KneeOffset.Size()-G.CalfLength)*MinimumReachMultiplier),bOuterReach);',
    'FMath::Max(.15f,FMath::Abs(G.KneeOffset.Size()-G.CalfLength)*MinimumReachMultiplier),bOuterReach);\n\t\t\t\telse if (W!=Agent.RecoveryWeights.Pelvis)\n\t\t\t\t\tResolvePelvisLeg(LegSourcePelvis[I],LegSourcePelvisRotation[I],ReadStateVec3(Transition,0),\n\t\t\t\t\t\tMatrixFromRot6(Transition+3),G,Transition,O,nullptr,false,nullptr,0.f,bOuterReach);')
sub('Agent.PublishedWalkWeight = Agent.PolicyBlend.WalkWeight;',
    'Agent.PublishedWalkWeight = Agent.RecoveryWeights.Pelvis;\n\t\tAgent.PublishedLegWalkWeights=Agent.RecoveryWeights.Legs();')
# Per-limb geometry shared by chain repair, inertia and presentation.
anchor='\tFFootAxes BuildFootAxes(int32 LimbIndex,'
idx=s.index(anchor)
s=s[:idx]+'''\tFLimb BlendLimb(int32 I,float W) const
\t{
\t\tif (W>=1.f) return WalkLimbs[I];
\t\tauto L=Limbs[I];
\t\tif (W>0.f)
\t\t{
\t\t\tfor (int32 A=0;A<2;++A) L.LocalPoleAxes[A]=SafeNormal(FMath::Lerp(L.LocalPoleAxes[A],WalkLimbs[I].LocalPoleAxes[A],W));
\t\t\tL.ToeOffset=FMath::Lerp(L.ToeOffset,WalkLimbs[I].ToeOffset,W);
\t\t\tL.ToeAxis=SafeNormal(FMath::Lerp(L.ToeAxis,WalkLimbs[I].ToeAxis,W));
\t\t}
\t\treturn L;
\t}
'''+s[idx:]
sub('const auto& L=bWalkPolicy ? Impl->WalkLimbs[I] : Impl->Limbs[I];',
    'const auto L=Impl->BlendLimb(I,Agent.PublishedLegWalkWeights[I]);')
sub('Impl->BuildFootAxes(I,Ankle,MatrixFromRot6(Transition+O+3),Transition[O+15],bWalkPolicy)',
    'Impl->BuildFootAxes(L,Ankle,MatrixFromRot6(Transition+O+3),Transition[O+15])')
sub('const FLocomotionClamps& C)\n\t{', 'const FLocomotionClamps& C,const FVector2f* LegWalkWeights=nullptr)\n\t{')
sub('FImpl::FLimb MixedLimb;\n\t\t\t\tconst FImpl::FLimb*',
    'const float WalkWeight=LegWalkWeights ? (*LegWalkWeights)[LimbIndex] : WalkWeightForFallback;\n\t\t\t\tFImpl::FLimb MixedLimb;\n\t\t\t\tconst FImpl::FLimb*')
# Rename incoming scalar to avoid shadowing in the per-limb block.
sub('const float* PoseState, const float* UpperState, float WalkWeight,','const float* PoseState, const float* UpperState, float WalkWeightForFallback,')
sub('auto BuildFullPoseTransforms = [&](const float* Lower, const float* Upper, float WalkWeight,',
    'auto BuildFullPoseTransforms = [&](const float* Lower, const float* Upper, float WalkWeight,const FVector2f& LegWeights,')
sub('DecodeLocomotionPose(Impl, Lower, Upper, WalkWeight, Out, Local, C);','DecodeLocomotionPose(Impl, Lower, Upper, WalkWeight, Out, Local, C,&LegWeights);')
sub('Agent.PreviousPublishedWalkWeight,\n\t\tPreviousComponentTransforms,','Agent.PreviousPublishedWalkWeight,Agent.PreviousPublishedLegWalkWeights,\n\t\tPreviousComponentTransforms,')
sub('Agent.PublishedWalkWeight,\n\t\tComponentTransforms,','Agent.PublishedWalkWeight,Agent.PublishedLegWalkWeights,\n\t\tComponentTransforms,')
p.write_text(s,encoding='utf-8')
