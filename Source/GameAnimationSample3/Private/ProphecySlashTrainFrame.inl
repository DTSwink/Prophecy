// Included in the manager's math namespace. Explicit seeded comparison only.
#if !UE_BUILD_SHIPPING
namespace SlashTrainFrame
{
struct FFrame { FTransform Anchor;FVector3f Position;FMat3f Rotation;int32 RemainingAttacks=30; };
TMap<TWeakObjectPtr<AProphecyAgent>,FFrame> Frames;
const FFrame* Find(AProphecyAgent* Agent)
{ return Frames.IsEmpty()?nullptr:Frames.Find(Agent); }
void Set(AProphecyAgent* Agent,const FFrame& Frame)
{
    static FDelegateHandle Cleanup;
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Frames.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
    Frames.Add(Agent,Frame);
}
void Started(AProphecyAgent* Agent)
{ if (auto* Frame=Frames.Find(Agent)) --Frame->RemainingAttacks; }
void Ended(AProphecyAgent* Agent)
{ if (const auto* Frame=Find(Agent);Frame && Frame->RemainingAttacks<=0) Frames.Remove(Agent); }
}
#endif
