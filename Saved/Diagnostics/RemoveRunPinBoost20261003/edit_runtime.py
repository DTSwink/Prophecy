from pathlib import Path
root=Path(__file__).resolve().parents[3]
def edit(name, fn):
    p=root/name; old=p.read_text(encoding='utf-8-sig'); new=fn(old)
    assert old!=new,name
    p.write_text(new,encoding='utf-8',newline='')
def cut(s,start,end):
    a=s.index(start); b=s.index(end,a); return s[:a]+s[b:]
edit('Source/GameAnimationSample3/Public/ProphecyWalkPinningLibrary.h',lambda s:cut(s,'    /** Run only:',"    /** Raise the opposite"))
def walk(s):
    s=s.replace('#include "ProphecyAttackControls.h"\n','')
    s=cut(s,'static TMap<TWeakObjectPtr<const AProphecyAgent>,float> RunBoosts;','// Separate storage')
    s=s.replace(' && RunBoosts.IsEmpty()','')
    s=s.replace('            for (auto It=RunBoosts.CreateIterator();It;++It)\n                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();\n','')
    s=cut(s,'bool UProphecyWalkPinningLibrary::SetRunPinningBoost','bool UProphecyWalkPinningLibrary::SetWalkPinningEveryTick')
    return cut(s,'IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRunPinningBoostTest','IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningCircleBoundTest')
edit('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp',walk)
edit('Source/GameAnimationSample3/Private/ProphecyWalkPinning.h',lambda s:s.replace('void BoostRunPin(const AProphecyAgent* Agent,float& Left,float& Right);\n',''))
def controls(s):
    s=cut(s,'struct FBoost','static TSet<TWeakObjectPtr<const AProphecyAgent>> Blocked')
    s=cut(s,'    for(auto It=Returns.CreateIterator();It;++It)','    RefreshTick();')
    s=s.replace('Returns.IsEmpty() && ','').replace('ReturnTick','CounterTick')
    s=cut(s,'void CancelLowerReturn','void ForgetReset')
    s=s.replace('ResetBoosts.Remove(A);','').replace('CancelLowerReturn(A);','').replace('Boosts.Remove(A);','')
    s=s.replace('    if(const auto* B=Boosts.Find(A))ResetBoosts.Add(A,*B);else \n','')
    s=s.replace('    if(const auto* B=ResetBoosts.Find(A))Boosts.Add(A,*B);else \n','')
    s=cut(s,'bool UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost','#if WITH_DEV_AUTOMATION_TESTS')
    s=s.replace('#include "ProphecyAttackRecovery.h"\n','').replace('#include "ProphecyWalkPinning.h"\n','')
    s=s.replace('FProphecyAttackRecoveryBoostGateTest','FProphecyAttackArmedGateTest').replace('RecoveryAndArmedGate','ArmedGate')
    s=cut(s,'    const int32 Before=Returns.Num();','    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,true);')
    s=s.replace('    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,true);CaptureReset(A);','    TestFalse(TEXT("Armed block defaults off"),ArmedBlocked(A));\n    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,true);CaptureReset(A);')
    s=s.replace('    UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,false,0,0,0);\n','')
    s=cut(s,'    BeginLowerReturn(A);TestEqual','    for(bool Legacy:')
    s=s.replace('if(Before==0 && SinceLowerAttack.IsEmpty())','if(SinceLowerAttack.IsEmpty())').replace('No active returns/counters leaves no tick delegate','No counters leaves no tick delegate')
    s=s.replace('    ProphecyAttackRecovery::Remove(A);UProphecyWalkPinningLibrary::SetRunPinningBoost(A,0);\n','')
    assert 'Boost' not in s and 'Returns' not in s
    return s
edit('Source/GameAnimationSample3/Private/ProphecyAttackControls.inl',controls)
edit('Source/GameAnimationSample3/Private/ProphecyAttackControls.h',lambda s:s.replace('void BeginLowerReturn(const AProphecyAgent* Agent);\n','').replace('void CancelLowerReturn(const AProphecyAgent* Agent);\n','').replace('float RunBoost(const AProphecyAgent* Agent,float Normal);\n',''))
edit('Source/GameAnimationSample3/Private/ProphecyGhostAttackLibrary.cpp',lambda s:s.replace('#include "ProphecyWalkPinningLibrary.h"\n',''))
def recovery(s):
    s=s.replace('    ProphecyAttackControls::CancelLowerReturn(Agent);\n','').replace('            if(Special==EProphecyAgentState::Attacking)ProphecyAttackControls::BeginLowerReturn(Agent);\n','')
    s=s.replace('static EProphecyAgentState EndEventSpecial=EProphecyAgentState::Locomotion;\n','').replace('    TGuardValue<EProphecyAgentState> SpecialScope(EndEventSpecial,Special);\n','')
    s=s.replace('bool IsLowerAttackEndEvent(const AProphecyAgent* Agent)\n{ return Agent && EndEventAgent==Agent && !EndEventUpper && EndEventSpecial==EProphecyAgentState::Attacking; }\n','')
    return s
edit('Source/GameAnimationSample3/Private/ProphecyAttackRecoveryLibrary.cpp',recovery)
edit('Source/GameAnimationSample3/Private/ProphecyAttackRecovery.h',lambda s:s.replace('bool IsLowerAttackEndEvent(const AProphecyAgent* Agent);\n',''))
edit('Source/GameAnimationSample3/Public/ProphecyAgent.h',lambda s:cut(s,"\t/** Upper height of locomotion's near-ground forced pin",'\t/** Full attacks only: maximum'))
edit('Source/GameAnimationSample3/Private/ProphecyAgent.cpp',lambda s:cut(s,'bool AProphecyAgent::SetLocomotionFootPinningThreshold','bool AProphecyAgent::SetAttackFootClamp'))
def manager(s):
    for line in s.splitlines(keepends=True):
        if any(x in line for x in ('NearFloorFullHeight','NearFloorFadeHeight','NearFloorMinPin')) and ('float NearFloor' in line or 'TryGetNumberField' in line):s=s.replace(line,'')
    s=s.replace('\t\t\tfloat Heights[2] = { 0.0f, 0.0f };\n','')
    a=s.index('\t\t\tconst int32 ToeOffsets[2] = { 24, 40 };',s.index('auto CorrectPolicy'))
    b=s.index('\t\t\tRawPin = ',a)
    s=s[:a]+s[a:b].split('\n',1)[0]+'\n'+s[b:]
    s=cut(s,'\t\t\tconst AProphecyAgent* PinActor =','\t\t\tconst bool bTransfer=')
    return s
edit('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp',manager)
edit('Tools/NN/AttackControls/TestAttackControls.py',lambda s:'\n'.join(line for line in s.splitlines() if not line.startswith('pins=') and "assert not pins." not in line).replace('RecoveryAndArmedGate','ArmedGate').replace('+Prophecy.NN.RunPinning.HighestBoost','+Prophecy.NN.AttackControls.EntryMagicAndTicks')+'\n')
print('Runtime Run boost removal applied')
