from pathlib import Path
root=Path(__file__).resolve().parents[2]
def edit(name, fn):
    p=root/name
    s=p.read_text(encoding='utf-8-sig')
    p.write_text(fn(s),encoding='utf-8')

def recovery(s):
    s=s.replace('#include "ProphecyBlendClock.h"','#include "ProphecyBlendClock.h"\n#include "ProphecyLowerTempering.h"')
    a=s.index('static EProphecyRecoverySource ResolveSource')
    b=s.index('struct FPart',a)
    s=s[:a]+s[b:]
    s=s.replace('static FDelegateHandle Cleanup;', '''static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> KickSettings;
static TSet<TWeakObjectPtr<const AProphecyAgent>> KickActive;
static bool EndEventKick=false;
static bool IsKick(FName Attack) { return Attack==TEXT("kickl") || Attack==TEXT("kickr"); }
static FDelegateHandle Cleanup;''')
    s=s.replace('for (auto It=Settings.CreateIterator();It;++It)\n            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();','''for (auto* Map:{&Settings,&KickSettings}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=KickActive.CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();''')
    s=s.replace('if (!Active.IsEmpty()) Active.Remove(Agent);','if (!Active.IsEmpty()) Active.Remove(Agent);\n    KickActive.Remove(Agent);')
    s=s.replace('void Begin(const AProphecyAgent* Agent)','void Begin(const AProphecyAgent* Agent,FName Attack)')
    s=s.replace('const auto* Config=Settings.Find(Agent);','const auto* Config=IsKick(Attack) ? KickSettings.Find(Agent) : nullptr;\n    if (!Config) Config=Settings.Find(Agent);')
    s=s.replace('EnsureCleanup();Active.Add(Agent,FRecovery{Value});','EnsureCleanup();Active.Add(Agent,FRecovery{Value});\n    if (IsKick(Attack)) KickActive.Add(Agent);',1)
    s=s.replace('Cancel(Agent);Settings.Remove(Agent);','Cancel(Agent);Settings.Remove(Agent);KickSettings.Remove(Agent);')
    s=s.replace('    Agent->OnNNAttackEnded(Attack,Half);','''    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));
    if (ReturningToLocomotion) ProphecyLowerTempering::SelectAttackProfile(Agent,Attack);
    Agent->OnNNAttackEnded(Attack,Half);''')
    s=s.replace('bool UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(AProphecyAgent* Agent,','static bool SetRecoveryProfile(bool Kick,AProphecyAgent* Agent,',1)
    s=s.replace('float RightLegDurationSeconds,bool bForceRun)','float RightLegDurationSeconds)',1)
    s=s.replace('    // Resolve once when configuring; no new state, per-tick branch or clock.\n','')
    for field in ['PelvisSource','LeftLegSource','RightLegSource']:
        s=s.replace(f'ResolveSource({field},bForceRun)',field)
    s=s.replace('EnsureCleanup();Settings.Add(Agent,Value);\n    if (EndEventAgent==Agent && !Active.Contains(Agent) && Value.End()>0) Begin(Agent);','''EnsureCleanup();(Kick ? KickSettings : Settings).Add(Agent,Value);
    const bool KickHandoff=KickActive.Contains(Agent) || (EndEventAgent==Agent && EndEventKick);
    const bool UsesKick=KickHandoff && KickSettings.Contains(Agent);
    if (Kick!=UsesKick) return true; // Configuring the other profile cannot overwrite this handoff.
    if (EndEventAgent==Agent && !Active.Contains(Agent) && Value.End()>0)
    {
        Active.Add(Agent,FRecovery{Value});
        if (KickHandoff) KickActive.Add(Agent);
    }''')
    wrappers=''
    for name,kick in [('SetAttackToLocomotionBlend','false'),('SetKickToLocomotionBlend','true')]:
        wrappers+=f'''bool UProphecyAttackRecoveryLibrary::{name}(AProphecyAgent* Agent,
    EProphecyRecoverySource PelvisSource,float HoldDurationSeconds,float DurationSeconds,
    EProphecyRecoverySource LeftLegSource,float LeftLegHoldDurationSeconds,float LeftLegDurationSeconds,
    EProphecyRecoverySource RightLegSource,float RightLegHoldDurationSeconds,float RightLegDurationSeconds)
{{
    return SetRecoveryProfile({kick},Agent,PelvisSource,HoldDurationSeconds,DurationSeconds,
        LeftLegSource,LeftLegHoldDurationSeconds,LeftLegDurationSeconds,
        RightLegSource,RightLegHoldDurationSeconds,RightLegDurationSeconds);
}}

'''
    s=s.replace('#if WITH_DEV_AUTOMATION_TESTS',wrappers+'#if WITH_DEV_AUTOMATION_TESTS',1)
    a=s.index('    TestEqual(TEXT("Force Run replaces Walk")')
    b=s.index('    const FPart Run',a)
    s=s[:a]+s[b:]
    # Selection tests exercise live handoff setters, zero, both kick families and normal fallback.
    marker='    Remove(Agent);World->DestroyWorld(false);return !HasAnyErrors();'
    tests='''    using L=UProphecyAttackRecoveryLibrary;
    L::SetAttackToLocomotionBlend(Agent,E::Walk,0,1,E::Walk,0,1,E::Walk,0,1);
    L::SetKickToLocomotionBlend(Agent,E::Run,0,1,E::Run,0,1,E::Walk,0,1);
    for (FName Family:{FName(TEXT("kickl")),FName(TEXT("kickr"))})
    {
        Begin(Agent,Family);
        L::SetAttackToLocomotionBlend(Agent,E::Walk,0,2,E::Walk,0,2,E::Walk,0,2);
        Step(Agent,1,W);
        TestTrue(TEXT("Both kicks select independent profile despite regular event setter"),W.Pelvis==0 && W.Left==0 && W.Right==1);
    }
    Begin(Agent,TEXT("overl"));Step(Agent,0,W);
    TestTrue(TEXT("Next non-kick restores regular regional settings"),W.Pelvis==1 && W.Left==1 && W.Right==1);
    L::SetKickToLocomotionBlend(Agent,E::Run,0,0,E::Run,0,0,E::Run,0,0);
    Begin(Agent,TEXT("kickr"));TestFalse(TEXT("Disabled kick creates no clock/active recovery"),Active.Contains(Agent));
    { TGuardValue<const AProphecyAgent*> Event(EndEventAgent,Agent);TGuardValue<bool> Kick(EndEventKick,true);
      L::SetAttackToLocomotionBlend(Agent);
      TestFalse(TEXT("Regular event setter cannot enable disabled kick profile"),Active.Contains(Agent));
      L::SetKickToLocomotionBlend(Agent);
      TestTrue(TEXT("Kick event setter can enable current zero handoff"),Active.Contains(Agent)); }
'''
    return s.replace(marker,tests+marker)
