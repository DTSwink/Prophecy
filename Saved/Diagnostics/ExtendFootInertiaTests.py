from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp');s=p.read_text();key='    CaptureReset(A);\n'
new=r'''    // Both feet can run without pelvis inertia and retire independently.
    Remove(A);
    Test.TestTrue(TEXT("Feet-only configuration accepted"),UProphecyAttackStartInertiaLibrary::SetAttackStartPelvisInertia(
        A,true,5,0,5,0,5,1,7,1,4,1,6,1));
    FHistories FeetHist;
    for(int32 B=1;B<3;++B)
    {
        auto& H=FeetHist.Body[B];H.Current=Start;H.Previous=Start;H.Tick=200;H.Samples=2;
        H.Previous.AddToTranslation(-Delta*B);
        H.Previous.SetRotation((ProphecyPelvisInertia::RotationIncrement(-Angular*B)*Start.GetRotation()).GetNormalized());
    }
    History.Add(A,FeetHist);Begin(A,Id,Start,Goal);Entries.FindChecked(A).Tick=200;
    const FTransform FootGoals[]={Goal,Goal,Goal};const bool FootValid[]={false,true,true};
    for(int32 Frame=1;Frame<=7;++Frame)
    {
        AdvanceAll(A,Id,FootGoals,FootValid,200+Frame);
        for(int32 B=1;B<3;++B)
        {
            const auto& H=History.FindChecked(A).Body[B];
            if(Frame==1)Test.TestTrue(TEXT("Each foot preserves its own WORLD delta"),H.Current.Equals(Step(Start,Goal,Delta*B,Angular*B,1,1),1.e-8));
            if(Frame==(B==1?5:4))Test.TestTrue(TEXT("Foot translation retires independently"),H.Current.GetLocation()==Goal.GetLocation());
            if(Frame==(B==1?7:6))Test.TestTrue(TEXT("Foot rotation retires independently"),H.Current.GetRotation().Equals(Goal.GetRotation(),1.e-10));
        }
        Test.TestEqual(TEXT("Feet-only mode collects no pelvis history"),History.FindChecked(A).Body[0].Samples,0);
        AdvanceAll(A,Id,FootGoals,FootValid,200+Frame);
        Test.TestEqual(TEXT("Duplicate update preserves active correction"),Active(Id),Frame<7);
    }
    Test.TestFalse(TEXT("Foot entry fully retires"),Entries.Contains(A));
'''
s=s.replace(key,new+key,1)
key='    EraseCorrection(Id);Repeated=Source;Apply(Id,Names,Repeated);'
new=r'''    // Combined hip/ankle solve preserves lengths, toe mounting and render parity.
    const FTransform FootGoal(FRotator(8,-20,12),Source[4].GetLocation()+FVector(4,2,1));
    { FWriteScopeLock Lock(CorrectionLock);auto& C=Corrections.FindChecked(Id);C.Body[1]={Source[4],FootGoal,true}; }
    auto Combined=Source;Apply(Id,Names,Combined);
    Test.TestTrue(TEXT("Reachable foot inertia target reached"),Combined[4].Equals(FootGoal,1.e-8));
    Test.TestTrue(TEXT("Foot rotation carries toe mount"),Combined[5].GetRelativeTransform(Combined[4]).Equals(Source[5].GetRelativeTransform(Source[4]),1.e-8));
    Test.TestTrue(TEXT("Simultaneous pelvis/foot corrections keep calf length"),FMath::IsNearlyEqual((Combined[4].GetLocation()-Combined[3].GetLocation()).Length(),Lower,1.e-8));
    auto CombinedLocal=Source;for(auto& B:CombinedLocal)B=B.GetRelativeTransform(Space);
    Apply(Id,Names,CombinedLocal,Space);
    for(int32 B=0;B<Combined.Num();++B)Test.TestTrue(TEXT("Combined foot rendering matches physical target"),(CombinedLocal[B]*Space).Equals(Combined[B],1.e-7));
    FTransform FarFoot=FootGoal;FarFoot.AddToTranslation(FVector(1000,0,0));
    auto Far=Source;MoveLeg(Far[2],Far[3],Far[4],&Far[5],Far[2].GetLocation(),&FarFoot);
    Test.TestTrue(TEXT("Unreachable foot projected without stretching"),FMath::IsNearlyEqual((Far[4].GetLocation()-Far[3].GetLocation()).Length(),Lower,1.e-7));
    Test.TestTrue(TEXT("Projected foot retains requested rotation"),Far[4].GetRotation().Equals(FarFoot.GetRotation(),1.e-9));
'''
s=s.replace(key,new+key)
p.write_text(s)
