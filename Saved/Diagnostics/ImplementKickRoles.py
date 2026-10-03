from pathlib import Path
r=Path(__file__).resolve().parents[2]
def edit(path,fn):
 p=r/path;s=p.read_text(encoding='utf-8-sig');p.write_text(fn(s),encoding='utf-8')
def recovery_header(s):
 a=s.index('    static bool SetKickToLocomotionBlend');pre=s[:a];tail=s[a:]
 for old,new in [('LeftLegSource','Kicking Leg Source'),('LeftLegHoldDurationSeconds','Kicking Leg Hold Duration Seconds'),('RightLegSource','Non Kicking Leg Source'),('RightLegHoldDurationSeconds','Non Kicking Leg Hold Duration Seconds')]:
  typ='EProphecyRecoverySource' if 'Source' in old else 'float'
  tail=tail.replace(f'{typ} {old}',f'UPARAM(DisplayName="{new}") {typ} {old}')
 tail=tail.replace('Left Leg Blend Duration Seconds','Kicking Leg Blend Duration Seconds').replace('Right Leg Blend Duration Seconds','Non Kicking Leg Blend Duration Seconds')
 return pre+tail
edit('Source/GameAnimationSample3/Public/ProphecyAttackRecoveryLibrary.h',recovery_header)
def recovery(s):
 s=s.replace('static bool EndEventKick=false;', '''static TSet<TWeakObjectPtr<const AProphecyAgent>> RightKickActive;
static bool EndEventKick=false,EndEventRightKick=false;
static FSettings ResolveKickRoles(FSettings Value,bool RightKick)
{
    if (RightKick) Swap(Value.Left,Value.Right);
    return Value;
}''')
 s=s.replace('for (auto It=KickActive.CreateIterator();It;++It)', 'for (auto* Set:{&KickActive,&RightKickActive}) for (auto It=Set->CreateIterator();It;++It)')
 s=s.replace('    KickActive.Remove(Agent);','    KickActive.Remove(Agent);RightKickActive.Remove(Agent);')
 s=s.replace('    if (!Config) Config=Settings.Find(Agent);\n    const FSettings Value=Config ? *Config : FSettings{};', '''    const bool HasKickProfile=Config!=nullptr;
    if (!Config) Config=Settings.Find(Agent);
    const FSettings Value=ResolveKickRoles(Config ? *Config : FSettings{},HasKickProfile && Attack==TEXT("kickr"));''')
 s=s.replace('    if (IsKick(Attack)) KickActive.Add(Agent);','    if (IsKick(Attack)) KickActive.Add(Agent);\n    if (Attack==TEXT("kickr")) RightKickActive.Add(Agent);',1)
 s=s.replace('    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));','    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));\n    TGuardValue<bool> SideScope(EndEventRightKick,Attack==TEXT("kickr"));')
 s=s.replace('    const FSettings Value{{PelvisSource','    FSettings Value{{PelvisSource',1)
 s=s.replace('    if (Kick!=UsesKick) return true; // Configuring the other profile cannot overwrite this handoff.','''    if (Kick!=UsesKick) return true; // Configuring the other profile cannot overwrite this handoff.
    const bool RightKick=RightKickActive.Contains(Agent) || (EndEventAgent==Agent && EndEventRightKick);
    if (Kick) Value=ResolveKickRoles(Value,RightKick);''')
 s=s.replace('        if (KickHandoff) KickActive.Add(Agent);','        if (KickHandoff) KickActive.Add(Agent);\n        if (RightKick) RightKickActive.Add(Agent);')
 s=s.replace('W.Pelvis==0 && W.Left==0 && W.Right==1);','W.Pelvis==0 && W.Left==(Family==TEXT("kickr") ? 1.f : 0.f) && W.Right==(Family==TEXT("kickr") ? 0.f : 1.f));')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyAttackRecoveryLibrary.cpp',recovery)

