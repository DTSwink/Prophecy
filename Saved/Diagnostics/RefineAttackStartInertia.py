from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp');s=p.read_text(encoding='utf-8')
s=s.replace('Entries.Remove(A);History.Remove(A);','Entries.Remove(A);')
s=s.replace('{Cancel(A);Configs.Remove(A);Baselines.remove(A);}', '{Cancel(A);History.Remove(A);Configs.Remove(A);Baselines.remove(A);}') if False else s
s=s.replace('{Cancel(A);Configs.Remove(A);Baselines.Remove(A);}', '{Cancel(A);History.Remove(A);Configs.Remove(A);Baselines.Remove(A);}')
s=s.replace('{Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))','{Cancel(A);History.Remove(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))')
s=s.replace('{Cancel(A);Configs.Remove(A);return true;}','{Cancel(A);History.Remove(A);Configs.Remove(A);return true;}')
# Pure advance path accepts a tick token; production uses GFrameCounter, tests do not mutate it.
a=s.index('void Update(const AProphecyAgent* A,int32 Id)');b=s.index('void Apply(int32 Id',a)
block=s[a:b]
block=block.replace('void Update(const AProphecyAgent* A,int32 Id)','static void Advance(const AProphecyAgent* A,int32 Id,const FTransform& Authored,uint64 Tick)')
block=block.replace('    if(!A->GetWorld() || A->GetWorld()->IsPaused())return;\n','')
block=block.replace('    FTransform Authored;if(!Sample(Id,Authored))return;\n','').replace('GFrameCounter','Tick')
s=s[:a]+block+'''void Update(const AProphecyAgent* A,int32 Id)
{
    if(Configs.IsEmpty() || !Configs.Contains(A) || !A->GetWorld() || A->GetWorld()->IsPaused())return;
    if(const auto* H=History.Find(A))if(H->Tick==GFrameCounter)return;
    FTransform Authored;if(Sample(Id,Authored))Advance(A,Id,Authored,GFrameCounter);
}
'''+s[b:]
p.write_text(s,encoding='utf-8')
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaMath.h');s=p.read_text();s=s.replace('const FVector OldHip=Thigh.GetLocation(),OldKnee=Calf.GetLocation(),OldFoot=Foot.GetLocation();','const FVector OldHip=Thigh.GetLocation(),OldKnee=Calf.GetLocation(),OldFoot=Foot.GetLocation();\n    if(Hip.Equals(OldHip,1.e-10))return;');p.write_text(s,encoding='utf-8')
