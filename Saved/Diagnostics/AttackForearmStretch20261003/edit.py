from pathlib import Path
import shutil
root=Path.cwd()
backup=root/'Saved/Diagnostics/AttackForearmStretch20261003/Before'
def edit(name,old,new):
    p=root/name
    b=backup/name
    if not b.exists():
        b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
    s=p.read_text(encoding='utf-8-sig')
    assert old in s,(name,old[:100])
    p.write_text(s.replace(old,new),encoding='utf-8')
g='Source/GameAnimationSample3/'
j='Plugins/ProphecyJolt/Source/ProphecyJolt/'
edit(g+'Public/ProphecyAttackWristLibrary.h','public:\n','''public:
    /** Preserve checkpoint forearm compression/extension during full and half attacks.
     * At upper-body release, capture each arm's length independently and return it
     * to reference length over ReturnTime (60 game ticks per second). Physical
     * wrists capture their own lengths and follow the same duration. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent"))
    static bool SetAttackForearmStretchReturn(AProphecyAgent* Agent,bool Enabled=true,
        UPARAM(meta=(ClampMin="0")) float ReturnTime=.3f);

''')
edit(g+'Private/ProphecyAttackWristLibrary.cpp','#include "ProphecyAttackWrist.h"','#include "ProphecyAttackWrist.h"\n#include "ProphecyForearmStretch.h"')
edit(g+'Private/ProphecyAttackWristLibrary.cpp','return !Freedom.IsEmpty() && (Freedom.FindRef(Agent)&1)!=0;','return ProphecyForearmStretch::OwnsPosition(Agent) || (!Freedom.IsEmpty() && (Freedom.FindRef(Agent)&1)!=0);')
for f in ['ProphecyNNLocomotionManager.cpp','ProphecyAttackRecoveryLibrary.cpp','ProphecyAgentResetPhysics.cpp','ProphecyAttackStartHandInertia.cpp','ProphecyJoltCharacterComponent.cpp']:
    edit(g+'Private/'+f,'#include "ProphecyAgent.h"','#include "ProphecyAgent.h"\n#include "ProphecyForearmStretch.h"')
edit(g+'Private/ProphecyAttackRecoveryLibrary.cpp','void EnterSpecial(const AProphecyAgent* Agent,bool Half)\n{','void EnterSpecial(const AProphecyAgent* Agent,bool Half)\n{\n    ProphecyForearmStretch::Cancel(const_cast<AProphecyAgent*>(Agent));')
edit(g+'Private/ProphecyNNSlashRuntime.inl','ProphecyAttackRecovery::EnterSpecial(Actor,bHalf);','ProphecyAttackRecovery::EnterSpecial(Actor,bHalf);\n\tProphecyForearmStretch::Begin(Actor);')
edit(g+'Private/ProphecyNNSlashRuntime.inl','AttackEndPredictions.Remove(Actor);\n\tProphecyAttackStartFKCore::Cancel(Actor);','AttackEndPredictions.Remove(Actor);\n\tProphecyForearmStretch::End(Actor,bReturnToLocomotion);\n\tProphecyAttackStartFKCore::Cancel(Actor);')
edit(g+'Private/ProphecyNNLocomotionManager.cpp','ProphecyAttackStartHands::Remove(AgentActor);','ProphecyAttackStartHands::Remove(AgentActor);\n\t\tProphecyForearmStretch::Remove(AgentActor);')
edit(g+'Private/ProphecyNNLocomotionManager.cpp','if(bNewFKSample)CommitFKReturnUpperPose(*Impl,AgentIndex,ComponentTransforms);','''const bool bLengthReturn=ProphecyForearmStretch::Apply(Controls,Impl->PublishedBoneNames,
        PreviousComponentTransforms,ComponentTransforms,LocalTransforms,bFKReturn);
	if(bNewFKSample || bLengthReturn)CommitFKReturnUpperPose(*Impl,AgentIndex,ComponentTransforms);''')
for method in ['ForgetReset','CaptureReset','Cancel','RestoreReset']:
    edit(g+'Private/ProphecyAgentResetPhysics.cpp',f'ProphecyAttackStartHands::{method}(Agent);',f'ProphecyAttackStartHands::{method}(Agent);\n    ProphecyForearmStretch::{method}(Agent);')
