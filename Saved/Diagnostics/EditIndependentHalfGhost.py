from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNSlashRuntime.inl')
s=p.read_text(encoding='utf-8')
start=s.index('\tstruct FHalfAttackGT')
end=s.index('\n\tvoid CatchUpFullAttackRoot',start)
s=s[:start]+'''\tvoid ResolveSlashTarget(const AProphecyNNLocomotionManager::FImpl& Impl,
\t\tconst AProphecyAgent* Actor, int32 Index, FVector& EffectiveWorld, FVector& GhostWorld)
\t{
\t\t// The independent ghost aims at the requested world point. Recomputing it
\t\t// through either pelvis makes a stationary target rotate with the attacker.
\t\tEffectiveWorld = GhostWorld = Impl.Agents[Index].Slash.TargetWorld;
\t}
'''+s[end:]
start=s.index('\tconst FHalfAttackGT* HalfGT =')
end=s.index('\tconst FTransform Carrier',start)
s=s[:start]+s[end:]
start=s.index('\tif (HalfGT)')
end=s.index('\n\t\tTArray<FTransform, TInlineAllocator<FullBodyBoneCount>> Previous;',start)
s=s[:start]+'''\t// Both modes start from the current agent, including its previous world pose.
\t// Keep this carrier fixed for the lifetime of the independent attack history.
\t{'''+s[end:]
s=s.replace('// Apply once after either full-body encoding or half-attack GT ghost seeding.','// Static initialization remains the explicit opt-in to discard entry velocity.')
s=s.replace('\tif (ProphecyAttackControls::IsStatic(Actor)) ProphecyAttackControls::MakeHistoryStatic(Slash.State);','\tif (ProphecyAttackControls::IsStatic(Actor)) ProphecyAttackControls::MakeHistoryStatic(Slash.State);\n\tif (bHalf) Slash.bHasPose = Slash.bNeedsFeedback = true;')
s=s.replace('\t\t\t\t\tfor (int32 Bone:{Arm.Start,Arm.Mid,Arm.End})','\t\t\t\t\t// Half-attack presentation must not feed the moving real carrier back\n\t\t\t\t\t// into the independent ghost. Full attacks retain their inertia feedback.\n\t\t\t\t\tif (!Slash.bHalf)\n\t\t\t\t\t{\n\t\t\t\t\tfor (int32 Bone:{Arm.Start,Arm.Mid,Arm.End})')
s=s.replace('Slash.GhostPose[Bone]=Slash.bHalf ? World.GetRelativeTransform(HalfMount*Carrier)*Slash.GhostPose[0]\n\t\t\t\t\t\t\t: World.GetRelativeTransform(Slash.AnchorWorld);','Slash.GhostPose[Bone]=World.GetRelativeTransform(Slash.AnchorWorld);')
s=s.replace('\t\t\t\t\tStoreInertiaArm(*Impl,I,Slash.GhostPose,FMat3f(),Slash.State.GetData()+172);','\t\t\t\t\tStoreInertiaArm(*Impl,I,Slash.GhostPose,FMat3f(),Slash.State.GetData()+172);\n\t\t\t\t\t}')
p.write_text(s,encoding='utf-8',newline='\n')
