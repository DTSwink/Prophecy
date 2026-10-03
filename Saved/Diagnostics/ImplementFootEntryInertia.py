from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp')
s=p.read_text(); start=s.index('struct FConfig'); end=s.index('\n#if WITH_DEV_AUTOMATION_TESTS')
new=r'''struct FChannelConfig
{
    int32 LinearFrames=5,AngularFrames=5;float Linear=0,Angular=0;
    bool Enabled() const { return (LinearFrames>1 && Linear!=0) || (AngularFrames>1 && Angular!=0); }
};
struct FConfig { FChannelConfig Body[3];bool Enabled() const {return Body[0].Enabled()||Body[1].Enabled()||Body[2].Enabled();} };
struct FHistory { FTransform Previous,Current;uint64 Tick=MAX_uint64;int32 Samples=0; };
struct FChannelEntry { FTransform Output;FVector Delta,AngularDelta;bool Valid=false; };
struct FEntry
{
    FConfig Config;FChannelEntry Body[3];
    uint64 Tick=0;int32 Frame=0,PoseId=INDEX_NONE;
};
struct FCorrection { FTransform Authored,Corrected;bool Enabled=false; };
struct FCorrections { FCorrection Body[3]; };
struct FHistories { FHistory Body[3]; };
static const FName BodyNames[]={TEXT("pelvis"),TEXT("foot_l"),TEXT("foot_r")};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FHistories> History;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FEntry> Entries;
static TMap<int32,FCorrections> Corrections;
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
    const auto* Histories=History.Find(A);
    for(int32 B=0;B<3;++B)
    {
        if(!C->Body[B].Enabled())continue;
        auto& Channel=E.Body[B];
        const auto* H=Histories?&Histories->Body[B]:nullptr;
        if(H && H->Samples>=2)
        {
            Channel.Output=H->Current;Channel.Delta=H->Current.GetLocation()-H->Previous.GetLocation();
            Channel.AngularDelta=ProphecyPelvisInertia::RotationVector(H->Current.GetRotation()*H->Previous.GetRotation().Inverse());
        }
        else
        {
            FTransform P=Previous,N=Current,Sample;
            if(B && !ProphecyNNPresentation::ReadBoneWorld(Id,BodyNames[B],Sample,&P,&N))continue;
            Channel.Output=N;Channel.Delta=(N.GetLocation()-P.GetLocation())*.5;
            Channel.AngularDelta=ProphecyPelvisInertia::RotationVector(N.GetRotation()*P.GetRotation().Inverse())*.5;
        }
        Channel.Valid=true;
    }
    Entries.Add(A,E);
}
static void AdvanceAll(const AProphecyAgent* A,int32 Id,const FTransform* Authored,const bool* Valid,uint64 Tick)
{
    const auto* Config=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!Config)return;
    auto& Histories=History.FindOrAdd(A);
    auto* E=Entries.Find(A);
    if(E && Tick!=E->Tick) {++E->Frame;E->Tick=Tick;}
    FCorrections Published;bool Any=false;
    for(int32 B=0;B<3;++B)
    {
        // A live setter changes the next attack, not an already latched entry.
        if(!(E?E->Config.Body[B]:Config->Body[B]).Enabled() || !Valid[B])continue;
        auto& H=Histories.Body[B];
        if(H.Tick==Tick)continue;
        FTransform Output=Authored[B];
        if(E && E->Body[B].Valid)
        {
            auto& Channel=E->Body[B];const auto& C=E->Config.Body[B];
            const double L=Weight(E->Frame,C.LinearFrames,C.Linear),R=Weight(E->Frame,C.AngularFrames,C.Angular);
            if(L!=0 || R!=0)
            {
                if(E->Frame==0)
                {
                    if(L!=0)Output.SetLocation(Channel.Output.GetLocation());
                    if(R!=0)Output.SetRotation(Channel.Output.GetRotation());
                }
                else Output=Step(Channel.Output,Authored[B],Channel.Delta,Channel.AngularDelta,L,R);
                Channel.Output=Output;Published.Body[B]={Authored[B],Output,true};Any=true;
            }
        }
        H.Previous=H.Current;H.Current=Output;H.Samples=FMath::Min(2,H.Samples+1);H.Tick=Tick;
    }
    if(Any) {FWriteScopeLock Lock(CorrectionLock);Corrections.Add(Id,Published);HasCorrections.Store(true);}
    else if(E) {EraseCorrection(Id);Entries.Remove(A);}
}
void Update(const AProphecyAgent* A,int32 Id)
{
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);
    if(!C || !A->GetWorld() || A->GetWorld()->IsPaused())return;
    const auto* E=Entries.Find(A);if(E)C=&E->Config;
    const auto* H=History.Find(A);
    FTransform Authored[3];bool Valid[3]={false,false,false};bool Any=false;
    for(int32 B=0;B<3;++B)if(C->Body[B].Enabled() && (!H || H->Body[B].Tick!=GFrameCounter))
    {Valid[B]=ProphecyNNPresentation::ReadBoneWorld(Id,BodyNames[B],Authored[B]);Any|=Valid[B];}
    if(Any)AdvanceAll(A,Id,Authored,Valid,GFrameCounter);
}
void Apply(int32 Id,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space)
{
    if(!HasCorrections.Load())return;
    FCorrections C;
    {FReadScopeLock Lock(CorrectionLock);const auto* Found=Corrections.Find(Id);if(!Found)return;C=*Found;}
    const auto& Pelvis=C.Body[0];
    const FTransform Before=Pelvis.Authored.GetRelativeTransform(Space),After=Pelvis.Corrected.GetRelativeTransform(Space);
    const bool MovePelvis=Pelvis.Enabled && !Before.Equals(After,1.e-10);
    const FQuat Rotation=MovePelvis?(After.GetRotation()*Before.GetRotation().Inverse()).GetNormalized():FQuat::Identity;
    auto Move=[&](const FVector& P){return MovePelvis?After.GetLocation()+Rotation.RotateVector(P-Before.GetLocation()):P;};
    int32 LegIndices[2][4];
    for(int32 Side=0;Side<2;++Side)
    {
        const FName LimbNames[]={Side?TEXT("thigh_r"):TEXT("thigh_l"),Side?TEXT("calf_r"):TEXT("calf_l"),
            Side?TEXT("foot_r"):TEXT("foot_l"),Side?TEXT("ball_r"):TEXT("ball_l")};
        for(int32 Part=0;Part<4;++Part) LegIndices[Side][Part]=Names.IndexOfByKey(LimbNames[Part]);
        const auto* I=LegIndices[Side];const auto& Foot=C.Body[Side+1];
        if((MovePelvis || Foot.Enabled) && Pose.IsValidIndex(I[0]) && Pose.IsValidIndex(I[1]) && Pose.IsValidIndex(I[2]))
        {
            const FTransform Target=Foot.Corrected.GetRelativeTransform(Space);
            MoveLeg(Pose[I[0]],Pose[I[1]],Pose[I[2]],Pose.IsValidIndex(I[3])?&Pose[I[3]]:nullptr,
                Move(Pose[I[0]].GetLocation()),Foot.Enabled?&Target:nullptr);
        }
    }
    if(!MovePelvis)return;
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
    int32 TranslationWindowFrames,float TranslationInertia,int32 RotationWindowFrames,float RotationInertia,
    int32 LeftFootTranslationWindowFrames,float LeftFootTranslationInertia,int32 LeftFootRotationWindowFrames,float LeftFootRotationInertia,
    int32 RightFootTranslationWindowFrames,float RightFootTranslationInertia,int32 RightFootRotationWindowFrames,float RightFootRotationInertia)
{
    using namespace ProphecyAttackStartInertia;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed())return false;
    const FConfig C{{{TranslationWindowFrames,RotationWindowFrames,TranslationInertia,RotationInertia},
        {LeftFootTranslationWindowFrames,LeftFootRotationWindowFrames,LeftFootTranslationInertia,LeftFootRotationInertia},
        {RightFootTranslationWindowFrames,RightFootRotationWindowFrames,RightFootTranslationInertia,RightFootRotationInertia}}};
    for(const auto& B:C.Body)if(B.LinearFrames<0 || B.AngularFrames<0 || !FMath::IsFinite(B.Linear)
        || !FMath::IsFinite(B.Angular) || B.Linear<0 || B.Angular<0)return false;
    if(!Enabled || !C.Enabled()) {Cancel(A);History.Remove(A);Configs.Remove(A);return true;}
    EnsureCleanup();Configs.Add(A,C);
    // Settings are latched at entry; repeated setter calls do not restart it.
    return true;
}
'''
s=s[:start]+new+s[end:]
# Adapt existing pelvis regression to shared arrays, retaining original expected math.
s=s.replace('History.Add(A,H);','FHistories Hist;Hist.Body[0]=H;History.Add(A,Hist);')
s=s.replace('History.FindChecked(A).Current','History.FindChecked(A).Body[0].Current')
s=s.replace('Advance(A,Id,Goal,100+Frame);','const FTransform Goals[]={Goal,Goal,Goal};const bool Valid[]={true,false,false};\n            AdvanceAll(A,Id,Goals,Valid,100+Frame);')
s=s.replace('Advance(A,Id,FTransform::Identity,100+Frame);','Update(A,Id); // Production tick gate is exercised separately below.')
s=s.replace('Corrections.Add(Id,{Pose[0],Corrected});','FCorrections C;C.Body[0]={Pose[0],Corrected,true};Corrections.Add(Id,C);')
# Remove bad synthetic Update using real GFrameCounter. Validate tick gating at helper level instead in followup.
s=s.replace('Update(A,Id); // Production tick gate is exercised separately below.','AdvanceAll(A,Id,Goals,Valid,100+Frame);')
p.write_text(s)
# Remove entire raw-threshold feature, including two processing points and its obsolete tests.
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinningLibrary.cpp');s=p.read_text()
s=s.replace('// Separate storage preserves the layout of settings retained across Live Coding.\nstatic TMap<TWeakObjectPtr<const AProphecyAgent>,float> Limits;\n','')
s=s.replace(' && Limits.IsEmpty()','')
s=s.replace('            for (auto It=Limits.CreateIterator();It;++It)\n                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();\n','')
a=s.index('void ApplyLimit(');b=s.index('\n}\n}',a);s=s[:a]+s[b+2:]
a=s.index('bool UProphecyWalkPinningLibrary::SetWalkPinningLimit');b=s.index('bool UProphecyWalkPinningLibrary::SetWalkPinningTolerance',a);s=s[:a]+s[b:]
a=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningLimitTest');b=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningToleranceTest',a);s=s[:a]+s[b:];p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyWalkPinning.h');s=p.read_text();a=s.index('inline void LimitRawValues');b=s.index('struct FSettings',a);p.write_text(s[:a]+s[b:])
p=Path('Source/GameAnimationSample3/Public/ProphecyWalkPinningLibrary.h');s=p.read_text();a=s.index('    /** Walk only: clear each');b=s.index('    /** Walk only: if both',a);p.write_text(s[:a]+s[b:])
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp');s=p.read_text();s=s.replace('\t\t\t// Apply after winner/tolerance selection. An ineligible winner leaves\n\t\t\t// both feet unpinned; the losing foot must not inherit its pin.\n','');s='\n'.join(l for l in s.split('\n') if 'ProphecyWalkPinning::ApplyLimit(' not in l);p.write_text(s)