edit('Source/GameAnimationSample3/Private/ProphecyAttackRecoveryLibrary.cpp',recovery)
edit('Source/GameAnimationSample3/Private/ProphecyNNSlashRuntime.inl',lambda s:s.replace('ProphecyAttackRecovery::Begin(Actor);','ProphecyAttackRecovery::Begin(Actor,EndedAttack);'))

def tempering(s):
    s=s.replace('static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> Settings;', '''static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> Settings;
// Configuration is independent of the active values consumed by Blend To Normal.
static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> RegularProfiles,KickProfiles;
static TSet<TWeakObjectPtr<const AProphecyAgent>> KickSelected;''')
    start=s.index('bool UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(')
    end=s.index('bool UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(',start)
    replacement='''namespace ProphecyLowerTempering
{
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto* Map:{&Settings,&RegularProfiles,&KickProfiles}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto* Map:{&Returns,&FeetReturns,&PelvisReturns}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=KickSelected.CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    });
}
static void Apply(const AProphecyAgent* Agent,const FSettings& Value)
{
    Remove(Agent);
    if (!Value.IsIdentity()) { EnsureCleanup();Settings.Add(Agent,Value); }
}
void ClearAttackSelection(const AProphecyAgent* Agent) { KickSelected.Remove(Agent); }
void ForgetProfiles(const AProphecyAgent* Agent)
{ Remove(Agent);KickSelected.Remove(Agent);RegularProfiles.Remove(Agent);KickProfiles.Remove(Agent); }
void SelectAttackProfile(const AProphecyAgent* Agent,FName Attack)
{
    const bool Kick=Attack==TEXT("kickl") || Attack==TEXT("kickr");
    if (Kick) { EnsureCleanup();KickSelected.Add(Agent); } else KickSelected.Remove(Agent);
    const auto* Special=KickProfiles.Find(Agent);
    if (!Special) return; // Unconfigured agents keep the previous immediate-set behavior.
    const auto* Regular=RegularProfiles.Find(Agent);
    Apply(Agent,Kick ? *Special : (Regular ? *Regular : FSettings{}));
}
static bool SetProfile(bool Kick,AProphecyAgent* Agent,bool Enabled,
    float FeetXY,float FeetZ,float FeetR,float PelvisXY,float PelvisZ,float PelvisR)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if (Enabled) for (float V:{FeetXY,FeetZ,FeetR,PelvisXY,PelvisZ,PelvisR})
        if (!FMath::IsFinite(V) || V<0 || V>1) return false;
    const FSettings Value=Enabled ? FSettings{FeetXY,FeetR,PelvisXY,PelvisR,FeetZ,PelvisZ} : FSettings{};
    EnsureCleanup();(Kick ? KickProfiles : RegularProfiles).Add(Agent,Value);
    const bool UsesKick=KickSelected.Contains(Agent) && KickProfiles.Contains(Agent);
    if (Kick==UsesKick) Apply(Agent,Value);
    return true;
}
}

'''
    for name,kick in [('SetLocomotionLowerBodyTempering','false'),('SetKickLocomotionLowerBodyTempering','true')]:
        replacement+=f'''bool UProphecyLowerTemperingLibrary::{name}(AProphecyAgent* Agent,bool Enabled,
    float FeetTranslation,float FeetTranslationZ,float FeetRotation,
    float PelvisTranslation,float PelvisTranslationZ,float PelvisRotation)
{{
    return ProphecyLowerTempering::SetProfile({kick},Agent,Enabled,FeetTranslation,FeetTranslationZ,FeetRotation,
        PelvisTranslation,PelvisTranslationZ,PelvisRotation);
}}

'''
    s=s[:start]+replacement+s[end:]
    s=s.replace('TEXT("Exactly Set and Blend exposed in the Blueprint menu"),VisibleNodes,2','TEXT("Regular Set, Kick Set and shared Blend exposed"),VisibleNodes,3')
    return s
