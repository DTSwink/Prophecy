#include "ProphecyJoltPHATSweepLibrary.h"
#include "ProphecyJoltPHATSweeps.h"
#include "ProphecyJoltMaterial.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/SimShapeFilter.h>
#include <Jolt/Physics/PhysicsSystem.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::PHATSweeps
{
// Sparse ownership, outside retained native layouts. GT writes only outside synchronous Update.
static TMap<TWeakObjectPtr<const AActor>, FSettings> Requests;
struct FConfiguration { FSettings Settings; bool Enabled = true; };
static TMap<TWeakObjectPtr<const AActor>, FConfiguration> Configurations;
static TSet<TWeakObjectPtr<const AActor>> AttackingAgents;
struct FParts { TArray<FName,TInlineAllocator<2>> Bones; TWeakObjectPtr<const UPrimitiveComponent> Sword; };
static TMap<TWeakObjectPtr<const AActor>,FParts> AttackParts;
static TMap<TWeakObjectPtr<const UPrimitiveComponent>,TWeakObjectPtr<const AActor>> SwordOwners;
static bool IsCombatActive(const AActor* Agent)
{ return AttackingAgents.Contains(Agent); }

static void RefreshRequest(AActor* Agent)
{
    const auto* Config = Configurations.Find(Agent);
    const auto* Parts = AttackParts.Find(Agent);
    if (!IsCombatActive(Agent) || !Parts || (Parts->Bones.IsEmpty() && !Parts->Sword.IsValid()) || (Config && !Config->Enabled))
    { Requests.Remove(Agent); return; }
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Agent);
    if (!Meshes.ContainsByPredicate([](const auto* Mesh) { return Mesh->GetFName() == TEXT("PhysicalMesh"); }))
    { Requests.Remove(Agent); return; }
    Requests.Add(Agent, Config ? Config->Settings : FSettings{});
}
struct FPacket
{
    const JPH::ObjectLayerPairFilter* Filter = nullptr;
    TArray<FBody> Selected;
    TArray<uint32> Candidates;
    TMap<uint32, FBody> SelectedByID;
};
static TMap<JPH::PhysicsSystem*, FPacket> Packets;
bool HasRequests(const UWorld* World)
{
    if (Requests.IsEmpty()) return false;
    for (auto It = Requests.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid()) { It.RemoveCurrent(); continue; }
        if (!IsCombatActive(It.Key().Get()))
        {
            if (!Configurations.Contains(It.Key())) Configurations.Add(It.Key(), {It.Value(), true});
            It.RemoveCurrent(); continue;
        }
        if (It.Key()->GetWorld() == World) return true;
    }
    return false;
}
const FSettings* Find(const AActor* Agent) { return Requests.Find(Agent); }
const FSettings* FindBody(const UPrimitiveComponent* Component, FName Bone)
{
    if (Requests.IsEmpty() || !Component) return nullptr;
    if (const auto* Owner=SwordOwners.Find(Component))
    {
        const AActor* Weapon=Component->GetOwner();
        return Weapon && Weapon->GetOwner()==Owner->Get() ? Requests.Find(*Owner) : nullptr;
    }
    if (Component->GetFName()!=TEXT("PhysicalMesh")) return nullptr;
    const auto* Agent=Component->GetOwner();
    const auto* Settings=Requests.Find(Agent);
    const auto* Parts=Settings ? AttackParts.Find(Agent) : nullptr;
    return Parts && Parts->Bones.Contains(Bone) ? Settings : nullptr;
}
void ForgetWorld(const UWorld* World)
{
    for (auto It = Requests.CreateIterator(); It; ++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
    for (auto It = Configurations.CreateIterator(); It; ++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
    for (auto It = AttackingAgents.CreateIterator(); It; ++It)
        if (!It->IsValid() || It->Get()->GetWorld() == World) It.RemoveCurrent();
    for (auto It = AttackParts.CreateIterator(); It; ++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
    for (auto It = SwordOwners.CreateIterator(); It; ++It)
        if (!It.Key().IsValid() || !It.Value().IsValid() || It.Value()->GetWorld() == World) It.RemoveCurrent();
}
void Publish(JPH::PhysicsSystem* Physics, const JPH::ObjectLayerPairFilter* Filter,
    TArray<FBody>&& Selected, TArray<uint32>&& Candidates)
{
    if (Selected.IsEmpty()) { Forget(Physics); return; }
    Selected.Sort([](const FBody& A, const FBody& B) { return A.ID < B.ID; });
    FPacket Packet; Packet.Filter = Filter; Packet.Selected = MoveTemp(Selected); Packet.Candidates = MoveTemp(Candidates);
    for (const auto& Body : Packet.Selected) Packet.SelectedByID.Add(Body.ID, Body);
    Packets.Add(Physics, MoveTemp(Packet));
}
void Forget(JPH::PhysicsSystem* Physics) { if (!Packets.IsEmpty()) Packets.Remove(Physics); }

class FPairShapeFilter final : public JPH::ShapeFilter
{
public:
    FPairShapeFilter(const JPH::PhysicsSystem& P, const JPH::Body& InA, const JPH::Body& InB, uint8 InPartsA, uint8 InPartsB)
        : Filter(P.GetSimShapeFilter()), A(InA), B(InB), PartsA(InPartsA), PartsB(InPartsB) {}
    bool ShouldCollide(const JPH::Shape* SA, const JPH::SubShapeID& IA,
        const JPH::Shape* SB, const JPH::SubShapeID& IB) const override
    {
        const auto* WA=Material::AttachedData(A);const auto* WB=Material::AttachedData(B);
        // Compound roots must remain traversable until the leaf's identity is known.
        if ((WA && (SA==WA->CarrierRoot || SA==WA->Compound)) ||
            (WB && (SB==WB->CarrierRoot || SB==WB->Compound))) return true;
        const bool SelectedA=WA ? (PartsA & (WA->IsSource(IA)?2:1))!=0 : PartsA!=0;
        const bool SelectedB=WB ? (PartsB & (WB->IsSource(IB)?2:1))!=0 : PartsB!=0;
        return (SelectedA || SelectedB) && (!Filter || Filter->ShouldCollide(A, SA, IA, B, SB, IB));
    }
private:
    const JPH::SimShapeFilter* Filter;
    const JPH::Body& A;
    const JPH::Body& B;
    uint8 PartsA,PartsB;
};

static float Radius(const JPH::Body& B)
{
    const auto Bounds = B.GetShape()->GetLocalBounds();
    return Bounds.GetCenter().Length() + Bounds.GetExtent().Length();
}
static JPH::Quat PredictedRotation(const JPH::Body& B, float Time)
{
    const auto W = B.GetAngularVelocity(); const float Speed = W.Length();
    return Speed > 1.e-8f ? (JPH::Quat::sRotation(W / Speed, Speed * Time) * B.GetRotation()).Normalized() : B.GetRotation();
}
bool Respond(JPH::PhysicsSystem& Physics, JPH::Body& A, JPH::Body& B, float Seconds, const FSettings& Settings,
    uint8 PartsA, uint8 PartsB)
{
    if (Settings.Strength <= 0 || Seconds <= 0 || A.IsSensor() || B.IsSensor()
        || (!A.IsDynamic() && !B.IsDynamic()) || (!A.IsActive() && !B.IsActive())) return false;
    const auto Base = A.GetCenterOfMassPosition();
    const JPH::Vec3 Relative(B.GetCenterOfMassPosition() - Base);
    const auto Travel = (B.GetLinearVelocity() - A.GetLinearVelocity()) * Seconds;
    const float R = Radius(A) + Radius(B);
    const float T = Travel.LengthSq() > 1.e-12f ? FMath::Clamp(-Relative.Dot(Travel) / Travel.LengthSq(), 0.f, 1.f) : 0.f;
    if ((Relative + Travel * T).LengthSq() > R * R) return false;
    const float Speed = Travel.Length() + Seconds * (A.GetAngularVelocity().Length() * Radius(A) + B.GetAngularVelocity().Length() * Radius(B));
    if (Speed <= 1.e-8f) return false;
    FPairShapeFilter Filter(Physics, A, B, PartsA, PartsB);
    JPH::CollideShapeSettings Query;
    Query.mCollisionTolerance = 1.e-6f;
    Query.mMaxSeparationDistance = Speed + 1.e-4f;
    float Fraction = 0.f;
    for (int32 I = 0; I < Settings.MaxIterations && Fraction <= 1.f; ++I)
    {
        const float Time = Fraction * Seconds;
        const auto QA = PredictedRotation(A, Time), QB = PredictedRotation(B, Time);
        const auto PA = A.GetLinearVelocity() * Time;
        const auto PB = Relative + B.GetLinearVelocity() * Time;
        JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> Hit;
        JPH::CollisionDispatch::sCollideShapeVsShape(A.GetShape(), B.GetShape(), JPH::Vec3::sOne(), JPH::Vec3::sOne(),
            JPH::Mat44::sRotationTranslation(QA, PA), JPH::Mat44::sRotationTranslation(QB, PB), {}, {}, Query, Hit, Filter);
        if (!Hit.HadHit()) return false;
        const float Gap = -Hit.mHit.mPenetrationDepth;
        if (Gap <= 1.e-5f)
        {
            // Do not add a second depenetration solver for already touching/overlapping pairs.
            if (Fraction == 0.f || Hit.mHit.mPenetrationAxis.LengthSq() <= 1.e-12f) return false;
            const auto N = Hit.mHit.mPenetrationAxis.Normalized(); // A -> B
            const auto RA = A.GetRotation() * (QA.Conjugated() * (Hit.mHit.mContactPointOn1 - PA));
            const auto RB = B.GetRotation() * (QB.Conjugated() * (Hit.mHit.mContactPointOn2 - PB));
            const float Closing = (A.GetPointVelocityCOM(RA) - B.GetPointVelocityCOM(RB)).Dot(N);
            const float Distance = FMath::Max(0.f, (Relative + RB - RA).Dot(N));
            const float Correction = Closing - Distance / Seconds;
            if (Correction <= 0.f) return false;
            auto InverseMass = [&](const JPH::Body& Body, JPH::Vec3Arg Arm)
            {
                if (!Body.IsDynamic()) return 0.f;
                const auto Cross = Arm.Cross(N);
                return Body.GetMotionProperties()->GetInverseMass() + Cross.Dot(Body.GetInverseInertia().Multiply3x3(Cross));
            };
            const float K = InverseMass(A, RA) + InverseMass(B, RB);
            if (K <= 1.e-12f) return false;
            const float Magnitude = Settings.Strength * Correction / K;
            if (!FMath::IsFinite(Magnitude)) return false;
            auto& BI = Physics.GetBodyInterfaceNoLock();
            if (A.IsDynamic()) { BI.ActivateBody(A.GetID()); A.AddImpulse(-N * Magnitude, Base + JPH::RVec3(RA)); }
            if (B.IsDynamic()) { BI.ActivateBody(B.GetID()); B.AddImpulse(N * Magnitude, B.GetCenterOfMassPosition() + JPH::RVec3(RB)); }
            // This is prevention, not an actual contact. Only the normal solver may emit Hit.
            return true;
        }
        Fraction += Gap / (Speed * 1.01f);
    }
    return false; // An exhausted query is not evidence of a collision.
}
void AfterServo(JPH::PhysicsSystem* Physics, float Seconds)
{
    if (Packets.IsEmpty()) return;
    const FPacket* Packet = Packets.Find(Physics);
    if (!Packet) return;
    for (const auto& Source : Packet->Selected)
    {
        JPH::BodyLockWrite LockA(Physics->GetBodyLockInterfaceNoLock(), JPH::BodyID(Source.ID));
        if (!LockA.SucceededAndIsInBroadPhase()) continue;
        auto& A = LockA.GetBody();
        for (uint32 ID : Packet->Candidates)
        {
            if (ID == Source.ID) continue;
            const auto* Other = Packet->SelectedByID.Find(ID);
            if (Other && ID < Source.ID) continue; // one response per pair even when both agents opt in
            JPH::BodyLockWrite LockB(Physics->GetBodyLockInterfaceNoLock(), JPH::BodyID(ID));
            if (!LockB.SucceededAndIsInBroadPhase()) continue;
            auto& B = LockB.GetBody();
            if (!Packet->Filter->ShouldCollide(A.GetObjectLayer(), B.GetObjectLayer())
                || !A.GetCollisionGroup().CanCollide(B.GetCollisionGroup())) continue;
            FSettings Effective = Source.Settings;
            if (Other) { Effective.Strength = FMath::Max(Effective.Strength, Other->Settings.Strength); Effective.MaxIterations = FMath::Max(Effective.MaxIterations, Other->Settings.MaxIterations); }
            Respond(*Physics, A, B, Seconds, Effective, Source.Parts, Other ? Other->Parts : 0);
        }
    }
}
}

bool UProphecyJoltPHATSweepLibrary::SetJoltPHATSweeps(AActor* Agent, bool Enabled, float Strength, int32 MaxIterations)
{
    using namespace ProphecyJolt::PHATSweeps;
    if (!IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || !Agent->GetWorld()->IsGameWorld()
        || Agent->GetWorld()->bIsTearingDown || !FMath::IsFinite(Strength) || Strength < 0.f || Strength > 1.f
        || MaxIterations < 1 || MaxIterations > 128) return false;
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Agent);
    if (!Meshes.ContainsByPredicate([](const auto* Mesh) { return Mesh->GetFName() == TEXT("PhysicalMesh"); })) return false;
    Configurations.Add(Agent, {{Strength, MaxIterations}, Enabled && Strength > 0.f});
    RefreshRequest(Agent); return true;
}
void UProphecyJoltPHATSweepLibrary::GetJoltPHATSweeps(AActor* Agent, bool& Enabled, float& Strength, int32& MaxIterations)
{
    using namespace ProphecyJolt::PHATSweeps;
    const bool Valid = IsInGameThread() && IsValid(Agent);
    const auto* Config = Valid ? Configurations.Find(Agent) : nullptr;
    Enabled = Valid && IsCombatActive(Agent) && Requests.Contains(Agent);
    Strength = Config ? Config->Settings.Strength : 1.f;
    MaxIterations = Config ? Config->Settings.MaxIterations : 64;
}
void UProphecyJoltPHATSweepLibrary::NotifyAttackState(AActor* Agent, bool Attacking)
{
    using namespace ProphecyJolt::PHATSweeps;
    if (!IsInGameThread() || !IsValid(Agent)) return;
    // Preserve a live pre-gating request's custom tuning when installing this patch.
    if (!Configurations.Contains(Agent))
        if (const auto* Existing = Requests.Find(Agent)) Configurations.Add(Agent, {*Existing, true});
    if (Attacking) AttackingAgents.Add(Agent);
    else
    {
        AttackingAgents.Remove(Agent);
        if (const auto* Parts=AttackParts.Find(Agent)) SwordOwners.Remove(Parts->Sword);
        AttackParts.Remove(Agent);
    }
    RefreshRequest(Agent);
}

void UProphecyJoltPHATSweepLibrary::SetAttackParts(AActor* Agent, const TArray<FName>& Bones, UPrimitiveComponent* Sword)
{
    using namespace ProphecyJolt::PHATSweeps;
    if (!IsInGameThread() || !IsValid(Agent)) return;
    if (const auto* Previous=AttackParts.Find(Agent)) SwordOwners.Remove(Previous->Sword);
    auto& Parts=AttackParts.FindOrAdd(Agent);Parts.Bones.Reset();Parts.Sword=nullptr;
    for (FName Bone:Bones) if (Bone!=TEXT("sword")) Parts.Bones.AddUnique(Bone);
    if (Bones.Contains(TEXT("sword")) && IsValid(Sword))
    { Parts.Sword=Sword;SwordOwners.Add(Sword,Agent); }
    RefreshRequest(Agent);
}

void UProphecyJoltPHATSweepLibrary::NotifyDefenseState(AActor* Agent, bool Defending)
{
    // Compatibility entry point only. Defense never owns predictive sweeps.
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySweepAttackGateTest, "Prophecy.Jolt.ContactShapes.AttackSweepGate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySweepAttackGateTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    if (!TestNotNull(TEXT("Test world"), World)) return false;
    ON_SCOPE_EXIT { ProphecyJolt::PHATSweeps::ForgetWorld(World); World->DestroyWorld(false); };
    AActor* Agent = World->SpawnActor<AActor>();
    if (!TestNotNull(TEXT("Test agent"), Agent)) return false;
    auto* Mesh=NewObject<USkeletalMeshComponent>(Agent, TEXT("PhysicalMesh"));Agent->AddInstanceComponent(Mesh);
    AActor* Weapon=World->SpawnActor<AActor>();Weapon->SetOwner(Agent);
    auto* Sword=NewObject<USkeletalMeshComponent>(Weapon,TEXT("Sword"));Weapon->AddInstanceComponent(Sword);
    using L = UProphecyJoltPHATSweepLibrary;
    auto Check = [&](bool Expected, float ExpectedStrength, int32 ExpectedIterations)
    {
        bool Enabled; float Strength; int32 Iterations;
        L::GetJoltPHATSweeps(Agent, Enabled, Strength, Iterations);
        TestEqual(TEXT("Effective attack gate"), Enabled, Expected);
        TestEqual(TEXT("Strength retained"), Strength, ExpectedStrength);
        TestEqual(TEXT("Iterations retained"), Iterations, ExpectedIterations);
        TestEqual(TEXT("No sweep packet requested outside attack"), ProphecyJolt::PHATSweeps::HasRequests(World), Expected);
    };
    const auto Begin=[&](const TArray<FName>& Bones,UPrimitiveComponent* Weapon=nullptr)
    { L::SetAttackParts(Agent,Bones,Weapon);L::NotifyAttackState(Agent,true); };
    const auto Selected=[&](FName Bone){return ProphecyJolt::PHATSweeps::FindBody(Mesh,Bone)!=nullptr;};
    Check(false,1.f,64);
    L::NotifyDefenseState(Agent,true);Check(false,1.f,64);
    L::NotifyAttackState(Agent,true);Check(false,1.f,64); // no implicit whole-body fallback
    Begin({TEXT("hand_l"),TEXT("lowerarm_l")});Check(true,1.f,64);
    TestTrue(TEXT("Punch selects hand and forearm only"),Selected(TEXT("hand_l"))&&Selected(TEXT("lowerarm_l"))&&!Selected(TEXT("head"))&&!Selected(TEXT("hand_r")));
    Begin({TEXT("foot_r"),TEXT("calf_r")});
    TestTrue(TEXT("Chain replaces selection with foot/calf only"),Selected(TEXT("foot_r"))&&Selected(TEXT("calf_r"))&&!Selected(TEXT("hand_l"))&&!Selected(TEXT("ball_r")));
    Begin({TEXT("head")});TestTrue(TEXT("Headbutt only head"),Selected(TEXT("head"))&&!Selected(TEXT("neck_01")));
    Begin({TEXT("sword")},Sword);
    TestTrue(TEXT("Sword only, not carrier hand"),ProphecyJolt::PHATSweeps::FindBody(Sword,NAME_None)!=nullptr&&!Selected(TEXT("hand_r")));
    Weapon->SetOwner(nullptr);
    TestNull(TEXT("Dropped sword no longer initiates sweeps"),ProphecyJolt::PHATSweeps::FindBody(Sword,NAME_None));
    Weapon->SetOwner(Agent);
    L::SetJoltPHATSweeps(Agent,false,.5f,32);Check(false,.5f,32);
    TestNull(TEXT("Disabled sword not selected"),ProphecyJolt::PHATSweeps::FindBody(Sword,NAME_None));
    L::NotifyAttackState(Agent,false);Begin({TEXT("head")});Check(false,.5f,32);
    L::SetJoltPHATSweeps(Agent,true,.5f,32);Check(true,.5f,32);
    TestNull(TEXT("Prior sword selection cleared"),ProphecyJolt::PHATSweeps::FindBody(Sword,NAME_None));
    L::NotifyDefenseState(Agent,false);Check(true,.5f,32);
    L::SetJoltPHATSweeps(Agent,true,0.f,32);Check(false,0.f,32);
    L::NotifyAttackState(Agent,false);Check(false,0.f,32);
    L::SetJoltPHATSweeps(Agent,true,.8f,48);Check(false,.8f,48);
    L::NotifyDefenseState(Agent,true);Check(false,.8f,48);
    Begin({TEXT("sword")});Check(false,.8f,48); // no held weapon, no sweep
    Begin({});Check(false,.8f,48);
    Begin({TEXT("head")});Check(true,.8f,48);
    L::NotifyAttackState(Agent,false);Check(false,.8f,48);
    ProphecyJolt::PHATSweeps::ForgetWorld(World);Check(false,1.f,64);
    return true;
}
#endif
