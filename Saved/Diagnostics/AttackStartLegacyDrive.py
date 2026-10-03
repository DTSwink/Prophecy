from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAgent.cpp');s=p.read_text(encoding='utf-8');a=s.index('void AProphecyAgent::ApplyAbsoluteWorldMagnetization(');b=s.index('\nvoid ',a+10);block=s[a:b]
old='\tfloat MaximumPositionErrorCm = 0.0f;'
assert old in block
block=block.replace(old,'''    TArray<FName> InertiaNames;TArray<FTransform> InertiaFuture,InertiaTargets;
    if(ProphecyAttackStartInertia::Active(AnimInstance->AgentId))
    {
        float InertiaAlpha;
        ReadNNFutureWorldPose(InertiaNames,InertiaFuture,InertiaTargets,InertiaAlpha);
    }
'''+old,1)
old='\t\tconst FTransform ActualBody = Body->GetUnrealWorldTransform();';assert old in block
block=block.replace(old,'''        if(!InertiaNames.IsEmpty())
        {
            const int32 CorrectedIndex=InertiaNames.IndexOfByKey(BodySetup->BoneName);
            if(InertiaTargets.IsValidIndex(CorrectedIndex))BodyTarget=InertiaTargets[CorrectedIndex];
        }
'''+old,1)
s=s[:a]+block+s[b:];p.write_text(s,encoding='utf-8')