def temper_header(s):
 a=s.index('    static bool SetKickLocomotionLowerBodyTempering');b=s.index('    /** Hold and restore',a)
 s=s[:a]+'''    static bool SetKickLocomotionLowerBodyTempering(AProphecyAgent* Agent, bool Enabled = true,
        UPARAM(DisplayName="Kicking Foot Translation XY") float FeetTranslation = 1.f,
        UPARAM(DisplayName="Kicking Foot Translation Z") float FeetTranslationZ = 1.f,
        UPARAM(DisplayName="Kicking Foot Rotation") float FeetRotation = 1.f,
        float NonKickingFootTranslationXY = 1.f, float NonKickingFootTranslationZ = 1.f,
        float NonKickingFootRotation = 1.f,
        UPARAM(DisplayName="Pelvis Translation XY") float PelvisTranslation = 1.f,
        float PelvisTranslationZ = 1.f, float PelvisRotation = 1.f);

'''+s[b:]
 return s
edit('Source/GameAnimationSample3/Public/ProphecyLowerTemperingLibrary.h',temper_header)
edit('Source/GameAnimationSample3/Private/ProphecyLowerTempering.h',lambda s:s.replace('    bool IsIdentity() const','    bool FeetAreIdentity() const { return FeetTranslation==1.f && FeetTranslationZ==1.f && FeetRotation==1.f; }\n    bool IsIdentity() const').replace('float MinimumLegReachMultiplier', '''// Find samples the existing clocks first; this accessor reads the already sampled right foot.
const FSettings& RightFootSettings(const AProphecyAgent* Agent,const FSettings& Left);
void RestoreRightFootSettings(const AProphecyAgent* Agent,const FSettings& Right);
float MinimumLegReachMultiplier'''))

