#include "ProphecyAttackStartInertiaLibrary.h"
#include "ProphecyAttackStartInertia.h"
#include "ProphecyAttackStartInertiaMath.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyNNInterpolation.h"
#include "Engine/World.h"
#include "Misc/ScopeRWLock.h"

namespace ProphecyAttackStartInertia
{
struct FConfig { int32 LinearFrames=5,AngularFrames=5;float Linear=1,Angular=1; };
struct FHistory { FTransform Previous,Current;uint64 Tick=MAX_uint64;int32 Samples=0; };
struct FEntry
{
    FConfig Config;FTransform Output;
    FVector Delta,AngularDelta;
    uint64 Tick=0;int32 Frame=0,PoseId=INDEX_NONE;
};
struct FCorrection { FTransform Authored,Corrected; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FHistory> History;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FEntry> Entries;
static TMap<int32,FCorrection> Corrections;
static FRWLock CorrectionLock;
static TAtomic<bool> HasCorrections(false);
static FDelegateHandle Cleanup;
static void EraseCorrection(int32 Id)
{
    FWriteScopeLock Lock(CorrectionLock);Corrections.Remove(Id);HasCorrections.Store(!Corrections.IsEmpty());
}
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for (auto It=Entries.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==W) {EraseCorrection(It.Value().PoseId);It.RemoveCurrent();}
        auto Clean=[W](auto& Map) {for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent();};
        Clean(Configs);Clean(Baselines);Clean(History);
    });
}
void Cancel(const AProphecyAgent* A)
{
    if (const auto* E=Entries.Find(A)) EraseCorrection(E->PoseId);
    Entries.Remove(A);
}
void Remove(const AProphecyAgent* A) {Cancel(A);History.Remove(A);Configs.Remove(A);Baselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A)
{EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A)
{Cancel(A);History.Remove(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C);}
void ForgetReset(const AProphecyAgent* A) {Baselines.Remove(A);}
bool Active(int32 Id)
{
    if (!HasCorrections.Load()) return false;
    FReadScopeLock Lock(CorrectionLock);return Corrections.Contains(Id);
}
void Begin(const AProphecyAgent* A,int32 Id,const FTransform& Previous,const FTransform& Current)
{
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C)return;
    FEntry E;E.Config=*C;E.PoseId=Id;E.Tick=GFrameCounter;
    const auto* H=History.Find(A);
    if (H && H->Samples>=2)
    {
        E.Output=H->Current;E.Delta=H->Current.GetLocation()-H->Previous.GetLocation();
        E.AngularDelta=ProphecyPelvisInertia::RotationVector(H->Current.GetRotation()*H->Previous.GetRotation().Inverse());
    }
    else
    {
        // A setter immediately followed by Trigger has no displayed history yet.
        // Seed from the existing two 30 Hz policy poses; no permanent extra history.
        E.Output=Current;E.Delta=(Current.GetLocation()-Previous.GetLocation())*.5;
        E.AngularDelta=ProphecyPelvisInertia::RotationVector(Current.GetRotation()*Previous.GetRotation().Inverse())*.5;
    }
    Entries.Add(A,E);
}
static void Advance(const AProphecyAgent* A,int32 Id,const FTransform& Authored,uint64 Tick)
{
    if(Configs.IsEmpty() || !Configs.Contains(A))return;
    auto& H=History.FindOrAdd(A);
    if(H.Tick==Tick)return; // collision rebases/readers never spend a second frame
    FTransform Output=Authored;
    if(auto* E=Entries.Find(A))
    {
        if(Tick!=E->Tick) {++E->Frame;E->Tick=Tick;}
        const double L=Weight(E->Frame,E->Config.LinearFrames,E->Config.Linear);
        const double R=Weight(E->Frame,E->Config.AngularFrames,E->Config.Angular);
        if(L==0 && R==0) {EraseCorrection(Id);Entries.Remove(A);}
        else
        {
            if(E->Frame==0)
            {
                if(L!=0)Output.SetLocation(E->Output.GetLocation());
                if(R!=0)Output.SetRotation(E->Output.GetRotation());
            }
            else Output=Step(E->Output,Authored,E->Delta,E->AngularDelta,L,R);
            E->Output=Output;
            FWriteScopeLock Lock(CorrectionLock);Corrections.Add(Id,{Authored,Output});HasCorrections.Store(true);
        }
    }
    H.Previous=H.Current;H.Current=Output;H.Samples=FMath::Min(2,H.Samples+1);H.Tick=Tick;
}
void Update(const AProphecyAgent* A,int32 Id)
{
    if(Configs.IsEmpty() || !Configs.Contains(A) || !A->GetWorld() || A->GetWorld()->IsPaused())return;
    if(const auto* H=History.Find(A))if(H->Tick==GFrameCounter)return;
    FTransform Authored;if(ProphecyNNPresentation::ReadPelvisWorld(Id,Authored))Advance(A,Id,Authored,GFrameCounter);
}
void Apply(int32 Id,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space)
{
    if(!HasCorrections.Load())return;
    FCorrection C;
    {FReadScopeLock Lock(CorrectionLock);const auto* Found=Corrections.Find(Id);if(!Found)return;C=*Found;}
    const FTransform Before=C.Authored.GetRelativeTransform(Space),After=C.Corrected.GetRelativeTransform(Space);
    if(Before.Equals(After,1.e-10))return;
    const FQuat Rotation=(After.GetRotation()*Before.GetRotation().Inverse()).GetNormalized();
    auto Move=[&](const FVector& P){return After.GetLocation()+Rotation.RotateVector(P-Before.GetLocation());};
    int32 LegIndices[2][4];
    for(int32 Side=0;Side<2;++Side)
    {
        const FName LimbNames[]={Side?TEXT("thigh_r"):TEXT("thigh_l"),Side?TEXT("calf_r"):TEXT("calf_l"),
            Side?TEXT("foot_r"):TEXT("foot_l"),Side?TEXT("ball_r"):TEXT("ball_l")};
        for(int32 Part=0;Part<4;++Part) LegIndices[Side][Part]=Names.IndexOfByKey(LimbNames[Part]);
        const auto* I=LegIndices[Side];
        if(Pose.IsValidIndex(I[0]) && Pose.IsValidIndex(I[1]) && Pose.IsValidIndex(I[2]))
            MoveHip(Pose[I[0]],Pose[I[1]],Pose[I[2]],Pose.IsValidIndex(I[3])?&Pose[I[3]]:nullptr,Move(Pose[I[0]].GetLocation()));
    }
    for(int32 B=0;B<Pose.Num();++B)
    {
        bool Leg=false;for(const auto& Indices:LegIndices)for(int32 I:Indices)Leg|=B==I;
        if(Leg || Names[B]==TEXT("root"))continue;
        Pose[B].SetLocation(Move(Pose[B].GetLocation()));
        Pose[B].SetRotation((Rotation*Pose[B].GetRotation()).GetNormalized());
    }
}
}
bool UProphecyAttackStartInertiaLibrary::SetAttackStartPelvisInertia(AProphecyAgent* A,bool Enabled,
    int32 TranslationWindowFrames,float TranslationInertia,int32 RotationWindowFrames,float RotationInertia)
{
    using namespace ProphecyAttackStartInertia;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed())return false;
    if(TranslationWindowFrames<0 || RotationWindowFrames<0 || !FMath::IsFinite(TranslationInertia)
        || !FMath::IsFinite(RotationInertia) || TranslationInertia<0 || RotationInertia<0)return false;
    if(!Enabled || ((TranslationWindowFrames<=1 || TranslationInertia==0) && (RotationWindowFrames<=1 || RotationInertia==0)))
    {Cancel(A);History.Remove(A);Configs.Remove(A);return true;}
    EnsureCleanup();Configs.Add(A,{TranslationWindowFrames,RotationWindowFrames,TranslationInertia,RotationInertia});
    // Active entry latches its settings. Repeated setter calls do not restart it.
    return true;
}

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
    const TArray<FName> PelvisName={TEXT("pelvis")};
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
