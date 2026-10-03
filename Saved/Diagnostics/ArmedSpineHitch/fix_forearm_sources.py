from pathlib import Path
root=Path('Source/GameAnimationSample3/Private');dest=Path('Saved/Diagnostics/ArmedSpineHitch/forearm-before');dest.mkdir(exist_ok=True)
for name in ['ProphecyNNLocomotionManager.cpp','ProphecyArmedPoseLibrary.cpp']:
 p=root/name;(dest/name).write_bytes(p.read_bytes())
p=root/'ProphecyNNLocomotionManager.cpp';s=p.read_text(encoding='utf-8');s='#include "ProphecyForearmConvention.h"\n'+s
start=s.index('\t\t\tfor(int32 I=0;I<2;++I) for(const auto& Bone:ProphecyFKReturn::Data::Bones)');end=s.index('\n\t\t\treturn Result;',start)
s=s[:start]+'''            for(int32 I=0;I<2;++I)
            {
                const FQuat& Q=ProphecyForearmConvention::IdleLocalUE(I);
                Result[I]=FQuat(-Q.X,Q.Y,-Q.Z,Q.W);
            }'''+s[end:]
start=s.index('\t\tconst FVector LocalAxis(SafeNormal(LocalAxisValue));');end=s.index('\n\t}\n',start)
s=s[:start]+'''        return QuatToMatrix(ProphecyForearmConvention::FromReference(
            FVector(SafeNormal(LocalAxisValue)),FVector(ElbowToHand),Reference));'''+s[end:];p.write_text(s,encoding='utf-8')
p=root/'ProphecyArmedPoseLibrary.cpp';s=p.read_text(encoding='utf-8');s='#include "ProphecyForearmConvention.h"\n'+s
s=s.replace('static TMap<FName,FTarget> Targets;', 'static TMap<FName,FTarget> Targets;\nstatic bool CanonicalTargetForearms=false; // Reload a bank cached before this Live Coding correction.')
s=s.replace('if(!Targets.IsEmpty())return true;', 'if(CanonicalTargetForearms && !Targets.IsEmpty())return true;')
s=s.replace('FTarget Target;\n        for(', 'FTarget Target;TArray<FVector> Positions;\n        for(')
s=s.replace('Target.Rotation.Add(Q.GetNormalized());','Target.Rotation.Add(Q.GetNormalized());\n            Positions.Emplace(Values[0]->AsNumber(),Values[1]->AsNumber(),Values[2]->AsNumber());')
s=s.replace('        NewTargets.Add(FName(Pair.Key),MoveTemp(Target));', '''        // GT controller frames still carry their source forearm roll. Convert
        // both parents before deriving locals, preserving the authored hand Q.
        for(int32 Side=0;Side<2;++Side)
        {
            const int32 Upper=NewNames.IndexOfByKey(FName(Side==0?TEXT("upperarm_l"):TEXT("upperarm_r")));
            const int32 Lower=NewNames.IndexOfByKey(FName(Side==0?TEXT("lowerarm_l"):TEXT("lowerarm_r")));
            const int32 Hand=NewNames.IndexOfByKey(FName(Side==0?TEXT("hand_l"):TEXT("hand_r")));
            if(Upper==INDEX_NONE || Lower==INDEX_NONE || Hand==INDEX_NONE)return false;
            Target.Rotation[Lower]=ProphecyForearmConvention::FromReference(FVector(Side==0?1.:-1.,0,0),
                Positions[Hand]-Positions[Lower],Target.Rotation[Upper]*ProphecyForearmConvention::IdleLocalUE(Side)).GetNormalized();
        }
        NewTargets.Add(FName(Pair.Key),MoveTemp(Target));''')
s=s.replace('GTNames=MoveTemp(NewNames);Targets=MoveTemp(NewTargets);return true;', 'GTNames=MoveTemp(NewNames);Targets=MoveTemp(NewTargets);CanonicalTargetForearms=true;return true;')
p.write_text(s,encoding='utf-8')
