"""One-shot checked migration of upper publication; retained for the audit trail."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'Source/GameAnimationSample3/Private'
p=root/'ProphecyNNLocomotionManager.cpp'
s=p.read_text()
def replace(a,b):
    global s
    assert s.count(a)==1,(a[:100],s.count(a))
    s=s.replace(a,b)
def cut(a,b):
    global s
    i=s.index(a);j=s.index(b,i);s=s[:i]+s[j:]
replace('#include "ProphecyAttackRecovery.h"','#include "ProphecyAttackRecovery.h"\n#include "ProphecyFKReturn.h"')
replace('\t\tProphecyUpperBodyInertia::Remove(AgentActor);','\t\tProphecyUpperBodyInertia::Remove(AgentActor);\n\t\tProphecyFKReturn::Remove(AgentActor);')
replace('\t\tif (!Agent.Slash.bActive && !Agent.DefensePose) ProphecyHandRecovery::Step(InputActor);','\t\t// Upper return is publication-only FK; lower recovery remains independent.')
replace('\t\tif (const auto* H=ProphecyHandRecovery::Frame(AgentActors[AgentIndex]))\n\t\t{ bNeedRun|=H->Need[0];bNeedWalk|=H->Need[1]; }','')
cut('\t// Preserve source outputs before the ordinary walk-only lane overwrites Run.','\tif (bNeedWalk)\n')
replace('\t\tif (auto* H=ProphecyHandRecovery::Frame(Actor))\n\t\t\tfor(int32 P=0;P<2;++P) if(H->Need[P]) RebaseStateRoot(H->Lower[P],*Impl,NextRootDelta,NextYawDelta);','')
cut('\t\tif (auto* H=ProphecyHandRecovery::Frame(AgentActors[AgentIndex]))','\t\tFVector2D RawDebug')
replace('namespace { bool RunHandRecoverySources(AProphecyNNLocomotionManager* Manager,AProphecyNNLocomotionManager::FImpl* Impl,TArrayView<TObjectPtr<AProphecyAgent>> Actors); }\n','')
replace('\treturn RunHandRecoverySources(this,Impl,MakeArrayView(AgentActors));','\treturn true; // One vanilla upper inference. No auxiliary walk/run hand policies.')
cut('namespace {\nvoid MixHandRecoveryUpper','void AProphecyNNLocomotionManager::ApplyUpperOutputBatch()')
cut('\t\t// Inference and recovery sources predict in the next root frame.','\t\tFMemory::Memcpy(Published, CurrentUpper, UpperStateDim * sizeof(float));')
cut('\t\tconst float CoreFollow=','\t\tFMemory::Memcpy(CurrentBase, NextBase, UpperStateDim * sizeof(float));')
cut('\tconst auto* HandTempering=!Agent.DefensePose','\tif (bDefensePose)\n')
cut('\tif (bTemperArms) for(int32 I=0;I<2;++I)','\t// Attacks constrain their native output')
replace('\tconst float WristDegrees=Agent.Slash.bActive?-1.f:EffectiveWrist;', '\t// Locomotion upper output is unfiltered. Defense keeps its explicit wrist control.\n\tconst float WristDegrees=bDefensePose?EffectiveWrist:-1.f;')
replace('bWristChanged || bTemperCalves || bTemperArms || bDefensePose','bWristChanged || bTemperCalves || bDefensePose')
cut('\tif (!bManualArmed && !Agent.Slash.bActive && !bDefensePose && ProphecyUpperBodyInertia::Active','\tconst AProphecyAgent* ClampActor = AgentActors[AgentIndex];')
replace('\tFProphecyNNPoseStore::SetAgentLocalPose(\n', '''\t// The clean NN endpoint above never receives recovery feedback. Sample the lab
\t// in parent space after normal anatomical decoding and before publishing.
\tconst auto* ReturnClock=ProphecyAgentTime::Context(this);
\tconst double ReturnInterval=ReturnClock?ReturnClock->Step->WorldIntervals[AgentIndex]:
\t\t1.0/(NNUpdateHz*FMath::Max(.001f,ProphecyAgentTime::Rate(this,AgentIndex)));
\tconst bool bFKReturn=!bManualArmed && !Agent.Slash.bActive && !bDefensePose &&
\t\tProphecyFKReturn::Apply(Controls,SourceTimeSeconds-ReturnInterval,SourceTimeSeconds,
\t\t\tPreviousComponentTransforms,ComponentTransforms,LocalTransforms);
\tFProphecyNNPoseStore::SetAgentLocalPose(
''')
replace('FixedArms,Agent.Slash.bActive && Agent.Slash.bHalf,C.bFixedArms);','FixedArms,Agent.Slash.bActive && Agent.Slash.bHalf,C.bFixedArms && !bFKReturn);')
p.write_text(s)
p=root/'ProphecyNNSlashRuntime.inl';s=p.read_text()
cut('\tconst auto& InertiaAgent=Impl->Agents[Handle.Index];','\tif (!bEndedHalfAttack)')
replace('\tSlash.bActive = false;','''\tSlash.bActive = false;
\tif (bReturnToLocomotion)
\t\tProphecyFKReturn::Begin(Actor,EndedAttack,Impl->BodyNames,Impl->Parents,
\t\t\tTransformSlice(Impl->PreviousComponentTransformBuffer,Handle.Index),
\t\t\tTransformSlice(Impl->ComponentTransformBuffer,Handle.Index),
\t\t\tImpl->Agents[Handle.Index].PublishedPoseTimeSeconds,1.f/NNUpdateHz);
\telse ProphecyFKReturn::Cancel(Actor);''')
cut('\tif (bReturnToLocomotion && !Slash.bActive && !Impl->Agents[Handle.Index].DefensePose && ProphecyUpperBodyInertia::Configured','\treturn true;\n')
p.write_text(s)
p=root/'ProphecyAttackRecoveryLibrary.cpp';s=p.read_text()
replace('#include "ProphecyAttackRecovery.h"','#include "ProphecyAttackRecovery.h"\n#include "ProphecyFKReturn.h"')
replace('void EnterSpecial(const AProphecyAgent* Agent,bool Half)\n{','void EnterSpecial(const AProphecyAgent* Agent,bool Half)\n{\n    ProphecyFKReturn::Cancel(Agent);')
replace('''            ProphecyHandRecovery::Begin(Agent);ProphecyCoreTempering::Begin(Agent);
            ProphecySlashReturn::Begin(Agent,Attack);
            if(Special==EProphecyAgentState::Attacking) ProphecyArmCone::Begin(Agent,Attack);''','''            // Legacy nodes can still exist in assets, but no upper modifiers enter
            // locomotion. The attack handoff has already captured its FK return.
            ProphecyHandRecovery::CancelMotion(Agent);ProphecyCoreTempering::CancelMotion(Agent);
            ProphecySlashReturn::Cancel(Agent);ProphecyUpperBodyInertia::Cancel(Agent);
            ProphecyArmCone::Cancel(Agent);''')
p.write_text(s)
p=root/'ProphecyNNAgentReset.inl';s=p.read_text()
replace('        ProphecyAttackRecovery::Cancel(Actor);','        ProphecyAttackRecovery::Cancel(Actor);\n        ProphecyFKReturn::Cancel(Actor);')
p.write_text(s)
print('Integrated FK return, removed legacy upper feedback/publication; lower path preserved.')
