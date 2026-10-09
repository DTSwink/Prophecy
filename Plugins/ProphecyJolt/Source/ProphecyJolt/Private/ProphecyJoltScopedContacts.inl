// Event-owned sidecar: no retained world layout change, and the ordinary listener
// remains installed without an additional contact lookup when no protection exists.
namespace ProphecyJolt::ScopedContacts
{
using namespace WorldPrivate;
struct FOwner
{
    TArray<FSuppressionKey> Suppressed;
    TArray<FProphecyJoltBodyPair> Protected;
};
struct FListener final : JPH::ContactListener
{
    FProphecyJoltWorldState& State;
    TMap<const void*,FOwner> Owners;
    TMap<FSuppressionKey,uint8> Protection;
    TMap<FBodyIdentity,float> NoReaction;
    explicit FListener(FProphecyJoltWorldState& In):State(In){}
    void Apply(const JPH::Body& A,const JPH::Body& B,const JPH::ContactManifold& M,JPH::ContactSettings& S)
    {
        // Resolve subshapes: a welded sword keeps its logical identity, distinct
        // from the hand carrying it. Workers access native immutable records only.
        const auto HA=State.HitHandle(A,M.mSubShapeID1),HB=State.HitHandle(B,M.mSubShapeID2);
        FSuppressionKey Key{{HA.Slot,HA.Generation},{HB.Slot,HB.Generation}};
        const bool SwapSides=Key.A.Slot>Key.B.Slot;
        if(SwapSides)Swap(Key.A,Key.B);
        if(const uint8* Mask=Protection.Find(Key))
        {
            if(*Mask & (SwapSides?2:1)){S.mInvMassScale1=0;S.mInvInertiaScale1=0;}
            if(*Mask & (SwapSides?1:2)){S.mInvMassScale2=0;S.mInvInertiaScale2=0;}
        }
        if(!NoReaction.IsEmpty())
        {
            if(const float* Scale=NoReaction.Find({HA.Slot,HA.Generation})){S.mInvMassScale1*=*Scale;S.mInvInertiaScale1*=*Scale;}
            if(const float* Scale=NoReaction.Find({HB.Slot,HB.Generation})){S.mInvMassScale2*=*Scale;S.mInvInertiaScale2*=*Scale;}
        }
        State.CaptureIncoming(A,B,M);
    }
    void OnContactAdded(const JPH::Body& A,const JPH::Body& B,const JPH::ContactManifold& M,JPH::ContactSettings& S) override {Apply(A,B,M,S);}
    void OnContactPersisted(const JPH::Body& A,const JPH::Body& B,const JPH::ContactManifold& M,JPH::ContactSettings& S) override {Apply(A,B,M,S);}
    void OnContactRemoved(const JPH::SubShapeIDPair& P) override {State.OnContactRemoved(P);}
};
static TMap<FProphecyJoltWorldState*,TUniquePtr<FListener>> Worlds;
void Refresh(FProphecyJoltWorldState& S)
{
    const auto* L=Worlds.Find(&S);
    JPH::ContactListener* Listener=S.HitEnabledBodies?&S:nullptr;
    if(L && (!(*L)->Protection.IsEmpty() || !(*L)->NoReaction.IsEmpty()))Listener=L->Get();
    S.Physics.SetContactListener(Listener);
}
void Forget(FProphecyJoltWorldState& S)
{
    S.Physics.SetContactListener(nullptr);
    Worlds.Remove(&S); // Bodies and their suppression records are being destroyed.
}
void ForgetBody(FProphecyJoltWorldState& S,int32 Slot,uint64 Generation)
{
    auto* L=Worlds.Find(&S);
    if(!L || !(*L)->NoReaction.Remove({Slot,Generation}))return;
    if((*L)->Owners.IsEmpty() && (*L)->NoReaction.IsEmpty())Worlds.Remove(&S);
    Refresh(S);
}
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyContactReactionEnabled(const FProphecyJoltBodyHandle& Body,bool bEnabled)
{
    return SetBodyContactReactionScale(Body,bEnabled?1.f:0.f);
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyContactReactionScale(const FProphecyJoltBodyHandle& Body,float Scale)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::ScopedContacts;
    const auto Ready=ValidateReady();if(!Ready.IsSuccess())return Ready;
    if(!FMath::IsFinite(Scale) || Scale<0.f || Scale>1.f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Contact response scale must be finite and within [0,1]."));
    if(!Native->Find(Body))return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Contact response requires a live body."));
    auto* Existing=Worlds.Find(Native.Get());
    const FBodyIdentity Key{Body.Slot,Body.Generation};
    if(Scale==1.f && (!Existing || !(*Existing)->NoReaction.Contains(Key)))return {};
    if(!Existing)Existing=&Worlds.Add(Native.Get(),MakeUnique<FListener>(*Native));
    auto& L=**Existing;
    if(const float* Previous=L.NoReaction.Find(Key);Previous && *Previous==Scale)return {};
    if(Scale==1.f)L.NoReaction.Remove(Key);else L.NoReaction.Add(Key,Scale);
    TSet<FBodyIdentity> Changed;Changed.Add(Key);
    Native->PublishSuppression(Changed); // Wake the carrier and invalidate persistent contacts.
    if(L.Owners.IsEmpty() && L.NoReaction.IsEmpty())Worlds.Remove(Native.Get());
    Refresh(*Native);return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateScopedContactRules(const void* Owner,
    TConstArrayView<FProphecyJoltBodyPair> Suppressed,TConstArrayView<FProphecyJoltBodyPair> Protected)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::ScopedContacts;
    const auto Ready=ValidateReady();if(!Ready.IsSuccess())return Ready;
    if(!Owner)return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Contact rule owner is required."));
    FOwner Next;
    auto Prepared=Native->PrepareSuppression(Suppressed,Next.Suppressed);
    if(!Prepared.IsSuccess())return Prepared;
    for(const auto& P:Protected)
        if(!Native->Find(P.A) || !Native->Find(P.B) || SameBody(P.A,P.B))
            return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Protection endpoints must be distinct live bodies."));
    Next.Protected.Append(Protected.GetData(),Protected.Num());
    auto* Existing=Worlds.Find(Native.Get());
    if(!Existing && Suppressed.IsEmpty() && Protected.IsEmpty())return {};
    if(!Existing)Existing=&Worlds.Add(Native.Get(),MakeUnique<FListener>(*Native));
    auto& L=**Existing;
    Native->AddSuppression(Next.Suppressed);
    TSet<FBodyIdentity> Changed;
    auto Touch=[&](const FOwner& O){for(const auto& P:O.Protected){Changed.Add({P.A.Slot,P.A.Generation});Changed.Add({P.B.Slot,P.B.Generation});}};
    Touch(Next);
    if(auto* Old=L.Owners.Find(Owner)){Touch(*Old);Native->ReleaseSuppression(Old->Suppressed);}
    if(Next.Suppressed.IsEmpty() && Next.Protected.IsEmpty())L.Owners.Remove(Owner);
    else L.Owners.Add(Owner,MoveTemp(Next));
    L.Protection.Reset();
    for(const auto& Entry:L.Owners)for(const auto& P:Entry.Value.Protected)
    {
        // Full adapter generations prevent a destroyed/recycled body inheriting rules.
        if(!Native->Find(P.A) || !Native->Find(P.B))continue;
        FSuppressionKey Key{{P.A.Slot,P.A.Generation},{P.B.Slot,P.B.Generation}};
        const bool Reverse=Key.A.Slot>Key.B.Slot;if(Reverse)Swap(Key.A,Key.B);
        L.Protection.FindOrAdd(Key)|=Reverse?2:1;
    }
    Native->PublishSuppression(Changed); // Invalidate cached contacts on both entry and exit.
    if(L.Owners.IsEmpty() && L.NoReaction.IsEmpty())Worlds.Remove(Native.Get());
    Refresh(*Native);
    RefreshDiagnostics();return {};
}
