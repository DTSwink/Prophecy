from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[2]
header='Source/GameAnimationSample3/Private/ProphecyHandChainMath.h'
old=subprocess.check_output(['git','show','HEAD:'+header],cwd=root)
(root/header).write_bytes(old)
p=root/'Source/GameAnimationSample3/Private/ProphecySlashReturnLibrary.cpp'
s=p.read_text(encoding='utf-8')
lines=[line for line in s.splitlines(keepends=True) if not any(x in line for x in (
 'static TAutoConsoleVariable<int32> ContinuousArmTwist(',
 'struct FArmTwistHistory ',
 'static TMap<TWeakObjectPtr<const AProphecyAgent>,FArmTwistHistory>',
 'Clean(PrimaryTwists);Clean(ExtraTwists);',
 'Clean(PrimaryBends);Clean(ExtraBends);'))]
s=''.join(lines)
for v in ('ExtraTwists','ExtraBends','PrimaryTwists','PrimaryBends'):s=s.replace(v+'.Remove(A);','')
a=s.index('    auto& Twist=(Extra ? ExtraTwists : PrimaryTwists).FindOrAdd(A);')
b=s.index('    // Fade the hinge guidance',a)
s=s[:a]+s[b:]
s=s.replace(',Alpha,&Twist.First,ContinuousTwist,&Bend.First);',',Alpha);')
s=s.replace('FMath::Lerp(RotationStep,1.,Alpha),&Twist.Second,ContinuousTwist,&Bend.Second);','FMath::Lerp(RotationStep,1.,Alpha));')
s=s.replace('#if WITH_EDITOR\n    const FTransform FirstSolveShoulder=GuideShoulder,FirstSolveElbow=GuideElbow,FirstSolveWrist=GuideWrist;\n#endif\n','')
a=s.index('        UE_LOG(LogTemp,Display,TEXT("SlashSolveAudit,')
b=s.index('        UE_LOG(LogTemp,Display,TEXT("SlashElbowAudit,',a)
s=s[:a]+s[b:]
a=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnTwistTest,')
b=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnRotationBlendTest,',a)
s=s[:a]+s[b:]
assert not any(x in s for x in ('ContinuousTwist','ContinuousArmTwist','FTwistHistory','SolveInputShoulder','FirstSolveShoulder','PrimaryTwists','ExtraBends'))
p.write_text(s,encoding='utf-8')
assert subprocess.check_output(['git','diff','--',header],cwd=root)==b''
print('Arm-chain header exactly matches HEAD. Removed runtime winding histories, added call arguments and corresponding experimental test.')
