from pathlib import Path
root=Path(__file__).resolve().parents[2]
def edit(n,a,b):
    p=root/n;s=p.read_text(encoding='utf-8-sig');assert a in s,(n,a);p.write_text(s.replace(a,b),encoding='utf-8')
base='Source/GameAnimationSample3/Private/'
edit(base+'ProphecyNNAgentReset.inl','A.PublishedWalkWeight = A.PreviousPublishedWalkWeight = A.PolicyBlend.WalkWeight;',
     'A.PublishedWalkWeight = A.PreviousPublishedWalkWeight = A.PolicyBlend.WalkWeight;\n    A.RecoveryWeights=ProphecyAttackRecovery::FWeights(A.PolicyBlend.WalkWeight);\n    A.PublishedLegWalkWeights=A.PreviousPublishedLegWalkWeights=A.RecoveryWeights.Legs();')
edit(base+'ProphecyNNDodgeRuntime.inl','Agent.PreviousPublishedWalkWeight=Agent.PublishedWalkWeight;',
     'Agent.PreviousPublishedWalkWeight=Agent.PublishedWalkWeight;Agent.PreviousPublishedLegWalkWeights=Agent.PublishedLegWalkWeights;')
edit(base+'ProphecyNNDodgeRuntime.inl','Agent.PublishedWalkWeight=P.Category==0?1.f:0.f;',
     'Agent.PublishedWalkWeight=P.Category==0?1.f:0.f;Agent.PublishedLegWalkWeights=FVector2f(Agent.PublishedWalkWeight,Agent.PublishedWalkWeight);')
edit(base+'ProphecyHandInertiaRuntime.inl','Agent.PublishedWalkWeight,MakeArrayView(Pose),nullptr,Unclamped);',
     'Agent.PublishedWalkWeight,MakeArrayView(Pose),nullptr,Unclamped,&Agent.PublishedLegWalkWeights);')
edit(base+'ProphecyHandInertiaRuntime.inl','MakeArrayView(Previous),nullptr,Unclamped);',
     'MakeArrayView(Previous),nullptr,Unclamped,&Agent.PreviousPublishedLegWalkWeights);')
edit(base+'ProphecyNNDefenseRuntime.inl','Agent.PublishedWalkWeight,MakeArrayView(FrozenComponent),nullptr,C);',
     'Agent.PublishedWalkWeight,MakeArrayView(FrozenComponent),nullptr,C,&Agent.PublishedLegWalkWeights);')
edit(base+'ProphecyNNInputDebug.inl','if (A.PolicyBlend.IsActive())','if (A.RecoveryWeights.NeedsBoth())')
edit(base+'ProphecyNNInputDebug.inl','Row->SetNumberField(TEXT("walk_weight"), A.PolicyBlend.WalkWeight);',
     'Row->SetNumberField(TEXT("walk_weight"), A.RecoveryWeights.Pelvis);\n        Row->SetNumberField(TEXT("left_walk_weight"),A.RecoveryWeights.Left);\n        Row->SetNumberField(TEXT("right_walk_weight"),A.RecoveryWeights.Right);')
edit(base+'ProphecyBlendClock.cpp','FProphecyNNPolicyBlend Blend;bool Walk=true;', 'ProphecyAttackRecovery::FWeights Weights;')
edit(base+'ProphecyBlendClock.cpp','ProphecyAttackRecovery::Step(Agent,Blend,Walk,1.f/30.f);','ProphecyAttackRecovery::Step(Agent,1.f,Weights);')
edit(base+'ProphecyBlendClock.cpp','Blend.WalkWeight','Weights.Pelvis')
edit(base+'ProphecyBlendClock.cpp','!Blend.IsActive() && Weights.Pelvis==1','Weights.Pelvis==1 && Weights.Left==1 && Weights.Right==1')
