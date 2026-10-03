exec((__import__('pathlib').Path(__file__).with_name('EditFixedArms.py')).read_text().split("edit('Source/GameAnimationSample3/Public/ProphecyAgent.h'")[0])
def agent(s):
 s='#include "ProphecyFixedArmPhysics.h"\n'+s
 s=s.replace('if (AuthoredPose.ForearmClamp.bEnabled && (BodySetup->BoneName == TEXT("hand_l") || BodySetup->BoneName == TEXT("hand_r")))','if (BodySetup->BoneName == TEXT("hand_l") || BodySetup->BoneName == TEXT("hand_r"))')
 s=sub(s,r'BodyTarget.SetTranslation\(AuthoredPose.ForearmClamp.ClampHand\(BodyTarget.GetTranslation\(\), Forearm,\n\s*AuthoredPose.LocalTransforms\[PoseIndex\].GetTranslation\(\), bLeft \? 0 : 1\)\);','BodyTarget.SetTranslation(Forearm.TransformPosition(AuthoredPose.FixedArms.ForearmOffsets[bLeft?0:1]));')
 s=re.sub(r'\b(PoseReferenceMesh|Mesh|PhysicalMesh)->SetAllBodiesBelowSimulatePhysics\(PhysicalRootBodyName, true, true\);',lambda m:'ProphecyFixedArmPhysics::AttachWrists('+m[1]+');\n\t\t'+m[0],s)
 return s
edit('Source/GameAnimationSample3/Private/ProphecyAgent.cpp',agent)
edit('Source/GameAnimationSample3/Private/ProphecyAgentHalfSimulation.cpp',lambda s:'#include "ProphecyFixedArmPhysics.h"\n'+s.replace('if (!bAlreadySimulating) PoseMesh->SetAllBodiesBelowSimulatePhysics','ProphecyFixedArmPhysics::AttachWrists(PoseMesh);\n\tif (!bAlreadySimulating) PoseMesh->SetAllBodiesBelowSimulatePhysics'))
edit('Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp',lambda s:'#include "ProphecyFixedArmPhysics.h"\n'+s.replace('    FProphecyJoltRigSnapshot Snapshot;\n    FProphecyJoltPreparedRig Prepared;','    ProphecyFixedArmPhysics::AttachWrists(Mesh);\n    FProphecyJoltRigSnapshot Snapshot;\n    FProphecyJoltPreparedRig Prepared;'))
def slash(s):
 needle='\t\tFProphecyNNPoseStore::SetAgentLocalPose(PoseStoreAgentBase + Index, Impl.PublishedBoneNames,'
 assert needle in s
 s=s.replace(needle,'''\t\tFProphecyNNFixedArms FixedArms;
\t\tfor(int32 Side=0;Side<2;++Side)FixedArms.ForearmOffsets[Side]=LocalTrainingToUnreal(Impl.UpperLocalOffsets[Impl.UpperArms[Side].End])*100.;
'''+needle).replace('Snapshot.FixedArms);','FixedArms,Slash.bHalf);')
 # The independent ghost has the same fixed geometry before mounting in half mode.
 needle='\t\t\tFMemory::Memmove(Slash.State.GetData(), Slash.State.GetData() + 41, 41 * sizeof(float));'
 assert needle in s
 s=s.replace(needle,'''\t\t\tfor(const auto& Arm:Impl->UpperArms)
\t\t\t\tSlash.GhostPose[Arm.End].SetLocation(Slash.GhostPose[Arm.Mid].TransformPosition(LocalTrainingToUnreal(Impl->UpperLocalOffsets[Arm.End])*100.));
'''+needle)
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNSlashRuntime.inl',slash)
def defense(s):
 needle='            Pose.R[Mid]=DefenseAxes(Forearm.GetRotation());'
 return s.replace(needle,needle+'\n            Pose.P[End]=UnrealToTraining(Forearm.TransformPosition(LocalTrainingToUnreal(Impl.UpperLocalOffsets[Arm.End])*100.));')
