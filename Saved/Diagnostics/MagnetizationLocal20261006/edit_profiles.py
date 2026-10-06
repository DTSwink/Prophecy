from pathlib import Path
root=Path('Source/GameAnimationSample3')
p=root/'Public/ProphecyPhysicalProfileLibrary.h';s=p.read_text();s=s.replace('FName SnapshotName = NAME_None);','FName SnapshotName = NAME_None, float HoldOutTime = 0.f);').replace('FName SnapshotName=NAME_None);','FName SnapshotName=NAME_None,float HoldOutTime=0.f);');s=s.replace('SavePhysicalProfileSnapshot(AProphecyAgent* Agent, FName SnapshotName = NAME_None, float HoldOutTime = 0.f)','SavePhysicalProfileSnapshot(AProphecyAgent* Agent, FName SnapshotName = NAME_None)')
s=s.replace('    /** Print one line', '''    /** 0 follows the actual physical parent; 1 keeps world targets. Pelvis stays global.
     * Intermediate values use one blended target and one servo. Default is 1. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool SetMagnetizationMode(AProphecyAgent* Agent, UPARAM(meta=(ClampMin="0",ClampMax="1")) float Mode=1.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static float GetMagnetizationMode(AProphecyAgent* Agent);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool BlendMagnetizationModeToSnapshot(AProphecyAgent* Agent,float DurationSeconds=1.f,
        FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    /** Print one line''',1)
