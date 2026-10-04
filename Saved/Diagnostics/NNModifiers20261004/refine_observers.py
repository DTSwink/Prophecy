from pathlib import Path
r=Path('Source/GameAnimationSample3/Private')
p=r/'ProphecyNNModifierInputs.cpp';s=p.read_text().replace('for(const auto* Body:Asset->SkeletalBodySetups)','for(const USkeletalBodySetup* Body:Asset->SkeletalBodySetups)');s=s.replace('{TEXT("Prophecy.KneeSmoothing.SpecialOrder"),1},','{TEXT("Prophecy.KneeSmoothing.SpecialOrder"),1},{TEXT("Prophecy.Debug.SharedCalfRecovery"),1},\n        {TEXT("Prophecy.Recovery.LocomotionLengthTarget"),1},{TEXT("Prophecy.Recovery.LengthInterpolation"),1},{TEXT("Prophecy.Recovery.UpperLengthBlend"),1},');p.write_text(s)
p=r/'ProphecyNNModifierDebug.h';s=p.read_text().replace('bool Attack=false,Half=false,Defense=false,Dodge=false,LowerLoco=false,UpperLoco=false;','bool Attack=false,Half=false,Defense=false,Dodge=false,LowerLoco=false,UpperLoco=false;\n    bool WalkFeet=false,Regional=false,RecoveryPresentation=true;');p.write_text(s)
p=r/'ProphecyNNModifierManager.inl';s=p.read_text().replace('if(!Impl || !A || ResolveAgent(A->GetAgentHandle())!=A)return false;','if(!Impl || !A || ResolveAgent(A->GetAgentHandle())!=A || !Impl->Agents.IsValidIndex(A->GetAgentHandle().Index))return false;')
s=s.replace('float Interval;bool Interpolate;','R.WalkFeet=S.RecoveryWeights.Left>0 || S.RecoveryWeights.Right>0;\n    R.Regional=S.RecoveryWeights.Left!=S.RecoveryWeights.Pelvis || S.RecoveryWeights.Right!=S.RecoveryWeights.Pelvis;\n    R.RecoveryPresentation=UsePresentationRecovery();\n    float Interval=0;bool Interpolate=false;')
s=s.replace('if(R.UpperLoco)\n', '''const float Dilation=GetAgentTimeDilation(A->GetAgentHandle());
    if(Dilation!=1)R.Add(TEXT("AgentClock"),TEXT("CLOCK"),TEXT("Agent NN / physics time scale"),FString::Printf(TEXT("%.3g | blend durations remain 60 game ticks"),Dilation));
    if(R.UpperLoco)
''')
s=s.replace('if(ProphecyAttackControls::IsStatic(A))', '''bool Parry=false,Dodge=false;GetAgentAttackDefenseState(A->GetAgentHandle(),Parry,Dodge);
        if(Parry||Dodge)R.Add(TEXT("AttackResponse"),TEXT("INPUT"),TEXT("Defender response conditioning"),FString::Printf(TEXT("parry %d dodge %d"),Parry,Dodge));
        R.Add(TEXT("AttackTarget"),TEXT("INPUT"),TEXT("Attack target conditioning"),FString::Printf(TEXT("requested %s | %s"),*Slash.TargetWorld.ToCompactString(),R.Half?TEXT("real-pelvis radius clamp, mapped to ghost carrier"):TEXT("anchored attack frame")));
        if(ProphecyAttackControls::IsStatic(A))''')
p.write_text(s)
for name,func in [('ProphecyAttackStartFKCore.inl','Attack-start FK core inertia'),('ProphecyAttackStartHandInertia.cpp','Attack-start hand inertia')]:
 p=r/name;s=p.read_text().replace('TEXT("POSE+HISTORY"),TEXT("'+func+'")','R.Half?TEXT("POSE"):TEXT("POSE+HISTORY"),TEXT("'+func+'")');p.write_text(s)
p=r/'ProphecyHandInertiaLibrary.cpp';s=p.read_text().replace('TEXT("POSE+HISTORY"),I?TEXT("Right hand inertia")','R.Half?TEXT("POSE"):TEXT("POSE+HISTORY"),I?TEXT("Right hand inertia")');p.write_text(s)
p=r/'ProphecyWalkPinningLibrary.cpp';s=p.read_text().replace('if(!R.LowerLoco)return;','if(!R.LowerLoco || !R.WalkFeet)return;');p.write_text(s)
p=r/'ProphecyLowerTemperingLibrary.cpp';s=p.read_text().replace('#include "ProphecyNNModifierDebug.h"','#include "ProphecyNNModifierDebug.h"\n#include "ProphecyKickFootLeeway.h"')
s=s.replace('TEXT("KneeRecovery"),TEXT("POSE+HISTORY")','TEXT("KneeRecovery"),R.RecoveryPresentation?TEXT("PRESENT"):TEXT("POSE+HISTORY")')
s=s.replace('if(ProphecyLegChainDebug::IsEnabled(R.Agent))\n        R.Add', 'if(ProphecyLegChainDebug::IsEnabled(R.Agent) && (Settings.Contains(R.Agent) || R.Regional || ProphecyKickFootLeeway::HasLengthReturn(R.Agent)))\n        R.Add')
s=s.replace('TEXT("LegReconstruction"),TEXT("CONSTRAINT")','TEXT("LegReconstruction"),R.RecoveryPresentation?TEXT("PRESENT"):TEXT("POSE+HISTORY")');p.write_text(s)
