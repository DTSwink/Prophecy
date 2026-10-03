from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp')
s=p.read_text(encoding='utf-8');s+='''
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
bool RunAttackStartInertiaChecks(FAutomationTestBase& Test)
{
    using namespace ProphecyAttackStartInertia;
    const FTransform Start(FRotator(12,73,-8),FVector(300,-120,93));
    const FVector Delta(2,-3,.7),Angular(.02,-.01,.03);
    const FTransform Goal(FRotator(-4,90,15),FVector(280,-95,100));
    const FTransform First=Step(Start,Goal,Delta,Angular,1,1);
    Test.TestTrue(TEXT("Attack entry keeps exact previous WORLD translation delta"),
        (First.GetLocation()-Start.GetLocation()).Equals(Delta,1.e-10));
    Test.TestTrue(TEXT("Attack entry keeps world angular delta, not local multiplication"),
        ProphecyPelvisInertia::RotationVector(First.GetRotation()*Start.GetRotation().Inverse()).Equals(Angular,1.e-10));
    Test.TestTrue(TEXT("Zero inertia exactly bypasses both channels"),Step(Start,Goal,Delta,Angular,0,0).Equals(Goal,0));
    Test.TestEqual(TEXT("Five-frame final weight is zero"),Weight(5,5,1),0.);
    Test.TestEqual(TEXT("Five-frame third weight is half"),Weight(3,5,1),.5);
    Test.TestEqual(TEXT("Zero/one-frame windows bypass"),Weight(1,1,1)+Weight(1,0,1),0.);
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    AProphecyAgent* A=World?World->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    const int32 Id=-935;
    for(int32 FPS:{30,60,120})
    {
        Remove(A);
        UProphecyAttackStartInertiaLibrary::SetAttackStartPelvisInertia(A,true,5,1,7,1);
        FHistory H;H.Current=Start;H.Previous=Start;
        H.Previous.AddToTranslation(-Delta);
        H.Previous.SetRotation((ProphecyPelvisInertia::RotationIncrement(-Angular)*Start.GetRotation()).GetNormalized());
        H.Samples=2;H.Tick=100;History.Add(A,H);
        Begin(A,Id,Start,Goal);Entries.FindChecked(A).Tick=100;
        for(int32 Frame=1;Frame<=7;++Frame)
        {
            Advance(A,Id,Goal,100+Frame);
            const FTransform Published=History.FindChecked(A).Current;
            if(Frame==1)Test.TestTrue(TEXT("Latched first step matches world momentum"),Published.Equals(First,1.e-8));
            if(Frame==5)Test.TestTrue(TEXT("Translation ends exactly at frame 5 while rotation continues"),
                Published.GetLocation()==Goal.GetLocation() && Active(Id));
            const auto Copy=Published;
            Advance(A,Id,FTransform::Identity,100+Frame);
            Test.TestTrue(TEXT("Repeated reads/rebases cannot spend another frame"),History.FindChecked(A).Current.Equals(Copy,0));
        }
        Test.TestFalse(FString::Printf(TEXT("Retires after 7 game ticks at %d FPS"),FPS),Active(Id));
        Test.TestFalse(TEXT("Finished entry retains no correction state"),Entries.Contains(A));
        Test.TestTrue(TEXT("Final transform exactly attack-authored"),History.FindChecked(A).Current.Equals(Goal,0));
    }
    CaptureReset(A);
    UProphecyAttackStartInertiaLibrary::SetAttackStartPelvisInertia(A,false,5,1,5,1);
    Test.TestFalse(TEXT("Disable removes idle history too"),History.Contains(A)||Configs.Contains(A));
    RestoreReset(A);Test.TestTrue(TEXT("Reset restores configured controls"),Configs.Contains(A));
    Test.TestFalse(TEXT("Reset cancels active motion/history"),Entries.Contains(A)||History.Contains(A));

    const TArray<FName> Names={TEXT("pelvis"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l")};
    TArray<FTransform> Pose={FTransform(FVector(0,0,90)),FTransform(FVector(0,0,160)),
        FTransform(FVector(0,-10,85)),FTransform(FVector(20,-10,45)),
        FTransform(FVector(0,-10,5)),FTransform(FVector(15,-10,5))};
    const auto Source=Pose;
    const double Upper=(Pose[3].GetLocation()-Pose[2].GetLocation()).Length();
    const double Lower=(Pose[4].GetLocation()-Pose[3].GetLocation()).Length();
    const FTransform Corrected(FRotator(0,8,0),FVector(3,2,88));
    {FWriteScopeLock Lock(CorrectionLock);Corrections.Add(Id,{Pose[0],Corrected});HasCorrections.Store(true);}
    Apply(Id,Names,Pose);
    Test.TestTrue(TEXT("Pelvis receives exact requested world pose"),Pose[0].Equals(Corrected,1.e-9));
    Test.TestTrue(TEXT("Core stays connected to pelvis"),Pose[1].GetRelativeTransform(Pose[0]).Equals(Source[1].GetRelativeTransform(Source[0]),1.e-8));
    Test.TestTrue(TEXT("Reachable attack ankle stays put including rotation"),Pose[4].Equals(Source[4],1.e-8));
    Test.TestTrue(TEXT("Both leg segment lengths retained"),FMath::IsNearlyEqual((Pose[3].GetLocation()-Pose[2].GetLocation()).Length(),Upper,1.e-8)
        && FMath::IsNearlyEqual((Pose[4].GetLocation()-Pose[3].GetLocation()).Length(),Lower,1.e-8));
    const FTransform Space(FRotator(5,80,12),FVector(200,50,30));
    auto Local=Source;for(auto& B:Local)B=B.GetRelativeTransform(Space);
    Apply(Id,Names,Local,Space);
    for(int32 I=0;I<Pose.Num();++I)Test.TestTrue(TEXT("World physical targets and component-space rendering agree"),(Local[I]*Space).Equals(Pose[I],1.e-7));
    auto Repeated=Source;Apply(Id,Names,Repeated);
    for(int32 I=0;I<Pose.Num();++I)Test.TestTrue(TEXT("Readers share one correction without advancing it"),Repeated[I].Equals(Pose[I],0));
    EraseCorrection(Id);Repeated=Source;Apply(Id,Names,Repeated);
    for(int32 I=0;I<Pose.Num();++I)Test.TestTrue(TEXT("Disabled pose path exactly unchanged"),Repeated[I].Equals(Source[I],0));
    double WorstLength=0;
    for(int32 I=0;I<=1000;++I)
    {
        auto P=Source;
        MoveHip(P[2],P[3],P[4],&P[5],Source[2].GetLocation()+FVector(5*FMath::Sin(I*.01),4*FMath::Cos(I*.01),I*.03));
        WorstLength=FMath::Max(WorstLength,FMath::Abs((P[3].GetLocation()-P[2].GetLocation()).Length()-Upper));
        WorstLength=FMath::Max(WorstLength,FMath::Abs((P[4].GetLocation()-P[3].GetLocation()).Length()-Lower));
        Test.TestFalse(TEXT("Reach shell remains finite"),P[3].ContainsNaN()||P[4].ContainsNaN());
    }
    Test.TestTrue(TEXT("1001 translated hips preserve connected lengths"),WorstLength<1.e-7);
    Remove(A);World->DestroyWorld(false);
    Test.AddInfo(FString::Printf(TEXT("AttackStartPelvisInertia: world deltas, independent 5/7 ticks, reset/disable, dual-space parity and 1001 connected hips passed; max length error %.12g"),WorstLength));
    return !Test.HasAnyErrors();
}
#endif
''';p.write_text(s,encoding='utf-8')
p=Path('Source/GameAnimationSample3/Private/ProphecyNNPresentationTests.cpp');s=p.read_text(encoding='utf-8');s=s.replace('bool RunKneePopSmoothingChecks','bool RunAttackStartInertiaChecks(FAutomationTestBase& Test);\nbool RunKneePopSmoothingChecks',1);s=s.replace('    TestTrue(TEXT("Optional knee smoothing regression")','    TestTrue(TEXT("Attack start pelvis inertia regression"),RunAttackStartInertiaChecks(*this));\n    TestTrue(TEXT("Optional knee smoothing regression")',1);p.write_text(s,encoding='utf-8')