def temper(s):
 s=s.replace('static TSet<TWeakObjectPtr<const AProphecyAgent>> KickSelected;', '''static TSet<TWeakObjectPtr<const AProphecyAgent>> KickSelected,RightKickSelected;
// Sidecars preserve live settings, return timelines and reset snapshot layouts.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> NonKickingProfiles,RightValues;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> ReturnRightInitial,FeetReturnRightInitial;
const FSettings& RightFootSettings(const AProphecyAgent* Agent,const FSettings& Left)
{
    const auto* Right=RightValues.IsEmpty() ? nullptr : RightValues.Find(Agent);
    return Right ? *Right : Left;
}
static bool AllNormal(const AProphecyAgent* Agent,const FSettings& Left)
{ return Left.IsIdentity() && RightFootSettings(Agent,Left).FeetAreIdentity(); }
static bool SameFeet(const FSettings& A,const FSettings& B)
{ return A.FeetTranslation==B.FeetTranslation && A.FeetTranslationZ==B.FeetTranslationZ && A.FeetRotation==B.FeetRotation; }
static void CopyFeet(FSettings& A,const FSettings& B)
{ A.FeetTranslation=B.FeetTranslation;A.FeetTranslationZ=B.FeetTranslationZ;A.FeetRotation=B.FeetRotation; }
void RestoreRightFootSettings(const AProphecyAgent* Agent,const FSettings& Right)
{
    const auto* Left=Settings.Find(Agent);
    if ((!Left && Right.FeetAreIdentity()) || (Left && SameFeet(*Left,Right))) { RightValues.Remove(Agent);return; }
    if (!Left) Settings.Add(Agent,FSettings{});
    RightValues.Add(Agent,Right);
}''')
 s=s.replace('    if (!Returns.IsEmpty()) Returns.Remove(Agent);','    ReturnRightInitial.Remove(Agent);FeetReturnRightInitial.Remove(Agent);\n    if (!Returns.IsEmpty()) Returns.Remove(Agent);',1)
 s=s.replace('        *Value=Return->Sample();\n        if (Value->IsIdentity())\n        { Returns.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }','''        *Value=Return->Sample();
        if (const auto* Initial=ReturnRightInitial.Find(Agent))
        { auto Right=*Return;Right.Initial=*Initial;CopyFeet(RightValues.FindOrAdd(Agent),Right.Sample()); }
        if (AllNormal(Agent,*Value))
        { Returns.Remove(Agent);ReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }''')
 s=s.replace('        if (Feet) { Value->FeetTranslation=Sample.FeetTranslation;Value->FeetTranslationZ=Sample.FeetTranslationZ;Value->FeetRotation=Sample.FeetRotation; }','''        if (Feet)
        {
            CopyFeet(*Value,Sample);
            if (const auto* Initial=FeetReturnRightInitial.Find(Agent))
            { auto Right=*Return;Right.Initial=*Initial;CopyFeet(RightValues.FindOrAdd(Agent),Right.Sample()); }
        }''')
 s=s.replace('const bool Done=Feet ? Value->FeetTranslation==1 && Value->FeetTranslationZ==1 && Value->FeetRotation==1','const bool Done=Feet ? Value->FeetAreIdentity() && RightFootSettings(Agent,*Value).FeetAreIdentity()')
 s=s.replace('if (Done) { Timelines.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind); }','if (Done) { Timelines.Remove(Agent);if (Feet) FeetReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind); }')
 s=s.replace('if (Value->IsIdentity()) { Remove(Agent);return nullptr; }','if (AllNormal(Agent,*Value)) { Remove(Agent);return nullptr; }')
 s=s.replace('    if (!Settings.IsEmpty()) Settings.Remove(Agent);','    RightValues.Remove(Agent);\n    if (!Settings.IsEmpty()) Settings.Remove(Agent);',1)
 s=s.replace('    const FSettings Initial=*Current;','    const FSettings Initial=*Current;\n    const FSettings InitialRight=RightFootSettings(Agent,Initial);',1)
 s=s.replace('        if (Shared->Initial.IsIdentity())\n        { Returns.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }','''        auto* SharedRight=ReturnRightInitial.Find(Agent);
        if (Feet && SharedRight) CopyFeet(*SharedRight,FSettings{});
        if (Shared->Initial.IsIdentity() && (!SharedRight || SharedRight->FeetAreIdentity()))
        { Returns.Remove(Agent);ReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }''')
 s=s.replace('const bool AlreadyNormal=Feet ? Initial.FeetTranslation==1 && Initial.FeetTranslationZ==1 && Initial.FeetRotation==1','const bool AlreadyNormal=Feet ? Initial.FeetAreIdentity() && InitialRight.FeetAreIdentity()')
 s=s.replace('        if (Feet) Value.FeetTranslation=Value.FeetTranslationZ=Value.FeetRotation=1;','''        if (Feet)
        { CopyFeet(Value,FSettings{});RightValues.Remove(Agent);FeetReturnRightInitial.Remove(Agent); }''')
 s=s.replace('        if (Value.IsIdentity()) Remove(Agent);','        if (AllNormal(Agent,Value)) Remove(Agent);',1)
 s=s.replace('    Timelines.Add(Agent,FReturnTimeline{Initial,Duration,Hold});','    Timelines.Add(Agent,FReturnTimeline{Initial,Duration,Hold});\n    if (Feet && RightValues.Contains(Agent)) FeetReturnRightInitial.Add(Agent,InitialRight);')
 s=s.replace('for (auto* Map:{&Settings,&RegularProfiles,&KickProfiles})','for (auto* Map:{&Settings,&RegularProfiles,&KickProfiles,&NonKickingProfiles,&RightValues,&ReturnRightInitial,&FeetReturnRightInitial})')
 s=s.replace('for (auto It=KickSelected.CreateIterator();It;++It)','for (auto* Set:{&KickSelected,&RightKickSelected}) for (auto It=Set->CreateIterator();It;++It)')
 s=s.replace('void ClearAttackSelection(const AProphecyAgent* Agent) { KickSelected.Remove(Agent); }','void ClearAttackSelection(const AProphecyAgent* Agent) { KickSelected.Remove(Agent);RightKickSelected.Remove(Agent); }')
 s=s.replace('{ Remove(Agent);KickSelected.Remove(Agent);RegularProfiles.Remove(Agent);KickProfiles.Remove(Agent); }','{ Remove(Agent);ClearAttackSelection(Agent);RegularProfiles.Remove(Agent);KickProfiles.Remove(Agent);NonKickingProfiles.Remove(Agent); }')
 s=s.replace('    const auto* Special=KickProfiles.Find(Agent);','    if (Attack==TEXT("kickr")) RightKickSelected.Add(Agent);else RightKickSelected.Remove(Agent);\n    const auto* Special=KickProfiles.Find(Agent);',1)
 s=s.replace('    Apply(Agent,Kick ? *Special : (Regular ? *Regular : FSettings{}));','''    if (!Kick) { Apply(Agent,Regular ? *Regular : FSettings{});return; }
    const auto* NonKicking=NonKickingProfiles.Find(Agent);
    FSettings Left=*Special,Right=NonKicking ? *NonKicking : *Special;
    if (Attack==TEXT("kickr")) Swap(Left,Right);
    // Pelvis is independent of which leg kicked.
    Left.PelvisTranslation=Special->PelvisTranslation;Left.PelvisTranslationZ=Special->PelvisTranslationZ;Left.PelvisRotation=Special->PelvisRotation;
    Apply(Agent,Left);RestoreRightFootSettings(Agent,Right);''')
 a=s.index('bool UProphecyLowerTemperingLibrary::SetKickLocomotionLowerBodyTempering(')
 b=s.index('bool UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(',a)
 s=s[:a]+'''bool UProphecyLowerTemperingLibrary::SetKickLocomotionLowerBodyTempering(AProphecyAgent* Agent,bool Enabled,
    float FeetTranslation,float FeetTranslationZ,float FeetRotation,
    float NonKickingFootTranslationXY,float NonKickingFootTranslationZ,float NonKickingFootRotation,
    float PelvisTranslation,float PelvisTranslationZ,float PelvisRotation)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if (Enabled) for (float V:{FeetTranslation,FeetTranslationZ,FeetRotation,NonKickingFootTranslationXY,
        NonKickingFootTranslationZ,NonKickingFootRotation,PelvisTranslation,PelvisTranslationZ,PelvisRotation})
        if (!FMath::IsFinite(V) || V<0 || V>1) return false;
    using namespace ProphecyLowerTempering;
    EnsureCleanup();
    KickProfiles.Add(Agent,Enabled ? FSettings{FeetTranslation,FeetRotation,PelvisTranslation,PelvisRotation,FeetTranslationZ,PelvisTranslationZ} : FSettings{});
    NonKickingProfiles.Add(Agent,Enabled ? FSettings{NonKickingFootTranslationXY,NonKickingFootRotation,1,1,NonKickingFootTranslationZ,1} : FSettings{});
    if (KickSelected.Contains(Agent)) SelectAttackProfile(Agent,RightKickSelected.Contains(Agent) ? TEXT("kickr") : TEXT("kickl"));
    return true;
}

'''+s[b:]
 # Capture asymmetric initial values before cancelling a shared return schedule.
 s=s.replace('    const FSettings Initial=*Current;\n    CancelReturns(Agent);\n    Returns.Add', '    const FSettings Initial=*Current;\n    const FSettings InitialRight=RightFootSettings(Agent,Initial);\n    CancelReturns(Agent);\n    if (RightValues.Contains(Agent)) ReturnRightInitial.Add(Agent,InitialRight);\n    Returns.Add')
 s=s.replace('SetKickLocomotionLowerBodyTempering(Agent,true,.8f,.7f,.6f,.4f,.3f,.2f)', 'SetKickLocomotionLowerBodyTempering(Agent,true,.8f,.7f,.6f,.8f,.7f,.6f,.4f,.3f,.2f)')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyLowerTemperingLibrary.cpp',temper)