edit('Source/GameAnimationSample3/Private/ProphecyLowerTemperingLibrary.cpp',tempering)
edit('Source/GameAnimationSample3/Private/ProphecyLowerTempering.h',lambda s:s.replace('const FSettings* Find','void SelectAttackProfile(const AProphecyAgent* Agent,FName Attack);\nvoid ClearAttackSelection(const AProphecyAgent* Agent);\nvoid ForgetProfiles(const AProphecyAgent* Agent);\nconst FSettings* Find'))
edit('Source/GameAnimationSample3/Private/ProphecyAgentResetPhysics.cpp',lambda s:s.replace('    ProphecyLowerTempering::Remove(Agent);\n    ProphecyBlendClock::Remove(Agent);','    ProphecyLowerTempering::ClearAttackSelection(Agent);\n    ProphecyLowerTempering::Remove(Agent);\n    ProphecyBlendClock::Remove(Agent);'))
edit('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp',lambda s:s.replace('ProphecyLowerTempering::Remove(AgentActor);','ProphecyLowerTempering::ForgetProfiles(AgentActor);'))

def sword(s):
    s=s.replace('TMap<TWeakObjectPtr<const AProphecyAgent>,FGate> Gates;', '''TMap<TWeakObjectPtr<const AProphecyAgent>,FGate> Gates;
TSet<TWeakObjectPtr<const AProphecyAgent>> HitOwners;
void RefreshOwner(AProphecyAgent* Agent)
{
    if (Agent) if (auto* Controller=Agent->FindComponentByClass<UProphecySwordComponent>())
        Controller->RefreshOwnerCollision();
}''')
    s=s.replace('bool IsAllowed(const AProphecyAgent* Agent)','''bool SuppressesOwner(const AProphecyAgent* Agent)
{
    return Agent && Agent->IsSwordAttackActive() && !HitOwners.Contains(Agent);
}
bool IsAllowed(const AProphecyAgent* Agent)''',1)
    s=s.replace('void Hit(AProphecyAgent* Agent)\n{\n\tauto* Gate=Gates.Find(Agent);','''void Hit(AProphecyAgent* Agent)
{
    if (!Agent || !Gates.Contains(Agent)) return;
    const bool First=!HitOwners.Contains(Agent);
    HitOwners.Add(Agent);
    // Restore owner pairs for every attack family without ending any attack systems.
    if (First) RefreshOwner(Agent);
\tauto* Gate=Gates.Find(Agent);''')
    s=s.replace('FGate Gate;if (Gates.RemoveAndCopyValue(Agent,Gate)) Restore(Gate);','FGate Gate;if (Gates.RemoveAndCopyValue(Agent,Gate)) Restore(Gate);\n    HitOwners.Remove(Agent);')
    s=s.replace('A->IsSwordAttackActive()', 'ProphecySwordAttackCollision::SuppressesOwner(A)')
    return s
edit('Source/GameAnimationSample3/Private/ProphecySwordComponent.cpp',sword)
edit('Source/GameAnimationSample3/Private/ProphecySwordAttackCollision.h',lambda s:s.replace('bool IsAllowed','bool SuppressesOwner(const AProphecyAgent* Agent);\nbool IsAllowed'))

def refresh(s):
    s=s.replace('const bool HadForceRun=N->FindPin(TEXT("bForceRun"))!=nullptr;','''N->Modify();
        if (FunctionName==TEXT("SetAttackToLocomotionBlend")) if (auto* Force=N->FindPin(TEXT("bForceRun")))
        {
            Force->BreakAllPinLinks();N->RemovePin(Force);
        }''')
    a=s.index('        if (!HadForceRun')
    b=s.index('        if (!HadDistanceToLimit',a)
    return s[:a]+s[b:]
edit('Source/ProphecyEditor/Private/ProphecyBlendNodeUpgrade.cpp',refresh)
