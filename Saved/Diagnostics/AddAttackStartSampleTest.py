from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp');s=p.read_text(encoding='utf-8')
old='    const int32 Id=-935;\n'
new=old+'''    const TArray<FName> PelvisName={TEXT("pelvis")};
    const TArray<FTransform> LocalPelvis={FTransform(FVector(10,2,90))};
    const FTransform RootA(FRotator(0,20,0),FVector(200,50,0));
    const FTransform RootB(FRotator(0,40,0),FVector(210,55,0));
    FProphecyNNPoseStore::SetAgentLocalPose(Id,PelvisName,LocalPelvis,LocalPelvis,LocalPelvis,RootA,RootB,1.);
    ProphecyNNPresentation::Publish(Id,1.,.5f);
    FTransform Sampled;
    Test.TestTrue(TEXT("Pelvis-only read works without copying a full pose"),ProphecyNNPresentation::ReadPelvisWorld(Id,Sampled));
    Test.TestTrue(TEXT("Entry sampling includes root translation and rotation"),Sampled.GetLocation().Equals(
        ((LocalPelvis[0]*RootA).GetLocation()+(LocalPelvis[0]*RootB).GetLocation())*.5,1.e-9));
    FProphecyNNPoseStore::ClearAgentPose(Id);
'''
assert old in s;s=s.replace(old,new,1);p.write_text(s,encoding='utf-8')
