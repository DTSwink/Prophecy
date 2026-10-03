from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackRecoveryLibrary.cpp')
s=p.read_text(encoding='utf-8')
s=s.replace('static FName EndAttack;','''static FName EndAttack;
static bool EndEventUpper=false;
#if WITH_EDITOR
static TAutoConsoleVariable<int32> RegionAudit(TEXT("Prophecy.Recovery.RegionAudit"),0,
    TEXT("Opt-in regional special-end dispatch log; event-only."));
#endif
#if WITH_DEV_AUTOMATION_TESTS
static TFunction<void(bool)> RegionObserver;
#endif''')
a=s.index('void EnterSpecial(');b=s.index('FVector2f FootRotationWeights',a)
s=s[:a]+'''void EnterLowerSpecial(const AProphecyAgent* Agent)
{
    ProphecyLegRecovery::Cancel(Agent);
    ProphecyKickFootLeeway::CancelPoseRecovery(Agent);
    Cancel(Agent);ProphecyLowerTempering::Remove(Agent);
}
void EnterSpecial(const AProphecyAgent* Agent,bool Half)
{
    if (EndEventAgent==Agent) EndEventAgent=nullptr;
    if (!Half) EnterLowerSpecial(Agent);
    ProphecyHandRecovery::CancelMotion(Agent);ProphecyCoreTempering::CancelMotion(Agent);
    ProphecySlashReturn::Cancel(Agent);ProphecyUpperBodyInertia::Cancel(Agent);
}
static void DispatchRegion(AProphecyAgent* Agent,FName Attack,bool Half,bool Returning,
    EProphecyAgentState Special,bool Upper)
{
    TGuardValue<bool> Region(EndEventUpper,Upper);
    if (Returning)
    {
        if (Upper)
        {
            ProphecyHandRecovery::Begin(Agent);ProphecyCoreTempering::Begin(Agent);
            ProphecySlashReturn::Begin(Agent,Attack);
        }
        else
        {
            ProphecyLowerTempering::SelectAttackProfile(Agent,Attack);
            ProphecyLegRecovery::Begin(Agent);
        }
    }
#if WITH_EDITOR
    if (RegionAudit.GetValueOnGameThread()!=0)
        UE_LOG(LogTemp,Display,TEXT("SpecialRegion actor=%s region=%s special=%d attack=%s half=%d returning=%d"),
            *Agent->GetName(),Upper?TEXT("upper"):TEXT("lower"),int32(Special),*Attack.ToString(),Half,Returning);
#endif
#if WITH_DEV_AUTOMATION_TESTS
    if (RegionObserver) RegionObserver(Upper);
#endif
    if (Agent->GetClass()->ImplementsInterface(UProphecySpecialRecoveryEvents::StaticClass()))
    {
        if (Upper) IProphecySpecialRecoveryEvents::Execute_OnNNUpperSpecialEnded(Agent,Special,Attack,Half,Returning);
        else IProphecySpecialRecoveryEvents::Execute_OnNNLowerSpecialEnded(Agent,Special,Attack,Half,Returning);
    }
}
void NotifyLowerEnded(AProphecyAgent* Agent,FName Attack,bool Half,bool Returning,EProphecyAgentState Special)
{
    if (Returning) Begin(Agent,Attack);
    TGuardValue<const AProphecyAgent*> Scope(EndEventAgent,Returning ? Agent : nullptr);
    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));
    TGuardValue<bool> SideScope(EndEventRightKick,Attack==TEXT("kickr"));
    TGuardValue<FName> AttackScope(EndAttack,Attack);
    DispatchRegion(Agent,Attack,Half,Returning,Special,false);
}
void NotifyEnded(AProphecyAgent* Agent,FName Attack,bool Half,bool Returning,EProphecyAgentState Special)
{
    const bool Lower=Special!=EProphecyAgentState::Attacking || !Half;
    if (Returning && Lower) Begin(Agent,Attack);
    TGuardValue<const AProphecyAgent*> Scope(EndEventAgent,Returning ? Agent : nullptr);
    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));
    TGuardValue<bool> SideScope(EndEventRightKick,Attack==TEXT("kickr"));
    TGuardValue<FName> AttackScope(EndAttack,Attack);
    if (Lower) DispatchRegion(Agent,Attack,Half,Returning,Special,false);
    // A lower handler may reset the agent or start a replacement special.
    if (IsValid(Agent) && !Agent->IsActorBeingDestroyed() && (!Returning || EndEventAgent==Agent))
        DispatchRegion(Agent,Attack,Half,Returning,Special,true);
    // The attack-only gameplay event still fires once, never on a mode switch.
    // Run it after regional recovery so event-driven chaining starts cleanly.
    if (IsValid(Agent) && !Agent->IsActorBeingDestroyed() && Special==EProphecyAgentState::Attacking)
        Agent->OnNNAttackEnded(Attack,Half);
}
bool IsEndEvent(const AProphecyAgent* Agent) { return EndEventAgent==Agent && EndEventUpper; }
FName EndEventAttack(const AProphecyAgent* Agent) { return IsEndEvent(Agent)?EndAttack:NAME_None; }
'''+s[b:]
s=s.replace('(EndEventAgent==Agent && EndEventKick)','(EndEventAgent==Agent && !EndEventUpper && EndEventKick)')
s=s.replace('(EndEventAgent==Agent && EndEventRightKick)','(EndEventAgent==Agent && !EndEventUpper && EndEventRightKick)')
s=s.replace('if (EndEventAgent==Agent && !Active.Contains(Agent)', 'if (EndEventAgent==Agent && !EndEventUpper && !Active.Contains(Agent)')
# A lower profile setter disabling its blend must not cancel the pending upper event.
s=s.replace('if (R->Settings.End()<=0) Cancel(Agent);','if (R->Settings.End()<=0) { const auto* Event=EndEventAgent;Cancel(Agent);EndEventAgent=Event; }')
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('Source/GameAnimationSample3/Private/ProphecyNNSlashRuntime.inl');s=p.read_text(encoding='utf-8')
s=s.replace('\tProphecyRootBalance::CancelKickException(Actor);','\tif (!bHalf) ProphecyRootBalance::CancelKickException(Actor);',1)
s=s.replace('\tProphecyWalkPinning::ResetSmoothing(Actor);','\tif (!bHalf) ProphecyWalkPinning::ResetSmoothing(Actor);',1)
s=s.replace('ProphecyAttackRecovery::EnterSpecial(Actor);','ProphecyAttackRecovery::EnterSpecial(Actor,bHalf);',1)
s=s.replace('\tProphecyKickFootLeeway::Begin(Actor,Attack);','\tif (!bHalf) ProphecyKickFootLeeway::Begin(Actor,Attack);',1)
# Extract the existing root return into a reusable native member helper, without changing retained layouts.
start=s.index('\tProphecyRootBalance::BeginKickException(Actor,EndedAttack,bReturnToLocomotion);')
end=s.index('\tActor->EndAttackFists();',start)
old=s[start:end]
root=old[:old.index('\tSlash.bActive = false;')]
root=root.replace('EndedAttack','Slash.Family')
root+='''\tProphecyKickFootLeeway::End(Actor,bReturnToLocomotion);
\tif (bHasReturnTarget) SetAgentLocomotionRootWindowLocation(Handle, ReturnTarget, true);
\tif (PlayerSpring && bReturnToLocomotion) ProphecyAttackCamera::CompensateRootSnap(Actor,PreviousCameraOrigin);
\tif (bReturnToLocomotion) ProphecyRootPelvisBounds::ResetMagicCubeToRoot(Actor);
'''
s=s[:start]+'''\tif (!bEndedHalfAttack) ReturnAttackLowerToLocomotion(Handle,bReturnToLocomotion);
\tSlash.bActive = false;
#if !UE_BUILD_SHIPPING
\tSlashTrainFrame::Ended(Actor);
#endif
\tProphecyAttackCheckpoint::Select(this,Actor,0,true);
'''+s[end:]
s=s.replace('\tif (bReturnToLocomotion) ProphecyAttackRecovery::Begin(Actor,EndedAttack);\n','')
pos=s.index('bool AProphecyNNLocomotionManager::SetAgentNNHalfAttack(')
s=s[:pos]+'''void AProphecyNNLocomotionManager::ReturnAttackLowerToLocomotion(FProphecyAgentHandle Handle,bool bReturnToLocomotion)
{
\tAProphecyAgent* Actor=ResolveAgent(Handle);
\tif (!Actor) return;
\tauto& Slash=Impl->Agents[Handle.Index].Slash;
'''+root+'''}

'''+s[pos:]
s=s.replace('''\tif (Slash.bHalf && !bHalf)
\t{''','''\tif (Slash.bHalf && !bHalf)
\t{
\t\tProphecyAttackRecovery::EnterLowerSpecial(Actor);
\t\tProphecyWalkPinning::ResetSmoothing(Actor);''')
s=s.replace('''\tif (bHalf)
\t{
\t\tProphecyAttackStartInertia::Cancel(Actor);''','''\tif (bHalf)
\t{
\t\tReturnAttackLowerToLocomotion(Handle,true);
\t\tProphecyAttackStartInertia::Cancel(Actor);''')
s=s.replace('''\tSlash.bHalf = bHalf;
\tSlash.bNeedsFeedback = true;
\treturn true;''','''\tSlash.bHalf = bHalf;
\tSlash.bNeedsFeedback = true;
\t// Commit ownership before dispatch: a callback can stop/reset/retrigger.
\tif (bHalf) ProphecyAttackRecovery::NotifyLowerEnded(Actor,Slash.Family,true,true);
\treturn true;''',1)
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('Source/GameAnimationSample3/Private/ProphecyNNDefenseRuntime.inl');s=p.read_text(encoding='utf-8').replace('    if (bReturnToLocomotion) ProphecyAttackRecovery::Begin(Actor);\n','');p.write_text(s,encoding='utf-8',newline='\n')

