from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaLibrary.cpp');s=p.read_text();a=s.index('struct FChannelConfig');b=s.index('\n#if WITH_DEV_AUTOMATION_TESTS')
original=r'''struct FConfig { int32 LinearFrames=5,AngularFrames=5;float Linear=1,Angular=1; };
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
'''
s=s[:a]+original+s[b:]
a=s.index('    // Both feet share timing/strength');b=s.index('    CaptureReset(A);',a);s=s[:a]+s[b:]
a=s.index('    // Combined hip/ankle solve');b=s.index('    EraseCorrection(Id);Repeated=Source;',a);s=s[:a]+s[b:]
s=s.replace('FHistories Hist;Hist.Body[0]=H;History.Add(A,Hist);','History.Add(A,H);')
s=s.replace('            const FTransform Goals[]={Goal,Goal,Goal};const bool Valid[]={true,false,false};\n            AdvanceAll(A,Id,Goals,Valid,100+Frame);','            Advance(A,Id,Goal,100+Frame);',1)
s=s.replace('AdvanceAll(A,Id,Goals,Valid,100+Frame);','Advance(A,Id,FTransform::Identity,100+Frame);')
s=s.replace('History.FindChecked(A).Body[0].Current','History.FindChecked(A).Current')
s=s.replace('FCorrections C;C.Body[0]={Pose[0],Corrected,true};Corrections.Add(Id,C);','Corrections.Add(Id,{Pose[0],Corrected});')
p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyAttackStartInertiaMath.h');s=p.read_text();s=s.replace('inline void MoveLeg(FTransform& Thigh,FTransform& Calf,FTransform& Foot,FTransform* Toe,const FVector& Hip,const FTransform* FootTarget=nullptr)','inline void MoveHip(FTransform& Thigh,FTransform& Calf,FTransform& Foot,FTransform* Toe,const FVector& Hip)')
a=s.index('    const FTransform ToeLocal=');b=s.index('    const FVector Upper=',a);s=s[:a]+'    if(Hip.Equals(OldHip,1.e-10))return;\n'+s[b:]
s=s.replace('const FVector Delta=Target-Hip;','const FVector Delta=OldFoot-Hip;')
a=s.index('    Foot.SetLocation(End);');s=s[:a]+'    Foot.SetLocation(End);if (Toe) Toe->AddToTranslation(End-OldFoot);\n}\n}\n';p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNPoseTypes.cpp');s=p.read_text();a=s.index('bool ProphecyNNPresentation::ReadPelvisWorld(');s=s[:a]+r'''bool ProphecyNNPresentation::ReadPelvisWorld(int32 Id,FTransform& Out)
{
    FReadScopeLock Lock(GProphecyNNPoseLock);
    const auto* Found=GProphecyNNPoses.Find(Id);if(!Found)return false;
    const auto& P=*Found;
    const int32 I=P.BoneNames.IndexOfByKey(FName(TEXT("pelvis")));
    if(!P.ComponentTransforms.IsValidIndex(I)||!P.PreviousComponentTransforms.IsValidIndex(I))return false;
    const auto* Presentation=GProphecyNNPresentation.Find(Id);
    const float Alpha=Presentation && Presentation->SourceTimeSeconds==P.SourceTimeSeconds?Presentation->Alpha:1.f;
    const FTransform A=P.PreviousComponentTransforms[I]*P.PreviousComponentWorldTransform;
    const FTransform B=P.ComponentTransforms[I]*P.ComponentWorldTransform;
    if(P.InterpolationMode==EProphecyNNInterpolationMode::HermiteSlerp) Out=ProphecyNNInterpolation::Sample(P,I,A,B,Alpha);
    else
    {
        // Same matrix-lerp polar rotation as the physical and animation readers.
        FQuat Start=A.GetRotation().GetNormalized(),End=B.GetRotation().GetNormalized();
        float Cos=Start|End;if(Cos<0){End=End*-1.;Cos=-Cos;}
        const float Angle=2.f*FMath::Acos(FMath::Clamp(Cos,0.f,1.f));
        const FQuat Q=Angle<=1.e-6f?Start:FQuat::Slerp(Start,End,
            FMath::Atan2(Alpha*FMath::Sin(Angle),(1.f-Alpha)+Alpha*FMath::Cos(Angle))/Angle).GetNormalized();
        Out=FTransform(Q,FMath::Lerp(A.GetLocation(),B.GetLocation(),Alpha));
    }
    return true;
}
''';p.write_text(s)
p=Path('Source/GameAnimationSample3/Private/ProphecyNNPresentation.h');s=p.read_text();s=s.replace('bool ReadBoneWorld(int32 AgentId,FName Bone,FTransform& OutWorld,\n    FTransform* PreviousEndpoint=nullptr,FTransform* CurrentEndpoint=nullptr);\n','');p.write_text(s)