edit('Source/GameAnimationSample3/Private/ProphecyNNDefenseRuntime.inl',defense)
def recover_tests(s):
 s=s.replace('Offset,Pole,Follow);','Offset,Pole,Follow,LowerLength);').replace('Offset,Pole,0.);','Offset,Pole,0.,LowerLength);').replace('Offset,Pole,.3);','Offset,Pole,.3,LowerLength);')
 s=s.replace('    for(double Follow:{0.,.1,.5,.9,1.})','    const double LowerLength=FVector::Distance(W.GetLocation(),E.GetLocation());\n    for(double Follow:{0.,.1,.5,.9,1.})')
 s=s.replace('const FTransform NW(FRotator(5,10,15),NE.GetLocation()+NS.TransformVector(FVector(15,28,6)));','const FTransform NW(FRotator(5,10,15),NE.GetLocation()+NS.TransformVector(FVector(15,28,6).GetSafeNormal()*LowerLength));')
 s=s.replace('// Stretched but deliberately unclamped source converges to EXACT normal,\n    // instead of forcing rest length until the last active sample.','// A new connected source converges to normal without changing either bone length.')
 s=s.replace('Offset,LocalPole,T);','Offset,LocalPole,T,LowerLength);').replace('Offset,LocalPole,.5);','Offset,LocalPole,.5,LowerLength);')
 s=s.replace('    const FTransform Target(FVector(-30.746899,43.775991,-18.572348));','    const double LowerLength=22.349;\n    const FTransform Target(FVector(-30.746899,43.775991,-18.572348));')
 s=s.replace('FMath::Lerp((PW.GetLocation()-PE.GetLocation()).Length(),(NW.GetLocation()-NE.GetLocation()).Length(),T),1.e-6)','LowerLength,1.e-6)')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyHandRecoveryLibrary.cpp',recover_tests)

def snapshot(s):
 pos=s.index('void FProphecyNNPoseStore::SetAgentLocalPose(')
 s=s[:pos]+'''namespace
{
void FixPublishedArms(FProphecyNNPoseSnapshot& Snapshot)
{
    static const FName Hands[]={TEXT("hand_l"),TEXT("hand_r")},Elbows[]={TEXT("lowerarm_l"),TEXT("lowerarm_r")};
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 H=Snapshot.BoneNames.IndexOfByKey(Hands[Side]),E=Snapshot.BoneNames.IndexOfByKey(Elbows[Side]);
        if(!Snapshot.LocalTransforms.IsValidIndex(H) || E==INDEX_NONE)continue;
        auto& Offset=Snapshot.FixedArms.ForearmOffsets[Side];
        // Generic animation/fixture producers establish their geometry once;
        // production NN publishers supply the anatomical contract explicitly.
        if(Offset.IsNearlyZero())Offset=Snapshot.LocalTransforms[H].GetLocation();
        Snapshot.LocalTransforms[H].SetLocation(Offset);
        for(auto* Pose:{&Snapshot.PreviousComponentTransforms,&Snapshot.ComponentTransforms})
            if(Pose->IsValidIndex(H) && Pose->IsValidIndex(E))(*Pose)[H].SetLocation((*Pose)[E].TransformPosition(Offset));
    }
}
}

'''+s[pos:]
 # All snapshot publishing overloads retain fixed offsets for a layout, including simple locals.
 s=s.replace('Snapshot.FixedArms = FixedArms;','for(int32 Side=0;Side<2;++Side)if(!FixedArms.ForearmOffsets[Side].IsNearlyZero())\n        Snapshot.FixedArms.ForearmOffsets[Side]=FixedArms.ForearmOffsets[Side];')
 s=s.replace('Snapshot.Revision = AllocatePoseRevision();','FixPublishedArms(Snapshot);\n\tSnapshot.Revision = AllocatePoseRevision();')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNPoseTypes.cpp',snapshot)
print('Fixed ghost/defense/physics attachment and updated coherent-chain regressions')
