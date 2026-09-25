// Optional comparison model; no manager/agent object layout or default-path model load.
namespace ProphecyAttackCheckpoint
{
static constexpr const TCHAR* AlternativeSHA=TEXT("73a549008e883e3b945ce5ebdc1597c75a1a79a816e59c67e131a7af8a04a143");
static constexpr const TCHAR* Refresh2SHA=TEXT("e0759ba5039db0db26f5dd17d58e74b72f1dc092f9f7bf6f54e4a622677f7d7b");
static constexpr const TCHAR* September20SHA=TEXT("6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072");
struct FComparison
{
    TUniquePtr<FSlashNative> Model;
    TSet<TWeakObjectPtr<const AProphecyAgent>> Selected,Active;
};
static TMap<TWeakObjectPtr<const AProphecyNNLocomotionManager>,TUniquePtr<FComparison>> Comparisons;
// Separate storage preserves the loaded first-comparison allocation during Live Coding.
static TMap<TWeakObjectPtr<const AProphecyNNLocomotionManager>,TUniquePtr<FComparison>> Refresh2Comparisons;
static TMap<TWeakObjectPtr<const AProphecyNNLocomotionManager>,TUniquePtr<FComparison>> September20Comparisons;
static auto& Storage(int32 Checkpoint) { return Checkpoint==3?September20Comparisons:Checkpoint==2?Refresh2Comparisons:Comparisons; }
static FComparison* Find(const AProphecyNNLocomotionManager* Owner,int32 Checkpoint=1)
{
    const auto& Map=Storage(Checkpoint);
    const auto* Value=Map.IsEmpty()?nullptr:Map.Find(Owner);
    return Value?Value->Get():nullptr;
}
static int32 Choice(const AProphecyNNLocomotionManager* Owner,const AProphecyAgent* Actor,bool Active)
{
    for(int32 I=1;I<=3;++I) if(const auto* C=Find(Owner,I))
        if((Active?C->Active:C->Selected).Contains(Actor)) return I;
    return 0;
}
static void Select(const AProphecyNNLocomotionManager* Owner,const AProphecyAgent* Actor,int32 Choice,bool Active)
{
    for(int32 I=1;I<=3;++I) if(auto* C=Find(Owner,I))
    { auto& Set=Active?C->Active:C->Selected;if(I==Choice)Set.Add(Actor);else Set.Remove(Actor); }
}
static void Clear(const AProphecyNNLocomotionManager* Owner) { Comparisons.Remove(Owner);Refresh2Comparisons.Remove(Owner);September20Comparisons.Remove(Owner); }
}