p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp');s=p.read_text(encoding='utf-8')
# Lower locomotion controls stay available during half ownership, including recovery after a full -> half release.
a=s.index('void AProphecyNNLocomotionManager::ApplyOutputBatch');b=s.index('void AProphecyNNLocomotionManager::',a+10)
part=s[a:b].replace('Agent.DefensePose || Agent.Slash.bActive ||','Agent.DefensePose || (Agent.Slash.bActive && !Agent.Slash.bHalf) ||')
part=part.replace('!Agent.Slash.bActive','(!Agent.Slash.bActive || Agent.Slash.bHalf)')
part=part.replace('// Tempering is locomotion-only. Half attacks also need their lower-body\n\t\t// movement unmodified, even though they use the locomotion lower policy.','// The lower body remains locomotion-owned during half attacks.')
s=s[:a]+part+s[b:]
s=s.replace('const auto* CalfTempering=!Agent.DefensePose && !Agent.Slash.bActive','const auto* CalfTempering=!Agent.DefensePose && (!Agent.Slash.bActive || Agent.Slash.bHalf)')
s=s.replace('if(!Agent.Slash.bActive && !Agent.DefensePose && T->Current.Valid','if((!Agent.Slash.bActive || Agent.Slash.bHalf) && !Agent.DefensePose && T->Current.Valid')
p.write_text(s,encoding='utf-8',newline='\n')
