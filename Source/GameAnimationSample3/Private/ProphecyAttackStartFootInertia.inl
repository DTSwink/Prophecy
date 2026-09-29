// Included in ProphecyAttackStartInertia. Shares the existing entry lifecycle;
// there is no foot timer, idle history, inference, or disabled pose sampling.
namespace Feet
{
struct FPair { FEntry Leg[2];uint8 Active=3; };
struct FTargets { FTransform World[2];uint8 Active=3,Linear=3,Angular=3; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FPair> Entries;
static TMap<int32,FTargets> Targets;
static FRWLock Lock;
static TAtomic<bool> HasTargets(false);
static void Erase(int32 Id)
{ FWriteScopeLock Guard(Lock);Targets.Remove(Id);HasTargets.Store(!Targets.IsEmpty()); }
static void Cancel(const AProphecyAgent* A)
{ if(const auto* E=Entries.Find(A))Erase(E->Leg[0].PoseId);Entries.Remove(A); }
static void CancelMask(const AProphecyAgent* A,uint8 Mask)
{
    auto* P=Entries.Find(A);if(!P)return;
    const int32 Id=P->Leg[0].PoseId;P->Active&=~Mask;
    {FWriteScopeLock Guard(Lock);if(auto* T=Targets.Find(Id)){T->Active&=~Mask;if(!T->Active)Targets.Remove(Id);}HasTargets.Store(!Targets.IsEmpty());}
    if(!P->Active)Entries.Remove(A);
}
static bool Active(int32 Id)
{ if(!HasTargets.Load())return false;FReadScopeLock Guard(Lock);return Targets.Contains(Id); }
static void CleanupWorld(UWorld* W)
{
    for(auto It=Entries.CreateIterator();It;++It)
        if(!It.Key().IsValid() || It.Key()->GetWorld()==W){Erase(It.Value().Leg[0].PoseId);It.RemoveCurrent();}
    for(auto* M:{&Configs,&Baselines})for(auto It=M->CreateIterator();It;++It)
        if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();
}
static void Begin(const AProphecyAgent* A,int32 Id,uint8 Mask=3)
{
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C || !Mask)return;
    FPair Pair;Pair.Active=0;
    if(const auto* Old=Entries.Find(A))Pair=*Old;
    // Both slots carry the owner id even when only the right foot is active.
    for(auto& E:Pair.Leg)E.PoseId=Id;
    for(int32 Side=0;Side<2;++Side)
    {
        if(!(Mask&(1<<Side)))continue;
        const bool WasActive=(Pair.Active&(1<<Side))!=0;
        const FTransform OldOutput=Pair.Leg[Side].Output;
        auto& E=Pair.Leg[Side];FTransform Prev,Cur;
        if(!ProphecyNNPresentation::ReadBoneWorld(Id,Side?TEXT("foot_r"):TEXT("foot_l"),E.Output,&Prev,&Cur))return;
        E.Config=*C;E.PoseId=Id;E.Tick=GFrameCounter;E.Frame=0;
        // Existing adjacent 30Hz world poses supply one 60Hz entry increment.
        E.Delta=(Cur.GetLocation()-Prev.GetLocation())*.5;
        E.AngularDelta=ProphecyPelvisInertia::RotationVector(Cur.GetRotation()*Prev.GetRotation().Inverse())*.5;
        if(WasActive)E.Output=OldOutput;
        Pair.Active|=1<<Side;
    }
    Entries.Add(A,Pair);
    // Handoffs may occur during publication: expose the latched foot immediately,
    // without spending a tick or letting the new attack endpoint flash through.
    FWriteScopeLock Guard(Lock);auto& T=Targets.FindOrAdd(Id);T.Active=Pair.Active;
    for(int32 Side=0;Side<2;++Side)if(Mask&(1<<Side))
    {
        const auto& E=Pair.Leg[Side];T.World[Side]=E.Output;
        if(Weight(0,E.Config.LinearFrames,E.Config.Linear)!=0)T.Linear|=1<<Side;else T.Linear&=~(1<<Side);
        if(Weight(0,E.Config.AngularFrames,E.Config.Angular)!=0)T.Angular|=1<<Side;else T.Angular&=~(1<<Side);
    }
    HasTargets.Store(true);
}
static void Advance(const AProphecyAgent* A,int32 Id,const FTransform (&Authored)[2],uint64 Tick)
{
    auto* Pair=Entries.Find(A);if(!Pair)return;
    FTargets Result;Result.Active=Result.Linear=Result.Angular=0;
    for(int32 Side=0;Side<2;++Side)
    {
        const uint8 Bit=1<<Side;if(!(Pair->Active&Bit))continue;
        auto& E=Pair->Leg[Side];const bool NewTick=E.Tick!=Tick;
        if(NewTick){++E.Frame;E.Tick=Tick;}
        const double L=Weight(E.Frame,E.Config.LinearFrames,E.Config.Linear);
        const double R=Weight(E.Frame,E.Config.AngularFrames,E.Config.Angular);
        if(L==0 && R==0){Pair->Active&=~Bit;continue;}
        if(NewTick)E.Output=Step(E.Output,Authored[Side],E.Delta,E.AngularDelta,L,R);
        Result.World[Side]=E.Output;Result.Active|=Bit;
        if(L!=0)Result.Linear|=Bit;if(R!=0)Result.Angular|=Bit;
    }
    if(!Pair->Active){Erase(Id);Entries.Remove(A);return;}
    FWriteScopeLock Guard(Lock);Targets.Add(Id,Result);HasTargets.Store(true);
}
static void Update(const AProphecyAgent* A,int32 Id)
{
    if(Entries.IsEmpty())return;
    const auto* Pair=Entries.Find(A);
    if(!Pair || !A->GetWorld() || A->GetWorld()->IsPaused())return;
    bool Due=false;
    for(int32 Side=0;Side<2;++Side)Due|=(Pair->Active&(1<<Side)) && Pair->Leg[Side].Tick!=GFrameCounter;
    if(!Due)return;
    FTransform Authored[2];
    for(int32 Side=0;Side<2;++Side)
        if((Pair->Active&(1<<Side)) && Pair->Leg[Side].Tick!=GFrameCounter
            && !ProphecyNNPresentation::ReadBoneWorld(Id,Side?TEXT("foot_r"):TEXT("foot_l"),Authored[Side]))return;
    Advance(A,Id,Authored,GFrameCounter);
}
static bool Apply(int32 Id,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space)
{
    if(!HasTargets.Load())return false;
    FTargets Target;
    {FReadScopeLock Guard(Lock);const auto* P=Targets.Find(Id);if(!P)return false;Target=*P;}
    for(int32 Side=0;Side<2;++Side)
    {
        const uint8 Bit=1<<Side;if(!(Target.Active&Bit))continue;
        const int32 H=Names.IndexOfByKey(Side?FName(TEXT("thigh_r")):FName(TEXT("thigh_l")));
        const int32 K=Names.IndexOfByKey(Side?FName(TEXT("calf_r")):FName(TEXT("calf_l")));
        const int32 F=Names.IndexOfByKey(Side?FName(TEXT("foot_r")):FName(TEXT("foot_l")));
        const int32 T=Names.IndexOfByKey(Side?FName(TEXT("ball_r")):FName(TEXT("ball_l")));
        if(!Pose.IsValidIndex(H)||!Pose.IsValidIndex(K)||!Pose.IsValidIndex(F))continue;
        const FTransform Desired=Target.World[Side].GetRelativeTransform(Space);
        const FTransform ToeLocal=Pose.IsValidIndex(T)?Pose[T].GetRelativeTransform(Pose[F]):FTransform::Identity;
        const FVector Hip=Pose[H].GetLocation(),Shift=Desired.GetLocation()-Pose[F].GetLocation();
        // Reuse the accepted bend-frame solve with the desired ankle, keeping
        // the original hip and segment lengths. Unreachable targets clamp to reach.
        if(Target.Linear&Bit)
        {
            Pose[H].AddToTranslation(Shift);Pose[K].AddToTranslation(Shift);Pose[F].AddToTranslation(Shift);
            MoveHip(Pose[H],Pose[K],Pose[F],nullptr,Hip);
        }
        if(Target.Angular&Bit)Pose[F].SetRotation(Desired.GetRotation());
        if(Pose.IsValidIndex(T))Pose[T]=ToeLocal*Pose[F];
    }
    return true;
}
}
