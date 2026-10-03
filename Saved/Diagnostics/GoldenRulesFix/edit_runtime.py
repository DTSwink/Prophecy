from pathlib import Path
root=Path.cwd(); dest=root/'Saved/Diagnostics/GoldenRulesFix/before'; dest.mkdir(parents=True,exist_ok=True)
def edit(name, replacements):
 p=root/name;s=p.read_text(encoding='utf-8-sig');b=dest/p.name
 if not b.exists(): b.write_text(s,encoding='utf-8')
 for a,b in replacements:
  assert a in s,(name,a[:100]);s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')
p='Source/GameAnimationSample3/Private/'
edit(p+'ProphecyNNLocomotionManager.cpp',[
 ('const float StepSeconds = 1.0f / NNUpdateHz;\n\tif (ProphecyAgentTime::HasClocks', 'const float StepSeconds = 1.0f / NNUpdateHz;\n\t// One authored tick per unpaused game tick, independent of FPS/dilation.\n\tconst float TickBudget = GetWorld() && !GetWorld()->IsPaused() && DeltaSeconds > 0\n\t\t? float(ProphecyBlendClock::TickSeconds) : 0.f;\n\tif (ProphecyAgentTime::HasClocks'),
 ('ProphecyAgentTime::Advance(this,DeltaSeconds,StepSeconds','ProphecyAgentTime::Advance(this,TickBudget,StepSeconds'),
 ('Impl->AccumulatedStepSeconds += DeltaSeconds;','Impl->AccumulatedStepSeconds += TickBudget;'),
 ('// Catch-up steps must also see the last accepted return pose. Ordinary','// Policy steps must also see the last accepted return pose. Ordinary'),
 ('UpdateWalkTickPinning(DeltaSeconds);','UpdateWalkTickPinning(TickBudget);'),
 ('Layer.ElapsedSeconds += StepSeconds;\n\t\tLayer.PlaybackTimeSeconds += StepSeconds * Layer.PlayRate;', 'const float LayerSeconds = float(ProphecyBlendClock::Consume(AgentActor, ProphecyBlendClock::EKind::AnimationLayer));\n\t\tLayer.ElapsedSeconds += LayerSeconds;\n\t\tLayer.PlaybackTimeSeconds += LayerSeconds * Layer.PlayRate;'),
 ('Layer.StopElapsedSeconds += StepSeconds;','Layer.StopElapsedSeconds += LayerSeconds;'),
 ('Layer.Reset();','ProphecyBlendClock::Stop(AgentActor, ProphecyBlendClock::EKind::AnimationLayer);\n\tLayer.Reset();'),
 ('Layer.Animation = Animation;','Layer.Animation = Animation;\n\tProphecyBlendClock::Start(AgentActor, ProphecyBlendClock::EKind::AnimationLayer);'),
 ('Layer.bStopping = true;', '// Spend pre-command ticks on playback, not on the new stop fade.\n\tconst float Pending = float(ProphecyBlendClock::Consume(AgentActor, ProphecyBlendClock::EKind::AnimationLayer));\n\tLayer.ElapsedSeconds += Pending;\n\tLayer.PlaybackTimeSeconds += Pending * Layer.PlayRate;\n\tLayer.bStopping = true;')])
edit(p+'ProphecyArmConeLibrary.cpp', [('// Called once per accepted NN prediction, including catch-up steps in one game frame.', '// Accepted policy steps use the fixed game-tick scheduler budget, never hitch catch-up.')])
edit(p+'ProphecyBloodFluidPostProcessController.cpp', [
 ('\tif (bUpdateParametersEveryTick)\n', '\tif (!bBloodFluidPostEnabled && !bShowStencilDebug)\n\t{\n\t\tApplyBloodFluidPostProcessSettings(); // Retire after a direct property edit, too.\n\t\treturn;\n\t}\n\tif (bUpdateParametersEveryTick)\n'),
 ('\tRebuildBlendables();\n\tPushScalarAndVectorParameters();', '\tconst bool Active = bBloodFluidPostEnabled || bShowStencilDebug;\n\tSetActorTickEnabled(Active && (bUpdateParametersEveryTick || bAutoTagBloodNiagaraInEditor));\n\tRebuildBlendables();\n\tif (Active) PushScalarAndVectorParameters();\n\telse if (bAutoTagBloodNiagaraInEditor) TagBloodNiagaraComponentsForStencil();'),
 ('GetWorld() == nullptr || !bAutoTagBloodNiagaraInEditor','GetWorld() == nullptr || !bAutoTagBloodNiagaraInEditor || (!bBloodFluidPostEnabled && !bShowStencilDebug)')])
