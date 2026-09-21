from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp')
s=p.read_text(encoding='utf-8')
start=s.index('\t\tAgent.bUseWalkPolicy = ProphecySelectWalkCheckpoint(',s.index('void AProphecyNNLocomotionManager::Build')) if 'void AProphecyNNLocomotionManager::Build' in s else -1
# Locate the per-step block, distinguished from initialization by InputActor.
start=s.rfind('\t\tAgent.bUseWalkPolicy = ProphecySelectWalkCheckpoint(',0,s.index('\t\tAgent.FedInputRoot = Agent.CurRootPos;'))
end=s.index('\t\tAgent.FedInputRoot = Agent.CurRootPos;',start)
block=s[start:end]
assert 'InputActor' in block and 'PolicyBlend.Step' in block
s=s[:start]+s[end:]
needle='\t\t\t\tFutureWindow, Impl->MaxSpeedScaleFinal, StepSeconds, Magic, Agent.WindowVerticalVelocity);'
assert s.count(needle)==1
new='''
		// Select from the trajectory actually fed to the NN, not the mover's
		// pre-magic/pre-limit velocity. Root teleports cannot create false speed.
		const float* NextRoot = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;
		const double SpeedScale = double(Impl->MaxSpeedScaleFinal) / StepSeconds;
		const double RootSpeedSquared = (double(NextRoot[0]) * NextRoot[0] + double(NextRoot[1]) * NextRoot[1]) * SpeedScale * SpeedScale;
'''+block.replace('\t\tif (Agent.Slash.bActive && !Agent.Slash.bHalf)', '\t\tif (ProphecyAutoRun::Above(RootSpeedSquared, ProphecyAutoRun::Threshold(InputActor)))\n\t\t\tAgent.bUseWalkPolicy = false;\n\t\tif (Agent.Slash.bActive && !Agent.Slash.bHalf)',1)
s=s.replace(needle,needle+new)
s=s.replace('ProphecyRootMagic::Remove(AgentActor);','ProphecyRootMagic::Remove(AgentActor);\n\t\tProphecyAutoRun::Remove(AgentActor);')
p.write_text(s,encoding='utf-8')
