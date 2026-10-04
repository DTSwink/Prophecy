from pathlib import Path
root=Path('Source/GameAnimationSample3/Private')
entries={
'ProphecyModeTransitions.cpp':r'''
void ProphecyNNModifierDebug::Presentation(FReport& R)
{
    const auto* S=ModeTransitionStorage().Blends.Find(R.Agent);
    if(S)R.Add(TEXT("ModeTransition"),TEXT("PRESENT"),TEXT("Simulation mode pose blend"),FString::Printf(TEXT("%.3f / %.3f authored seconds"),S->Start,BlendSeconds));
}
''',
'ProphecyAttackFists.cpp':r'''
void ProphecyNNModifierDebug::Fists(FReport& R)
{
    if(!R.Agent->bEnableAttackFists)return;
    const auto* S=Storage().States.Find(R.Agent);if(!S)return;
    const double Alpha=S->Duration<=UE_SMALL_NUMBER?1.:FMath::Clamp((S->StartTime+1.e-7)/S->Duration,0.,1.);
    const auto V=FMath::Lerp(S->Start,S->Target,Alpha);
    if(!V.IsNearlyZero())R.Add(TEXT("Fingers"),TEXT("PRESENT"),TEXT("Authored closed fingers"),FString::Printf(TEXT("last accepted L %.3f R %.3f | does not change NN wrist channels"),V.X,V.Y));
}
''',
'ProphecyPhysicalFootTargetLibrary.cpp':r'''
void ProphecyNNModifierDebug::ClampBlends(FReport& R)
{
    using namespace ProphecyClampEase;
    const auto* S=States.Find(R.Agent);
    const bool Physical=R.Agent->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic;
    static const TCHAR* Names[]={TEXT("Foot reach"),TEXT("Calf length"),TEXT("Physical calf"),TEXT("Physical foot target"),TEXT("Left wrist")};
    if(S)for(int32 I=0;I<int32(EChannel::Count);++I)
    {
        const auto& C=S->Values[I];if(!C.Active || ((I==2 || I==3) && !Physical))continue;
        const FString Key=FString::Printf(TEXT("ClampTighten%d"),I);
        R.Add(*Key,TEXT("CONSTRAINT"),*FString::Printf(TEXT("%s tightening"),Names[I]),FString::Printf(TEXT("%.3f -> %.3f | %.3f / %.3f"),C.Value,C.Target,C.Elapsed,Duration));
    }
    if(Physical)
    {
        const auto Mode=R.Defense?(R.Dodge?EProphecyAgentState::Dodging:EProphecyAgentState::Parrying):R.Attack&&!R.Half?EProphecyAgentState::Attacking:EProphecyAgentState::Locomotion;
        const auto* C=ProphecyPhysicalFootTarget::Overrides.Find(R.Agent);
        const float Foot=Current(R.Agent,EChannel::PhysicalFoot,C?C->For(Mode):0);
        const float Calf=Current(R.Agent,EChannel::PhysicalCalf,ProphecyPhysicalFootTarget::CalfLeewayFor(R.Agent,Mode));
        R.Add(TEXT("PhysicalFootTarget"),TEXT("PHYSICS"),TEXT("Physical foot target / calf joint limits"),FString::Printf(TEXT("foot offset %.3f cm | calf allowance %.3f cm"),Foot,Calf));
    }
}
''',
'ProphecyNNPoseTypes.cpp':r'''
void ProphecyNNModifierDebug::PosePresentation(FReport& R)
{
    FReadScopeLock Lock(GProphecyNNPoseLock);
    if(const auto* Zone=GKneePopSmoothing.Find(R.PoseId))
        R.Add(TEXT("KneeSoftIK"),TEXT("CONSTRAINT"),TEXT("Knee pop smoothing / soft IK"),FString::Printf(TEXT("zone %.3f cm | presentation only"),*Zone));
}
''',
}
for name,code in entries.items():
    p=root/name;s=p.read_text(encoding='utf-8-sig');s='#include "ProphecyNNModifierDebug.h"\n'+s
    p.write_text(s+'\n'+code,encoding='utf-8')
