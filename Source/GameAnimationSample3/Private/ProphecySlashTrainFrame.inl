// Included in the manager's math namespace. Explicit seeded comparison only.
#if !UE_BUILD_SHIPPING
namespace SlashTrainFrame
{
// Separate sidecar: do not resize existing Live Coding frame records.
TMap<TWeakObjectPtr<AProphecyAgent>,TArray<float>> CustomSeeds;
bool HasCustomSeed(AProphecyAgent* Agent){return !CustomSeeds.IsEmpty() && CustomSeeds.Contains(Agent);}
struct FFrame { FTransform Anchor;FVector3f Position;FMat3f Rotation;int32 RemainingAttacks=30; };
TMap<TWeakObjectPtr<AProphecyAgent>,FFrame> Frames;
const FFrame* Find(AProphecyAgent* Agent)
{ return Frames.IsEmpty()?nullptr:Frames.Find(Agent); }
void Set(AProphecyAgent* Agent,const FFrame& Frame)
{
    static FDelegateHandle Cleanup;
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=CustomSeeds.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
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