edit(g+'Private/ProphecyJoltCharacterComponent.cpp','!ProphecyKickFootLeeway::Reapply(Agent,Error)','!ProphecyKickFootLeeway::Reapply(Agent,Error) || !ProphecyForearmStretch::Reapply(Agent,Error)')
edit(g+'Private/ProphecyAttackStartHandInertia.cpp','double Dt,const FTransform& Root)\n{','double Dt,const FTransform& Root,bool VariableLength=false)\n{')
edit(g+'Private/ProphecyAttackStartHandInertia.cpp','Follow,M.ForearmLength);','Follow,VariableLength?FVector::Distance(Goal[1].GetLocation(),Goal[2].GetLocation()):M.ForearmLength);')
edit(g+'Private/ProphecyAttackStartHandInertia.cpp','else Solve(*State,Pose,Carrier,Dt>0?PoseStepSeconds:0.,Root);','else Solve(*State,Pose,Carrier,Dt>0?PoseStepSeconds:0.,Root,ProphecyForearmStretch::OwnsPosition(A));')
edit(g+'Private/ProphecySlashTrainDebug.inl','if (Actor->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic || A.Slash.bActive','if ((OriginalGTAttack.IsNone() && Actor->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic) || A.Slash.bActive')
edit(g+'Private/ProphecySlashTrainDebug.inl','    const TSharedPtr<FJsonObject>* History=nullptr;','''    if (bOriginalGT && Actor->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)
    {
        // Simulated GT repeats keep the live pose, velocity and recurrent history.
        // Only resolve the authored target in the current mover frame.
        SlashTrainFrame::Frames.Remove(Actor);
        if(OutGTTarget)*OutGTTarget=SlashComponentWorld(Actor,A.PublishedRoot,A.PublishedYaw).TransformPosition(LocalGTTarget);
        return true;
    }
    const TSharedPtr<FJsonObject>* History=nullptr;''')
edit(g+'Public/ProphecyNNPoseTypes.h','public:\n','public:\n    static void SetForearmReturnLengths(int32 AgentId,FVector2D Lengths);\n')
edit(g+'Private/ProphecyNNPoseTypes.cpp','TMap<int32, FProphecyNNPoseSnapshot> GProphecyNNPoses;','TMap<int32, FProphecyNNPoseSnapshot> GProphecyNNPoses;\n    TMap<int32,FVector2D> GForearmReturnLengths;')
edit(g+'Private/ProphecyNNPoseTypes.cpp','GKneeBendFrames.Remove(AgentId);\n}', 'GKneeBendFrames.Remove(AgentId);\n    GForearmReturnLengths.Remove(AgentId);\n}')
edit(g+'Private/ProphecyNNPoseTypes.cpp','GKneeBendFrames.Reset();','GKneeBendFrames.Reset();\n    GForearmReturnLengths.Reset();')
edit(g+'Private/ProphecyNNPoseTypes.cpp','void FProphecyNNPoseStore::ApplyRigidForearms(','''void FProphecyNNPoseStore::SetForearmReturnLengths(int32 AgentId,FVector2D Lengths)
{
    FWriteScopeLock Lock(GProphecyNNPoseLock);
    if(Lengths.X>0 && Lengths.Y>0)GForearmReturnLengths.Add(AgentId,Lengths);
    else GForearmReturnLengths.Remove(AgentId);
}

void FProphecyNNPoseStore::ApplyRigidForearms(''')
edit(g+'Private/ProphecyNNPoseTypes.cpp','static const FName Forearms[] = { TEXT("lowerarm_l"), TEXT("lowerarm_r") };\n\tfor','''static const FName Forearms[] = { TEXT("lowerarm_l"), TEXT("lowerarm_r") };
    FVector2D Lengths=FVector2D::ZeroVector;
    { FReadScopeLock Lock(GProphecyNNPoseLock);if(const auto* L=GForearmReturnLengths.Find(AgentId))Lengths=*L; }
	for''')
edit(g+'Private/ProphecyNNPoseTypes.cpp','if(Transforms.IsValidIndex(H) && Transforms.IsValidIndex(E) && !Offset.IsNearlyZero())\n\t\t\tTransforms[H].SetTranslation(Transforms[E].TransformPosition(Offset));','''if(!Transforms.IsValidIndex(H) || !Transforms.IsValidIndex(E))continue;
        if(Lengths[Side]>0)
        {
            const FVector Axis=(Transforms[H].GetLocation()-Transforms[E].GetLocation()).GetSafeNormal();
            if(!Axis.IsNearlyZero())Transforms[H].SetTranslation(Transforms[E].GetLocation()+Axis*Lengths[Side]);
        }
        else if(!Offset.IsNearlyZero())Transforms[H].SetTranslation(Transforms[E].TransformPosition(Offset));''')
# The Chaos target reader used a private copy of the old rigid-wrist operation.
edit(g+'Private/ProphecyAgent.cpp','const FVector& Offset=AuthoredPose.FixedArms.ForearmOffsets[bLeft?0:1];\n\t\t\t\tif(!Offset.IsNearlyZero())BodyTarget.SetTranslation(Forearm.TransformPosition(Offset));','''const FName Names[]={bLeft?FName(TEXT("lowerarm_l")):FName(TEXT("lowerarm_r")),BodySetup->BoneName};
                FTransform Pair[]={Forearm,BodyTarget};
                int32 PoseId;float Interval;bool Interpolate;
                if(GetNNPoseDataSource(PoseId,Interval,Interpolate))FProphecyNNPoseStore::ApplyRigidForearms(PoseId,AuthoredPose,Names,Pair);
                BodyTarget=Pair[1];''')
