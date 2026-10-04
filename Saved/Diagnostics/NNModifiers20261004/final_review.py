from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyFKReturnLibrary.cpp');s=p.read_text();a=s.index('    FString Groups;\n',s.index('void ProphecyNNModifierDebug::FKReturn'))
b=s.index('\n}',a)
s=s[:a]+'''    if(P->Complete)return;
    const TCHAR* Names[]={TEXT("spine"),TEXT("clav"),TEXT("upperarm"),TEXT("forearm"),TEXT("neck1"),TEXT("neck2"),TEXT("head")};
    FString Groups;
    for(int32 I=0;I<GroupCount;++I)Groups+=FString::Printf(TEXT("%s%s %.3g"),I?TEXT(" | "):TEXT(""),Names[I],W.Momentum[I]);
    R.Add(TEXT("FKMomentum"),TEXT("POSE+HISTORY"),TEXT("FK momentum coefficients (seconds)"),Groups);'''+s[b:];p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyArmedPoseLibrary.cpp');s=p.read_text();h='#include "ProphecyArmedPoseLibrary.h"\n';s=h+s.replace(h,'',1);p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNModifierManager.inl');s=p.read_text().replace('    if(R.UpperLoco)\n','    if(!R.Attack && !R.Defense && !ProphecyArmedPose::OwnsUpperOutput(A))\n');p.write_text(s)