s=s.replace('Duration <= 0 restores immediately.', 'Hold Out Time delays interpolation without changing current values. Duration <= 0 snaps after the hold.').replace('Also captures shared left/right clamps','Also captures magnetization mode and shared left/right clamps')
p.write_text(s)
p=root/'Public/ProphecyClampProfileLibrary.h';s=p.read_text().replace('EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All);','EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All,float HoldOutTime=0.f);');p.write_text(s)
p=root/'Private/ProphecyPhysicalContext.h';s=p.read_text().replace('Magnetization, Feedback, Damping','Magnetization, Feedback, Damping, Mode');s=s.replace('bool IsApplying();','bool IsApplying();\nfloat MagnetizationMode(const AProphecyAgent* Agent);');p.write_text(s)
p=root/'Private/ProphecyPhysicalContext.cpp';s=p.read_text();s=s.replace('double Begin=0,Duration=0;','double Begin=0,Duration=0,Hold=0;')
s=s.replace('if (Duration<=0) return;','if ((Duration<=0 && Hold<=0) || Clock+1.e-9<Begin) return;',1).replace('const double T=Clock-Begin+1.e-9>=Duration','const double T=Duration<=0 || Clock-Begin+1.e-9>=Duration',1)
s=s.replace('Value=Target; Duration=0;', 'Value=Target; Duration=0; Hold=0;',1)
s=s.replace('void Write(FValue NewValue,float Seconds,double Clock)','void Write(FValue NewValue,float Seconds,double Clock,float HoldSeconds=0)')
s=s.replace('Target=NewValue; Begin=Clock;','Target=NewValue; Hold=HoldSeconds; Begin=Clock+Hold;')
s=s.replace('Value=Duration>0 ? FValue{Start.Scales,true} : Target;','if(Hold<=0) Value=Duration>0 ? FValue{Start.Scales,true} : Target;')
s=s.replace('if (Attack) return {Kind==','if (Kind==EKind::Mode) return Cells[0].Value;\n        if (Attack) return {Kind==',1)
s=s.replace('if (Cell.Duration>0) return true','if (Cell.Duration>0 || Cell.Hold>0) return true')
s=s.replace('static bool Applying=false;', '''static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Modes;
static const FName ModeBone(TEXT("__MagnetizationMode"));
float MagnetizationMode(const AProphecyAgent* Agent)
{ const auto* V=Modes.IsEmpty()?nullptr:Modes.Find(Agent);return V?*V:1.f; }
static bool Applying=false;''')
s=s.replace('States.Remove(Agent); Snapshots.Remove(Agent);','Modes.Remove(Agent);States.Remove(Agent); Snapshots.Remove(Agent);',1)
s=s.replace('if (Entry.Kind==EKind::Feedback)\n        Agent.', 'if (Entry.Kind==EKind::Mode)\n    { if(Value.Scales.X==1.f) Modes.Remove(&Agent);else Modes.Add(&Agent,Value.Scales.X); }\n    else if (Entry.Kind==EKind::Feedback)\n        Agent.',1)
s=s.replace('Universal && Kind!=EKind::Damping &&', 'Universal && Kind!=EKind::Damping && Kind!=EKind::Mode &&')
s=s.replace('FValue Initial;\n    if (Kind==EKind::Feedback)', 'FValue Initial;\n    if(Kind==EKind::Mode) Initial={{MagnetizationMode(&Agent),MagnetizationMode(&Agent)},true};\n    else if (Kind==EKind::Feedback)',1)
s=s.replace('else Agent.CancelBodyMagnetizationBlend(Bone);','else if(Kind!=EKind::Mode) Agent.CancelBodyMagnetizationBlend(Bone);')
s=s.replace('Cell.Duration=Duration; Cell.Begin=', 'Cell.Hold=0;Cell.Duration=Duration; Cell.Begin=')
s=s.replace('Cell.Duration=0; }','Cell.Duration=0;Cell.Hold=0; }')
s=s.replace('if (Kind==EKind::Magnetization)\n    {\n        FProphecyBodyMagnetizationSettings', 'if(Kind==EKind::Mode) Value={{MagnetizationMode(&Agent),MagnetizationMode(&Agent)},true};\n    else if (Kind==EKind::Magnetization)\n    {\n        FProphecyBodyMagnetizationSettings',1)
s=s.replace('TArray<FEntry> Saved;\n    TArray<FName> Bodies;', 'TArray<FEntry> Saved;\n    Saved.Add(Capture(*Agent,ModeBone,EKind::Mode));\n    TArray<FName> Bodies;',1)
s=s.replace('float Duration,bool AllowOfflineDamping=false)', 'float Duration,bool AllowOfflineDamping=false,float Hold=0)')
s=s.replace('|| !FMath::IsFinite(Duration) || (Selection!=2', '|| !FMath::IsFinite(Duration) || !FMath::IsFinite(Hold) || Hold<0 || (Selection!=2')
s=s.replace('else Agent->CancelPhysicalFeedbackToleranceBlend(Target->Bone);','else if(Kind!=EKind::Mode) Agent->CancelPhysicalFeedbackToleranceBlend(Target->Bone);')
s=s.replace('Write(Target->Cells[I].Value,Duration,State.Clock);','Write(Target->Cells[I].Value,Duration,State.Clock,Hold);')
s=s.replace('EKind::Magnetization,EKind::Feedback,EKind::Damping}', 'EKind::Magnetization,EKind::Feedback,EKind::Damping,EKind::Mode}')
# All nine existing reflected blend definitions, with positional legacy arguments preserved.
import re
s=re.sub(r'(UProphecyPhysicalProfileLibrary::Blend\w+ToSnapshot\([^\n]*)FName Name\)',r'\1FName Name,float Hold)',s)
start=s.index('bool UProphecyPhysicalProfileLibrary::BlendBodyMagnetizationToSnapshot');end=s.index('#if WITH_DEV_AUTOMATION_TESTS',start)
s=s[:start]+s[start:end].replace('true,Duration)','true,Duration,false,Hold)').replace('Include,Duration)','Include,Duration,false,Hold)')+s[end:]
s=s.replace('bool UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot', '''bool UProphecyPhysicalProfileLibrary::SetMagnetizationMode(AProphecyAgent* Agent,float Mode)
{
    if(!IsValid(Agent) || !FMath::IsFinite(Mode) || Mode<0 || Mode>1)return false;
    return ProphecyPhysicalContext::Set(*Agent,ProphecyPhysicalContext::ModeBone,ProphecyPhysicalContext::EKind::Mode,true,{Mode,Mode},0);
}
float UProphecyPhysicalProfileLibrary::GetMagnetizationMode(AProphecyAgent* Agent)
{ return ProphecyPhysicalContext::MagnetizationMode(Agent); }
bool UProphecyPhysicalProfileLibrary::BlendMagnetizationModeToSnapshot(AProphecyAgent* Agent,float Duration,FName Name,float Hold)
{ return ProphecyPhysicalContext::RestoreSnapshot(Agent,Name,ProphecyPhysicalContext::EKind::Mode,NAME_None,2,true,Duration,false,Hold)>0; }
bool UProphecyPhysicalProfileLibrary::SavePhysicalProfileSnapshot''',1)
p.write_text(s)
p=root/'Private/ProphecyClampProfiles.h';s=p.read_text().replace('int32 Limb,float Duration);','int32 Limb,float Duration,float Hold=0);');p.write_text(s)
p=root/'Private/ProphecyClampProfiles.inl';s=p.read_text().replace('double Elapsed=0,Duration=0;','double Elapsed=0,Duration=0,Hold=0;');s=s.replace('if (B.Elapsed+1.e-9>=B.Duration)', 'if(B.Elapsed+1.e-9<B.Hold)continue;\n            if (B.Elapsed+1.e-9>=B.Hold+B.Duration)').replace('float(B.Elapsed/B.Duration)','float((B.Elapsed-B.Hold)/B.Duration)')
s=s.replace('int32 Limb,float Duration)','int32 Limb,float Duration,float Hold)');s=s.replace('!FMath::IsFinite(Duration) || uint8(Mode)', '!FMath::IsFinite(Duration) || !FMath::IsFinite(Hold) || Hold<0 || uint8(Mode)');s=s.replace('double(FMath::Max(0.f,Duration))});','double(FMath::Max(0.f,Duration)),Hold});');s=s.replace('if (B.Duration<=0) Write','if (B.Duration<=0 && B.Hold<=0) Write');s=s.replace('else { Write(*A,{B.Target.Mode,B.Target.Limb,{true,true,B.Start}});Active', 'else { if(B.Hold<=0)Write(*A,{B.Target.Mode,B.Target.Limb,{true,true,B.Start}});Active')
s=s.replace('FName Name,EProphecyClampProfileMode Mode)','FName Name,EProphecyClampProfileMode Mode,float Hold)');s=s.replace('Mode,int32(Limb),Duration)>0','Mode,int32(Limb),Duration,Hold)>0').replace('Mode,-1,Duration);','Mode,-1,Duration,Hold);');p.write_text(s)