def pose(s):
 s=s.replace('const float* Previous, float* Predicted)\n{','const float* Previous, float* Predicted,\n    const ProphecyLowerTempering::FSettings* Right=nullptr)\n{',1)
 a=s.index('    for (int32 Offset : {9,25})');b=s.index('\n}\n',a)
 part=s[a:b].replace('        Position(Offset, S.FeetTranslation','        const auto& Foot=Offset==25 && Right ? *Right : S;\n        Position(Offset, Foot.FeetTranslation').replace('S.Feet','Foot.Feet')
 return s[:a]+part+s[b:]
edit('Source/GameAnimationSample3/Private/ProphecyLowerTempering.inl',pose)

def manager(s):
 s=s.replace('bool bSupportSource=bReconstructTemperedLegs && Tempering->FeetRotation>0.f;', '''const auto* RightTempering=Tempering ? &ProphecyLowerTempering::RightFootSettings(AgentActors[AgentIndex],*Tempering) : nullptr;
        bool bSupportSource=bReconstructTemperedLegs && (Tempering->FeetRotation>0.f || RightTempering->FeetRotation>0.f);''')
 s=s.replace('TemperLowerPose(*Tempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex), Transition);','TemperLowerPose(*Tempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex), Transition,RightTempering);')
 # I is the leg index in this loop (verify against source).
 s=s.replace('ResolveTemperedLeg(*Tempering, StateSlice', 'ResolveTemperedLeg(I==0 ? *Tempering : *RightTempering, StateSlice')
 s=s.replace('bool bTemperCalves=bHasPreviousPose && CalfTempering && CalfTempering->FeetRotation<1.f && ProphecyLegChainDebug::IsEnabled(Controls);', '''const auto* RightCalfTempering=CalfTempering ? &ProphecyLowerTempering::RightFootSettings(Controls,*CalfTempering) : nullptr;
    bool bTemperCalves=bHasPreviousPose && CalfTempering && (CalfTempering->FeetRotation<1.f || RightCalfTempering->FeetRotation<1.f) && ProphecyLegChainDebug::IsEnabled(Controls);''')
 s=s.replace('        const auto& Leg=Impl->Limbs[I];\n', '        const auto& Leg=Impl->Limbs[I];\n')
 s=s.replace('''		const auto& Leg=Impl->Limbs[I];
		PreviousComponentTransforms[Leg.Mid].SetRotation(PreviousCalfRotations[I]);''','''        const float Follow=(I==0 ? CalfTempering : RightCalfTempering)->FeetRotation;
        if (Follow==1.f) continue;
		const auto& Leg=Impl->Limbs[I];
		PreviousComponentTransforms[Leg.Mid].SetRotation(PreviousCalfRotations[I]);''')
 s=s.replace('LocalTrainingToUnreal(Impl->LocalOffsets[Leg.End]),CalfTempering->FeetRotation)', 'LocalTrainingToUnreal(Impl->LocalOffsets[Leg.End]),Follow)')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp',manager)
