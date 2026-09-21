from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp')
s=p.read_text()
start=s.index('\t\tconst float* Future = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;',s.index('void AProphecyNNLocomotionManager::ApplyOutputBatch'))
end=s.index('\n\t}\n\tSwap(Impl->PrevStateBuffer',start)
block=s[start:end]
rebase='\t\tFMemory::Memcpy(NextState, Transition, StateDim * sizeof(float));\n\t\tRebaseStateRoot(NextState, *Impl, NextRootDelta, NextYawDelta);'
assert rebase in block
block=block.replace(rebase,'\t\tif (NextState) RebaseStateRoot(NextState, *Impl, NextRootDelta, NextYawDelta);')
helper='''void AProphecyNNLocomotionManager::AdvanceAgentMover(int32 AgentIndex, float StepSeconds)
{
    auto& Agent=Impl->Agents[AgentIndex];
    auto& MoverTargets=ResolvedMoverTargets.FindChecked(this);
    float* NextState=Agent.DefensePose && Agent.DefensePose->bDodge ? nullptr : StateSlice(Impl->NextStateBuffer,AgentIndex);
'''+block+'\n}\n\n'
s=s[:start]+'\t\tFMemory::Memcpy(NextState, Transition, StateDim * sizeof(float));\n\t\tAdvanceAgentMover(AgentIndex,StepSeconds);'+s[end:]
point=s.index('void AProphecyNNLocomotionManager::ApplyOutputBatch')
s=s[:point]+helper+s[point:]
# Drop unused reference in original function only.
s=s.replace('void AProphecyNNLocomotionManager::ApplyOutputBatch(float StepSeconds)\n{\n\tTArray<FResolvedMoverTarget>& MoverTargets = ResolvedMoverTargets.FindChecked(this);','void AProphecyNNLocomotionManager::ApplyOutputBatch(float StepSeconds)\n{')
start=s.index('void AProphecyNNLocomotionManager::BuildInputBatch')
end=s.index('bool AProphecyNNLocomotionManager::RunModelBatch',start)
section=s[start:end]
section=section.replace('\t\tif (Agent.DefensePose && Agent.DefensePose->bDodge) continue;\n','',1)
s=s[:start]+section+s[end:]
old='FMemory::Memcpy(StateSlice(Impl->NextStateBuffer,AgentIndex),StateSlice(Impl->CurStateBuffer,AgentIndex),StateDim*sizeof(float));\n\t\t\tcontinue;'
assert old in s
s=s.replace(old,old.replace('\n\t\t\tcontinue;','\n\t\t\tAdvanceAgentMover(AgentIndex,StepSeconds);\n\t\t\tcontinue;'),1)
s=s.replace(' && !Agent.DefensePose && (!Agent.Slash.bActive || Agent.Slash.bHalf)',' && (!Agent.Slash.bActive || Agent.Slash.bHalf)')
p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNInputDebug.inl')
s=p.read_text().replace('\tif (Agent.DefensePose && Agent.DefensePose->bDodge) return false;\n','',1)
p.write_text(s)