# Jolt: separate axial translation constraint leaves authored angular frames intact.
edit(j+'Public/ProphecyJoltFootJointLibrary.h','public:\n','''public:
    UFUNCTION()
    static bool SetWristRange(UObject* WorldContext,FGuid Lifetime,int32 BodySlot,int64 BodyGeneration,
        FVector2D MinimumCm,FVector2D MaximumCm,FVector LeftAxis,FVector RightAxis,FString& OutError);
''')
p=root/(j+'Private/ProphecyJoltWorldSubsystem.cpp')
s=p.read_text()
a=s.index('bool UProphecyJoltFootJointLibrary::SetFootRange(');b=s.index('\nbool UProphecyJoltBodyDriveLibrary::SetDriveFollower',a)
new=s[a:b].replace('SetFootRange','SetWristRange').replace('float CompressionCm,float ExtensionCm,FVector LeftCalfAxis,FVector RightCalfAxis','FVector2D MinimumCm,FVector2D MaximumCm,FVector LeftAxis,FVector RightAxis')
new=new.replace('!FMath::IsFinite(ExtensionCm) || ExtensionCm<0\n        || !FMath::IsFinite(CompressionCm) || CompressionCm<0','MinimumCm.ContainsNaN() || MaximumCm.ContainsNaN() || MinimumCm.X>MaximumCm.X || MinimumCm.Y>MaximumCm.Y')
new=new.replace('    const JPH::Vec3 Minimum(-CompressionCm*.01f,0,0),Maximum(ExtensionCm*.01f,0,0);\n','')
new=new.replace('ExtensionCm==0 && CompressionCm==0','MinimumCm.IsNearlyZero(0) && MaximumCm.IsNearlyZero(0)')
new=new.replace('FootExtensions','WristExtensions').replace('Foot leeway','Wrist leeway').replace('foot leeway','wrist range')
new=new.replace('        for (auto& Entry:*Entries)\n','        for(int Side=0;Side<Entries->Num();++Side)\n        {\n            auto& Entry=(*Entries)[Side];\n            const JPH::Vec3 Minimum(MinimumCm[Side]*.01f,0,0),Maximum(MaximumCm[Side]*.01f,0,0);\n')
new=new.replace('        if (Changed) Wake(); return true;','        }\n        if (Changed) Wake(); return true;')
new=new.replace('TEXT("foot_l")','TEXT("hand_l")').replace('TEXT("foot_r")','TEXT("hand_r")').replace('TEXT("calf_l")','TEXT("lowerarm_l")').replace('TEXT("calf_r")','TEXT("lowerarm_r")').replace('LeftCalfAxis,RightCalfAxis','LeftAxis,RightAxis')
new=new.replace('ExtensionCm*.01f','float(MaximumCm[Side]*.01)').replace('-CompressionCm*.01f','float(MinimumCm[Side]*.01)')
new=new.replace('        Pending.Add(MoveTemp(Entry));','''        Entry.Translation->SetNumVelocityStepsOverride(Original->GetNumVelocityStepsOverride());
        Entry.Translation->SetNumPositionStepsOverride(Original->GetNumPositionStepsOverride());
        Pending.Add(MoveTemp(Entry));''')
new=new.replace('foot-to-calf','hand-to-forearm').replace('calf length','forearm length').replace('Foot extension','Wrist extension').replace('ankle','wrist').replace('calf-axis','forearm-axis')
edit(j+'Private/ProphecyJoltWorldSubsystem.cpp',s[a:b],s[a:b]+'\n'+new)
edit(j+'Private/ProphecyJoltWorldSubsystem.cpp','static TMap<const FRigRecord*,TArray<ProphecyJolt::FootExtension::FJoint>> FootExtensions;','static TMap<const FRigRecord*,TArray<ProphecyJolt::FootExtension::FJoint>> FootExtensions,WristExtensions;')
s=p.read_text();a=s.index('static void RemoveFootExtensions(');b=s.index('\n// Called only at possession',a)
edit(j+'Private/ProphecyJoltWorldSubsystem.cpp',s[a:b],s[a:b]+'\n'+s[a:b].replace('FootExtensions','WristExtensions'))
edit(j+'Private/ProphecyJoltWorldSubsystem.cpp','RemoveFootExtensions(Physics,Rig);','RemoveFootExtensions(Physics,Rig);\n        RemoveWristExtensions(Physics,Rig);')
edit(j+'Private/ProphecyJoltWorldSubsystem.cpp','if (auto* Entries=FootExtensions.Find(Rig)) for (auto& Entry:*Entries)','for(auto* Entries:{FootExtensions.Find(Rig),WristExtensions.Find(Rig)}) if(Entries) for (auto& Entry:*Entries)')