edit('Source/GameAnimationSample3/Private/ProphecyNNInputDebug.inl',lambda s:s.replace('Add(TEXT("tempering"),Values,UE_ARRAY_COUNT(Values));','''Add(TEXT("tempering"),Values,UE_ARRAY_COUNT(Values));
            const auto& R=ProphecyLowerTempering::RightFootSettings(AgentActors[I],*S);
            const float Right[]={R.FeetTranslation,R.FeetTranslationZ,R.FeetRotation};
            Add(TEXT("right_foot_tempering"),Right,UE_ARRAY_COUNT(Right));'''))

def reset(s):
 s=s.replace('static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;','static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;\nstatic TMap<TWeakObjectPtr<const AProphecyAgent>,ProphecyLowerTempering::FSettings> RightTemperingStates;')
 s=s.replace('    States.Remove(Agent);','    States.Remove(Agent);RightTemperingStates.Remove(Agent);',1)
 s=s.replace('if (const auto* T=ProphecyLowerTempering::Find(Agent)) S.Tempering=*T;','if (const auto* T=ProphecyLowerTempering::Find(Agent))\n    { S.Tempering=*T;RightTemperingStates.Add(Agent,ProphecyLowerTempering::RightFootSettings(Agent,*T)); }')
 s=s.replace('    if (S.HadMaterial && !S.Material.IsValid())', '    if (const auto* Right=RightTemperingStates.Find(Agent)) ProphecyLowerTempering::RestoreRightFootSettings(Agent,*Right);\n    if (S.HadMaterial && !S.Material.IsValid())',1)
 return s
edit('Source/GameAnimationSample3/Private/ProphecyAgentResetPhysics.cpp',reset)
