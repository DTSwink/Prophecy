#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltAttackCollisionLibrary.h"
#include "ProphecyJoltBodyDriveLibrary.h"
#include "ProphecyJoltFootJointLibrary.h"
#include "ProphecyJoltPhysicsCommand.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeLock.h"
#include "PhysicsPublic.h"
#include "PhysicsEngine/BodyInstance.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltBody.h"
#include "ProphecyJoltStaticBody.h"
#include "ProphecyJoltJointConversion.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltMaterial.h"
#include "ProphecyJoltVelocityServo.h"
#include "ProphecyJoltPHATSweeps.h"
#include "Templates/UnrealTemplate.h"
#include "UObject/WeakObjectPtr.h"

#include <atomic>

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemThreadPool.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/Body/BodyLockMulti.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/GroupFilterTable.h>
#include <Jolt/Physics/Collision/NarrowPhaseQuery.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/SimShapeFilter.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END
#include "ProphecyJoltSpeculativeJoint.h"
#include "ProphecyJoltRadialJoint.h"
#include "ProphecyJoltJointDamping.h"
#include "ProphecyJoltFootExtension.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltWorld, Log, All);

namespace ProphecyJolt::WorldPrivate
{
std::atomic<int32> LiveSimulations{0};
static_assert(sizeof(JPH::ObjectLayer) == sizeof(uint16), "Review the collision profile capacity for a changed Jolt ABI.");
static_assert(JPH::Body::cProphecyNumericalSafetyVersion == 1, "Rebuild the reviewed numerical-safety Jolt dependency.");

FProphecyJoltWorldStatus Fail(EProphecyJoltWorldResult Code, const TCHAR* Message)
{
    return { Code, Message };
}

bool Finite(const FVector& Value)
{
    return FMath::IsFinite(Value.X) && FMath::IsFinite(Value.Y) && FMath::IsFinite(Value.Z);
}

bool FitsFloat(double Value)
{
    return FMath::IsFinite(Value) && FMath::IsFinite(static_cast<float>(Value));
}

bool FitsFloatVector(const FVector& Value, double Scale)
{
    return FitsFloat(Value.X * Scale) && FitsFloat(Value.Y * Scale) && FitsFloat(Value.Z * Scale);
}

struct FCollisionProfile
{
    bool bStatic = false;
    uint8 ObjectChannel = 0;
    uint32 BlockMask = 0;
    bool bCompoundCarrier = false;
    uint32 ChannelBit() const { return bCompoundCarrier ? MAX_uint32 : uint32(1) << ObjectChannel; }
    uint64 Key() const { return (uint64(bCompoundCarrier) << 38) | (uint64(BlockMask) << 6) | (uint64(ObjectChannel) << 1) | uint64(bStatic); }
};

bool MakeCollisionProfile(bool bStatic, ECollisionChannel ObjectChannel,
    const FCollisionResponseContainer& Responses, FCollisionProfile& Out)
{
    if (static_cast<uint32>(ObjectChannel) >= 32) return false;
    Out = { bStatic, static_cast<uint8>(ObjectChannel), 0 };
    for (uint32 Channel = 0; Channel < 32; ++Channel)
    {
        const ECollisionResponse Response = Responses.GetResponse(static_cast<ECollisionChannel>(Channel));
        if (Response == ECR_Block) Out.BlockMask |= uint32(1) << Channel;
        else if (Response != ECR_Ignore && Response != ECR_Overlap) return false;
    }
    return true;
}

// Mutated only by game-thread creation outside Update. Worker callbacks read immutable indexed rows,
// never the GT-only hash map, adapter handles, source components, or other UObject state.
class FCollisionProfiles final
{
public:
    explicit FCollisionProfiles(uint32 InCapacity) : Capacity(InCapacity) {}

    FProphecyJoltWorldStatus Intern(TConstArrayView<FCollisionProfile> Requested, TArray<JPH::ObjectLayer>& OutLayers)
    {
        OutLayers.Reset();
        TSet<uint64> NewKeys;
        for (const FCollisionProfile& Profile : Requested)
            if (!LayersByKey.Contains(Profile.Key())) NewKeys.Add(Profile.Key());
        if (uint64(Profiles.Num()) + uint64(NewKeys.Num()) > Capacity)
            return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Complete request exceeds the interned collision-profile capacity; no body was created."));
        OutLayers.Reserve(Requested.Num());
        for (const FCollisionProfile& Profile : Requested)
        {
            JPH::ObjectLayer Layer;
            if (const JPH::ObjectLayer* Existing = LayersByKey.Find(Profile.Key())) Layer = *Existing;
            else
            {
                Layer = static_cast<JPH::ObjectLayer>(Profiles.Num());
                check(Layer != JPH::cObjectLayerInvalid);
                Profiles.Add(Profile);
                LayersByKey.Add(Profile.Key(), Layer);
                // A conservative union can retain channels from removed bodies or failed creation.
                // It may allow extra traversal, but can never hide a subsequently added channel.
                UsedChannels[Profile.bStatic ? 0 : 1] |= Profile.ChannelBit();
            }
            OutLayers.Add(Layer);
        }
        return {};
    }

    const FCollisionProfile& Get(JPH::ObjectLayer Layer) const { check(Profiles.IsValidIndex(Layer)); return Profiles[Layer]; }
    uint32 GetUsedChannels(uint8 BroadPhase) const { check(BroadPhase < 2); return UsedChannels[BroadPhase]; }
    uint32 Num() const { return static_cast<uint32>(Profiles.Num()); }
private:
    uint32 Capacity;
    TArray<FCollisionProfile> Profiles;
    TMap<uint64, JPH::ObjectLayer> LayersByKey;
    uint32 UsedChannels[2] = {};
};

class FBroadPhaseLayers final : public JPH::BroadPhaseLayerInterface
{
public:
    explicit FBroadPhaseLayers(const FCollisionProfiles& InProfiles) : Profiles(InProfiles) {}
    virtual JPH::uint GetNumBroadPhaseLayers() const override { return 2; }
    virtual JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer Layer) const override
    {
        return JPH::BroadPhaseLayer(Profiles.Get(Layer).bStatic ? 0 : 1);
    }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer Layer) const override
    {
        return Layer == JPH::BroadPhaseLayer(0) ? "FixtureStatic" : "FixtureMoving";
    }
#endif
private:
    const FCollisionProfiles& Profiles;
};

class FObjectPairs final : public JPH::ObjectLayerPairFilter
{
public:
    explicit FObjectPairs(const FCollisionProfiles& InProfiles) : Profiles(InProfiles) {}
    virtual bool ShouldCollide(JPH::ObjectLayer A, JPH::ObjectLayer B) const override
    {
        const FCollisionProfile& First = Profiles.Get(A);
        const FCollisionProfile& Second = Profiles.Get(B);
        return !(First.bStatic && Second.bStatic)
            && (First.BlockMask & Second.ChannelBit()) != 0
            && (Second.BlockMask & First.ChannelBit()) != 0;
    }
private:
    const FCollisionProfiles& Profiles;
};

class FObjectVsBroadPhase final : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
    explicit FObjectVsBroadPhase(const FCollisionProfiles& InProfiles) : Profiles(InProfiles) {}
    virtual bool ShouldCollide(JPH::ObjectLayer Object, JPH::BroadPhaseLayer BroadPhase) const override
    {
        const FCollisionProfile& Profile = Profiles.Get(Object);
        const uint8 Tree = static_cast<JPH::BroadPhaseLayer::Type>(BroadPhase);
        return !(Profile.bStatic && Tree == 0) && (Profile.BlockMask & Profiles.GetUsedChannels(Tree)) != 0;
    }
private:
    const FCollisionProfiles& Profiles;
};

// Jolt guarantees ordered stack allocations/frees through job dependencies, even across worker threads.
// No fallback hides insufficient capacity. Jolt's allocator aborts on exhaustion; the outer runner must
// treat process failure as failure, and these counters cannot make that path recoverable.
class FMeasuredTempAllocator final : public JPH::TempAllocator
{
public:
    explicit FMeasuredTempAllocator(uint32 Bytes) : Storage(Bytes) {}
    virtual void* Allocate(JPH::uint Bytes) override
    {
        if (!Storage.CanAllocate(Bytes))
        {
            UE_LOG(LogProphecyJoltWorld, Error, TEXT("Jolt fixed temp capacity exhausted: requested %u, used %llu, capacity %llu bytes. Jolt will abort."),
                Bytes, static_cast<uint64>(Storage.GetUsage()), static_cast<uint64>(Storage.GetSize()));
        }
        void* Result = Storage.Allocate(Bytes);
        Peak = FMath::Max(Peak, static_cast<uint64>(Storage.GetUsage()));
        ++AllocationCount;
        return Result;
    }
    virtual void Free(void* Address, JPH::uint Bytes) override { Storage.Free(Address, Bytes); }
    uint64 GetUsage() const { return static_cast<uint64>(Storage.GetUsage()); }
    uint64 Peak = 0;
    uint64 AllocationCount = 0;
private:
    JPH::TempAllocatorImpl Storage;
};

struct FBodyIdentity
{
    int32 Slot = INDEX_NONE;
    uint64 Generation = 0;
    bool operator==(const FBodyIdentity& Other) const { return Slot == Other.Slot && Generation == Other.Generation; }
    friend uint32 GetTypeHash(const FBodyIdentity& Key) { return HashCombine(::GetTypeHash(Key.Slot), ::GetTypeHash(Key.Generation)); }
};

struct FSuppressionKey
{
    FBodyIdentity A, B;
    bool operator==(const FSuppressionKey& Other) const { return A == Other.A && B == Other.B; }
    friend uint32 GetTypeHash(const FSuppressionKey& Key) { return HashCombine(GetTypeHash(Key.A), GetTypeHash(Key.B)); }
};

bool SameBody(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

uint64 NativePairKey(const JPH::BodyID& A, const JPH::BodyID& B)
{
    const uint32 First = A.GetIndexAndSequenceNumber(), Second = B.GetIndexAndSequenceNumber();
    return (uint64(FMath::Min(First, Second)) << 32) | uint64(FMath::Max(First, Second));
}

// Immutable throughout synchronous Update. Only this compact numeric array is visible to workers.
// The separate GT ownership keys include full adapter generations; reused native IDs inherit no veto.
struct FWeldRecord : ProphecyJolt::Material::FAttachedMaterialData
{
    FProphecyJoltBodyHandle SourceHandle;
    FTransform SourceToParent;
    JPH::RefConst<JPH::Shape> OriginalShape;
    JPH::RefConst<JPH::Shape> WeldedShape;
    JPH::CollisionGroup OriginalGroup;
    JPH::ObjectLayer OriginalLayer;
    JPH::EMotionQuality OriginalQuality;
    JPH::MassProperties OriginalMass;
    JPH::Mat44 SwordInertia;
    float InertiaScale = 0.0f;
};

class FScopedPairFilter final : public JPH::SimShapeFilter
{
public:
    const FCollisionProfiles* Profiles = nullptr;
    TArray<uint64> SortedPairs;
    virtual bool ShouldCollide(const JPH::Body& A, const JPH::Shape* ShapeA, const JPH::SubShapeID& IDA,
        const JPH::Body& B, const JPH::Shape* ShapeB, const JPH::SubShapeID& IDB) const override
    {
        const auto* WeldA=static_cast<const FWeldRecord*>(ProphecyJolt::Material::AttachedData(A));
        const auto* WeldB=static_cast<const FWeldRecord*>(ProphecyJolt::Material::AttachedData(B));
        const JPH::Body* EffectiveA=&A; const JPH::Body* EffectiveB=&B;
        if (WeldA || WeldB)
        {
            // Compound/decorator roots are only traversal candidates. Apply the exact
            // profile, PHAT groups and pair exclusions after selecting each child.
            const auto Unresolved=[](const FWeldRecord* W,const JPH::Shape* S)
            { return W && (S==W->CarrierRoot || S==W->Compound); };
            if (Unresolved(WeldA,ShapeA) || Unresolved(WeldB,ShapeB)) return true;
            const auto Child=[](const FWeldRecord* W,const JPH::SubShapeID& ID)
            { return W && W->IsSource(ID); };
            const bool ChildA=Child(WeldA,IDA), ChildB=Child(WeldB,IDB);
            if(ChildA) EffectiveA=WeldA->Source;
            if(ChildB) EffectiveB=WeldB->Source;
            const auto& PA=Profiles->Get(WeldA && !ChildA ? WeldA->OriginalLayer : EffectiveA->GetObjectLayer());
            const auto& PB=Profiles->Get(WeldB && !ChildB ? WeldB->OriginalLayer : EffectiveB->GetObjectLayer());
            if (!(PA.BlockMask & PB.ChannelBit()) || !(PB.BlockMask & PA.ChannelBit())) return false;
            const auto& GA=WeldA && !ChildA ? WeldA->OriginalGroup : EffectiveA->GetCollisionGroup();
            const auto& GB=WeldB && !ChildB ? WeldB->OriginalGroup : EffectiveB->GetCollisionGroup();
            if(!GA.CanCollide(GB)) return false;
        }
        const uint64 Key = NativePairKey(EffectiveA->GetID(), EffectiveB->GetID());
        int32 First = 0, End = SortedPairs.Num();
        while (First < End)
        {
            const int32 Middle = First + (End - First) / 2;
            if (SortedPairs[Middle] < Key) First = Middle + 1;
            else End = Middle;
        }
        return First == SortedPairs.Num() || SortedPairs[First] != Key;
    }
};

struct FSuppressionRecord
{
    uint64 NativeKey = 0;
    uint32 References = 0;
};

struct FJointRecord
{
    FProphecyJoltJointSettings Settings;
    JPH::Ref<JPH::TwoBodyConstraint> Constraint;
    TArray<FSuppressionKey> Suppression;
};

struct FJointSlot
{
    uint64 Generation = 1;
    TUniquePtr<FJointRecord> Record;
};

bool RigidJointFrame(const FTransform& Frame)
{
    return Frame.IsValid() && Frame.GetScale3D().Equals(FVector::OneVector, 1.0e-6)
        && FitsFloatVector(Frame.GetTranslation(), 0.01);
}

FProphecyJoltWorldStatus FillHardLimits(const FProphecyJoltJointSettings& In, JPH::SixDOFConstraintSettings& Out)
{
    if (In.SwingGeometry != EProphecyJoltSwingGeometry::Cone && In.SwingGeometry != EProphecyJoltSwingGeometry::Pyramid)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Unknown stock swing geometry."));
    Out.mSwingType = In.SwingGeometry == EProphecyJoltSwingGeometry::Cone ? JPH::ESwingType::Cone : JPH::ESwingType::Pyramid;
    for (int32 Index = 0; Index < 6; ++Index)
    {
        const bool bAngular = Index >= 3;
        const auto& Limit = bAngular ? In.Rotation[Index - 3] : In.Translation[Index];
        const auto Axis = static_cast<JPH::SixDOFConstraintSettings::EAxis>(Index);
        // Even unused fields must be finite; Locked/Free never interpret a nonzero stored interval.
        if (!FMath::IsFinite(Limit.Minimum) || !FMath::IsFinite(Limit.Maximum))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint limits must be finite."));
        if (Limit.Motion == EProphecyJoltAxisMotion::Locked) { Out.MakeFixedAxis(Axis); continue; }
        if (Limit.Motion == EProphecyJoltAxisMotion::Free) { Out.MakeFreeAxis(Axis); continue; }
        const double Scale = bAngular ? 1.0 : 0.01;
        const float Minimum = static_cast<float>(Limit.Minimum * Scale), Maximum = static_cast<float>(Limit.Maximum * Scale);
        if (Limit.Motion != EProphecyJoltAxisMotion::Limited || !FMath::IsFinite(Minimum) || !FMath::IsFinite(Maximum)
            || Minimum >= Maximum || Minimum == -FLT_MAX || Maximum == FLT_MAX)
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Limited axis requires an ordered, representable interval, excluding native free-axis sentinels."));
        if (bAngular)
        {
            if (Limit.Minimum < -UE_DOUBLE_PI || Limit.Maximum > UE_DOUBLE_PI)
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Angular limits must be within [-pi, pi] radians."));
            if (Index >= 4 && In.SwingGeometry == EProphecyJoltSwingGeometry::Cone
                && (Limit.Minimum != -Limit.Maximum || Maximum <= 0.0f))
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Cone swing requires exactly symmetric positive half ranges; use Pyramid for asymmetric swing."));
            const float Locked = JPH::DegreesToRadians(0.5f), Free = JPH::DegreesToRadians(179.5f);
            if ((Minimum > -Locked && Maximum < Locked) || (Minimum < -Free && Maximum > Free))
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Limited angular range enters a stock internal Locked/Free threshold; specify that mode explicitly."));
        }
        Out.SetLimitedAxis(Axis, Minimum, Maximum);
    }
    return {};
}

struct FBodySlot
{
    JPH::BodyID Body;
    uint64 Generation = 1;
    TWeakObjectPtr<UObject> AssociatedObject;
    FName HitBone;
    int32 HitBodyIndex = INDEX_NONE;
    bool bHitEvents = false;
    FProphecyJoltRigHandle OwnerRig;
    TArray<int32> IncidentJoints;
    TSet<FSuppressionKey> SuppressionPairs;
    TArray<FSuppressionKey> OwnedSuppression;
    TUniquePtr<FWeldRecord> Weld;
    FProphecyJoltBodyHandle WeldParent;
};

bool SameRig(const FProphecyJoltRigHandle& A, const FProphecyJoltRigHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

uint64 RigPairKey(int32 A, int32 B)
{
    return (uint64(FMath::Min(A, B)) << 32) | uint32(FMath::Max(A, B));
}

struct FRigRecord
{
    FRigRecord() { ServoState.DenominatorSeconds = 1.0f / 60.0f; }
    FGuid CaptureId;
    bool bCommitted = false;
    bool bPlayerSwingLimits = false;
    uint8 CCDMode = 0;
    TArray<uint8> AuthoredCCD;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<JPH::Ref<JPH::TwoBodyConstraint>> Constraints;
    TArray<FProphecyJoltRigJoint> JointDescriptions;
    TArray<FProphecyJoltRigDisabledPair> DisabledPairs;
    TSet<uint64> AuthoredDisabledPairKeys;
    bool bSelfCollisionEnabled = true;
    TSet<int32> SelfCollisionDisabledBodies;
    TSet<uint64> SelfCollisionDisabledPairs;
    JPH::Ref<JPH::GroupFilterTable> CollisionFilter;
    JPH::CollisionGroup::GroupID CollisionGroupId = JPH::CollisionGroup::cInvalidGroup;
    TArray<FString> CoverageNotes;
    TArray<ProphecyJolt::FVelocityServo::FTarget> Targets;
    TArray<FProphecyJoltBodyHandle> PublishedHandles;
    FProphecyJoltRigServoState ServoState;
};

// Sparse sidecar rather than changing the layout of retained live rig records.
static TMap<const FRigRecord*,TArray<ProphecyJolt::FootExtension::FJoint>> FootExtensions;
// Sparse event state: no rig layout change, per-tick poll, or contact-time lookup.
static TSet<const FRigRecord*> AttackSelfCollisionSuppressed;
static void RemoveFootExtensions(JPH::PhysicsSystem& Physics,const FRigRecord* Rig)
{
    if (auto* Entries=FootExtensions.Find(Rig))
    {
        for (auto& Entry:*Entries)
        {
            Physics.RemoveConstraint(Entry.Translation.GetPtr());
            Entry.Original->SetTranslationLimits(Entry.Minimum,Entry.Maximum);
        }
        FootExtensions.Remove(Rig);
    }
}

// Called only at possession/range transitions, outside Update. Keep the same
// native SixDOF (and its warm start/body state) when changing its registered wrapper.
void RefreshSpeculativeJoint(JPH::PhysicsSystem& Physics, JPH::Ref<JPH::TwoBodyConstraint>& Registered, bool bPlayer)
{
    JPH::SixDOFConstraint* NativeJoint = ProphecyJolt::GetSixDOF(Registered.GetPtr());
    const bool bWanted = bPlayer && ProphecyJolt::NeedsSpeculativeSwing(*NativeJoint);
    const bool bWrapped = Registered->GetSubType() == JPH::EConstraintSubType::User1;
    if (bWanted == bWrapped) return;
    JPH::Ref<JPH::TwoBodyConstraint> Replacement = NativeJoint;
    if (bWanted)
    {
        const JPH::Ref<JPH::ConstraintSettings> Settings = NativeJoint->GetConstraintSettings();
        Replacement = new ProphecyJolt::FSpeculativeJoint(*NativeJoint,
            *static_cast<JPH::SixDOFConstraintSettings*>(Settings.GetPtr()));
    }
    Replacement->SetNumVelocityStepsOverride(Registered->GetNumVelocityStepsOverride());
    Replacement->SetNumPositionStepsOverride(Registered->GetNumPositionStepsOverride());
    Replacement->SetConstraintPriority(Registered->GetConstraintPriority());
    // Preserve the registration index as well as the native joint state. Remove/Add
    // changes the solve order and can kick an attachment even with inactive limits.
    Physics.ReplaceConstraint(Registered.GetPtr(), Replacement.GetPtr());
    Registered = MoveTemp(Replacement);
}

struct FRigSlot
{
    uint64 Generation = 1;
    TUniquePtr<FRigRecord> Record;
};

struct FServoRange
{
    FProphecyJoltRigHandle Rig;
    int32 Begin = 0;
    int32 Count = 0;
};
}

struct FProphecyJoltPendingHit
{
    FProphecyJoltBodyHandle Body1, Body2;
    FVector Point1, Point2, Normal, Impulse;
};

namespace ProphecyJolt::DriveFollowers
{
struct FBinding
{
    JPH::BodyID Body, Parent;
    FProphecyJoltRigHandle ParentRig;
};
// Sparse, event-owned bindings; no change to retained world/rig/servo layouts.
static TMap<const FProphecyJoltWorldState*, TMap<uint32, FBinding>> Bindings;
}

class FProphecyJoltWorldState final : public JPH::ContactImpulseListener
{
public:
    explicit FProphecyJoltWorldState(const FProphecyJoltWorldSettings& InSettings)
        : Settings(InSettings), Lifetime(FGuid::NewGuid()), CollisionProfiles(InSettings.MaxCollisionProfiles),
          BroadPhaseLayers(CollisionProfiles), ObjectPairs(CollisionProfiles), ObjectVsBroadPhase(CollisionProfiles),
          Temp(InSettings.TempAllocatorBytes)
    {
        Physics.Init(Settings.MaxBodies, 0, Settings.MaxBodyPairs, Settings.MaxContactConstraints,
            BroadPhaseLayers, ObjectVsBroadPhase, ObjectPairs);
        Physics.SetCombineFriction(&ProphecyJolt::Material::CombineFriction);
        Physics.SetCombineRestitution(&ProphecyJolt::Material::CombineRestitution);
        ScopedPairFilter.Profiles = &CollisionProfiles;
        // Explicit same-binary diagnostic, resolved once for this world's lifetime.
        bNoLockIdleBodyReads = FParse::Param(FCommandLine::Get(), TEXT("ProphecyJoltNoLockIdleReads"));
        // The optional sparse filter is installed only while exclusions exist.
        Physics.SetGravity(ProphecyJolt::Conversions::ToJoltDirection(
            Settings.GravityCmPerSecondSquared * ProphecyJolt::Conversions::CentimetersToMeters));
        Jobs = MakeUnique<JPH::JobSystemThreadPool>(JPH::cMaxPhysicsJobs, JPH::cMaxPhysicsBarriers, Settings.WorkerThreads);
        Physics.AddStepListener(&Servo);
        ProphecyJolt::WorldPrivate::LiveSimulations.fetch_add(1, std::memory_order_relaxed);
    }

    ~FProphecyJoltWorldState()
    {
        ProphecyJolt::PHATSweeps::Forget(&Physics);
        // Update is synchronous, and public methods are game-thread-only. No work can race teardown.
        Physics.SetContactListener(nullptr);
        Physics.SetContactImpulseListener(nullptr);
        Physics.SetBodyActivationListener(nullptr);
        Physics.SetSimShapeFilter(nullptr);
        Physics.RemoveStepListener(&Servo);
        Servo.Clear();
        for (int32 Index = 0; Index < Joints.Num(); ++Index) DestroyJointSlot(Index);
        for (int32 Index = 0; Index < Rigs.Num(); ++Index) DestroyRigSlot(Index);
        Jobs.Reset();
        check(Physics.GetConstraints().empty());
        for (int32 Index = 0; Index < Slots.Num(); ++Index) DestroySlot(Index);
        check(Temp.GetUsage() == 0);
        ProphecyJolt::WorldPrivate::LiveSimulations.fetch_sub(1, std::memory_order_relaxed);
    }

    // Registry mutations occur only on GT outside Update. Workers read native/plain data only.
    TArray<int32> NativeBodySlots;
    int32 HitEnabledBodies = 0;
    FCriticalSection HitMutex;
    TArray<FProphecyJoltPendingHit> PendingHits;
    uint64 DeliveredHits = 0;
    bool bDispatchingHits = false;

    const ProphecyJolt::WorldPrivate::FBodySlot* HitSlot(const JPH::Body& Body) const
    {
        const uint32 Index = Body.GetID().GetIndex();
        if (Index >= uint32(NativeBodySlots.Num())) return nullptr;
        const int32 SlotIndex = NativeBodySlots[Index];
        if (!Slots.IsValidIndex(SlotIndex)) return nullptr;
        const auto& Slot = Slots[SlotIndex];
        return Slot.Body == Body.GetID() ? &Slot : nullptr;
    }
    bool WantsContactImpulse(const JPH::Body& A, const JPH::Body& B) const override
    {
        const auto Wants = [this](const JPH::Body& Body)
        {
            const auto* Slot = HitSlot(Body);
            if (!Slot) return false;
            if (Slot->bHitEvents) return true;
            const auto* Source = Slot->Weld ? Find(Slot->Weld->SourceHandle) : nullptr;
            return Source && Source->bHitEvents;
        };
        return Wants(A) || Wants(B);
    }
    FProphecyJoltBodyHandle HitHandle(const JPH::Body& Body, const JPH::SubShapeID& Shape) const
    {
        const auto* Slot = HitSlot(Body);
        if (!Slot) return {};
        if (Slot->Weld && Slot->Weld->IsSource(Shape)) return Slot->Weld->SourceHandle;
        FProphecyJoltBodyHandle Handle;
        Handle.WorldLifetime = Lifetime;
        Handle.Slot = NativeBodySlots[Body.GetID().GetIndex()];
        Handle.Generation = Slot->Generation;
        return Handle;
    }
    void OnContactImpulse(const JPH::Body& A, const JPH::Body& B,
        const JPH::SubShapeID& ShapeA, const JPH::SubShapeID& ShapeB,
        JPH::RVec3Arg PointA, JPH::RVec3Arg PointB, JPH::Vec3Arg Normal, float Impulse) override
    {
        using namespace ProphecyJolt::Conversions;
        FProphecyJoltPendingHit Hit;
        Hit.Body1 = HitHandle(A, ShapeA); Hit.Body2 = HitHandle(B, ShapeB);
        const auto* Slot1 = Find(Hit.Body1); const auto* Slot2 = Find(Hit.Body2);
        if (!Slot1 || !Slot2 || (!Slot1->bHitEvents && !Slot2->bHitEvents)) return;
        Hit.Point1 = FromJoltPosition(PointA); Hit.Point2 = FromJoltPosition(PointB);
        Hit.Normal = FromJoltDirection(Normal);
        Hit.Impulse = Hit.Normal * (Impulse * MetersToCentimeters);
        FScopeLock Lock(&HitMutex);
        PendingHits.Add(Hit);
    }
    void SetHitEnabled(ProphecyJolt::WorldPrivate::FBodySlot& Slot, bool bEnabled)
    {
        if (Slot.bHitEvents == bEnabled) return;
        Slot.bHitEvents = bEnabled;
        HitEnabledBodies += bEnabled ? 1 : -1;
        Physics.SetContactImpulseListener(HitEnabledBodies ? this : nullptr);
    }

    // Only the GT owner uses this before synchronous Update or after all its jobs joined.
    // Keep BodyLockRead's full-ID and broadphase checks; select only its mutex policy.
    const JPH::BodyLockInterface& IdleBodyReadLocks() const
    {
        if (bNoLockIdleBodyReads) return Physics.GetBodyLockInterfaceNoLock();
        return Physics.GetBodyLockInterface();
    }

    const ProphecyJolt::WorldPrivate::FBodySlot* Find(const FProphecyJoltBodyHandle& Handle) const
    {
        if (Handle.WorldLifetime != Lifetime || !Slots.IsValidIndex(Handle.Slot)) return nullptr;
        const auto& Slot = Slots[Handle.Slot];
        return !Slot.Body.IsInvalid() && Slot.Generation == Handle.Generation && Handle.Generation != 0 ? &Slot : nullptr;
    }

    const ProphecyJolt::WorldPrivate::FRigRecord* FindRig(const FProphecyJoltRigHandle& Handle) const
    {
        if (Handle.WorldLifetime != Lifetime || !Rigs.IsValidIndex(Handle.Slot) || Handle.Generation == 0) return nullptr;
        const auto& Slot = Rigs[Handle.Slot];
        return Slot.Generation == Handle.Generation && Slot.Record && Slot.Record->bCommitted ? Slot.Record.Get() : nullptr;
    }

    ProphecyJolt::WorldPrivate::FRigRecord* FindRig(const FProphecyJoltRigHandle& Handle)
    {
        return const_cast<ProphecyJolt::WorldPrivate::FRigRecord*>(
            static_cast<const FProphecyJoltWorldState*>(this)->FindRig(Handle));
    }

    bool HasRigs() const
    {
        for (const auto& Slot : Rigs) if (Slot.Record) return true;
        return false;
    }

    int32 AllocateRigSlot()
    {
        for (int32 Index = 0; Index < Rigs.Num(); ++Index)
            if (!Rigs[Index].Record && Rigs[Index].Generation < MAX_uint64) return Index;
        return Rigs.Num() < MAX_int32 ? Rigs.AddDefaulted() : INDEX_NONE;
    }

    const ProphecyJolt::WorldPrivate::FJointRecord* FindJoint(const FProphecyJoltJointHandle& Handle) const
    {
        if (Handle.WorldLifetime != Lifetime || !Joints.IsValidIndex(Handle.Slot) || Handle.Generation == 0) return nullptr;
        const auto& Slot = Joints[Handle.Slot];
        return Slot.Generation == Handle.Generation ? Slot.Record.Get() : nullptr;
    }

    const ProphecyJolt::WorldPrivate::FBodySlot* FindIdentity(const ProphecyJolt::WorldPrivate::FBodyIdentity& Id) const
    {
        return Find({ Lifetime, Id.Slot, Id.Generation });
    }

    FProphecyJoltWorldStatus ValidateJointDrives(const FProphecyJoltJointSettings& In)
    {
        using namespace ProphecyJolt::WorldPrivate;
        if (In.PositionTargetCm.ContainsNaN() || In.VelocityTargetCmPerSecond.ContainsNaN()
            || In.AngularVelocityTargetRadians.ContainsNaN() || !In.OrientationTarget.IsNormalized()
            || In.OrientationTarget.ContainsNaN())
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint drive targets must be finite and orientation normalized."));
        if (!FitsFloatVector(In.PositionTargetCm, .01) || !FitsFloatVector(In.VelocityTargetCmPerSecond, .01)
            || !FitsFloatVector(In.AngularVelocityTargetRadians, 1.0))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint drive targets exceed native numeric range."));
        for (const auto& Drive : In.Drives)
            for (float Value : { Drive.Stiffness, Drive.Damping, Drive.MaximumForce })
                if (!FMath::IsFinite(Value) || Value < 0)
                    return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint drive coefficients must be finite and nonnegative."));
        for (float Value : { In.TranslationStiffness, In.TranslationDamping })
            if (!FMath::IsFinite(Value) || Value < 0)
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint spring coefficients must be finite and nonnegative."));
        return {};
    }

    void ConfigureJointMotors(const FProphecyJoltJointSettings& In, JPH::SixDOFConstraint& Six)
    {
        using namespace ProphecyJolt::Conversions;
        for (int32 I = 0; I < 6; ++I)
        {
            const auto Axis = JPH::SixDOFConstraint::EAxis(I);
            const auto& Input = In.Drives[I];
            auto& Motor = Six.GetMotorSettings(Axis);
            const float Units = I >= 3 && !Input.bAcceleration ? .0001f : 1.f;
            Motor.mSpringSettings = JPH::SpringSettings(Input.bAcceleration
                ? JPH::ESpringMode::MassNormalizedStiffnessAndDamping : JPH::ESpringMode::StiffnessAndDamping,
                Input.bPosition ? Input.Stiffness * Units : 0.f, Input.bVelocity ? Input.Damping * Units : 0.f);
            const float Limit = Input.MaximumForce > 0 ? Input.MaximumForce * (I < 3 ? .01f : .0001f) : FLT_MAX;
            Motor.SetForceLimit(Limit); Motor.SetTorqueLimit(Limit);
            const bool Locked = I < 3 ? In.Translation[I].Motion == EProphecyJoltAxisMotion::Locked
                : In.Rotation[I - 3].Motion == EProphecyJoltAxisMotion::Locked;
            Six.SetMotorState(Axis, !Locked && (Input.bPosition || Input.bVelocity)
                ? JPH::EMotorState::PositionAndVelocity : JPH::EMotorState::Off);
        }
        Six.SetTargetPositionCS(ToJoltLinearVelocity(In.PositionTargetCm));
        Six.SetTargetVelocityCS(ToJoltLinearVelocity(In.VelocityTargetCmPerSecond));
        Six.SetTargetOrientationCS(ToJoltRotation(In.OrientationTarget));
        Six.SetTargetAngularVelocityCS(ToJoltAngularVelocity(In.AngularVelocityTargetRadians));
    }

    FProphecyJoltWorldStatus BuildJoint(const FProphecyJoltJointSettings& In, JPH::Ref<JPH::TwoBodyConstraint>& Out)
    {
        using namespace ProphecyJolt::WorldPrivate;
        using namespace ProphecyJolt::Conversions;
        Out = nullptr;
        const auto DrivesValid = ValidateJointDrives(In);
        if (!DrivesValid.IsSuccess()) return DrivesValid;
        const FBodySlot* A = Find(In.BodyA), *B = Find(In.BodyB);
        if (!A || !B) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Both joint endpoints must be live bodies in this world; missing endpoints never mean fixed-to-world."));
        if (SameBody(In.BodyA, In.BodyB))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint endpoints must be distinct."));
        if (!RigidJointFrame(In.FrameA) || !RigidJointFrame(In.FrameB))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint frames must be finite, normalized, unit-scale body-origin-local transforms."));
        const JPH::BodyID IDs[] = { A->Body, B->Body };
        JPH::RVec3 PositionA, PositionB;
        {
            JPH::BodyLockMultiRead Lock(Physics.GetBodyLockInterface(), IDs, 2);
            const JPH::Body* First = Lock.GetBody(0), *Second = Lock.GetBody(1);
            if (!First || !Second) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Native joint endpoint no longer exists."));
            if (!First->IsDynamic() && !Second->IsDynamic())
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("A stock two-body joint requires at least one dynamic endpoint."));
            // Jolt's COM frame has the body's orientation. Only the local shape COM translation
            // is removed; principal inertia orientation must not be applied to a connector frame.
            PositionA = ToJoltPosition(In.FrameA.GetTranslation()) - JPH::RVec3(First->GetShape()->GetCenterOfMass());
            PositionB = ToJoltPosition(In.FrameB.GetTranslation()) - JPH::RVec3(Second->GetShape()->GetCenterOfMass());
        } // Do not nest CreateConstraint's write locks under the read lock.
        if (!FitsFloatVector(FromJoltPosition(PositionA), 0.01) || !FitsFloatVector(FromJoltPosition(PositionB), 0.01))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("COM-local connector position exceeds finite native local precision."));
        const JPH::Vec3 XA = ToJoltDirection(In.FrameA.GetRotation().GetAxisX());
        const JPH::Vec3 YA = ToJoltDirection(In.FrameA.GetRotation().GetAxisY());
        const JPH::Vec3 XB = ToJoltDirection(In.FrameB.GetRotation().GetAxisX());
        const JPH::Vec3 YB = ToJoltDirection(In.FrameB.GetRotation().GetAxisY());
        if (In.Type == EProphecyJoltJointType::Fixed)
        {
            if (In.bRadialTranslation)
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Radial translation requires SixDOF limits."));
            for (int32 Index = 0; Index < 3; ++Index)
                if (In.Translation[Index].Motion != EProphecyJoltAxisMotion::Locked || In.Rotation[Index].Motion != EProphecyJoltAxisMotion::Locked
                    || In.Translation[Index].Minimum != 0.0 || In.Translation[Index].Maximum != 0.0
                    || In.Rotation[Index].Minimum != 0.0 || In.Rotation[Index].Maximum != 0.0)
                    return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Fixed joints require default locked limit fields; select HardSixDOF for axis settings."));
            JPH::FixedConstraintSettings Fixed;
            Fixed.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
            Fixed.mPoint1 = PositionA; Fixed.mPoint2 = PositionB;
            Fixed.mAxisX1 = XA; Fixed.mAxisY1 = YA; Fixed.mAxisX2 = XB; Fixed.mAxisY2 = YB;
            Out = Physics.GetBodyInterface().CreateConstraint(&Fixed, IDs[0], IDs[1]);
        }
        else if (In.Type == EProphecyJoltJointType::HardSixDOF)
        {
            JPH::SixDOFConstraintSettings Six;
            const FProphecyJoltWorldStatus Limits = FillHardLimits(In, Six);
            if (!Limits.IsSuccess()) return Limits;
            JPH::Vec3 RadialMask = JPH::Vec3::sZero();
            float Radius = 0.f;
            if (In.bRadialTranslation)
            {
                int32 LimitedCount = 0;
                double SharedRadius = 0;
                for (int32 I = 0; I < 3; ++I)
                {
                    const auto& Limit = In.Translation[I];
                    if (Limit.Motion != EProphecyJoltAxisMotion::Limited) continue;
                    if (Limit.Minimum != -Limit.Maximum || (LimitedCount && SharedRadius != Limit.Maximum))
                        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Radial limits require equal symmetric positive intervals."));
                    SharedRadius = Limit.Maximum; ++LimitedCount; RadialMask.SetComponent(I, 1.f);
                    Six.MakeFreeAxis(JPH::SixDOFConstraintSettings::EAxis(I));
                }
                if (LimitedCount < 2)
                    return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Radial translation requires at least two Limited axes."));
                Radius = float(SharedRadius * .01);
            }
            Six.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
            Six.mPosition1 = PositionA; Six.mPosition2 = PositionB;
            Six.mAxisX1 = XA; Six.mAxisY1 = YA; Six.mAxisX2 = XB; Six.mAxisY2 = YB;
            const JPH::SpringSettings Spring(JPH::ESpringMode::StiffnessAndDamping,
                In.bSoftTranslation ? In.TranslationStiffness : 0.f, In.bSoftTranslation ? In.TranslationDamping : 0.f);
            if (In.bSoftTranslation && !In.bRadialTranslation) for (int32 I = 0; I < 3; ++I)
                if (In.Translation[I].Motion == EProphecyJoltAxisMotion::Limited) Six.mLimitsSpringSettings[I] = Spring;
            Out = Physics.GetBodyInterface().CreateConstraint(&Six, IDs[0], IDs[1]);
            if (Out)
            {
                auto& Joint = *static_cast<JPH::SixDOFConstraint*>(Out.GetPtr());
                ConfigureJointMotors(In, Joint);
                if (In.bRadialTranslation) Out = new ProphecyJolt::FRadialJoint(Joint, Six, RadialMask, Radius, Spring);
            }
        }
        else return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Unknown generic joint type."));
        return Out != nullptr ? FProphecyJoltWorldStatus{} : Fail(EProphecyJoltWorldResult::PhysicsFailure, TEXT("Native constraint creation returned null."));
    }

    FProphecyJoltWorldStatus PrepareSuppression(TConstArrayView<FProphecyJoltBodyPair> Pairs,
        TArray<ProphecyJolt::WorldPrivate::FSuppressionKey>& Out) const
    {
        using namespace ProphecyJolt::WorldPrivate;
        Out.Reset();
        TSet<FSuppressionKey> Unique;
        uint32 NewCount = 0;
        for (const FProphecyJoltBodyPair& Pair : Pairs)
        {
            if (!Find(Pair.A) || !Find(Pair.B))
                return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Suppression endpoints must be live bodies in this world."));
            if (SameBody(Pair.A, Pair.B))
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Cannot suppress a body against itself."));
            FSuppressionKey Key{ { Pair.A.Slot, Pair.A.Generation }, { Pair.B.Slot, Pair.B.Generation } };
            if (Key.A.Slot > Key.B.Slot) Swap(Key.A, Key.B);
            if (Unique.Contains(Key)) continue;
            Unique.Add(Key);
            if (const FSuppressionRecord* Existing = Suppression.Find(Key))
            {
                if (Existing->References == MAX_uint32)
                    return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Suppression reference count is exhausted."));
            }
            else ++NewCount;
            Out.Add(Key);
        }
        if (uint64(Suppression.Num()) + NewCount > Settings.MaxSuppressedBodyPairs)
            return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Complete suppression request exceeds pair capacity; no joint or filter was changed."));
        return {};
    }

    void Wake(const FProphecyJoltBodyHandle& Handle)
    {
        if (const auto* Body = Find(Handle))
        {
            if (Body->WeldParent.IsSet()) { Wake(Body->WeldParent); return; }
            JPH::BodyInterface& Bodies = Physics.GetBodyInterface();
            if (Bodies.GetMotionType(Body->Body) == JPH::EMotionType::Dynamic) Bodies.ActivateBody(Body->Body);
        }
    }

    FProphecyJoltWorldStatus ApplyRigSelfCollision(ProphecyJolt::WorldPrivate::FRigRecord& Rig,
        bool bEnabled, TSet<int32> DisabledBodies, TSet<uint64> DisabledPairs)
    {
        using namespace ProphecyJolt::WorldPrivate;
        TArray<JPH::BodyID, TInlineAllocator<64>> BodyIds;
        BodyIds.Reserve(Rig.Handles.Num());
        for (const auto& Handle : Rig.Handles)
        {
            const auto* Body = Find(Handle);
            if (!Body) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("A self-collision rig body is no longer owned."));
            BodyIds.Add(Body->Body);
        }
        struct FChange { int32 A; int32 B; bool bEnabled; };
        TArray<FChange, TInlineAllocator<64>> Changes;
        TArray<JPH::BodyID, TInlineAllocator<64>> ChangedBodies;
        for (int32 A = 0; A < Rig.Handles.Num(); ++A)
            for (int32 B = A + 1; B < Rig.Handles.Num(); ++B)
            {
                const uint64 Key = RigPairKey(A, B);
                const bool bPairEnabled = bEnabled && !AttackSelfCollisionSuppressed.Contains(&Rig)
                    && !DisabledBodies.Contains(A) && !DisabledBodies.Contains(B)
                    && !DisabledPairs.Contains(Key) && !Rig.AuthoredDisabledPairKeys.Contains(Key);
                if (Rig.CollisionFilter->IsCollisionEnabled(A, B) != bPairEnabled)
                {
                    Changes.Add({ A, B, bPairEnabled });
                    ChangedBodies.AddUnique(BodyIds[A]);
                    ChangedBodies.AddUnique(BodyIds[B]);
                }
            }
        // All validation/allocation is complete. This runs only outside Update, so worker reads
        // cannot race the existing shared filter. Keep all native identities and other filters.
        Rig.bSelfCollisionEnabled = bEnabled;
        Rig.SelfCollisionDisabledBodies = MoveTemp(DisabledBodies);
        Rig.SelfCollisionDisabledPairs = MoveTemp(DisabledPairs);
        for (const FChange& Change : Changes)
        {
            if (Change.bEnabled) Rig.CollisionFilter->EnableCollision(Change.A, Change.B);
            else Rig.CollisionFilter->DisableCollision(Change.A, Change.B);
        }
        auto& Bodies = Physics.GetBodyInterface();
        // Invalidate both contact and cached-no-contact pairs for either transition; wake to
        // rediscover sleeping overlaps when re-enabling. An effective no-op does neither.
        for (const auto& BodyId : ChangedBodies) Bodies.InvalidateContactCache(BodyId);
        if (!ChangedBodies.IsEmpty()) Bodies.ActivateBodies(ChangedBodies.GetData(), ChangedBodies.Num());
        return {};
    }

    void PublishSuppression(const TSet<ProphecyJolt::WorldPrivate::FBodyIdentity>& Changed)
    {
        if (Changed.IsEmpty()) return;
        ScopedPairFilter.SortedPairs.Reset(Suppression.Num());
        for (const auto& Pair : Suppression) ScopedPairFilter.SortedPairs.Add(Pair.Value.NativeKey);
        ScopedPairFilter.SortedPairs.Sort();
        Physics.SetSimShapeFilter(Suppression.IsEmpty() && WeldCount==0 ? nullptr : &ScopedPairFilter);
        for (const auto& Identity : Changed)
        {
            if (const auto* Body = FindIdentity(Identity))
            {
                // Both 0->1 and 1->0 transitions must discard existing caches, including cached
                // pairs with no contacts. Activation ensures a sleeping pair is rediscovered.
                const auto* Carrier = Body->WeldParent.IsSet() ? Find(Body->WeldParent) : Body;
                if (Carrier)
                {
                    Physics.GetBodyInterface().InvalidateContactCache(Carrier->Body);
                    // A sword's owner exclusions must also wake the simulated counterpart.
                    Wake({ Lifetime, Identity.Slot, Identity.Generation });
                }
            }
        }
    }

    void AddSuppression(const TArray<ProphecyJolt::WorldPrivate::FSuppressionKey>& Keys)
    {
        using namespace ProphecyJolt::WorldPrivate;
        TSet<FBodyIdentity> Changed;
        for (const auto& Key : Keys)
        {
            FSuppressionRecord& Pair = Suppression.FindOrAdd(Key);
            check(Pair.References < MAX_uint32);
            if (Pair.References++ == 0)
            {
                Pair.NativeKey = NativePairKey(FindIdentity(Key.A)->Body, FindIdentity(Key.B)->Body);
                Slots[Key.A.Slot].SuppressionPairs.Add(Key);
                Slots[Key.B.Slot].SuppressionPairs.Add(Key);
                Changed.Add(Key.A); Changed.Add(Key.B);
            }
        }
        PublishSuppression(Changed);
    }

    void RetireSuppression(const ProphecyJolt::WorldPrivate::FSuppressionKey& Key,
        TSet<ProphecyJolt::WorldPrivate::FBodyIdentity>& Changed)
    {
        if (FindIdentity(Key.A)) Slots[Key.A.Slot].SuppressionPairs.Remove(Key);
        if (FindIdentity(Key.B)) Slots[Key.B.Slot].SuppressionPairs.Remove(Key);
        Suppression.Remove(Key);
        Changed.Add(Key.A); Changed.Add(Key.B);
    }

    void ReleaseSuppression(const TArray<ProphecyJolt::WorldPrivate::FSuppressionKey>& Keys)
    {
        using namespace ProphecyJolt::WorldPrivate;
        TSet<FBodyIdentity> Changed;
        for (const auto& Key : Keys)
        {
            // A third-party body may already have retired this exact generation's pair.
            if (FSuppressionRecord* Pair = Suppression.Find(Key))
            {
                check(Pair->References > 0);
                if (--Pair->References == 0) RetireSuppression(Key, Changed);
            }
        }
        PublishSuppression(Changed);
    }

    void DestroyJointSlot(int32 Index)
    {
        if (!Joints.IsValidIndex(Index) || !Joints[Index].Record) return;
        auto& Record = *Joints[Index].Record;
        Physics.RemoveConstraint(Record.Constraint.GetPtr());
        for (const auto& Endpoint : { Record.Settings.BodyA, Record.Settings.BodyB })
        {
            if (Find(Endpoint)) Slots[Endpoint.Slot].IncidentJoints.RemoveSingleSwap(Index);
            Wake(Endpoint);
        }
        ReleaseSuppression(Record.Suppression);
        Joints[Index].Record.Reset();
        if (Joints[Index].Generation < MAX_uint64) ++Joints[Index].Generation;
        check(JointCount > 0);
        --JointCount;
    }

    FProphecyJoltWorldStatus Add(const JPH::Shape* Shape, const FProphecyJoltFixtureBodySettings& InSettings,
        FProphecyJoltBodyHandle& OutHandle)
    {
        using namespace ProphecyJolt::WorldPrivate;
        using namespace ProphecyJolt::Conversions;
        JPH::BodyCreationSettings BodySettings(Shape, ToJoltPosition(InSettings.PositionCm), ToJoltRotation(InSettings.Rotation),
            InSettings.bDynamic ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static,
            JPH::cObjectLayerInvalid); // Assigned only after the complete profile preflight below.
        BodySettings.mFriction = InSettings.Friction;
        BodySettings.mRestitution = InSettings.Restitution;
        BodySettings.mLinearDamping = InSettings.LinearDamping;
        BodySettings.mAngularDamping = InSettings.AngularDamping;
        BodySettings.mAllowSleeping = InSettings.bAllowSleeping;
        if (InSettings.bDynamic)
        {
            // Validate the actual mass-scaled inertia before entering Jolt's body constructor.
            JPH::MassProperties Mass = Shape->GetMassProperties();
            if (!FMath::IsFinite(Mass.mMass) || Mass.mMass <= 0.0f)
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Shape mass overflow/underflow; dimensions are outside this fixture's numeric range."));
            Mass.ScaleToMass(static_cast<float>(InSettings.MassKg));
            for (JPH::uint Axis = 0; Axis < 3; ++Axis)
                if (!FMath::IsFinite(Mass.mInertia(Axis, Axis)) || Mass.mInertia(Axis, Axis) <= 0.0f
                    || !FMath::IsFinite(1.0f / Mass.mInertia(Axis, Axis)))
                    return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Scaled shape inertia is not positive and finite."));
            BodySettings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            BodySettings.mMassPropertiesOverride = Mass;
        }
        FCollisionProfile Profile;
        if (!MakeCollisionProfile(!InSettings.bDynamic,
            InSettings.ObjectChannel.Get(InSettings.bDynamic ? ECC_PhysicsBody : ECC_WorldStatic), InSettings.CollisionResponses, Profile))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid fixture object channel or collision response."));
        TArray<JPH::ObjectLayer> Layers;
        const FProphecyJoltWorldStatus Interned = CollisionProfiles.Intern(TConstArrayView<FCollisionProfile>(&Profile, 1), Layers);
        if (!Interned.IsSuccess()) return Interned;
        BodySettings.mObjectLayer = Layers[0];
        return AddNative(BodySettings, InSettings.bDynamic ? JPH::EActivation::Activate : JPH::EActivation::DontActivate,
            InSettings.AssociatedObject, {}, OutHandle);
    }

    FProphecyJoltWorldStatus AddNative(const JPH::BodyCreationSettings& BodySettings, JPH::EActivation Activation,
        UObject* Association, const FProphecyJoltRigHandle& OwnerRig, FProphecyJoltBodyHandle& OutHandle)
    {
        using namespace ProphecyJolt::WorldPrivate;
        if (!FMath::IsFinite(BodySettings.mLinearVelocity.LengthSq())
            || !FMath::IsFinite(BodySettings.mAngularVelocity.LengthSq()))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Initial velocity magnitude exceeds finite native clamping arithmetic."));
        if (Physics.GetNumBodies() >= Settings.MaxBodies)
        {
            ++CreationFailures;
            return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Configured body capacity reached; no body was created."));
        }
        int32 SlotIndex = INDEX_NONE;
        for (int32 Index = 0; Index < Slots.Num(); ++Index)
        {
            // A generation that could wrap is permanently retired, even in a long-lived session.
            if (Slots[Index].Body.IsInvalid() && Slots[Index].Generation < MAX_uint64) { SlotIndex = Index; break; }
        }
        if (SlotIndex == INDEX_NONE)
        {
            if (Slots.Num() == MAX_int32)
                return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Adapter handle slots exhausted."));
            SlotIndex = Slots.AddDefaulted();
        }
        // Chaos can hand over a current speed above its configured cap. Jolt's creation
        // setters assert in that case; use its normal clamped setters before broadphase
        // insertion, retaining the captured limits and requested awake/asleep state.
        JPH::BodyCreationSettings InitialSettings = BodySettings;
        InitialSettings.mLinearVelocity = JPH::Vec3::sZero();
        InitialSettings.mAngularVelocity = JPH::Vec3::sZero();
        JPH::Body* CreatedBody = Physics.GetBodyInterface().CreateBody(InitialSettings);
        if (!CreatedBody)
        {
            ++CreationFailures;
            return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Jolt returned an invalid body ID; body creation failed."));
        }
        if (!CreatedBody->IsStatic())
        {
            CreatedBody->SetLinearVelocityClamped(BodySettings.mLinearVelocity);
            CreatedBody->SetAngularVelocityClamped(BodySettings.mAngularVelocity);
        }
        const JPH::BodyID Body = CreatedBody->GetID();
        Physics.GetBodyInterface().AddBody(Body, Activation);
        auto& Slot = Slots[SlotIndex];
        Slot.Body = Body;
        const int32 OldNum = NativeBodySlots.Num();
        if (Body.GetIndex() >= uint32(OldNum))
        {
            NativeBodySlots.SetNum(int32(Body.GetIndex()) + 1);
            for (int32 I = OldNum; I < NativeBodySlots.Num(); ++I) NativeBodySlots[I] = INDEX_NONE;
        }
        NativeBodySlots[Body.GetIndex()] = SlotIndex;
        Slot.AssociatedObject = Association;
        Slot.OwnerRig = OwnerRig;
        OutHandle.WorldLifetime = Lifetime;
        OutHandle.Slot = SlotIndex;
        OutHandle.Generation = Slot.Generation;
        return {};
    }

    void UnweldSource(int32 SourceIndex, bool bReactivate)
    {
        using namespace ProphecyJolt::Conversions;
        auto& SourceSlot=Slots[SourceIndex];
        const auto ParentHandle=SourceSlot.WeldParent;
        if (!Find(ParentHandle)) { SourceSlot.WeldParent={}; return; }
        auto& ParentSlot=Slots[ParentHandle.Slot];
        if (!ParentSlot.Weld) { SourceSlot.WeldParent={}; return; }
        auto Record=MoveTemp(ParentSlot.Weld);
        auto& Bodies=Physics.GetBodyInterface();
        const FTransform ParentPose(FromJoltRotation(Bodies.GetRotation(ParentSlot.Body)),FromJoltPosition(Bodies.GetPosition(ParentSlot.Body)));
        const FTransform SourcePose=Record->SourceToParent * ParentPose;
        const auto V=Bodies.GetPointVelocity(ParentSlot.Body,ToJoltPosition(SourcePose.GetLocation()));
        const auto W=Bodies.GetAngularVelocity(ParentSlot.Body);
        Bodies.SetUserData(ParentSlot.Body,Bodies.GetUserData(ParentSlot.Body)&15);
        Bodies.SetShape(ParentSlot.Body,Record->OriginalShape.GetPtr(),false,JPH::EActivation::Activate);
        if (Record->InertiaScale != 0.0f)
        {
            JPH::BodyLockWrite Lock(Physics.GetBodyLockInterface(),ParentSlot.Body);
            auto* Motion=Lock.GetBody().GetMotionProperties();
            Motion->SetMassProperties(Motion->GetAllowedDOFs(),Record->OriginalMass);
        }
        Bodies.SetCollisionGroup(ParentSlot.Body,Record->OriginalGroup);
        Bodies.SetObjectLayer(ParentSlot.Body,Record->OriginalLayer);
        const auto* Rig = FindRig(ParentSlot.OwnerRig);
        const auto Quality = Rig && Rig->CCDMode != 0
            ? (Rig->CCDMode == 2 ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete)
            : Record->OriginalQuality;
        Bodies.SetMotionQuality(ParentSlot.Body,Quality);
        Bodies.InvalidateContactCache(ParentSlot.Body);
        SourceSlot.WeldParent={};
        --WeldCount;
        Physics.SetSimShapeFilter(Suppression.IsEmpty() && WeldCount==0 ? nullptr : &ScopedPairFilter);
        if (bReactivate)
        {
            Bodies.SetPositionAndRotation(SourceSlot.Body,ToJoltPosition(SourcePose.GetLocation()),ToJoltRotation(SourcePose.GetRotation()),JPH::EActivation::DontActivate);
            const auto COM=Bodies.GetCenterOfMassPosition(SourceSlot.Body);
            // Native velocities are COM velocities, including the source COM offset.
            const auto SourceV=V+W.Cross(JPH::Vec3(COM-ToJoltPosition(SourcePose.GetLocation())));
            Bodies.SetLinearAndAngularVelocity(SourceSlot.Body,SourceV,W);
            Bodies.AddBody(SourceSlot.Body,JPH::EActivation::Activate);
        }
    }

    void DestroySlot(int32 Index)
    {
        auto& Slot = Slots[Index];
        if (Slot.Body.IsInvalid()) return;
        if (auto* Followers = ProphecyJolt::DriveFollowers::Bindings.Find(this))
        {
            for (auto It = Followers->CreateIterator(); It; ++It)
                if (It.Value().Body == Slot.Body || It.Value().Parent == Slot.Body)
                {
                    Servo.RemoveBodyTargetOffset(It.Value().Body);
                    It.RemoveCurrent();
                }
            if (Followers->IsEmpty()) ProphecyJolt::DriveFollowers::Bindings.Remove(this);
        }
        if (Slot.Weld) UnweldSource(Slot.Weld->SourceHandle.Slot,true);
        while (!Slot.IncidentJoints.IsEmpty()) DestroyJointSlot(Slot.IncidentJoints.Last());
        ReleaseSuppression(Slot.OwnedSuppression);
        Slot.OwnedSuppression.Reset();
        TSet<ProphecyJolt::WorldPrivate::FBodyIdentity> Changed;
        const auto RetiredPairs = Slot.SuppressionPairs.Array();
        for (const auto& Key : RetiredPairs) RetireSuppression(Key, Changed);
        PublishSuppression(Changed);
        // Keep the carrier relationship until pair retirement finishes: changing
        // a sword exclusion wakes its hand, never the dormant metadata body.
        if (Slot.WeldParent.IsSet()) UnweldSource(Index,false);
        JPH::BodyInterface& Bodies = Physics.GetBodyInterface();
        if (Bodies.IsAdded(Slot.Body)) Bodies.RemoveBody(Slot.Body);
        Servo.RemoveBodyFollow(Slot.Body);
        SetHitEnabled(Slot, false);
        NativeBodySlots[Slot.Body.GetIndex()] = INDEX_NONE;
        Slot.HitBone = NAME_None; Slot.HitBodyIndex = INDEX_NONE;
        Bodies.DestroyBody(Slot.Body);
        Slot.Body = JPH::BodyID();
        Slot.AssociatedObject.Reset();
        Slot.OwnerRig = {};
        if (Slot.Generation < MAX_uint64) ++Slot.Generation;
    }

    void DestroyRigSlot(int32 Index)
    {
        if (!Rigs.IsValidIndex(Index) || !Rigs[Index].Record) return;
        // Drop every flattened native ID before deletion; surviving per-rig packets/history remain intact.
        // The next Step rebuilds the flat listener packet from those surviving records.
        Servo.Clear();
        FlatTargets.Reset();
        ServoRanges.Reset();
        auto& Rig = *Rigs[Index].Record;
        ProphecyJolt::WorldPrivate::AttackSelfCollisionSuppressed.Remove(&Rig);
        RemoveFootExtensions(Physics,&Rig);
        Rig.Targets.Reset();
        Rig.PublishedHandles.Reset();
        for (const auto& Constraint : Rig.Constraints) Physics.RemoveConstraint(Constraint.GetPtr());
        Rig.Constraints.Reset();
        for (const auto& Handle : Rig.Handles)
            if (Find(Handle)) DestroySlot(Handle.Slot);
        Rigs[Index].Record.Reset();
        if (Rigs[Index].Generation < MAX_uint64) ++Rigs[Index].Generation;
        if (LegacyRig.Slot == Index) LegacyRig = {};
    }

    bool PrepareServoPacket(FString& Error)
    {
        FlatTargets.Reset();
        ServoRanges.Reset();
        for (int32 Index = 0; Index < Rigs.Num(); ++Index)
        {
            const auto& Slot = Rigs[Index];
            if (!Slot.Record || !Slot.Record->bCommitted || Slot.Record->Targets.IsEmpty()) continue;
            auto& Range = ServoRanges.AddDefaulted_GetRef();
            Range.Rig = { Lifetime, Index, Slot.Generation };
            Range.Begin = FlatTargets.Num();
            Range.Count = Slot.Record->Targets.Num();
            FlatTargets.Append(Slot.Record->Targets);

        }
        // PublishRigVelocityTargets already validated these owned values transactionally.
        if (const auto* Followers = ProphecyJolt::DriveFollowers::Bindings.IsEmpty() ? nullptr
            : ProphecyJolt::DriveFollowers::Bindings.Find(this))
        {
            for (const auto& Pair : *Followers)
            {
                const auto& F = Pair.Value;
                const auto* ParentRig = FindRig(F.ParentRig);
                if (!ParentRig || Physics.GetBodyInterface().GetMotionType(F.Body) != JPH::EMotionType::Dynamic) continue;
                const auto* ParentTarget = ParentRig->Targets.FindByPredicate([&](const auto& T) { return T.Body == F.Parent; });
                // Absence means hand magnetisation is disabled. Never retain a stale sword drive.
                if (!ParentTarget || (ParentTarget->LinearStrength == 0.f && ParentTarget->AngularStrength == 0.f)) continue;
                auto Target = *ParentTarget;
                Target.Body = F.Body;
                FlatTargets.Add(Target);
            }
        }
        // Rig body sets are disjoint, and whole-rig removal clears this packet before deleting IDs.
        Error.Reset();
        Servo.CommitValidatedTargets(FlatTargets);
        return true;
    }

    void CaptureServoSamples(uint64 PreviousInvocations)
    {
        const auto& Samples = Servo.GetLastSamples();
        check(Samples.Num() == FlatTargets.Num());
        const uint64 InvocationDelta = Servo.GetInvocationCount() - PreviousInvocations;
        for (const auto& Range : ServoRanges)
        {
            auto* Rig = FindRig(Range.Rig);
            check(Rig && Rig->PublishedHandles.Num() == Range.Count);
            auto& State = Rig->ServoState;
            State.InvocationCount += InvocationDelta;
            State.LastIntegrationSeconds = Servo.GetLastIntegrationSeconds();
            State.Samples.SetNum(Range.Count);
            for (int32 Index = 0; Index < Range.Count; ++Index)
            {
                // Rebuilding the flat packet next Update must continue this rig's
                // accepted trajectory, not replay its first substep.
                Rig->Targets[Index].TrajectoryElapsedSeconds = Servo.Targets[Range.Begin + Index].TrajectoryElapsedSeconds;
                const auto& Source = Samples[Range.Begin + Index];
                auto& Destination = State.Samples[Index];
                Destination.Handle = Rig->PublishedHandles[Index];
                Destination.bValid = Source.bValid;
                Destination.PositionCm = Source.PositionCm;
                Destination.Rotation = Source.Rotation;
                Destination.LinearBeforeCmPerSecond = Source.LinearBeforeCmPerSecond;
                Destination.AngularBeforeRadiansPerSecond = Source.AngularBeforeRadiansPerSecond;
                Destination.LinearAfterCmPerSecond = Source.LinearAfterCmPerSecond;
                Destination.AngularAfterRadiansPerSecond = Source.AngularAfterRadiansPerSecond;
                if (!Source.bValid) ++State.InvalidBodyCount;
            }
        }
    }

    FProphecyJoltWorldSettings Settings;
    FGuid Lifetime;
    // Declaration order makes filters and temporary memory outlive PhysicsSystem.
    ProphecyJolt::WorldPrivate::FCollisionProfiles CollisionProfiles;
    ProphecyJolt::WorldPrivate::FBroadPhaseLayers BroadPhaseLayers;
    ProphecyJolt::WorldPrivate::FObjectPairs ObjectPairs;
    ProphecyJolt::WorldPrivate::FObjectVsBroadPhase ObjectVsBroadPhase;
    ProphecyJolt::WorldPrivate::FScopedPairFilter ScopedPairFilter;
    uint32 WeldCount = 0;
    ProphecyJolt::WorldPrivate::FMeasuredTempAllocator Temp;
    // Registered listener must outlive PhysicsSystem, and is removed explicitly before teardown.
    ProphecyJolt::FVelocityServo Servo;
    JPH::PhysicsSystem Physics;
    bool bNoLockIdleBodyReads = false;
    TUniquePtr<JPH::JobSystemThreadPool> Jobs;
    TArray<ProphecyJolt::WorldPrivate::FBodySlot> Slots;
    TArray<ProphecyJolt::WorldPrivate::FRigSlot> Rigs;
    TArray<ProphecyJolt::WorldPrivate::FJointSlot> Joints;
    TMap<ProphecyJolt::WorldPrivate::FSuppressionKey, ProphecyJolt::WorldPrivate::FSuppressionRecord> Suppression;
    uint32 JointCount = 0;
    FProphecyJoltRigHandle LegacyRig;
    float LegacyDenominatorSeconds = 1.0f / 60.0f;
    TArray<ProphecyJolt::FVelocityServo::FTarget> FlatTargets;
    TArray<ProphecyJolt::WorldPrivate::FServoRange> ServoRanges;
    uint64 CreationFailures = 0;
    // Distinct from capture IDs and recyclable adapter slots. Invalid sentinel is never allocated.
    uint64 NextRigCollisionGroup = 0;
};

void FProphecyJoltWorldStateDeleter::operator()(FProphecyJoltWorldState* State) const { delete State; }

bool UProphecyJoltAttackCollisionLibrary::SetSuppressed(UObject* WorldContext, FGuid Lifetime,
    int32 RigSlot, int64 RigGeneration, bool bSuppressed, FString& OutError)
{
    using namespace ProphecyJolt::WorldPrivate;
    OutError.Reset();
    UWorld* World = IsValid(WorldContext) ? WorldContext->GetWorld() : nullptr;
    auto* Owner = World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner) { OutError = TEXT("Attack collision requires a Jolt world."); return false; }
    const auto Ready = Owner->ValidateReady();
    if (!Ready.IsSuccess()) { OutError = Ready.Message; return false; }
    auto* Native = Owner->Native.Get();
    auto* Rig = Native->FindRig(FProphecyJoltRigHandle{Lifetime, RigSlot, uint64(RigGeneration)});
    if (!Rig) { OutError = TEXT("Attack collision requires a live skeletal rig."); return false; }
    if (AttackSelfCollisionSuppressed.Contains(Rig) == bSuppressed) return true;
    if (bSuppressed) AttackSelfCollisionSuppressed.Add(Rig);
    else AttackSelfCollisionSuppressed.Remove(Rig);
    const auto Result = Native->ApplyRigSelfCollision(*Rig, Rig->bSelfCollisionEnabled,
        Rig->SelfCollisionDisabledBodies, Rig->SelfCollisionDisabledPairs);
    if (!Result.IsSuccess())
    {
        if (bSuppressed) AttackSelfCollisionSuppressed.Remove(Rig);
        else AttackSelfCollisionSuppressed.Add(Rig);
    }
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltFootJointLibrary::SetFootExtension(UObject* WorldContext,FGuid Lifetime,
    int32 BodySlot,int64 BodyGeneration,float LeewayCm,FVector LeftCalfAxis,FVector RightCalfAxis,FString& OutError)
{
    return SetFootRange(WorldContext,Lifetime,BodySlot,BodyGeneration,0,LeewayCm,LeftCalfAxis,RightCalfAxis,OutError);
}

bool UProphecyJoltFootJointLibrary::SetFootRange(UObject* WorldContext,FGuid Lifetime,
    int32 BodySlot,int64 BodyGeneration,float CompressionCm,float ExtensionCm,FVector LeftCalfAxis,FVector RightCalfAxis,FString& OutError)
{
    using namespace ProphecyJolt::WorldPrivate;
    using Axis=JPH::SixDOFConstraintSettings::EAxis;
    OutError.Reset();
    UWorld* World=IsValid(WorldContext) ? WorldContext->GetWorld() : nullptr;
    auto* Owner=World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || !Owner->ValidateReady().IsSuccess() || !FMath::IsFinite(ExtensionCm) || ExtensionCm<0
        || !FMath::IsFinite(CompressionCm) || CompressionCm<0)
    { OutError=TEXT("A ready Jolt world and finite nonnegative foot leeway are required."); return false; }
    auto* Native=Owner->Native.Get();
    const auto* Body=Native->Find(FProphecyJoltBodyHandle{Lifetime,BodySlot,uint64(BodyGeneration)});
    auto* Rig=Body ? Native->FindRig(Body->OwnerRig) : nullptr;
    if (!Rig) { OutError=TEXT("Foot leeway requires a live skeletal rig."); return false; }
    const auto Wake=[&]()
    {
        for (const auto& Handle:Rig->Handles) Native->Wake(Handle);
    };
    const JPH::Vec3 Minimum(-CompressionCm*.01f,0,0),Maximum(ExtensionCm*.01f,0,0);
    if (ExtensionCm==0 && CompressionCm==0)
    {
        const bool Changed=FootExtensions.Contains(Rig);
        RemoveFootExtensions(Native->Physics,Rig);
        if (Changed) { Wake(); Owner->RefreshDiagnostics(); }
        return true;
    }
    if (auto* Entries=FootExtensions.Find(Rig))
    {
        bool Changed=false;
        for (auto& Entry:*Entries)
            if (Entry.Translation->GetTranslationLimitsMin()!=Minimum || Entry.Translation->GetTranslationLimitsMax()!=Maximum)
            { Entry.Translation->SetTranslationLimits(Minimum,Maximum);Changed=true; }
        if (Changed) Wake(); return true;
    }
    TArray<ProphecyJolt::FootExtension::FJoint> Pending;
    const FName Feet[]={TEXT("foot_l"),TEXT("foot_r")},Calves[]={TEXT("calf_l"),TEXT("calf_r")};
    const FVector Directions[]={LeftCalfAxis,RightCalfAxis};
    for (int32 Side=0;Side<2;++Side)
    {
        const int32 Index=Rig->JointDescriptions.IndexOfByPredicate([&](const FProphecyJoltRigJoint& J)
            { return J.Bone1==Feet[Side] && J.Bone2==Calves[Side]; });
        if (Index==INDEX_NONE || Directions[Side].ContainsNaN() || Directions[Side].IsNearlyZero())
        { OutError=TEXT("Expected a foot-to-calf joint and a valid parent-local calf length axis on each side."); return false; }
        auto* Original=ProphecyJolt::GetSixDOF(Rig->Constraints[Index].GetPtr());
        if (!Original || !Original->IsFixedAxis(Axis::TranslationX) || !Original->IsFixedAxis(Axis::TranslationY)
            || !Original->IsFixedAxis(Axis::TranslationZ))
        { OutError=TEXT("Foot extension expects authored locked ankle translations."); return false; }
        auto Settings=ProphecyJolt::FootExtension::Settings(*Original,
            ProphecyJolt::Conversions::ToJoltDirection(Directions[Side].GetSafeNormal()),ExtensionCm*.01f);
        Settings.SetLimitedAxis(Axis::TranslationX,-CompressionCm*.01f,ExtensionCm*.01f);
        JPH::Ref<JPH::TwoBodyConstraint> Extra=Native->Physics.GetBodyInterface().CreateConstraint(&Settings,
            Original->GetBody1()->GetID(),Original->GetBody2()->GetID());
        if (!Extra) { OutError=TEXT("Could not create the calf-axis translation constraint."); return false; }
        ProphecyJolt::FootExtension::FJoint Entry;
        Entry.Original=Original;
        Entry.Translation=static_cast<JPH::SixDOFConstraint*>(Extra.GetPtr());
        Entry.Minimum=Original->GetTranslationLimitsMin(); Entry.Maximum=Original->GetTranslationLimitsMax();
        Pending.Add(MoveTemp(Entry));
    }
    // Both ankles validated/allocated before changing any live constraint.
    for (auto& Entry:Pending)
    {
        Entry.Original->SetTranslationLimits(JPH::Vec3::sReplicate(-FLT_MAX),JPH::Vec3::sReplicate(FLT_MAX));
        Native->Physics.AddConstraint(Entry.Translation.GetPtr());
    }
    FootExtensions.Add(Rig,MoveTemp(Pending)); Wake(); Owner->RefreshDiagnostics(); return true;
}

bool UProphecyJoltBodyDriveLibrary::SetDriveFollower(UObject* WorldContext, FGuid Lifetime,
    int32 BodySlot, int64 BodyGeneration, int32 ParentSlot, int64 ParentGeneration,
    FTransform BodyToParent, bool Enabled)
{
    if (!IsInGameThread() || !IsValid(WorldContext)) return false;
    UWorld* World = WorldContext->GetWorld();
    auto* Owner = World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || !Owner->Native) return false;
    auto* Native = Owner->Native.Get();
    const FProphecyJoltBodyHandle BodyHandle{Lifetime, BodySlot, uint64(BodyGeneration)};
    const auto* Body = Native->Find(BodyHandle);
    if (!Body) return !Enabled;
    using namespace ProphecyJolt::DriveFollowers;
    if (!Enabled)
    {
        Native->Servo.RemoveBodyTargetOffset(Body->Body);
        if (auto* Entries = Bindings.Find(Native))
        {
            Entries->Remove(Body->Body.GetIndexAndSequenceNumber());
            if (Entries->IsEmpty()) Bindings.Remove(Native);
        }
        // Removing a drive must also retire the already-flattened packet before body cleanup.
        Native->Servo.Clear(); Native->FlatTargets.Reset(); Native->ServoRanges.Reset();
        return true;
    }
    if (!Owner->ValidateReady().IsSuccess() || BodyToParent.ContainsNaN()
        || !BodyToParent.GetRotation().IsNormalized() || !BodyToParent.GetScale3D().Equals(FVector::OneVector)
        || Body->OwnerRig.IsSet()) return false;
    const auto* Parent = Native->Find(FProphecyJoltBodyHandle{Lifetime, ParentSlot, uint64(ParentGeneration)});
    if (!Parent || !Parent->OwnerRig.IsSet() || Parent->Body == Body->Body
        || Native->Physics.GetBodyInterface().GetMotionType(Body->Body) != JPH::EMotionType::Dynamic) return false;
    Bindings.FindOrAdd(Native).Add(Body->Body.GetIndexAndSequenceNumber(), {Body->Body, Parent->Body, Parent->OwnerRig});
    Native->Servo.SetBodyTargetOffset(Body->Body, BodyToParent);
    return true;
}

UProphecyJoltWorldSubsystem::UProphecyJoltWorldSubsystem() = default;
UProphecyJoltWorldSubsystem::~UProphecyJoltWorldSubsystem() = default;

namespace ProphecyJolt::ContactSettings
{
// Only configured worlds allocate an entry. Read on initialization/set/get, never during Step.
static TMap<TWeakObjectPtr<const UProphecyJoltWorldSubsystem>, float> SlopOverridesCm;
static float SlopCm(const UProphecyJoltWorldSubsystem* Owner)
{
    const float* Value = SlopOverridesCm.Find(Owner);
    return Value ? *Value : 2.0f;
}
}

bool UProphecyJoltWorldSubsystem::SetJoltPenetrationSlop(const UObject* Context, float SlopCm)
{
    if (!IsInGameThread() || !FMath::IsFinite(SlopCm) || SlopCm < 0.0f) return false;
    auto* World = GEngine ? GEngine->GetWorldFromContextObject(Context, EGetWorldErrorMode::ReturnNull) : nullptr;
    auto* Owner = World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || !Owner->bSubsystemInitialized || Owner->bWorldEnding || World->bIsTearingDown
        || Owner->bStepInProgress || Owner->Diagnostics.bFaulted) return false;
    if (SlopCm == 2.0f) ProphecyJolt::ContactSettings::SlopOverridesCm.Remove(Owner);
    else ProphecyJolt::ContactSettings::SlopOverridesCm.Add(Owner, SlopCm);
    if (Owner->Native)
    {
        auto Settings = Owner->Native->Physics.GetPhysicsSettings();
        Settings.mPenetrationSlop = SlopCm * 0.01f;
        Owner->Native->Physics.SetPhysicsSettings(Settings);
    }
    return true;
}

float UProphecyJoltWorldSubsystem::GetJoltPenetrationSlop(const UObject* Context)
{
    if (!IsInGameThread()) return 2.0f;
    auto* World = GEngine ? GEngine->GetWorldFromContextObject(Context, EGetWorldErrorMode::ReturnNull) : nullptr;
    auto* Owner = World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || Owner->bStepInProgress || Owner->bWorldEnding) return 2.0f;
    return Owner->Native ? Owner->Native->Physics.GetPhysicsSettings().mPenetrationSlop * 100.0f
        : ProphecyJolt::ContactSettings::SlopCm(Owner);
}

#if !UE_BUILD_SHIPPING
void UProphecyJoltWorldSubsystem::RunContactExperiment(const TArray<FString>& Input)
{
    using namespace ProphecyJolt::WorldPrivate;
    if (Input.Num() < 5 || !ValidateReady().IsSuccess()) return;
    const int32 N = Input.Num();
    if (Input[N-4] != TEXT("at")) return;
    const FVector SelectedHand(FCString::Atod(*Input[N-3]), FCString::Atod(*Input[N-2]), FCString::Atod(*Input[N-1]));
    TArray<FString> Args(Input.GetData(), N-4);
    auto& BI = Native->Physics.GetBodyInterface();
    for (auto& RS : Native->Rigs)
    {
        if (!RS.Record || RS.Record->Handles.IsEmpty()) continue;
        auto& R = *RS.Record;
        TMap<FName, JPH::Body*> Bodies;
        for (int32 I = 0; I < R.Constraints.Num(); ++I)
        {
            const auto* C = R.Constraints[I].GetPtr();
            // Native conversion reverses UE's child/parent endpoint order.
            Bodies.Add(R.JointDescriptions[I].Bone1, C->GetBody2());
            Bodies.Add(R.JointDescriptions[I].Bone2, C->GetBody1());
        }
        const auto* Hand = Bodies.Find(TEXT("hand_r"));
        if (!Hand || !ProphecyJolt::Conversions::FromJoltPosition((*Hand)->GetPosition()).Equals(SelectedHand, 0.001)) continue;
        if (Args[0] == TEXT("iterations") && Args.Num() == 3)
        {
            const int32 V = FCString::Atoi(*Args[1]), P = FCString::Atoi(*Args[2]);
            if (V < 0 || V > 128 || P < 0 || P > 128) return;
            for (auto& C : R.Constraints) { C->SetNumVelocityStepsOverride(V); C->SetNumPositionStepsOverride(P); }
        }
        else if (Args[0] == TEXT("ccd") && Args.Num() == 3)
        {
            for (auto& Pair : Bodies)
                if (Args[1] == TEXT("all") || Pair.Key == FName(*Args[1]))
                    BI.SetMotionQuality(Pair.Value->GetID(), FCString::Atoi(*Args[2]) ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete);
        }
        else if (Args[0] == TEXT("slop") && Args.Num() == 2)
        {
            auto Settings = Native->Physics.GetPhysicsSettings();
            Settings.mPenetrationSlop = FMath::Clamp(FCString::Atof(*Args[1]) * 0.01f, 0.00001f, 0.02f);
            Native->Physics.SetPhysicsSettings(Settings);
        }
        else if (Args[0] == TEXT("capture") && Args.Num() == 2)
        {
            if (Args[1].EndsWith(TEXT("_60")))
                for (const auto& Slot : Native->Slots)
                    if (!Slot.Body.IsInvalid())
                        UE_LOG(LogProphecyJoltWorld, Display, TEXT("CONTACT_SLOT,%s,%u,weld=%d,parent=%d,source=%s,hand=%u"),
                            *Args[1],Slot.Body.GetIndexAndSequenceNumber(),Slot.Weld.IsValid(),Slot.WeldParent.Slot,
                            *GetNameSafe(Slot.AssociatedObject.Get()),(*Hand)->GetID().GetIndexAndSequenceNumber());
            for (int32 I = 0; I < R.Constraints.Num(); ++I)
            {
                auto* C = R.Constraints[I].GetPtr();
                const auto& Name = R.JointDescriptions[I].Bone1;
                if (Name != TEXT("hand_r") && Name != TEXT("lowerarm_r") && Name != TEXT("upperarm_r")
                    && Name != TEXT("hand_l") && Name != TEXT("lowerarm_l") && Name != TEXT("upperarm_l")) continue;
                const auto A = C->GetBody1()->GetCenterOfMassTransform() * C->GetConstraintToBody1Matrix().GetTranslation();
                const auto B = C->GetBody2()->GetCenterOfMassTransform() * C->GetConstraintToBody2Matrix().GetTranslation();
                const auto* Six = ProphecyJolt::GetSixDOF(C);
                UE_LOG(LogProphecyJoltWorld, Display, TEXT("CONTACT_EXP,%s,joint,%s,%.6f,%.6f,%u,%u"), *Args[1], *Name.ToString(),
                    (A-B).Length()*100.0, Six->GetTotalLambdaPosition().Length(), C->GetNumVelocityStepsOverride(), C->GetNumPositionStepsOverride());
            }
            for (const auto& Pair : Bodies)
            {
                if (Pair.Key != TEXT("hand_r") && Pair.Key != TEXT("lowerarm_r") && Pair.Key != TEXT("upperarm_r")) continue;
                const auto* M = Pair.Value->GetMotionPropertiesUnchecked();
                const auto D = M->GetInverseInertiaDiagonal();
                UE_LOG(LogProphecyJoltWorld, Display, TEXT("CONTACT_EXP,%s,body,%s,%.6f,%.6f,%.6f,%.6f,%d"), *Args[1], *Pair.Key.ToString(),
                    1.0f/M->GetInverseMassUnchecked(), 1.0f/D.GetX(), 1.0f/D.GetY(), 1.0f/D.GetZ(), int(M->GetMotionQuality()));
                for (const FName Thigh : {FName(TEXT("thigh_r")), FName(TEXT("thigh_l"))})
                {
                    JPH::Body* const* Other = Bodies.Find(Thigh);
                    if (!Other) continue;
                    JPH::AllHitCollisionCollector<JPH::CollideShapeCollector> Hits;
                    const auto Base = Pair.Value->GetCenterOfMassPosition();
                    JPH::CollisionDispatch::sCollideShapeVsShape(Pair.Value->GetShape(), (*Other)->GetShape(), JPH::Vec3::sReplicate(1), JPH::Vec3::sReplicate(1),
                        Pair.Value->GetCenterOfMassTransform().PostTranslated(-Base).ToMat44(), (*Other)->GetCenterOfMassTransform().PostTranslated(-Base).ToMat44(),
                        {}, {}, {}, Hits);
                    const auto* Weld = static_cast<const FWeldRecord*>(ProphecyJolt::Material::AttachedData(*Pair.Value));
                    float BodyDepth = 0, SwordDepth = 0;
                    for (const auto& Hit : Hits.mHits)
                    {
                        float& Depth = Weld && Weld->IsSource(Hit.mSubShapeID1) ? SwordDepth : BodyDepth;
                        Depth = FMath::Max(Depth, Hit.mPenetrationDepth*100.0f);
                    }
                    UE_LOG(LogProphecyJoltWorld, Display, TEXT("CONTACT_EXP,%s,contact,%s_%s,%.6f,%.6f"), *Args[1], *Pair.Key.ToString(), *Thigh.ToString(), BodyDepth, SwordDepth);
                }
            }
        }
    }
}
static FAutoConsoleCommandWithWorldAndArgs ContactExperimentCommand(TEXT("Prophecy.Jolt.ContactExperiment"),
    TEXT("Explicit transient rig diagnostics. capture <tag>, iterations <v> <p>, ccd <bone|all> <0|1>, slop <cm>. Suffix: at <hand X Y Z cm>."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
    { if (World) if (auto* S = World->GetSubsystem<UProphecyJoltWorldSubsystem>()) S->RunContactExperiment(Args); }));
#endif

bool UProphecyJoltWorldSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UProphecyJoltWorldSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    bSubsystemInitialized = true;
    bWorldEnding = false;
    Super::Initialize(Collection);
}

void UProphecyJoltWorldSubsystem::StopForWorldTeardown()
{
    check(IsInGameThread());
    bWorldEnding = true;
    ProphecyJolt::PHATSweeps::ForgetWorld(GetWorld());
    ProphecyJolt::ContactSettings::SlopOverridesCm.Remove(this);
    const FProphecyJoltWorldStatus Status = ShutdownSimulation();
    checkf(Status.IsSuccess(), TEXT("Jolt world teardown failed: %s"), *Status.Message);
}

void UProphecyJoltWorldSubsystem::OnWorldEndPlay(UWorld& InWorld)
{
    StopForWorldTeardown();
    Super::OnWorldEndPlay(InWorld);
}

void UProphecyJoltWorldSubsystem::PreDeinitialize()
{
    StopForWorldTeardown();
    Super::PreDeinitialize();
}

void UProphecyJoltWorldSubsystem::Deinitialize()
{
    StopForWorldTeardown();
    bSubsystemInitialized = false;
    Super::Deinitialize();
}

void UProphecyJoltWorldSubsystem::BeginDestroy()
{
    // Covers abnormal disposal too; normal world cleanup already deinitialized and released Native.
    StopForWorldTeardown();
    bSubsystemInitialized = false;
    Super::BeginDestroy();
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::InitializeSimulation(const FProphecyJoltWorldSettings& Settings)
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("World initialization requires the game thread."));
    UWorld* World = GetWorld();
    if (!World || !DoesSupportWorldType(World->WorldType))
        return Fail(EProphecyJoltWorldResult::UnsupportedWorld, TEXT("Only Game and PIE worlds are eligible."));
    if (!bSubsystemInitialized || bWorldEnding || World->bIsTearingDown)
        return Fail(EProphecyJoltWorldResult::WorldEnding, TEXT("Subsystem is not initialized or world teardown has begun."));
    if (Native) return Fail(EProphecyJoltWorldResult::AlreadyInitialized, TEXT("Shut down explicitly before changing simulation settings."));
    if (!Finite(Settings.GravityCmPerSecondSquared) || !FitsFloatVector(Settings.GravityCmPerSecondSquared, 0.01)
        || Settings.MaxBodies == 0 || Settings.MaxBodies > JPH::PhysicsSystem::cMaxBodiesLimit
        || Settings.MaxBodyPairs == 0 || Settings.MaxBodyPairs > JPH::PhysicsSystem::cMaxBodyPairsLimit
        || Settings.MaxContactConstraints == 0 || Settings.MaxContactConstraints > JPH::PhysicsSystem::cMaxContactConstraintsLimit
        || Settings.MaxCollisionProfiles == 0 || Settings.MaxCollisionProfiles > static_cast<uint32>(JPH::cObjectLayerInvalid)
        || Settings.MaxGenericJoints == 0 || Settings.MaxGenericJoints > MAX_int32
        || Settings.MaxSuppressedBodyPairs == 0 || Settings.MaxSuppressedBodyPairs > MAX_int32
        || Settings.TempAllocatorBytes == 0 || Settings.WorkerThreads < 0 || Settings.WorkerThreads > 32)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid gravity/capacity settings; worker count must be 0..32 and collision-profile capacity 1..65535."));
    if (!JPH::VerifyJoltVersionID() || !JPH::Factory::sInstance || !JPH::Factory::sInstance->Find("SphereShapeSettings"))
        return Fail(EProphecyJoltWorldResult::RuntimeUnavailable, TEXT("Compatible process-wide Jolt registration is unavailable."));
    // Allocation/thread creation failure is not converted into a success or fallback configuration.
    Native.Reset(new FProphecyJoltWorldState(Settings));
    if (const float* Slop = ProphecyJolt::ContactSettings::SlopOverridesCm.Find(this))
    {
        auto PhysicsSettings = Native->Physics.GetPhysicsSettings();
        PhysicsSettings.mPenetrationSlop = *Slop * 0.01f;
        Native->Physics.SetPhysicsSettings(PhysicsSettings);
    }
    Diagnostics = {};
    Diagnostics.Settings = Settings;
    Diagnostics.WorldLifetime = Native->Lifetime;
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ShutdownSimulation()
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Shutdown requires the game thread."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Cannot shut down from within a step."));
    if (Native)
    {
        RefreshDiagnostics();
        Native.Reset();
    }
    Diagnostics.bInitialized = false;
    Diagnostics.BodyCount = 0;
    Diagnostics.ActiveRigidBodyCount = 0;
    Diagnostics.ConstraintCount = 0;
    Diagnostics.CollisionProfileCount = 0;
    Diagnostics.GenericJointCount = 0;
    Diagnostics.SuppressedBodyPairCount = 0;
    Diagnostics.TempCurrentBytes = 0;
    Diagnostics.JobConcurrency = 0;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ValidateReady() const
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("This interface is game-thread-only."));
    if (!bSubsystemInitialized || bWorldEnding || !GetWorld() || GetWorld()->bIsTearingDown)
        return Fail(EProphecyJoltWorldResult::WorldEnding, TEXT("World/subsystem lifetime is ending."));
    if (!Native) return Fail(EProphecyJoltWorldResult::NotInitialized, TEXT("InitializeSimulation must be called explicitly."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Reentrant access during Update is unsupported."));
    if (Diagnostics.bFaulted) return Fail(EProphecyJoltWorldResult::PhysicsFailure, TEXT("A failed simulation must be shut down before reuse."));
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ValidateBodySettings(const FProphecyJoltFixtureBodySettings& Settings) const
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Finite(Settings.PositionCm) || Settings.Rotation.ContainsNaN() || !Settings.Rotation.IsNormalized()
        || !FitsFloat(Settings.MassKg) || static_cast<float>(Settings.MassKg) <= 0.0f
        || !FMath::IsFinite(1.0f / static_cast<float>(Settings.MassKg))
        || !FMath::IsFinite(Settings.Friction) || Settings.Friction < 0.0f
        || !FMath::IsFinite(Settings.Restitution) || Settings.Restitution < 0.0f || Settings.Restitution > 1.0f
        || !FMath::IsFinite(Settings.LinearDamping) || Settings.LinearDamping < 0.0f
        || !FMath::IsFinite(Settings.AngularDamping) || Settings.AngularDamping < 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Body settings contain invalid pose, mass, friction, restitution or damping."));
    if (Settings.AssociatedObject && (!IsValid(Settings.AssociatedObject)
        || (Settings.AssociatedObject->GetWorld() && Settings.AssociatedObject->GetWorld() != GetWorld())))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Association is invalid or belongs to another world."));
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateSphere(double RadiusCm,
    const FProphecyJoltFixtureBodySettings& Settings, FProphecyJoltBodyHandle& OutHandle)
{
    using namespace ProphecyJolt::WorldPrivate;
    OutHandle = {};
    const FProphecyJoltWorldStatus Ready = ValidateBodySettings(Settings);
    if (!Ready.IsSuccess()) return Ready;
    const float RadiusMeters = static_cast<float>(RadiusCm * 0.01);
    if (!FitsFloat(RadiusCm * 0.01) || RadiusMeters <= 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Sphere radius must remain positive and finite after conversion."));
    JPH::SphereShapeSettings ShapeSettings(RadiusMeters);
    const JPH::Shape::ShapeResult Shape = ShapeSettings.Create();
    if (Shape.HasError()) return { EProphecyJoltWorldResult::ShapeCreationFailed, UTF8_TO_TCHAR(Shape.GetError().c_str()) };
    const FProphecyJoltWorldStatus Result = Native->Add(Shape.Get().GetPtr(), Settings, OutHandle);
    RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateBox(const FVector& HalfExtentCm, double ConvexRadiusCm,
    const FProphecyJoltFixtureBodySettings& Settings, FProphecyJoltBodyHandle& OutHandle)
{
    using namespace ProphecyJolt::WorldPrivate;
    OutHandle = {};
    const FProphecyJoltWorldStatus Ready = ValidateBodySettings(Settings);
    if (!Ready.IsSuccess()) return Ready;
    if (!Finite(HalfExtentCm) || !FitsFloatVector(HalfExtentCm, 0.01) || HalfExtentCm.GetMin() <= 0.0
        || !FitsFloat(ConvexRadiusCm * 0.01) || ConvexRadiusCm < 0.0 || ConvexRadiusCm > HalfExtentCm.GetMin())
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Box half extents must be positive/finite, and convex radius must fit inside every half extent."));
    const JPH::Vec3 HalfExtent = static_cast<JPH::Vec3>(ProphecyJolt::Conversions::ToJoltPosition(HalfExtentCm));
    if (HalfExtent.ReduceMin() <= 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Box dimensions underflow float shape precision."));
    JPH::BoxShapeSettings ShapeSettings(HalfExtent, static_cast<float>(ConvexRadiusCm * 0.01));
    const JPH::Shape::ShapeResult Shape = ShapeSettings.Create();
    if (Shape.HasError()) return { EProphecyJoltWorldResult::ShapeCreationFailed, UTF8_TO_TCHAR(Shape.GetError().c_str()) };
    const FProphecyJoltWorldStatus Result = Native->Add(Shape.Get().GetPtr(), Settings, OutHandle);
    RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateBody(const FProphecyJoltBodySnapshot& Snapshot,
    const FProphecyJoltPreparedBody& Prepared, FProphecyJoltBodyHandle& OutHandle, TArray<FString>& OutCoverageNotes)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    OutHandle = {};
    OutCoverageNotes.Reset();
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FString Error;
    if (!ProphecyJolt::Body::ValidateSnapshot(Snapshot, Error)) return { EProphecyJoltWorldResult::InvalidArgument, Error };
    if (!Prepared.IsValid() || Prepared.GetCaptureId() != Snapshot.CaptureId)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Prepared standalone shape/mass data does not belong to this sealed capture."));
    if ((!Snapshot.SourceWorld.IsExplicitlyNull() && Snapshot.SourceWorld.Get() != GetWorld())
        || (!Snapshot.SourceComponent.IsExplicitlyNull() && (!Snapshot.SourceComponent.IsValid()
            || Snapshot.SourceComponent->GetWorld() != GetWorld())))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Standalone source identity is expired or belongs to another world."));
    const FProphecyJoltBodyData& Body = Snapshot.Body;
    if (Body.CollisionEnabled != ECollisionEnabled::QueryAndPhysics && Body.CollisionEnabled != ECollisionEnabled::PhysicsOnly)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Standalone creation requires a captured simulation-enabled body."));
    FCollisionProfile Profile;
    if (!MakeCollisionProfile(false, Body.ObjectType, Body.CollisionResponses, Profile))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Standalone body has an invalid effective collision channel or response."));
    if (!FitsFloatVector(Body.CenterOfMassVelocityCmPerSecond, CentimetersToMeters)
        || !FitsFloatVector(Body.AngularVelocityRadiansPerSecond, 1.0))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Standalone velocity does not fit native precision."));
    const JPH::Vec3 Linear = ToJoltLinearVelocity(Body.CenterOfMassVelocityCmPerSecond);
    const JPH::Vec3 Angular = ToJoltAngularVelocity(Body.AngularVelocityRadiansPerSecond);
    if (!FMath::IsFinite(Linear.LengthSq()) || !FMath::IsFinite(Angular.LengthSq()))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Standalone velocity magnitude exceeds finite native clamping arithmetic."));
    const JPH::Shape* Shape = Prepared.GetNativeShape();
    JPH::MassProperties Mass;
    if (!Shape || !Prepared.GetNativeMassProperties(Mass))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Prepared standalone body is missing its native shape or captured mass tensor."));
    if (Native->Physics.GetNumBodies() >= Native->Settings.MaxBodies)
    {
        ++Native->CreationFailures;
        RefreshDiagnostics();
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Standalone body exceeds configured body capacity; no body was created."));
    }
    JPH::BodyCreationSettings Settings(Shape, ToJoltPosition(Body.BodyOriginToWorld.GetTranslation()),
        ToJoltRotation(Body.BodyOriginToWorld.GetRotation()), JPH::EMotionType::Dynamic, JPH::cObjectLayerInvalid);
    Settings.mLinearVelocity = Linear;
    Settings.mAngularVelocity = Angular;
    Settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
    Settings.mMassPropertiesOverride = Mass;
    Settings.mFriction = static_cast<float>(Body.Friction);
    Settings.mRestitution = static_cast<float>(Body.Restitution);
    Settings.mUserData = ProphecyJolt::Material::PackModes(Body.EffectiveFrictionCombineMode, Body.EffectiveRestitutionCombineMode);
    Settings.mLinearDamping = static_cast<float>(Body.LinearDamping);
    Settings.mAngularDamping = static_cast<float>(Body.AngularDamping);
    Settings.mMaxLinearVelocity = static_cast<float>(Body.MaxLinearVelocityCmPerSecond * CentimetersToMeters);
    Settings.mMaxAngularVelocity = static_cast<float>(Body.MaxAngularVelocityRadiansPerSecond);
    Settings.mGravityFactor = Body.bGravityEnabled ? 1.0f : 0.0f;
    Settings.mAllowSleeping = true;
    Settings.mMotionQuality = Body.bCCD ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete;
    TArray<JPH::ObjectLayer> Layers;
    const FProphecyJoltWorldStatus Interned = Native->CollisionProfiles.Intern(TConstArrayView<FCollisionProfile>(&Profile, 1), Layers);
    if (!Interned.IsSuccess()) return Interned;
    Settings.mObjectLayer = Layers[0];
    const FProphecyJoltWorldStatus Created = Native->AddNative(Settings,
        Body.bAwake ? JPH::EActivation::Activate : JPH::EActivation::DontActivate,
        Snapshot.SourceComponent.Get(), {}, OutHandle);
    RefreshDiagnostics();
    if (!Created.IsSuccess()) return Created;
    OutCoverageNotes = Snapshot.CoverageNotes;
    OutCoverageNotes.AddUnique(TEXT("Standalone creation applies the prepared native geometry and full captured mass tensor, body-origin pose, COM V/W, gravity, damping, speed caps, awake state, friction/restitution and effective bilateral Block filters. Original component identity is retained as a weak association only."));
    OutCoverageNotes.AddUnique(Body.bCCD
        ? TEXT("Captured CCD selects stock Jolt LinearCast. Rotation-only swept coverage and Chaos CCD trajectory equivalence are not implied.")
        : TEXT("Captured discrete motion selects stock Jolt Discrete motion quality."));
    OutCoverageNotes.AddUnique(TEXT("Stock Jolt sleep/contact/solver behavior applies. Captured static friction, material combine modes, inertia conditioning, iteration/projection counts and initial-overlap depenetration overrides remain provenance. UE queries, paint metadata and overlap events require the retained component adapter."));
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateStaticBody(const FProphecyJoltStaticBodySnapshot& Snapshot,
    const FProphecyJoltPreparedStaticBody& Prepared, FProphecyJoltBodyHandle& OutHandle, TArray<FString>& OutCoverageNotes)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    OutHandle = {}; OutCoverageNotes.Reset();
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FString Error;
    if (!ProphecyJolt::StaticBody::ValidateSnapshot(Snapshot, Error)) return { EProphecyJoltWorldResult::InvalidArgument, Error };
    if (!Prepared.IsValid() || Prepared.GetCaptureId() != Snapshot.CaptureId)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Prepared static geometry does not belong to this capture."));
    if ((!Snapshot.SourceWorld.IsExplicitlyNull() && Snapshot.SourceWorld.Get() != GetWorld())
        || (!Snapshot.SourceComponent.IsExplicitlyNull() && (!Snapshot.SourceComponent.IsValid()
            || Snapshot.SourceComponent->GetWorld() != GetWorld() || !Snapshot.SourceComponent->IsRegistered()
            || (Snapshot.SourceComponent->GetMobility() != EComponentMobility::Static && !Snapshot.bKinematic))))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Static source is expired, unregistered, moving or belongs to another world."));
    FCollisionProfile Profile;
    if (!MakeCollisionProfile(!Snapshot.bKinematic, Snapshot.ObjectType, Snapshot.CollisionResponses, Profile))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Static body has an invalid effective collision policy."));
    if (Native->Physics.GetNumBodies() >= Native->Settings.MaxBodies)
    {
        ++Native->CreationFailures;
        RefreshDiagnostics();
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Static body exceeds configured capacity; no body was created."));
    }
    JPH::BodyCreationSettings Settings(Prepared.GetNativeShape(), ToJoltPosition(Snapshot.BodyOriginToWorld.GetTranslation()),
        ToJoltRotation(Snapshot.BodyOriginToWorld.GetRotation()),
        Snapshot.bKinematic ? JPH::EMotionType::Kinematic : JPH::EMotionType::Static, JPH::cObjectLayerInvalid);
    if (Snapshot.bKinematic)
    {
        // Kinematic collision has infinite effective mass. Supply an unused valid tensor rather
        // than asking triangle scenery to calculate dynamic mass properties.
        Settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        Settings.mMassPropertiesOverride.mMass = 1.0f;
        Settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sIdentity();
    }
    Settings.mFriction = static_cast<float>(Snapshot.Friction);
    Settings.mRestitution = static_cast<float>(Snapshot.Restitution);
    Settings.mUserData = ProphecyJolt::Material::PackModes(Snapshot.EffectiveFrictionCombineMode, Snapshot.EffectiveRestitutionCombineMode);
    TArray<JPH::ObjectLayer> Layers;
    const auto Interned = Native->CollisionProfiles.Intern(TConstArrayView<FCollisionProfile>(&Profile, 1), Layers);
    if (!Interned.IsSuccess()) return Interned;
    Settings.mObjectLayer = Layers[0];
    const auto Created = Native->AddNative(Settings, JPH::EActivation::DontActivate, Snapshot.SourceComponent.Get(), {}, OutHandle);
    RefreshDiagnostics();
    if (!Created.IsSuccess()) return Created;
    OutCoverageNotes = Snapshot.CoverageNotes;
    OutCoverageNotes.AddUnique(TEXT("Static creation applies exact prepared geometry, captured body-origin pose, body-level friction/restitution and bilateral Block filters in the existing world. No mass/velocity override or extra simulation is created. Source component association is weak; instance index and later source lifecycle remain the caller's responsibility."));
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateRig(const FProphecyJoltRigSnapshot& Snapshot,
    const FProphecyJoltPreparedRig& Prepared, FProphecyJoltRigHandle& OutRig,
    TArray<FProphecyJoltBodyHandle>& OutBodyHandles, TArray<FString>& OutCoverageNotes, bool bPlayerSwingLimits)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    OutRig = {};
    OutBodyHandles.Reset();
    OutCoverageNotes.Reset();
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FString Error;
    if (!ProphecyJolt::Rig::ValidateSnapshot(Snapshot, Error)) return { EProphecyJoltWorldResult::InvalidArgument, Error };
    if (Prepared.GetCaptureId() != Snapshot.CaptureId || Prepared.GetBodyCount() != Snapshot.Bodies.Num())
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Prepared shape/mass data does not belong to this sealed rig capture."));
    if (static_cast<uint64>(Native->Physics.GetNumBodies()) + static_cast<uint64>(Snapshot.Bodies.Num()) > Native->Settings.MaxBodies)
    {
        ++Native->CreationFailures;
        RefreshDiagnostics();
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("The complete rig does not fit the remaining configured body capacity; no body was created."));
    }

    // Complete preflight before mutating this world. The snapshot may be replayed in a different world;
    // its weak source pointers are provenance and are never dereferenced or attached to native bodies.
    TArray<TUniquePtr<JPH::BodyCreationSettings>> BodySettings;
    BodySettings.Reserve(Snapshot.Bodies.Num());
    TArray<FCollisionProfile> BodyProfiles;
    BodyProfiles.Reserve(Snapshot.Bodies.Num());
    TArray<FString> Notes = Snapshot.CoverageNotes;
    Notes.AddUnique(TEXT("Simulation applies captured bilateral Block channel masks and exactly the captured PHAT/current-joint disabled pairs within each independently identified rig. Other rigs and ordinary props still require bilateral Block responses."));
    Notes.AddUnique(TEXT("Overlap responses are nonblocking; overlap events, UE query-channel filtering and arbitrary scene ignore-pair mutations are not implemented. Native simulation Word2 is a component ID; overlap provenance remains in the captured query data."));
    Notes.AddUnique(TEXT("Captured COM, mass, body pose/velocities, gravity flag, damping and speed caps are applied. Rig inertia includes admission-time conditioning when the body and engine policy enable it; raw captured principal I remains provenance. Chaos body iteration/projection counts, sleep thresholds and initial-overlap depenetration overrides are not mapped to equivalent Jolt solver behavior."));
    Notes.AddUnique(TEXT("Body friction/restitution coefficients and effective UE combine modes are applied using native contact callbacks. Separate static friction and physical surface identity remain capture provenance; per-triangle materials and live material updates are not implied."));
    Notes.AddUnique(TEXT("Initial awake state is captured. Stock Jolt sleep thresholds and velocity caps apply. Pending nonzero control wakes bodies before Update so they receive first-step gravity/damping; publication alone and zero control do not force wake."));
    for (int32 Index = 0; Index < Snapshot.Bodies.Num(); ++Index)
    {
        const FProphecyJoltRigBody& Body = Snapshot.Bodies[Index];
        if (Body.bCCD || Body.bMACD
            || (Body.CollisionEnabled != ECollisionEnabled::QueryAndPhysics && Body.CollisionEnabled != ECollisionEnabled::PhysicsOnly))
            return { EProphecyJoltWorldResult::InvalidArgument, FString::Printf(TEXT("Body %s is outside the discrete physical rig contract."), *Body.BodyName.ToString()) };
        FCollisionProfile Profile;
        if (!MakeCollisionProfile(false, Body.ObjectType, Body.CollisionResponses, Profile))
            return { EProphecyJoltWorldResult::InvalidArgument, FString::Printf(TEXT("Body %s has an invalid object channel or collision response."), *Body.BodyName.ToString()) };
        BodyProfiles.Add(Profile);
        if (!FitsFloatVector(Body.CenterOfMassVelocityCmPerSecond, CentimetersToMeters)
            || !FitsFloatVector(Body.AngularVelocityRadiansPerSecond, 1.0))
            return { EProphecyJoltWorldResult::InvalidArgument, FString::Printf(TEXT("Body %s velocity does not fit native precision."), *Body.BodyName.ToString()) };
        const JPH::Shape* Shape = Prepared.GetNativeBodyShape(Index);
        JPH::MassProperties Mass;
        if (!Shape || !Prepared.GetNativeBodyMassProperties(Index, Mass))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Prepared rig is missing a required native shape or mass tensor."));
        auto Settings = MakeUnique<JPH::BodyCreationSettings>(Shape,
            ToJoltPosition(Body.BodyOriginToWorld.GetTranslation()), ToJoltRotation(Body.BodyOriginToWorld.GetRotation()),
            Body.bSimulating ? JPH::EMotionType::Dynamic : JPH::EMotionType::Kinematic, JPH::cObjectLayerInvalid);
        Settings->mLinearVelocity = ToJoltLinearVelocity(Body.CenterOfMassVelocityCmPerSecond);
        Settings->mAngularVelocity = ToJoltAngularVelocity(Body.AngularVelocityRadiansPerSecond);
        Settings->mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        Settings->mMassPropertiesOverride = Mass;
        Settings->mFriction = static_cast<float>(Body.Friction);
        Settings->mRestitution = static_cast<float>(Body.Restitution);
        Settings->mUserData = ProphecyJolt::Material::PackModes(Body.EffectiveFrictionCombineMode, Body.EffectiveRestitutionCombineMode);
        Settings->mLinearDamping = static_cast<float>(Body.LinearDamping);
        Settings->mAngularDamping = static_cast<float>(Body.AngularDamping);
        Settings->mMaxLinearVelocity = static_cast<float>(Body.MaxLinearVelocityCmPerSecond * CentimetersToMeters);
        Settings->mMaxAngularVelocity = static_cast<float>(Body.MaxAngularVelocityRadiansPerSecond);
        Settings->mGravityFactor = Body.bGravityEnabled ? 1.0f : 0.0f;
        Settings->mAllowSleeping = true;
        BodySettings.Add(MoveTemp(Settings));
    }

    TArray<TUniquePtr<JPH::SixDOFConstraintSettings>> JointSettings;
    TArray<ProphecyJolt::FHardJointConversionReport> JointReports;
    JointSettings.Reserve(Snapshot.Joints.Num());
    JointReports.Reserve(Snapshot.Joints.Num());
    for (const FProphecyJoltRigJoint& Joint : Snapshot.Joints)
    {
        auto Settings = MakeUnique<JPH::SixDOFConstraintSettings>();
        ProphecyJolt::FHardJointConversionReport Report;
        if (!ProphecyJolt::BuildHardJointSettings(Joint,
            Snapshot.Bodies[Joint.Body1Index].GetCenterOfMassToBodyOrigin(),
            Snapshot.Bodies[Joint.Body2Index].GetCenterOfMassToBodyOrigin(), *Settings, Report, Error))
            return { EProphecyJoltWorldResult::InvalidArgument, Error };
        if (Report.bAuthoredSoftSwing || Report.bAuthoredSoftTwist)
            Notes.AddUnique(TEXT("Authorized angular-limit change: authored soft flags and coefficients remain in capture provenance; this fixture uses hard Jolt cone/twist limits at the exact captured angles, without coefficient or angle retuning. Combined swing response is not claimed identical to Chaos."));
        for (const FString& Feature : Report.DeferredProfileFeatures)
            Notes.AddUnique(FString::Printf(TEXT("Joint %s: %s"), *Joint.JointName.ToString(), *Feature));
        JointSettings.Add(MoveTemp(Settings));
        JointReports.Add(MoveTemp(Report));
    }

    if (Native->NextRigCollisionGroup >= JPH::CollisionGroup::cInvalidGroup)
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("World-lifetime rig collision group IDs exhausted; no body was created."));
    const uint64 BodyCount = static_cast<uint64>(Snapshot.Bodies.Num());
    // GroupFilterTable's pinned constructor computes N*(N-1) in uint32 before dividing.
    if (BodyCount * (BodyCount - 1) > MAX_uint32)
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Rig is too large for the pinned collision exclusion table; no body was created."));
    TArray<JPH::ObjectLayer> BodyLayers;
    const FProphecyJoltWorldStatus Interned = Native->CollisionProfiles.Intern(BodyProfiles, BodyLayers);
    if (!Interned.IsSuccess()) return Interned;
    JPH::Ref<JPH::GroupFilterTable> CollisionFilter = new JPH::GroupFilterTable(static_cast<JPH::uint>(BodyCount));
    for (const FProphecyJoltRigDisabledPair& Pair : Snapshot.DisabledPairs)
        CollisionFilter->DisableCollision(static_cast<JPH::uint32>(Pair.Body1Index), static_cast<JPH::uint32>(Pair.Body2Index));

    const int32 RigIndex = Native->AllocateRigSlot();
    if (RigIndex == INDEX_NONE)
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Adapter rig slots exhausted; no body was created."));
    auto& RigSlot = Native->Rigs[RigIndex];
    RigSlot.Record = MakeUnique<FRigRecord>();
    FRigRecord& Rig = *RigSlot.Record;
    const FProphecyJoltRigHandle PendingHandle{ Native->Lifetime, RigIndex, RigSlot.Generation };
    Rig.CaptureId = Snapshot.CaptureId;
    Rig.Handles.Reserve(Snapshot.Bodies.Num());
    Rig.Constraints.Reserve(Snapshot.Joints.Num());
    Rig.JointDescriptions = Snapshot.Joints;
    Rig.bPlayerSwingLimits = bPlayerSwingLimits;
    Rig.DisabledPairs = Snapshot.DisabledPairs;
    for (const auto& Pair : Snapshot.DisabledPairs)
        Rig.AuthoredDisabledPairKeys.Add(RigPairKey(Pair.Body1Index, Pair.Body2Index));
    Rig.CollisionFilter = CollisionFilter;
    Rig.CollisionGroupId = static_cast<JPH::CollisionGroup::GroupID>(Native->NextRigCollisionGroup++);
    Rig.CoverageNotes = MoveTemp(Notes);
    for (int32 Index = 0; Index < BodySettings.Num(); ++Index)
    {
        BodySettings[Index]->mObjectLayer = BodyLayers[Index];
        BodySettings[Index]->mCollisionGroup = JPH::CollisionGroup(Rig.CollisionFilter.GetPtr(), Rig.CollisionGroupId, static_cast<JPH::uint32>(Index));
        FProphecyJoltBodyHandle Handle;
        const FProphecyJoltWorldStatus Created = Native->AddNative(*BodySettings[Index],
            Snapshot.Bodies[Index].bAwake ? JPH::EActivation::Activate : JPH::EActivation::DontActivate, nullptr, PendingHandle, Handle);
        if (!Created.IsSuccess())
        {
            Native->DestroyRigSlot(RigIndex);
            RefreshDiagnostics();
            return Created;
        }
        Native->Slots[Handle.Slot].HitBone = Snapshot.Bodies[Index].BodyName;
        Native->Slots[Handle.Slot].HitBodyIndex = Snapshot.Bodies[Index].SourceBodyIndex;
        Rig.Handles.Add(Handle);
        Rig.AuthoredCCD.Add(Snapshot.Bodies[Index].bCCD ? 1 : 0);
    }
    for (int32 Index = 0; Index < JointSettings.Num(); ++Index)
    {
        const ProphecyJolt::FHardJointConversionReport& Report = JointReports[Index];
        const auto* Body1 = Native->Find(Rig.Handles[Report.JoltBody1Index]);
        const auto* Body2 = Native->Find(Rig.Handles[Report.JoltBody2Index]);
        check(Body1 && Body2);
        // Chaos solver order is parent first: the mapper returns UE Body2 then UE Body1 explicitly.
        JPH::Ref<JPH::TwoBodyConstraint> Constraint = Native->Physics.GetBodyInterface().CreateConstraint(
            JointSettings[Index].Get(), Body1->Body, Body2->Body);
        if (!Constraint)
        {
            Native->DestroyRigSlot(RigIndex);
            RefreshDiagnostics();
            return Fail(EProphecyJoltWorldResult::PhysicsFailure, TEXT("Jolt constraint creation failed; only the new pending rig was removed."));
        }
        auto* NativeJoint = static_cast<JPH::SixDOFConstraint*>(Constraint.GetPtr());
        if (bPlayerSwingLimits && ProphecyJolt::NeedsSpeculativeSwing(*NativeJoint))
            Constraint = new ProphecyJolt::FSpeculativeJoint(*NativeJoint, *JointSettings[Index]);
        Native->Physics.AddConstraint(Constraint.GetPtr());
        Rig.Constraints.Add(MoveTemp(Constraint));
    }
    Rig.bCommitted = true;
    OutRig = PendingHandle;
    OutBodyHandles = Rig.Handles;
    OutCoverageNotes = Rig.CoverageNotes;
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::DestroyRig(const FProphecyJoltRigHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Rig destruction requires the game thread."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Cannot destroy a rig during a physics step."));
    // Identity cleanup is intentionally available while faulted or ending.
    if (!Native || !Native->FindRig(Handle))
        return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    Native->DestroyRigSlot(Handle.Slot);
    RefreshDiagnostics();
    return {};
}

bool UProphecyJoltWorldSubsystem::OwnsRig(const FProphecyJoltRigHandle& Handle) const
{
    return IsInGameThread() && !bStepInProgress && Native && Native->FindRig(Handle);
}

namespace ProphecyJolt::WorldPrivate
{
void CopyAngularLimits(const FConstraintProfileProperties& Source, FConstraintProfileProperties& Destination)
{
    Destination.ConeLimit.Swing1Motion = Source.ConeLimit.Swing1Motion;
    Destination.ConeLimit.Swing2Motion = Source.ConeLimit.Swing2Motion;
    Destination.ConeLimit.Swing1LimitDegrees = Source.ConeLimit.Swing1LimitDegrees;
    Destination.ConeLimit.Swing2LimitDegrees = Source.ConeLimit.Swing2LimitDegrees;
    Destination.TwistLimit.TwistMotion = Source.TwistLimit.TwistMotion;
    Destination.TwistLimit.TwistLimitDegrees = Source.TwistLimit.TwistLimitDegrees;
}
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigPlayerSwingLimits(const FProphecyJoltRigHandle& Handle, bool bEnabled)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (Rig->bPlayerSwingLimits == bEnabled) return {};
    for (auto& Constraint : Rig->Constraints) RefreshSpeculativeJoint(Native->Physics, Constraint, bEnabled);
    Rig->bPlayerSwingLimits = bEnabled;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateRigAngularLimits(const FProphecyJoltRigHandle& Handle,
    TConstArrayView<FProphecyJoltRigJoint> Joints)
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (Joints.Num() != Rig->JointDescriptions.Num() || Joints.Num() != Rig->Constraints.Num())
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Angular updates require the complete captured joint order."));
    struct FChange { int32 Index; JPH::Vec3 Minimum; JPH::Vec3 Maximum; };
    TArray<FChange, TInlineAllocator<32>> Changes;
    TArray<JPH::BodyID, TInlineAllocator<64>> WakeBodies;
    for (int32 Index = 0; Index < Joints.Num(); ++Index)
    {
        const auto& Input = Joints[Index];
        const auto& Captured = Rig->JointDescriptions[Index];
        if (Input.SourceConstraintIndex != Captured.SourceConstraintIndex || Input.JointName != Captured.JointName
            || Input.Bone1 != Captured.Bone1 || Input.Bone2 != Captured.Bone2
            || Input.Body1Index != Captured.Body1Index || Input.Body2Index != Captured.Body2Index
            || !Input.Frame1.Equals(Captured.Frame1, 0.0) || !Input.Frame2.Equals(Captured.Frame2, 0.0)
            || !Input.AngularRotationOffsetDegrees.Equals(Captured.AngularRotationOffsetDegrees, 0.0))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Angular updates cannot change captured joint identity, endpoints or frames."));
        const auto& Profile = Input.CurrentProfile;
        for (float Angle : { Profile.ConeLimit.Swing1LimitDegrees, Profile.ConeLimit.Swing2LimitDegrees, Profile.TwistLimit.TwistLimitDegrees })
            if (!FMath::IsFinite(Angle) || Angle < 0.0f || Angle > 180.0f)
                return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Every angular limit angle must be finite and within [0,180] degrees, including inactive fields."));
        FProphecyJoltRigJoint Candidate = Captured;
        CopyAngularLimits(Profile, Candidate.CurrentProfile);
        JPH::SixDOFConstraintSettings Settings;
        ProphecyJolt::FHardJointConversionReport Report;
        FString Error;
        // Only angular ranges are consumed. COM translations affect the discarded anchor positions.
        if (!ProphecyJolt::BuildHardJointSettings(Candidate, FTransform::Identity, FTransform::Identity, Settings, Report, Error))
            return { EProphecyJoltWorldResult::InvalidArgument, Error };
        JPH::TwoBodyConstraint* Base = Rig->Constraints[Index].GetPtr();
        const auto* Body1 = Native->Find(Rig->Handles[Report.JoltBody1Index]);
        const auto* Body2 = Native->Find(Rig->Handles[Report.JoltBody2Index]);
        if (!Base || !ProphecyJolt::GetSixDOF(Base) || !Body1 || !Body2
            || !SameRig(Body1->OwnerRig, Handle) || !SameRig(Body2->OwnerRig, Handle)
            || Base->GetBody1()->GetID() != Body1->Body || Base->GetBody2()->GetID() != Body2->Body)
            return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("The captured anatomical joint endpoints are no longer owned by this rig."));
        float Min[3], Max[3];
        for (int32 Axis = 0; Axis < 3; ++Axis)
        {
            // SixDOF canonicalizes free sentinels to +/-pi and locked sentinels to zero.
            Min[Axis] = FMath::Clamp(Settings.mLimitMin[JPH::SixDOFConstraintSettings::RotationX + Axis], -JPH::JPH_PI, JPH::JPH_PI);
            Max[Axis] = FMath::Clamp(Settings.mLimitMax[JPH::SixDOFConstraintSettings::RotationX + Axis], -JPH::JPH_PI, JPH::JPH_PI);
            if (Min[Axis] > Max[Axis]) Min[Axis] = Max[Axis] = 0.0f;
        }
        auto* Constraint = ProphecyJolt::GetSixDOF(Base);
        const JPH::Vec3 Minimum(Min[0], Min[1], Min[2]), Maximum(Max[0], Max[1], Max[2]);
        if (Constraint->GetRotationLimitsMin() != Minimum || Constraint->GetRotationLimitsMax() != Maximum)
        {
            Changes.Add({ Index, Minimum, Maximum });
            WakeBodies.AddUnique(Body1->Body);
            WakeBodies.AddUnique(Body2->Body);
        }
    }
    // All validation/allocation precedes mutation. SetRotationLimits cannot fail and retains
    // translation limits and local frames; native warm starts reset when an axis changes mode.
    for (const auto& Change : Changes)
    {
        auto& Registered = Rig->Constraints[Change.Index];
        if (Registered->GetSubType() == JPH::EConstraintSubType::User1)
            static_cast<ProphecyJolt::FSpeculativeJoint*>(Registered.GetPtr())->SetRotationLimits(Change.Minimum, Change.Maximum);
        else ProphecyJolt::GetSixDOF(Registered.GetPtr())->SetRotationLimits(Change.Minimum, Change.Maximum);
        RefreshSpeculativeJoint(Native->Physics, Registered, Rig->bPlayerSwingLimits);
    }
    for (int32 Index = 0; Index < Joints.Num(); ++Index)
        CopyAngularLimits(Joints[Index].CurrentProfile, Rig->JointDescriptions[Index].CurrentProfile);
    if (!WakeBodies.IsEmpty()) Native->Physics.GetBodyInterface().ActivateBodies(WakeBodies.GetData(), WakeBodies.Num());
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadRigAngularLimits(const FProphecyJoltRigHandle& Handle,
    TArray<FProphecyJoltRigJoint>& OutJoints, int32* OutSpeculativeJointCount) const
{
    using namespace ProphecyJolt::WorldPrivate;
    OutJoints.Reset();
    if (OutSpeculativeJointCount) *OutSpeculativeJointCount = 0;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    TArray<FProphecyJoltRigJoint> Result = Rig->JointDescriptions;
    for (int32 Index = 0; Index < Result.Num(); ++Index)
    {
        if (OutSpeculativeJointCount && Rig->Constraints[Index]->GetSubType() == JPH::EConstraintSubType::User1)
            ++*OutSpeculativeJointCount;
        const auto* Constraint = ProphecyJolt::GetSixDOF(Rig->Constraints[Index].GetPtr());
        auto& Profile = Result[Index].CurrentProfile;
        const auto ReadAxis = [&](JPH::SixDOFConstraintSettings::EAxis Axis, TEnumAsByte<EAngularConstraintMotion>& Motion, float& Angle)
        {
            Motion = Constraint->IsFixedAxis(Axis) ? ACM_Locked : Constraint->IsFreeAxis(Axis) ? ACM_Free : ACM_Limited;
            if (Motion == ACM_Limited) Angle = JPH::RadiansToDegrees(Constraint->GetLimitsMax(Axis));
        };
        ReadAxis(JPH::SixDOFConstraintSettings::RotationX, Profile.TwistLimit.TwistMotion, Profile.TwistLimit.TwistLimitDegrees);
        ReadAxis(JPH::SixDOFConstraintSettings::RotationY, Profile.ConeLimit.Swing2Motion, Profile.ConeLimit.Swing2LimitDegrees);
        ReadAxis(JPH::SixDOFConstraintSettings::RotationZ, Profile.ConeLimit.Swing1Motion, Profile.ConeLimit.Swing1LimitDegrees);
    }
    OutJoints = MoveTemp(Result);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadBodyCollision(const FProphecyJoltBodyHandle& Handle, FProphecyJoltCollisionUpdate& Out) const
{
    Out = {};
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot) return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Collision inspection requires a live body."));
    const auto& Profile = Native->CollisionProfiles.Get(Slot->Weld ? Slot->Weld->OriginalLayer
        : Native->Physics.GetBodyInterface().GetObjectLayer(Slot->Body));
    Out.Handle = Handle;
    Out.ObjectChannel = static_cast<ECollisionChannel>(Profile.ObjectChannel);
    Out.Responses.SetAllChannels(ECR_Ignore);
    for (uint32 Channel = 0; Channel < 32; ++Channel)
        if ((Profile.BlockMask & (uint32(1) << Channel)) != 0) Out.Responses.SetResponse(static_cast<ECollisionChannel>(Channel), ECR_Block);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateBodyCollision(TConstArrayView<FProphecyJoltCollisionUpdate> Updates)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    TSet<int32> Seen;
    TArray<FCollisionProfile> Profiles;
    TArray<JPH::BodyID> IDs;
    for (const auto& Update : Updates)
    {
        const FBodySlot* Slot = Native->Find(Update.Handle);
        if (!Slot || Seen.Contains(Update.Handle.Slot))
            return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Collision updates require unique live body handles."));
        Seen.Add(Update.Handle.Slot);
        const auto OldLayer = Native->Physics.GetBodyInterface().GetObjectLayer(Slot->Body);
        FCollisionProfile Profile;
        if (!MakeCollisionProfile(Native->CollisionProfiles.Get(OldLayer).bStatic, Update.ObjectChannel, Update.Responses, Profile))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid collision channel or response."));
        Profiles.Add(Profile);
        IDs.Add(Slot->Body);
    }
    TArray<JPH::ObjectLayer> Layers;
    const auto Interned = Native->CollisionProfiles.Intern(Profiles, Layers);
    if (!Interned.IsSuccess()) return Interned;
    auto& Bodies = Native->Physics.GetBodyInterface();
    for (int32 Index = 0; Index < IDs.Num(); ++Index)
    {
        auto& Slot=Native->Slots[Updates[Index].Handle.Slot];
        const auto OldLayer=Slot.Weld ? Slot.Weld->OriginalLayer : Bodies.GetObjectLayer(IDs[Index]);
        if (OldLayer == Layers[Index]) continue;
        const auto* Carrier=Slot.WeldParent.IsSet() ? Native->Find(Slot.WeldParent) : &Slot;
        const auto CollisionBody=Carrier ? Carrier->Body : IDs[Index];
        JPH::AABox Bounds;
        {
            JPH::BodyLockRead Lock(Native->Physics.GetBodyLockInterface(), CollisionBody);
            check(Lock.Succeeded());
            Bounds = Lock.GetBody().GetWorldSpaceBounds();
        }
        if (Slot.Weld) Slot.Weld->OriginalLayer=Layers[Index];
        else Bodies.SetObjectLayer(IDs[Index], Layers[Index]);
        Bodies.InvalidateContactCache(CollisionBody);
        // Also wake sleeping counterparts when a supporting static body stops blocking.
        Bounds.ExpandBy(JPH::Vec3::sReplicate(0.02f));
        Bodies.ActivateBodiesInAABox(Bounds, JPH::BroadPhaseLayerFilter(), JPH::ObjectLayerFilter());
    }
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadBodyMaterial(const FProphecyJoltBodyHandle& Handle, FProphecyJoltBodyMaterial& Out) const
{
    Out = {};
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot) return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Material inspection requires a live body."));
    JPH::BodyLockRead Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
    check(Lock.Succeeded());
    const auto& Body = Lock.GetBody();
    Out.Friction = Body.GetFriction(); Out.Restitution = Body.GetRestitution();
    Out.FrictionCombineMode = uint8(Body.GetUserData() & 3);
    Out.RestitutionCombineMode = uint8((Body.GetUserData() >> 2) & 3);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateBodyMaterials(TConstArrayView<FProphecyJoltMaterialUpdate> Updates)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    TArray<JPH::BodyID, TInlineAllocator<8>> IDs;
    for (const auto& Update : Updates)
    {
        const FBodySlot* Slot = Native->Find(Update.Handle);
        if (!Slot || IDs.Contains(Slot->Body))
            return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Material updates require unique live body handles."));
        const auto& M = Update.Material;
        if (!FMath::IsFinite(M.Friction) || M.Friction < 0 || !FMath::IsFinite(M.Restitution)
            || M.Restitution < 0 || M.Restitution > 1 || !ProphecyJolt::Material::ValidModes(M.FrictionCombineMode, M.RestitutionCombineMode))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Material values require finite nonnegative friction, restitution in [0,1] and valid combine modes."));
        IDs.Add(Slot->Body);
    }
    auto& Bodies = Native->Physics.GetBodyInterface();
    for (int32 Index = 0; Index < IDs.Num(); ++Index)
    {
        const auto& M = Updates[Index].Material;
        const uint64 Modes = ProphecyJolt::Material::PackModes(M.FrictionCombineMode, M.RestitutionCombineMode);
        JPH::AABox Bounds;
        {
            JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(), IDs[Index]);
            check(Lock.Succeeded());
            auto& Body = Lock.GetBody();
            if (Body.GetFriction() == M.Friction && Body.GetRestitution() == M.Restitution && (Body.GetUserData() & 15) == Modes) continue;
            Bounds = Body.GetWorldSpaceBounds();
            Body.SetFriction(M.Friction); Body.SetRestitution(M.Restitution);
            Body.SetUserData((Body.GetUserData() & ~uint64(15)) | Modes);
        }
        // Discard old friction impulses and wake touching sleepers; retain bodies, joints,
        // velocities and poses. Only executed on an explicit material change, never polled.
        const auto& Slot=Native->Slots[Updates[Index].Handle.Slot];
        const auto* Carrier=Slot.WeldParent.IsSet() ? Native->Find(Slot.WeldParent) : &Slot;
        const auto ContactBody=Carrier ? Carrier->Body : IDs[Index];
        Bodies.InvalidateContactCache(ContactBody);
        if(Slot.WeldParent.IsSet())
        {
            JPH::BodyLockRead Lock(Native->Physics.GetBodyLockInterface(),ContactBody);
            if(Lock.Succeeded()) Bounds=Lock.GetBody().GetWorldSpaceBounds();
        }
        Bounds.ExpandBy(JPH::Vec3::sReplicate(Native->Physics.GetPhysicsSettings().mSpeculativeContactDistance));
        Bodies.ActivateBodiesInAABox(Bounds, JPH::BroadPhaseLayerFilter(), JPH::ObjectLayerFilter());
    }
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigSelfCollisionEnabled(const FProphecyJoltRigHandle& Handle, bool bEnabled)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (Rig->bSelfCollisionEnabled == bEnabled) return {};
    const auto Result = Native->ApplyRigSelfCollision(*Rig, bEnabled, Rig->SelfCollisionDisabledBodies, Rig->SelfCollisionDisabledPairs);
    if (Result.IsSuccess()) RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigBodiesSelfCollisionEnabled(const FProphecyJoltRigHandle& Handle,
    TConstArrayView<int32> BodyIndices, bool bEnabled)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    for (const int32 Index : BodyIndices)
        if (!Rig->Handles.IsValidIndex(Index))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Every selected self-collision body index must belong to this rig."));
    bool bChanged = false;
    for (const int32 Index : BodyIndices) bChanged |= Rig->SelfCollisionDisabledBodies.Contains(Index) == bEnabled;
    if (!bChanged) return {};
    TSet<int32> DisabledBodies = Rig->SelfCollisionDisabledBodies;
    for (const int32 Index : BodyIndices)
    {
        if (bEnabled) DisabledBodies.Remove(Index);
        else DisabledBodies.Add(Index);
    }
    const auto Result = Native->ApplyRigSelfCollision(*Rig, Rig->bSelfCollisionEnabled, MoveTemp(DisabledBodies), Rig->SelfCollisionDisabledPairs);
    if (Result.IsSuccess()) RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigBodyPairSelfCollisionEnabled(const FProphecyJoltRigHandle& Handle,
    int32 Body1Index, int32 Body2Index, bool bEnabled)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (!Rig->Handles.IsValidIndex(Body1Index) || !Rig->Handles.IsValidIndex(Body2Index) || Body1Index == Body2Index)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Self-collision pairs require two distinct body indices belonging to this rig."));
    const uint64 Key = RigPairKey(Body1Index, Body2Index);
    if (Rig->SelfCollisionDisabledPairs.Contains(Key) != bEnabled) return {};
    TSet<uint64> DisabledPairs = Rig->SelfCollisionDisabledPairs;
    if (bEnabled) DisabledPairs.Remove(Key);
    else DisabledPairs.Add(Key);
    const auto Result = Native->ApplyRigSelfCollision(*Rig, Rig->bSelfCollisionEnabled, Rig->SelfCollisionDisabledBodies, MoveTemp(DisabledPairs));
    if (Result.IsSuccess()) RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ResetRigSelfCollision(const FProphecyJoltRigHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (Rig->bSelfCollisionEnabled && Rig->SelfCollisionDisabledBodies.IsEmpty() && Rig->SelfCollisionDisabledPairs.IsEmpty()) return {};
    const auto Result = Native->ApplyRigSelfCollision(*Rig, true, {}, {});
    if (Result.IsSuccess()) RefreshDiagnostics();
    return Result;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadRigBodyPairSelfCollisionEnabled(const FProphecyJoltRigHandle& Handle,
    int32 Body1Index, int32 Body2Index, bool& bOutEnabled) const
{
    using namespace ProphecyJolt::WorldPrivate;
    bOutEnabled = false;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (!Rig->Handles.IsValidIndex(Body1Index) || !Rig->Handles.IsValidIndex(Body2Index) || Body1Index == Body2Index)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Self-collision pairs require two distinct body indices belonging to this rig."));
    bOutEnabled = Rig->CollisionFilter->IsCollisionEnabled(Body1Index, Body2Index);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::PublishRigVelocityTargets(const FProphecyJoltRigHandle& Handle,
    TConstArrayView<FProphecyJoltRigVelocityTarget> Targets, float MaximumSubstepSeconds)
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    FRigRecord* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    if (!FMath::IsFinite(MaximumSubstepSeconds) || MaximumSubstepSeconds <= 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Rig target denominator must be positive and finite."));
    const float Denominator = FMath::Max(MaximumSubstepSeconds, UE_SMALL_NUMBER);
    TArray<ProphecyJolt::FVelocityServo::FTarget, TInlineAllocator<32>> NativeTargets;
    TArray<FProphecyJoltBodyHandle, TInlineAllocator<32>> Handles;
    TSet<int32, DefaultKeyFuncs<int32>, TInlineSetAllocator<32>> UniqueSlots;
    NativeTargets.Reserve(Targets.Num());
    Handles.Reserve(Targets.Num());
    for (const auto& Target : Targets)
    {
        const FBodySlot* Slot = Native->Find(Target.Handle);
        if (!Slot || !SameRig(Slot->OwnerRig, Handle))
            return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Every target must name a current body owned by the specified rig."));
        if (UniqueSlots.Contains(Target.Handle.Slot) || Target.TargetPositionCm.ContainsNaN()
            || Target.TargetRotation.ContainsNaN() || !Target.TargetRotation.IsNormalized()
            || !FMath::IsFinite(Target.LinearStrength) || Target.LinearStrength < 0.0f
            || !FMath::IsFinite(Target.AngularStrength) || Target.AngularStrength < 0.0f
            || !FMath::IsFinite(Target.GravityCompensationCmPerSecondSquared)
            || !FMath::IsFinite(Target.TrajectoryDurationSeconds) || Target.TrajectoryDurationSeconds < 0.0f
            || (Target.TrajectoryDurationSeconds > 0.0f && (Target.StartPositionCm.ContainsNaN()
                || Target.StartRotation.ContainsNaN() || !Target.StartRotation.IsNormalized())))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Rig targets require unique bodies, finite endpoints, nonnegative finite strengths and valid optional trajectories."));
        UniqueSlots.Add(Target.Handle.Slot);
        ProphecyJolt::FVelocityServo::FTarget NativeTarget;
        NativeTarget.Body = Slot->Body;
        NativeTarget.TargetPositionCm = Target.TargetPositionCm;
        NativeTarget.TargetRotation = Target.TargetRotation;
        NativeTarget.LinearStrength = Target.LinearStrength;
        NativeTarget.AngularStrength = Target.AngularStrength;
        NativeTarget.GravityCompensationCmPerSecondSquared = Target.GravityCompensationCmPerSecondSquared;
        NativeTarget.DenominatorSeconds = Denominator;
        NativeTarget.StartPositionCm = Target.StartPositionCm;
        NativeTarget.StartRotation = Target.StartRotation;
        NativeTarget.TrajectoryDurationSeconds = Target.TrajectoryDurationSeconds;
        NativeTargets.Add(NativeTarget);
        Handles.Add(Target.Handle);
    }
    // Transactional per-rig publication. Complete the stack-staged preflight before touching
    // either accepted array, then reuse its capacity instead of replacing two allocations per tick.
    Rig->Targets.Reset(NativeTargets.Num());
    Rig->Targets.Append(NativeTargets.GetData(), NativeTargets.Num());
    Rig->PublishedHandles.Reset(Handles.Num());
    Rig->PublishedHandles.Append(Handles.GetData(), Handles.Num());
    Rig->ServoState.DenominatorSeconds = Denominator;
    Rig->ServoState.Samples.SetNum(Rig->PublishedHandles.Num());
    for (int32 Index = 0; Index < Rig->PublishedHandles.Num(); ++Index)
    {
        Rig->ServoState.Samples[Index] = {};
        Rig->ServoState.Samples[Index].Handle = Rig->PublishedHandles[Index];
    }
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadRigServoSamples(const FProphecyJoltRigHandle& Handle,
    FProphecyJoltRigServoState& OutState) const
{
    OutState = {};
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Rig = Native->FindRig(Handle);
    if (!Rig) return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world rig handle."));
    OutState = Rig->ServoState;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateRigFixture(const FProphecyJoltRigSnapshot& Snapshot,
    const FProphecyJoltPreparedRig& Prepared, TArray<FProphecyJoltBodyHandle>& OutBodyHandles, TArray<FString>& OutCoverageNotes)
{
    OutBodyHandles.Reset();
    OutCoverageNotes.Reset();
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (Native->HasRigs())
        return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::AlreadyInitialized,
            TEXT("Legacy fixture creation requires an empty rig registry; use CreateRig for multiple independent rigs."));
    FProphecyJoltRigHandle Rig;
    const FProphecyJoltWorldStatus Created = CreateRig(Snapshot, Prepared, Rig, OutBodyHandles, OutCoverageNotes);
    if (Created.IsSuccess()) Native->LegacyRig = Rig;
    return Created;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::DestroyRigFixture()
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Rig destruction requires the game thread."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Cannot destroy a rig during a physics step."));
    // Preserve legacy idempotence without treating an unrelated explicit rig as legacy ownership.
    if (!Native || !Native->FindRig(Native->LegacyRig)) return {};
    return DestroyRig(Native->LegacyRig);
}

bool UProphecyJoltWorldSubsystem::OwnsRigFixture(TConstArrayView<FProphecyJoltBodyHandle> Handles) const
{
    if (!IsInGameThread() || bStepInProgress || !Native || Handles.IsEmpty()) return false;
    const auto* Rig = Native->FindRig(Native->LegacyRig);
    if (!Rig || Handles.Num() != Rig->Handles.Num()) return false;
    for (int32 Index = 0; Index < Handles.Num(); ++Index)
    {
        const auto& Handle = Handles[Index];
        const auto& Current = Rig->Handles[Index];
        if (Handle.WorldLifetime != Current.WorldLifetime || Handle.Slot != Current.Slot || Handle.Generation != Current.Generation) return false;
        const auto* Slot = Native->Find(Handle);
        if (!Slot || !ProphecyJolt::WorldPrivate::SameRig(Slot->OwnerRig, Native->LegacyRig)) return false;
    }
    return true;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::PublishRigFixtureVelocityTargets(
    TConstArrayView<FProphecyJoltRigVelocityTarget> Targets, float MaximumSubstepSeconds)
{
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Native->FindRig(Native->LegacyRig))
        return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Create a legacy rig fixture before publishing its targets."));
    const FProphecyJoltWorldStatus Published = PublishRigVelocityTargets(Native->LegacyRig, Targets, MaximumSubstepSeconds);
    if (Published.IsSuccess()) Native->LegacyDenominatorSeconds = FMath::Max(MaximumSubstepSeconds, UE_SMALL_NUMBER);
    return Published;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadRigFixtureServoSamples(FProphecyJoltRigServoState& OutState) const
{
    OutState = {};
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (Native->FindRig(Native->LegacyRig)) return ReadRigServoSamples(Native->LegacyRig, OutState);
    OutState.DenominatorSeconds = Native->LegacyDenominatorSeconds;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadBody(const FProphecyJoltBodyHandle& Handle, FProphecyJoltBodyState& OutState) const
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    OutState = {};
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FBodySlot* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    if (Slot->WeldParent.IsSet())
    {
        const auto* Parent=Native->Find(Slot->WeldParent);
        if(!Parent || !Parent->Weld) return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Welded collider lost its parent."));
        FProphecyJoltBodyState ParentState;
        const auto Read=ReadBody(Slot->WeldParent,ParentState);
        if(!Read.IsSuccess()) return Read;
        const FTransform Pose=Parent->Weld->SourceToParent * FTransform(ParentState.Rotation,ParentState.PositionCm);
        const JPH::BodyLockRead Lock(Native->IdleBodyReadLocks(),Slot->Body);
        if(!Lock.Succeeded()) return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Welded source metadata is absent."));
        OutState.PositionCm=Pose.GetLocation(); OutState.Rotation=Pose.GetRotation();
        OutState.CenterOfMassPositionCm=Pose.TransformPosition(FromJoltPosition(JPH::RVec3(Lock.GetBody().GetShape()->GetCenterOfMass())));
        OutState.AngularVelocityRadiansPerSecond=ParentState.AngularVelocityRadiansPerSecond;
        OutState.CenterOfMassVelocityCmPerSecond=ParentState.CenterOfMassVelocityCmPerSecond+FVector::CrossProduct(
            ParentState.AngularVelocityRadiansPerSecond,OutState.CenterOfMassPositionCm-ParentState.CenterOfMassPositionCm);
        OutState.bActive=ParentState.bActive;
        return {};
    }
    const JPH::BodyLockRead Lock(Native->IdleBodyReadLocks(), Slot->Body);
    if (!Lock.SucceededAndIsInBroadPhase()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body registry disagrees with Jolt; body is absent."));
    const JPH::Body& Body = Lock.GetBody();
    OutState.PositionCm = FromJoltPosition(Body.GetPosition());
    OutState.CenterOfMassPositionCm = FromJoltPosition(Body.GetCenterOfMassPosition());
    OutState.Rotation = FromJoltRotation(Body.GetRotation());
    OutState.CenterOfMassVelocityCmPerSecond = FromJoltLinearVelocity(Body.GetLinearVelocity());
    OutState.AngularVelocityRadiansPerSecond = FromJoltAngularVelocity(Body.GetAngularVelocity());
    OutState.bDynamic = Body.IsDynamic();
    OutState.bActive = Body.IsActive();
    if (!Finite(OutState.PositionCm) || !Finite(OutState.CenterOfMassPositionCm) || OutState.Rotation.ContainsNaN()
        || !Finite(OutState.CenterOfMassVelocityCmPerSecond) || !Finite(OutState.AngularVelocityRadiansPerSecond))
        return Fail(EProphecyJoltWorldResult::PhysicsFailure, TEXT("Body state contains a non-finite value."));
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::RayCast(const FVector& StartCm, const FVector& EndCm,
    FProphecyJoltRayHit& OutHit, bool& bOutHit) const
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    OutHit = {};
    bOutHit = false;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FVector DeltaCm = EndCm - StartCm;
    if (!Finite(StartCm) || !Finite(EndCm) || !Finite(DeltaCm) || !FitsFloatVector(DeltaCm, CentimetersToMeters))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Ray endpoints and segment must be finite and fit native query precision."));
    const JPH::Vec3 Direction = ToJoltDirection(DeltaCm * CentimetersToMeters);
    const float LengthSquared = Direction.LengthSq();
    if (!FMath::IsFinite(LengthSquared) || LengthSquared <= 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Ray segment must have a positive finite length in native query precision."));

    const JPH::RRayCast Ray(ToJoltPosition(StartCm), Direction);
    JPH::RayCastResult Hit;
    // Default query filters admit every fixture layer; simulation pair policy does not filter this query.
    if (!Native->Physics.GetNarrowPhaseQuery().CastRay(Ray, Hit)) return {};
    int32 SlotIndex = INDEX_NONE;
    for (int32 Index = 0; Index < Native->Slots.Num(); ++Index)
    {
        if (Native->Slots[Index].Body == Hit.mBodyID) { SlotIndex = Index; break; }
    }
    if (SlotIndex == INDEX_NONE || Hit.mBodyID.IsInvalid())
        return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Ray hit body is absent from the adapter registry."));
    const JPH::BodyLockRead Lock(Native->Physics.GetBodyLockInterface(), Hit.mBodyID);
    if (!Lock.SucceededAndIsInBroadPhase())
        return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Ray hit body is absent from Jolt."));
    const JPH::RVec3 NativePoint = Ray.GetPointOnRay(Hit.mFraction);
    const FVector PointCm = FromJoltPosition(NativePoint);
    const FVector Normal = FromJoltDirection(Lock.GetBody().GetWorldSpaceSurfaceNormal(Hit.mSubShapeID2, NativePoint));
    if (!FMath::IsFinite(Hit.mFraction) || Hit.mFraction < 0.0f || Hit.mFraction > 1.0f || !Finite(PointCm) || !Finite(Normal))
        return Fail(EProphecyJoltWorldResult::PhysicsFailure, TEXT("Ray hit contains an invalid fraction, point or normal."));
    OutHit.Handle.WorldLifetime = Native->Lifetime;
    OutHit.Handle.Slot = SlotIndex;
    OutHit.Handle.Generation = Native->Slots[SlotIndex].Generation;
    OutHit.PositionCm = PointCm;
    OutHit.Normal = Normal;
    OutHit.Fraction = Hit.mFraction;
    OutHit.NativeSubShapeId = Hit.mSubShapeID2.GetValue();
    if(const auto* Weld=static_cast<const FWeldRecord*>(ProphecyJolt::Material::AttachedData(Lock.GetBody())))
    {
        JPH::SubShapeID Rest;
        Weld->Compound->GetSubShapeIndexFromID(Hit.mSubShapeID2,Rest);
        OutHit.NativeSubShapeId=Rest.GetValue();
        if(Weld->IsSource(Hit.mSubShapeID2)) OutHit.Handle=Weld->SourceHandle;
    }
    bOutHit = true;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ExecutePhysicsCommand(
    const FProphecyJoltBodyHandle& Handle, const FProphecyJoltPhysicsCommand& Command)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    using EOp = EProphecyJoltPhysicsCommand;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FBodySlot* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Physics command requires a live body in this world."));
    const EOp Op = Command.Operation;
    if (uint8(Op) > uint8(EOp::AngularVelocity) || !Finite(Command.Value)
        || (Command.bAtPosition && (!Finite(Command.Position) || (Op != EOp::Force && Op != EOp::Impulse)))
        || (Command.bLocalSpace && !Command.bAtPosition))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid physics command or non-finite input."));
    const auto Safe = [](JPH::Vec3Arg V)
    {
        return FMath::IsFinite(V.GetX()) && FMath::IsFinite(V.GetY()) && FMath::IsFinite(V.GetZ())
            && FMath::IsFinite(V.LengthSq());
    };
    bool bWake = false;
    {
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
        if (!Lock.SucceededAndIsInBroadPhase()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body is absent from Jolt."));
        JPH::Body& Body = Lock.GetBody();
        if (!Body.IsDynamic()) return {}; // UE ignores force/impulse calls on kinematic/static bodies.
        const JPH::MotionProperties& Motion = *Body.GetMotionProperties();
        FVector Value = Command.Value;
        FVector Point = Command.Position;
        if (Command.bLocalSpace)
        {
            const FTransform BodyWorld(FromJoltRotation(Body.GetRotation()), FromJoltPosition(Body.GetPosition()));
            Value = BodyWorld.TransformVectorNoScale(Value);
            Point = BodyWorld.TransformPositionNoScale(Point);
        }
        JPH::Vec3 Linear = Body.GetLinearVelocity(), Angular = Body.GetAngularVelocity();
        JPH::Vec3 Force = JPH::Vec3::sZero(), Torque = JPH::Vec3::sZero();
        const bool bLinear = Op == EOp::Force || Op == EOp::Impulse || Op == EOp::LinearVelocity;
        const double Scale = bLinear ? 0.01 : ((Command.bMassIndependent || Op == EOp::AngularVelocity) ? 1.0 : 0.0001);
        if (!FitsFloatVector(Value, Scale)) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Physics input exceeds native precision."));
        JPH::Vec3 V = ToJoltDirection(Value * Scale);
        if (!Safe(V)) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Physics input magnitude exceeds native precision."));
        JPH::Vec3 Lever = JPH::Vec3::sZero();
        if (Command.bAtPosition)
        {
            const FVector Offset = Point - FromJoltPosition(Body.GetCenterOfMassPosition());
            if (!FitsFloatVector(Offset, 0.01)) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Force lever arm exceeds native precision."));
            Lever = ToJoltLinearVelocity(Offset);
            if (!Safe(Lever)) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Force lever arm magnitude exceeds native precision."));
        }
        switch (Op)
        {
        case EOp::Force:
            Force = Command.bMassIndependent ? (Motion.GetInverseMass() > 0 ? V / Motion.GetInverseMass() : JPH::Vec3::sZero()) : V;
            if (Command.bAtPosition) Torque = Lever.Cross(Force);
            break;
        case EOp::Impulse:
            Linear += Command.bMassIndependent ? V : V * Motion.GetInverseMass();
            if (Command.bMassIndependent) V = Motion.GetInverseMass() > 0 ? V / Motion.GetInverseMass() : JPH::Vec3::sZero();
            if (Command.bAtPosition) Angular += Motion.MultiplyWorldSpaceInverseInertiaByVector(Body.GetRotation(), Lever.Cross(V));
            break;
        case EOp::Torque:
            Torque = V;
            if (Command.bMassIndependent)
            {
                // Principal inertia can have locked axes. Do not invert a singular world tensor.
                const JPH::Quat Principal = Body.GetRotation() * Motion.GetInertiaRotation();
                const JPH::Vec3 Inv = Motion.GetInverseInertiaDiagonal();
                const JPH::Vec3 I(Inv.GetX() > 0 ? 1.0f / Inv.GetX() : 0,
                    Inv.GetY() > 0 ? 1.0f / Inv.GetY() : 0, Inv.GetZ() > 0 ? 1.0f / Inv.GetZ() : 0);
                Torque = Principal * (I * (Principal.Conjugated() * V));
            }
            break;
        case EOp::AngularImpulse:
            Angular += Command.bMassIndependent ? V : Motion.MultiplyWorldSpaceInverseInertiaByVector(Body.GetRotation(), V);
            break;
        case EOp::LinearVelocity: Linear = Command.bAddToCurrent ? Linear + V : V; break;
        case EOp::AngularVelocity: Angular = Command.bAddToCurrent ? Angular + V : V; break;
        }
        if (!Safe(Linear) || !Safe(Angular) || !Safe(Force) || !Safe(Torque)
            || !Safe(Body.GetAccumulatedForce() + Force) || !Safe(Body.GetAccumulatedTorque() + Torque))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Physics command would overflow native force, torque or velocity; body unchanged."));
        if (Op == EOp::Force || Op == EOp::Torque)
        {
            Body.AddForce(Force);
            Body.AddTorque(Torque);
            bWake = !Force.IsNearZero() || !Torque.IsNearZero();
        }
        else
        {
            Body.SetLinearVelocityClamped(Linear);
            Body.SetAngularVelocityClamped(Angular);
            bWake = !V.IsNearZero();
        }
    }
    // Activation takes its own lock; never call it while holding BodyLockWrite.
    if (bWake) Native->Physics.GetBodyInterface().ActivateBody(Slot->Body);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::AddPointImpulse(const FProphecyJoltBodyHandle& Handle,
    const FVector& ImpulseKgCmPerSecond, const FVector& WorldPointCm)
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FBodySlot* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    if (!Finite(WorldPointCm) || !Finite(ImpulseKgCmPerSecond) || !FitsFloatVector(ImpulseKgCmPerSecond, 0.01))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Point/impulse values must be finite and fit their target precision."));
    {
        const JPH::BodyLockRead Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
        if (!Lock.SucceededAndIsInBroadPhase()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body is absent from Jolt."));
        if (!Lock.GetBody().IsDynamic()) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Point impulses require a dynamic body."));
        const FVector OffsetCm = WorldPointCm - ProphecyJolt::Conversions::FromJoltPosition(Lock.GetBody().GetCenterOfMassPosition());
        if (!FitsFloatVector(OffsetCm, 0.01)) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Impulse lever arm exceeds float precision range."));
        const JPH::Body& Body = Lock.GetBody();
        const JPH::MotionProperties& Motion = *Body.GetMotionProperties();
        const JPH::Vec3 Impulse = ProphecyJolt::Conversions::ToJoltLinearImpulse(ImpulseKgCmPerSecond);
        const JPH::Vec3 Lever = static_cast<JPH::Vec3>(ProphecyJolt::Conversions::ToJoltPosition(WorldPointCm) - Body.GetCenterOfMassPosition());
        const JPH::Vec3 NewLinear = Body.GetLinearVelocity() + Impulse * Motion.GetInverseMass();
        const JPH::Vec3 NewAngular = Body.GetAngularVelocity()
            + Motion.MultiplyWorldSpaceInverseInertiaByVector(Body.GetRotation(), Lever.Cross(Impulse));
        if (!Finite(ProphecyJolt::Conversions::FromJoltDirection(NewLinear))
            || !Finite(ProphecyJolt::Conversions::FromJoltDirection(NewAngular)))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Impulse would overflow body velocity before Jolt's documented velocity clamp."));
    }
    Native->Physics.GetBodyInterface().AddImpulse(Slot->Body,
        ProphecyJolt::Conversions::ToJoltLinearImpulse(ImpulseKgCmPerSecond), ProphecyJolt::Conversions::ToJoltPosition(WorldPointCm));
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::CreateJoint(const FProphecyJoltJointSettings& Settings,
    TConstArrayView<FProphecyJoltBodyPair> SuppressedPairs, FProphecyJoltJointHandle& OutJoint)
{
    using namespace ProphecyJolt::WorldPrivate;
    OutJoint = {};
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (Native->JointCount >= Native->Settings.MaxGenericJoints)
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Generic joint capacity reached."));
    int32 Index = INDEX_NONE;
    for (int32 Candidate = 0; Candidate < Native->Joints.Num(); ++Candidate)
        if (!Native->Joints[Candidate].Record && Native->Joints[Candidate].Generation < MAX_uint64) { Index = Candidate; break; }
    if (Index == INDEX_NONE && Native->Joints.Num() == MAX_int32)
        return Fail(EProphecyJoltWorldResult::CapacityExceeded, TEXT("Joint identity slots exhausted."));
    TUniquePtr<FJointRecord> Record = MakeUnique<FJointRecord>();
    const FProphecyJoltWorldStatus Pairs = Native->PrepareSuppression(SuppressedPairs, Record->Suppression);
    if (!Pairs.IsSuccess()) return Pairs;
    const FProphecyJoltWorldStatus Built = Native->BuildJoint(Settings, Record->Constraint);
    if (!Built.IsSuccess()) return Built;
    Record->Settings = Settings;
    // All recoverable validation/capacity failures occur before registration or filter mutation.
    // Like existing body/rig creation, allocator failure is not claimed to be recoverable.
    if (Index == INDEX_NONE) Index = Native->Joints.AddDefaulted();
    Native->Physics.AddConstraint(Record->Constraint.GetPtr());
    Native->AddSuppression(Record->Suppression);
    Native->Slots[Settings.BodyA.Slot].IncidentJoints.Add(Index);
    Native->Slots[Settings.BodyB.Slot].IncidentJoints.Add(Index);
    Native->Joints[Index].Record = MoveTemp(Record);
    ++Native->JointCount;
    Native->Wake(Settings.BodyA);
    Native->Wake(Settings.BodyB);
    OutJoint = { Native->Lifetime, Index, Native->Joints[Index].Generation };
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateJoint(const FProphecyJoltJointHandle& Handle,
    const FProphecyJoltJointSettings& Settings)
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FJointRecord* Old = Native->FindJoint(Handle);
    if (!Old) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world joint handle."));
    if (!SameBody(Old->Settings.BodyA, Settings.BodyA) || !SameBody(Old->Settings.BodyB, Settings.BodyB) || Old->Settings.Type != Settings.Type)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Joint updates cannot change endpoints, endpoint order or type; create a new joint explicitly."));
    bool SameGeometry = Settings.Type == EProphecyJoltJointType::HardSixDOF
        && Old->Settings.FrameA.Equals(Settings.FrameA, 0) && Old->Settings.FrameB.Equals(Settings.FrameB, 0)
        && Old->Settings.SwingGeometry == Settings.SwingGeometry && Old->Settings.bSoftTranslation == Settings.bSoftTranslation
        && Old->Settings.bRadialTranslation == Settings.bRadialTranslation
        && Old->Settings.TranslationStiffness == Settings.TranslationStiffness && Old->Settings.TranslationDamping == Settings.TranslationDamping;
    for (int32 I = 0; I < 3 && SameGeometry; ++I)
    {
        auto SameLimit = [](const FProphecyJoltAxisLimit& A, const FProphecyJoltAxisLimit& B)
        { return A.Motion == B.Motion && A.Minimum == B.Minimum && A.Maximum == B.Maximum; };
        SameGeometry = SameLimit(Old->Settings.Translation[I], Settings.Translation[I]) && SameLimit(Old->Settings.Rotation[I], Settings.Rotation[I]);
    }
    if (SameGeometry)
    {
        const auto Valid = Native->ValidateJointDrives(Settings);
        if (!Valid.IsSuccess()) return Valid;
        auto& Record = *Native->Joints[Handle.Slot].Record;
        Native->ConfigureJointMotors(Settings, ProphecyJolt::GenericSixDOF(*Record.Constraint));
        Record.Settings = Settings;
        Native->Wake(Settings.BodyA); Native->Wake(Settings.BodyB);
        return {}; // Retargeting a drive must preserve constraint warm starts.
    }
    JPH::Ref<JPH::TwoBodyConstraint> Replacement;
    const FProphecyJoltWorldStatus Built = Native->BuildJoint(Settings, Replacement);
    if (!Built.IsSuccess()) return Built;
    FJointRecord& Record = *Native->Joints[Handle.Slot].Record;
    Native->Physics.RemoveConstraint(Record.Constraint.GetPtr());
    Native->Physics.AddConstraint(Replacement.GetPtr());
    Record.Constraint = MoveTemp(Replacement); // New constraint intentionally has no warm-start history.
    Record.Settings = Settings;
    Native->Wake(Settings.BodyA);
    Native->Wake(Settings.BodyB);
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateJointSuppressedPairs(
    const FProphecyJoltJointHandle& Handle, TConstArrayView<FProphecyJoltBodyPair> SuppressedPairs)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Native->FindJoint(Handle))
        return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world joint handle."));
    TArray<FSuppressionKey> Keys;
    const auto Prepared = Native->PrepareSuppression(SuppressedPairs, Keys);
    if (!Prepared.IsSuccess()) return Prepared;
    auto& Record = *Native->Joints[Handle.Slot].Record;
    if (Record.Suppression == Keys) return {};
    // Retain common pairs before releasing old references. No solver step can interleave.
    Native->AddSuppression(Keys);
    Native->ReleaseSuppression(Record.Suppression);
    Record.Suppression = MoveTemp(Keys);
    RefreshDiagnostics();
    return {};
}

bool UProphecyJoltWorldSubsystem::SetRigJointDamping(FGuid WorldLifetime,int32 BodySlot,int64 BodyGeneration,int32 SourceConstraintIndex,
    float Damping,FString& OutError)
{
    OutError.Reset();
    const auto Ready=ValidateReady();
    if (!Ready.IsSuccess()) { OutError=Ready.Message; return false; }
    if (!FMath::IsFinite(Damping) || Damping<0 || SourceConstraintIndex<INDEX_NONE)
    { OutError=TEXT("Joint damping must be finite and nonnegative."); return false; }
    const FProphecyJoltBodyHandle Body{WorldLifetime,BodySlot,uint64(BodyGeneration)};
    const auto* Slot=Native->Find(Body);
    auto* Rig=Slot ? Native->FindRig(Slot->OwnerRig) : nullptr;
    if (!Rig || Rig->Constraints.Num()!=Rig->JointDescriptions.Num())
    { OutError=TEXT("A healthy live Jolt skeletal rig is required."); return false; }
    TArray<JPH::SixDOFConstraint*,TInlineAllocator<32>> Selected;
    for (int32 I=0;I<Rig->Constraints.Num();++I)
        if (SourceConstraintIndex==INDEX_NONE || Rig->JointDescriptions[I].SourceConstraintIndex==SourceConstraintIndex)
        {
            auto* Joint=ProphecyJolt::GetSixDOF(Rig->Constraints[I].GetPtr());
            if (!Joint) { OutError=TEXT("Unsupported native anatomical joint."); return false; }
            Selected.Add(Joint);
        }
    if (Selected.IsEmpty()) { OutError=TEXT("The requested inbound joint is not in the live Jolt rig."); return false; }
    // Entire selection validated before mutation. No per-step polling or separate force controller.
    for (auto* Joint:Selected)
        if (ProphecyJolt::SetJointDamping(*Joint,Damping))
            for (const auto* Endpoint:{Joint->GetBody1(),Joint->GetBody2()})
                if (Endpoint->IsDynamic()) Native->Physics.GetBodyInterface().ActivateBody(Endpoint->GetID());
    return true;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigCCDMode(const FProphecyJoltRigHandle& Handle, uint8 Mode)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    auto* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Invalid Jolt rig."));
    if (Mode > 2) return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Unknown Jolt CCD mode."));
    auto& Bodies = Native->Physics.GetBodyInterface();
    for (int32 I = 0; I < Rig->Handles.Num(); ++I)
    {
        auto* Slot = Native->Find(Rig->Handles[I]);
        bool bCCD = Mode == 2 || (Mode == 0 && Rig->AuthoredCCD[I] != 0);
        if (Mode == 0 && Slot->Weld)
            bCCD |= Slot->Weld->Source->GetMotionProperties()->GetMotionQuality() == JPH::EMotionQuality::LinearCast;
        // OriginalQuality is the quality to restore after detaching, without the sword policy.
        if (Slot->Weld)
            Slot->Weld->OriginalQuality = Rig->AuthoredCCD[I] ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete;
        Bodies.SetMotionQuality(Slot->Body,bCCD ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete);
    }
    Rig->CCDMode = Mode;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigSolverIterations(const FProphecyJoltRigHandle& Handle, int32 Velocity, int32 Position)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    auto* Rig = Native->FindRig(Handle);
    if (!Rig) return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Invalid Jolt rig."));
    if (Velocity < 0 || Velocity > 128 || Position < 0 || Position > 128)
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Solver iterations must be in 0..128; zero restores world defaults."));
    for (auto& C : Rig->Constraints)
    {
        C->SetNumVelocityStepsOverride(Velocity); C->SetNumPositionStepsOverride(Position);
        auto* Six = ProphecyJolt::GetSixDOF(C.GetPtr());
        Six->SetNumVelocityStepsOverride(Velocity); Six->SetNumPositionStepsOverride(Position);
    }
    if (auto* Entries=FootExtensions.Find(Rig)) for (auto& Entry:*Entries)
    {
        Entry.Translation->SetNumVelocityStepsOverride(Velocity);
        Entry.Translation->SetNumPositionStepsOverride(Position);
    }
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::UpdateBodySuppressedPairs(
    const FProphecyJoltBodyHandle& Handle, TConstArrayView<FProphecyJoltBodyPair> Pairs)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Native->Find(Handle)) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Invalid collision owner body."));
    for (const auto& Pair : Pairs)
        if (!SameBody(Pair.A, Handle) && !SameBody(Pair.B, Handle))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Body-owned exclusions must involve their owner."));
    TArray<FSuppressionKey> Keys;
    const auto Prepared = Native->PrepareSuppression(Pairs, Keys);
    if (!Prepared.IsSuccess()) return Prepared;
    auto& Owned = Native->Slots[Handle.Slot].OwnedSuppression;
    if (Owned == Keys) return {};
    Native->AddSuppression(Keys);
    Native->ReleaseSuppression(Owned);
    Owned = MoveTemp(Keys);
    RefreshDiagnostics();
    return {};
}

bool UProphecyJoltWorldSubsystem::IsBodyShapeWelded(const FProphecyJoltBodyHandle& Handle) const
{
    const auto* Slot=IsInGameThread() && !bStepInProgress && Native ? Native->Find(Handle) : nullptr;
    return Slot && Slot->WeldParent.IsSet();
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetWeldedBodyInertiaScale(const FProphecyJoltBodyHandle& Source, float Scale)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready=ValidateReady(); if(!Ready.IsSuccess()) return Ready;
    if (!FMath::IsFinite(Scale) || Scale<0)
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Attached inertia scale must be finite and nonnegative."));
    const auto* SourceSlot=Native->Find(Source);
    const auto* Parent=SourceSlot ? Native->Find(SourceSlot->WeldParent) : nullptr;
    if (!Parent || !Parent->Weld)
        return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Attached inertia requires a live welded collider."));
    auto& Record=*Parent->Weld;
    if (Scale==Record.InertiaScale) return {};
    auto Combined=Record.OriginalMass;
    for (int Column=0;Column<3;++Column)
    {
        float Values[4]={};
        for(int Row=0;Row<3;++Row)
        {
            const double Value=double(Record.OriginalMass.mInertia.GetColumn4(Column)[Row])
                + double(Scale)*Record.SwordInertia.GetColumn4(Column)[Row];
            if (!FMath::IsFinite(Value) || FMath::Abs(Value)>MAX_flt)
                return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Attached inertia scale exceeds native precision."));
            Values[Row]=float(Value);
        }
        Combined.mInertia.SetColumn4(Column,JPH::Vec4(Values[0],Values[1],Values[2],0));
    }
    Combined.mInertia.SetColumn4(3,JPH::Vec4(0,0,0,1));
    JPH::Mat44 Rotation; JPH::Vec3 Moments;
    if (!Combined.DecomposePrincipalMomentsOfInertia(Rotation,Moments))
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Attached inertia could not be decomposed safely."));
    for(int Axis=0;Axis<3;++Axis)
        if(!FMath::IsFinite(Moments[Axis]) || Moments[Axis]<=0 || !FMath::IsFinite(1.0f/Moments[Axis]))
            return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Attached inertia has unrepresentable principal moments."));
    {
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(),Parent->Body);
        auto* Motion=Lock.GetBody().GetMotionProperties();
        Motion->SetMassProperties(Motion->GetAllowedDOFs(),Combined);
    }
    Record.InertiaScale=Scale;
    // Changing an explicit setting preserves pose/V/W and discards old contact impulses.
    Native->Physics.GetBodyInterface().InvalidateContactCache(Parent->Body);
    Native->Wake(SourceSlot->WeldParent);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::WeldBodyShape(const FProphecyJoltBodyHandle& Parent,
    const FProphecyJoltBodyHandle& Source, const FTransform& SourceOriginToParentOrigin)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    const auto Ready=ValidateReady(); if(!Ready.IsSuccess()) return Ready;
    const auto* ParentSlot=Native->Find(Parent); const auto* SourceSlot=Native->Find(Source);
    if(!ParentSlot || !SourceSlot || SameBody(Parent,Source))
        return Fail(EProphecyJoltWorldResult::InvalidHandle,TEXT("Welding requires two live distinct bodies."));
    if(SourceSlot->WeldParent.IsSet() && SameBody(SourceSlot->WeldParent,Parent)) return {};
    if(ParentSlot->Weld || ParentSlot->WeldParent.IsSet() || SourceSlot->Weld || SourceSlot->WeldParent.IsSet()
        || SourceSlot->OwnerRig.IsSet() || !SourceSlot->IncidentJoints.IsEmpty() || !RigidJointFrame(SourceOriginToParentOrigin))
        return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Weld requires an independent unconnected source, an unwelded parent and a rigid local frame."));
    auto Record=MakeUnique<FWeldRecord>();
    Record->SourceHandle=Source; Record->SourceToParent=SourceOriginToParentOrigin;
    const JPH::BodyID IDs[]={ParentSlot->Body,SourceSlot->Body};
    JPH::RefConst<JPH::Shape> SourceShape;
    uint64 ParentUserData=0;
    JPH::EMotionQuality SourceQuality;
    JPH::MassProperties SourceMass;
    {
        JPH::BodyLockMultiRead Lock(Native->Physics.GetBodyLockInterface(),IDs,2);
        const auto* P=Lock.GetBody(0); const auto* S=Lock.GetBody(1);
        if(!P || !S || !P->IsInBroadPhase() || !S->IsInBroadPhase() || !P->IsDynamic() || !S->IsDynamic())
            return Fail(EProphecyJoltWorldResult::InvalidArgument,TEXT("Welding starts from two admitted dynamic bodies."));
        Record->OriginalShape=P->GetShape(); SourceShape=S->GetShape(); Record->Source=S;
        Record->OriginalGroup=P->GetCollisionGroup(); Record->OriginalLayer=P->GetObjectLayer();
        Record->OriginalQuality=P->GetMotionProperties()->GetMotionQuality();
        SourceQuality=S->GetMotionProperties()->GetMotionQuality(); ParentUserData=P->GetUserData();
        Record->OriginalMass.mMass=1.0f/P->GetMotionProperties()->GetInverseMass();
        Record->OriginalMass.mInertia=P->GetMotionProperties()->GetLocalSpaceInverseInertia().Inversed3x3();
        SourceMass.mMass=1.0f/S->GetMotionProperties()->GetInverseMass();
        SourceMass.mInertia=S->GetMotionProperties()->GetLocalSpaceInverseInertia().Inversed3x3();
    }
    JPH::StaticCompoundShapeSettings Compound;
    Compound.AddShape(JPH::Vec3::sZero(),JPH::Quat::sIdentity(),Record->OriginalShape.GetPtr());
    Compound.AddShape(ToJoltDirection(SourceOriginToParentOrigin.GetLocation()*CentimetersToMeters),
        ToJoltRotation(SourceOriginToParentOrigin.GetRotation()),SourceShape.GetPtr(),1);
    const auto Built=Compound.Create();
    if(Built.HasError()) return Fail(EProphecyJoltWorldResult::PhysicsFailure,TEXT("Could not build welded collision compound."));
    Record->Compound=static_cast<const JPH::CompoundShape*>(Built.Get().GetPtr());
    Record->WeldedShape=new JPH::OffsetCenterOfMassShape(Built.Get().GetPtr(),Record->OriginalShape->GetCenterOfMass()-Built.Get()->GetCenterOfMass());
    Record->CarrierRoot=Record->WeldedShape.GetPtr();
    const auto SourceRotation=ToJoltRotation(SourceOriginToParentOrigin.GetRotation());
    SourceMass.Rotate(JPH::Mat44::sRotation(SourceRotation));
    SourceMass.Translate(ToJoltDirection(SourceOriginToParentOrigin.GetLocation()*CentimetersToMeters)
        + SourceRotation*SourceShape->GetCenterOfMass()-Record->OriginalShape->GetCenterOfMass());
    Record->SwordInertia=SourceMass.mInertia;
    FCollisionProfile Carrier; Carrier.BlockMask=MAX_uint32; Carrier.bCompoundCarrier=true;
    TArray<JPH::ObjectLayer> CarrierLayers;
    const auto Interned=Native->CollisionProfiles.Intern({Carrier},CarrierLayers);
    if(!Interned.IsSuccess()) return Interned;
    const uint64 Pointer=uint64(reinterpret_cast<UPTRINT>(static_cast<ProphecyJolt::Material::FAttachedMaterialData*>(Record.Get())));
    check((Pointer & (ProphecyJolt::Material::AttachedMarker | 15))==0 && (ParentUserData & ~uint64(15))==0);
    auto& Bodies=Native->Physics.GetBodyInterface();
    Bodies.RemoveBody(SourceSlot->Body);
    Bodies.SetShape(ParentSlot->Body,Record->WeldedShape.GetPtr(),false,JPH::EActivation::Activate);
    Bodies.SetUserData(ParentSlot->Body,Pointer|ProphecyJolt::Material::AttachedMarker|ParentUserData);
    Bodies.SetCollisionGroup(ParentSlot->Body,JPH::CollisionGroup());
    Bodies.SetObjectLayer(ParentSlot->Body,CarrierLayers[0]);
    const auto* Rig = Native->FindRig(ParentSlot->OwnerRig);
    if (Rig && Rig->CCDMode != 0)
        Bodies.SetMotionQuality(ParentSlot->Body,Rig->CCDMode == 2 ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete);
    else if(SourceQuality==JPH::EMotionQuality::LinearCast) Bodies.SetMotionQuality(ParentSlot->Body,SourceQuality);
    Native->Slots[Source.Slot].WeldParent=Parent;
    Native->Slots[Parent.Slot].Weld=MoveTemp(Record);
    ++Native->WeldCount;
    Native->Physics.SetSimShapeFilter(&Native->ScopedPairFilter);
    Bodies.InvalidateContactCache(ParentSlot->Body);
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyKinematic(const FProphecyJoltBodyHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Invalid kinematic body."));
    if (Slot->OwnerRig.IsSet()) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Rig motion belongs to its character controller."));
    auto& Bodies = Native->Physics.GetBodyInterface();
    if (Bodies.GetMotionType(Slot->Body) == JPH::EMotionType::Static)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("A static body cannot become an attached mover."));
    Bodies.SetMotionType(Slot->Body, JPH::EMotionType::Kinematic, JPH::EActivation::Activate);
    Bodies.SetLinearAndAngularVelocity(Slot->Body, JPH::Vec3::sZero(), JPH::Vec3::sZero());
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::MoveKinematicBody(const FProphecyJoltBodyHandle& Handle,
    const FTransform& TargetBodyOrigin, float DeltaSeconds)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Invalid kinematic body."));
    if (!RigidJointFrame(TargetBodyOrigin) || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Kinematic target and step duration must be valid."));
    auto& Bodies = Native->Physics.GetBodyInterface();
    if (Bodies.GetMotionType(Slot->Body) != JPH::EMotionType::Kinematic)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("MoveKinematic requires a kinematic body."));
    Bodies.MoveKinematic(Slot->Body, ToJoltPosition(TargetBodyOrigin.GetLocation()),
        ToJoltRotation(TargetBodyOrigin.GetRotation()), DeltaSeconds);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyDynamic(const FProphecyJoltBodyHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady(); if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot || Slot->OwnerRig.IsSet()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Not an independent Jolt body."));
    auto& Bodies = Native->Physics.GetBodyInterface();
    if (Bodies.GetMotionType(Slot->Body) == JPH::EMotionType::Static)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("A static collider must be recaptured with dynamic mass first."));
    Bodies.SetMotionType(Slot->Body, JPH::EMotionType::Dynamic, JPH::EActivation::Activate);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyPose(const FProphecyJoltBodyHandle& Handle, const FTransform& Pose)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    const auto Ready = ValidateReady(); if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot || Slot->OwnerRig.IsSet() || !RigidJointFrame(Pose))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid independent body pose."));
    Native->Physics.GetBodyInterface().SetPositionAndRotation(Slot->Body,
        ToJoltPosition(Pose.GetLocation()), ToJoltRotation(Pose.GetRotation()), JPH::EActivation::Activate);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyRuntimeSettings(const FProphecyJoltBodyHandle& Handle,
    bool bGravity, float LinearDamping, float AngularDamping, bool bCCD)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady(); if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot || Slot->OwnerRig.IsSet() || !FMath::IsFinite(LinearDamping) || !FMath::IsFinite(AngularDamping)
        || LinearDamping < 0 || AngularDamping < 0)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Invalid independent body settings."));
    {
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
        if (!Lock.Succeeded() || Lock.GetBody().IsStatic()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body has no motion properties."));
        auto* Motion = Lock.GetBody().GetMotionProperties();
        Motion->SetGravityFactor(bGravity ? 1.0f : 0.0f);
        Motion->SetLinearDamping(LinearDamping);
        Motion->SetAngularDamping(AngularDamping);
    }
    Native->Physics.GetBodyInterface().SetMotionQuality(Slot->Body, bCCD ? JPH::EMotionQuality::LinearCast : JPH::EMotionQuality::Discrete);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyMassKg(
    const FProphecyJoltBodyHandle& Handle, float MassKg)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    if (!FMath::IsFinite(MassKg) || MassKg <= 0 || !FMath::IsFinite(1.0f / MassKg))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Mass must be positive and have a finite inverse."));
    {
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
        if (!Lock.SucceededAndIsInBroadPhase()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body is absent from Jolt."));
        auto& Body = Lock.GetBody();
        if (!Body.IsDynamic()) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Mass scaling requires a dynamic body."));
        auto* Motion = Body.GetMotionProperties();
        const float OldInverse = Motion->GetInverseMass();
        const float Ratio = (1.0f / MassKg) / OldInverse;
        const JPH::Vec3 Inertia = Motion->GetInverseInertiaDiagonal() * Ratio;
        if (OldInverse <= 0 || !FMath::IsFinite(Ratio) || Ratio <= 0
            || !FMath::IsFinite(Inertia.GetX()) || !FMath::IsFinite(Inertia.GetY()) || !FMath::IsFinite(Inertia.GetZ()))
            return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Mass scaling exceeds finite inertia precision."));
        Motion->ScaleToMass(MassKg);
    }
    Native->Physics.GetBodyInterface().ActivateBody(Slot->Body);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadJoint(const FProphecyJoltJointHandle& Handle,
    FProphecyJoltJointSettings& OutSettings) const
{
    using namespace ProphecyJolt::WorldPrivate;
    OutSettings = {};
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FJointRecord* Record = Native->FindJoint(Handle);
    if (!Record) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world joint handle."));
    OutSettings = Record->Settings;
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ReadJointReaction(const FProphecyJoltJointHandle& Handle,
    FVector& Force, FVector& Torque) const
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    Force = Torque = FVector::ZeroVector;
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FJointRecord* Record = Native->FindJoint(Handle);
    if (!Record) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("No live joint for reaction readback."));
    if (!Diagnostics.CompletedSteps) return {};
    const double Seconds = Diagnostics.LastRequestedDeltaSeconds / double(FMath::Max(1, Diagnostics.LastCollisionSteps));
    if (Seconds <= 0) return {};
    JPH::Vec3 Linear, Angular;
    if (Record->Settings.Type == EProphecyJoltJointType::HardSixDOF)
    {
        if (Record->Settings.bRadialTranslation)
        {
            const auto* Radial = static_cast<const ProphecyJolt::FRadialJoint*>(Record->Constraint.GetPtr());
            Linear = Radial->GetLinearImpulse(); Angular = Radial->GetAngularImpulse();
        }
        else
        {
            const auto* Six = static_cast<const JPH::SixDOFConstraint*>(Record->Constraint.GetPtr());
            Linear = Six->GetTotalWorldSpaceLinearImpulse(); Angular = Six->GetTotalWorldSpaceAngularImpulse();
        }
    }
    else
    {
        const auto* Fixed = static_cast<const JPH::FixedConstraint*>(Record->Constraint.GetPtr());
        Linear = Fixed->GetTotalLambdaPosition(); Angular = Fixed->GetTotalLambdaRotation();
    }
    Force = FromJoltDirection(Linear) * (100. / Seconds);
    Torque = FromJoltDirection(Angular) * (10000. / Seconds);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::DestroyJoint(const FProphecyJoltJointHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Joint destruction requires the game thread."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Cannot destroy a joint during a physics step."));
    if (!Native || !Native->FindJoint(Handle))
        return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world joint handle."));
    Native->DestroyJointSlot(Handle.Slot);
    RefreshDiagnostics();
    return {};
}

bool UProphecyJoltWorldSubsystem::OwnsJoint(const FProphecyJoltJointHandle& Handle) const
{
    return IsInGameThread() && !bStepInProgress && Native && Native->FindJoint(Handle);
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyServoFollow(const FProphecyJoltBodyHandle& Handle,
    const FVector& Linear, const FVector& Angular)
{
    using namespace ProphecyJolt::WorldPrivate;
    const auto Ready=ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Slot=Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Invalid servo body handle."));
    if (Linear.ContainsNaN() || Angular.ContainsNaN() || Linear.GetMin()<0. || Linear.GetMax()>1.
        || Angular.GetMin()<0. || Angular.GetMax()>1.)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Servo follow weights must be finite and in [0,1]."));
    Native->Servo.SetBodyFollow(Slot->Body,Linear,Angular);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyVelocity(const FProphecyJoltBodyHandle& Handle,
    const FVector& CenterOfMassVelocityCmPerSecond, const FVector& AngularVelocityRadiansPerSecond, bool bWake)
{
    using namespace ProphecyJolt::WorldPrivate;
    using namespace ProphecyJolt::Conversions;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FBodySlot* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    if (!FitsFloatVector(CenterOfMassVelocityCmPerSecond, CentimetersToMeters)
        || !FitsFloatVector(AngularVelocityRadiansPerSecond, 1.0))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("COM and angular velocity must fit finite native precision."));
    const JPH::Vec3 Linear = ToJoltLinearVelocity(CenterOfMassVelocityCmPerSecond);
    const JPH::Vec3 Angular = ToJoltAngularVelocity(AngularVelocityRadiansPerSecond);
    if (!FMath::IsFinite(Linear.LengthSq()) || !FMath::IsFinite(Angular.LengthSq()))
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Velocity magnitude exceeds finite native clamping arithmetic."));
    {
        JPH::BodyLockWrite Lock(Native->Physics.GetBodyLockInterface(), Slot->Body);
        if (!Lock.SucceededAndIsInBroadPhase()) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Body is absent from Jolt."));
        JPH::Body& Body = Lock.GetBody();
        if (!Body.IsDynamic()) return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Velocity writes require a dynamic body."));
        // BodyInterface setters implicitly activate; use the locked body so the explicit wake
        // policy survives carried/drop transitions and a rejected request never partially writes.
        Body.SetLinearVelocityClamped(Linear);
        Body.SetAngularVelocityClamped(Angular);
    }
    if (bWake) Native->Physics.GetBodyInterface().ActivateBody(Slot->Body);
    RefreshDiagnostics();
    return {};
}

bool UProphecyJoltWorldSubsystem::OwnsBody(const FProphecyJoltBodyHandle& Handle) const
{
    return IsInGameThread() && !bStepInProgress && Native && Native->Find(Handle);
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::DestroyBody(const FProphecyJoltBodyHandle& Handle)
{
    using namespace ProphecyJolt::WorldPrivate;
    if (!IsInGameThread()) return Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Body destruction requires the game thread."));
    if (bStepInProgress) return Fail(EProphecyJoltWorldResult::Busy, TEXT("Cannot destroy a body during a physics step."));
    if (!Native || !Native->Find(Handle)) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    if (Native->Slots[Handle.Slot].OwnerRig.IsSet())
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("A rig body cannot be removed independently; destroy its owning rig to remove constraints and invalidate the complete rig safely."));
    Native->DestroySlot(Handle.Slot);
    RefreshDiagnostics();
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::ResolveAssociatedObject(const FProphecyJoltBodyHandle& Handle, UObject*& OutObject) const
{
    using namespace ProphecyJolt::WorldPrivate;
    OutObject = nullptr;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const FBodySlot* Slot = Native->Find(Handle);
    if (!Slot) return Fail(EProphecyJoltWorldResult::InvalidHandle, TEXT("Stale, unset or cross-world body handle."));
    OutObject = Slot->AssociatedObject.Get();
    return OutObject ? FProphecyJoltWorldStatus{} : Fail(EProphecyJoltWorldResult::AssociationUnavailable, TEXT("Optional object association is absent or expired."));
}


FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetBodyHitEvents(
    const FProphecyJoltBodyHandle& Handle, bool bEnabled)
{
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!Native->Find(Handle)) return ProphecyJolt::WorldPrivate::Fail(
        EProphecyJoltWorldResult::InvalidHandle, TEXT("Hit event body is stale."));
    Native->SetHitEnabled(Native->Slots[Handle.Slot], bEnabled);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::SetRigHitEvents(
    const FProphecyJoltRigHandle& Handle, UPrimitiveComponent* Receiver, bool bEnabled)
{
    const auto Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    const auto* Rig = Native->FindRig(Handle);
    if (!Rig || !IsValid(Receiver) || Receiver->GetWorld() != GetWorld())
        return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Hit event rig/receiver is unavailable."));
    for (const auto& Body : Rig->Handles)
    {
        auto& Slot = Native->Slots[Body.Slot];
        Slot.AssociatedObject = Receiver;
        Native->SetHitEnabled(Slot, bEnabled);
    }
    return {};
}

uint64 UProphecyJoltWorldSubsystem::GetDeliveredHitEventCount() const
{
    return IsInGameThread() && Native ? Native->DeliveredHits : 0;
}

void UProphecyJoltWorldSubsystem::DispatchPendingHitEvents()
{
    if (!ValidateReady().IsSuccess() || Native->bDispatchingHits || Native->PendingHits.IsEmpty()) return;
    const FGuid Lifetime = Native->Lifetime;
    Native->bDispatchingHits = true;
    TArray<FProphecyJoltPendingHit> Hits;
    Swap(Hits, Native->PendingHits);
    // Worker scheduling must not determine callback order. Aggregate subshapes/substeps per body pair.
    for (auto& Hit : Hits)
        if (Hit.Body1.Slot > Hit.Body2.Slot)
        {
            Swap(Hit.Body1, Hit.Body2); Swap(Hit.Point1, Hit.Point2);
            Hit.Normal = -Hit.Normal; Hit.Impulse = -Hit.Impulse;
        }
    Hits.Sort([](const auto& A, const auto& B) {
        if (A.Body1.Slot != B.Body1.Slot) return A.Body1.Slot < B.Body1.Slot;
        if (A.Body2.Slot != B.Body2.Slot) return A.Body2.Slot < B.Body2.Slot;
        if (A.Point1.X != B.Point1.X) return A.Point1.X < B.Point1.X;
        if (A.Point1.Y != B.Point1.Y) return A.Point1.Y < B.Point1.Y;
        return A.Point1.Z < B.Point1.Z;
    });
    for (int32 I = 0; I < Hits.Num(); ++I)
    {
        auto& Hit = Hits[I];
        while (I + 1 < Hits.Num() && Hit.Body1.Slot == Hits[I+1].Body1.Slot && Hit.Body2.Slot == Hits[I+1].Body2.Slot)
            Hit.Impulse += Hits[++I].Impulse;
        for (int32 Side = 0; Side < 2; ++Side)
        {
            // A previous delegate may destroy a body, disable notifications or shut down the world.
            if (!Native || Native->Lifetime != Lifetime || !ValidateReady().IsSuccess()) return;
            const auto* Mine = Native->Find(Side ? Hit.Body2 : Hit.Body1);
            const auto* Other = Native->Find(Side ? Hit.Body1 : Hit.Body2);
            if (!Mine || !Other || !Mine->bHitEvents) continue;
            auto* MyComp = Cast<UPrimitiveComponent>(Mine->AssociatedObject.Get());
            auto* OtherComp = Cast<UPrimitiveComponent>(Other->AssociatedObject.Get());
            AActor* Actor = MyComp ? MyComp->GetOwner() : nullptr;
            if (!IsValid(MyComp) || !IsValid(OtherComp) || !IsValid(Actor) || Actor->IsActorBeingDestroyed()) continue;
            FRigidBodyCollisionInfo MyInfo, OtherInfo;
            MyInfo.Component = MyComp; MyInfo.Actor = Actor;
            MyInfo.BoneName = Mine->HitBone; MyInfo.BodyIndex = Mine->HitBodyIndex;
            OtherInfo.Component = OtherComp; OtherInfo.Actor = OtherComp->GetOwner();
            OtherInfo.BoneName = Other->HitBone; OtherInfo.BodyIndex = Other->HitBodyIndex;
            FCollisionImpactData Impact;
            Impact.TotalNormalImpulse = Side ? Hit.Impulse : -Hit.Impulse;
            const auto* MyBody = MyComp->GetBodyInstance(Mine->HitBone);
            const auto* OtherBody = OtherComp->GetBodyInstance(Other->HitBone);
            Impact.ContactInfos.Emplace(Side ? Hit.Point1 : Hit.Point2, Side ? Hit.Normal : -Hit.Normal,
                float(FMath::Max(0.0, FVector::DotProduct(Hit.Point1 - Hit.Point2, Hit.Normal))), false,
                MyBody ? MyBody->GetSimplePhysicalMaterial() : nullptr,
                OtherBody ? OtherBody->GetSimplePhysicalMaterial() : nullptr);
            ++Native->DeliveredHits;
            Actor->DispatchPhysicsCollisionHit(MyInfo, OtherInfo, Impact);
        }
    }
    if (Native && Native->Lifetime == Lifetime)
    {
        Native->bDispatchingHits = false;
        Hits.Reset(); Swap(Hits, Native->PendingHits);
    }
}

void UProphecyJoltWorldSubsystem::RefreshDiagnostics()
{
    check(IsInGameThread());
    if (!Native) return;
    Diagnostics.bInitialized = true;
    Diagnostics.bNoLockIdleBodyReads = Native->bNoLockIdleBodyReads;
    Diagnostics.BodyCount = Native->Physics.GetNumBodies();
    Diagnostics.ActiveRigidBodyCount = Native->Physics.GetNumActiveBodies(JPH::EBodyType::RigidBody);
    Diagnostics.ConstraintCount = static_cast<uint32>(Native->Physics.GetConstraints().size());
    Diagnostics.CollisionProfileCount = Native->CollisionProfiles.Num();
    Diagnostics.GenericJointCount = Native->JointCount;
    Diagnostics.SuppressedBodyPairCount = static_cast<uint32>(Native->Suppression.Num());
    Diagnostics.JobConcurrency = Native->Jobs->GetMaxConcurrency();
    Diagnostics.BodyCreationFailures = Native->CreationFailures;
    Diagnostics.TempPeakBytes = Native->Temp.Peak;
    Diagnostics.TempCurrentBytes = Native->Temp.GetUsage();
    Diagnostics.TempAllocationCount = Native->Temp.AllocationCount;
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::Step(float DeltaSeconds, int32 CollisionSteps)
{
    using namespace ProphecyJolt::WorldPrivate;
    const FProphecyJoltWorldStatus Ready = ValidateReady();
    if (!Ready.IsSuccess()) return Ready;
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f || CollisionSteps <= 0
        || DeltaSeconds / static_cast<float>(CollisionSteps) <= 0.0f)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Step requires a positive finite interval and positive collision-step count."));
    if (Native->bDispatchingHits)
        return Fail(EProphecyJoltWorldResult::InvalidArgument, TEXT("Cannot recursively step from a hit callback."));
    Native->PendingHits.Reset();
    TGuardValue<bool> Guard(bStepInProgress, true);
    Diagnostics.LastRequestedDeltaSeconds = DeltaSeconds;
    Diagnostics.LastCollisionSteps = CollisionSteps;
    const double Started = FPlatformTime::Seconds();
    Diagnostics.LastServoPrepareWallSeconds = Diagnostics.LastActivationWallSeconds = 0.0;
    Diagnostics.LastPhysicsUpdateWallSeconds = Diagnostics.LastServoCaptureWallSeconds = 0.0;
    Diagnostics.LastValidationWallSeconds = 0.0;
    // Prepare target-driven activation before Jolt snapshots its active list,
    // so controlled bodies receive gravity/force/damping on the first awake step.
    FString ActivationError;
    const bool bPrepared = Native->PrepareServoPacket(ActivationError);
    const double PreparedAt = FPlatformTime::Seconds();
    Diagnostics.LastServoPrepareWallSeconds = PreparedAt - Started;
    const bool bActivated = bPrepared && Native->Servo.PrepareActivation(Native->Physics, ActivationError,
        Native->bNoLockIdleBodyReads, DeltaSeconds / float(CollisionSteps));
    const double ActivatedAt = FPlatformTime::Seconds();
    Diagnostics.LastActivationWallSeconds = ActivatedAt - PreparedAt;
    if (!bActivated)
    {
        Diagnostics.LastStepWallSeconds = FPlatformTime::Seconds() - Started;
        Diagnostics.bFaulted = true;
        Diagnostics.Failure = ActivationError;
        RefreshDiagnostics();
        return { EProphecyJoltWorldResult::PhysicsFailure, Diagnostics.Failure };
    }
    // No accumulator, tick subscription, fixed-step substitution, delta clamp or automatic catch-up policy.
    if (ProphecyJolt::PHATSweeps::HasRequests(GetWorld()))
    {
        TArray<ProphecyJolt::PHATSweeps::FBody> Selected;
        TArray<uint32> Candidates;
        for (const auto& Slot : Native->Slots)
        {
            if (Slot.Body.IsInvalid() || Slot.WeldParent.IsSet()) continue;
            Candidates.Add(Slot.Body.GetIndexAndSequenceNumber());
            const auto* Component = Cast<UPrimitiveComponent>(Slot.AssociatedObject.Get());
            if (!Slot.OwnerRig.IsSet() || !Component || Component->GetFName() != TEXT("PhysicalMesh")) continue;
            if (const auto* Settings = ProphecyJolt::PHATSweeps::Find(Component->GetOwner()))
                Selected.Add({Slot.Body.GetIndexAndSequenceNumber(), *Settings});
        }
        ProphecyJolt::PHATSweeps::Publish(&Native->Physics, &Native->ObjectPairs, MoveTemp(Selected), MoveTemp(Candidates),
            Native->HitEnabledBodies ? Native.Get() : nullptr);
    }
    else ProphecyJolt::PHATSweeps::Forget(&Native->Physics);
    const uint64 PreviousServoInvocations = Native->Servo.GetInvocationCount();
    const JPH::EPhysicsUpdateError Result = Native->Physics.Update(DeltaSeconds, CollisionSteps, &Native->Temp, Native->Jobs.Get());
    const double UpdatedAt = FPlatformTime::Seconds();
    Diagnostics.LastPhysicsUpdateWallSeconds = UpdatedAt - ActivatedAt;
    // A numerical fault is contained inside Jolt before invalid transforms are
    // committed. Do not capture servo samples or publish any part of this step.
    if ((Result & JPH::EPhysicsUpdateError::NumericalFailure) != JPH::EPhysicsUpdateError::None)
    {
        Diagnostics.LastUpdateErrorBits = static_cast<uint32>(Result);
        Diagnostics.LastStepWallSeconds = UpdatedAt - Started;
        Diagnostics.bFaulted = true;
        Diagnostics.Failure = TEXT("Jolt stopped safely after a numerical solver failure; the last published pose is retained. Stop Play and restart the simulation to reset it.");
        RefreshDiagnostics();
        UE_LOG(LogProphecyJoltWorld, Warning, TEXT("%s"), *Diagnostics.Failure);
        return { EProphecyJoltWorldResult::PhysicsFailure, Diagnostics.Failure };
    }
    Native->CaptureServoSamples(PreviousServoInvocations);
    const double CapturedAt = FPlatformTime::Seconds();
    Diagnostics.LastServoCaptureWallSeconds = CapturedAt - UpdatedAt;
    Diagnostics.LastStepWallSeconds = CapturedAt - Started;
    Diagnostics.LastUpdateErrorBits = static_cast<uint32>(Result);
    RefreshDiagnostics();
    if (Native->Servo.GetInvalidBodyCount() != 0)
    {
        Diagnostics.bFaulted = true;
        Diagnostics.Failure = TEXT("Jolt fixture servo encountered invalid body state or a velocity overflow; explicit shutdown is required.");
        return { EProphecyJoltWorldResult::PhysicsFailure, Diagnostics.Failure };
    }
    if (Result != JPH::EPhysicsUpdateError::None || Diagnostics.TempCurrentBytes != 0)
    {
        Diagnostics.bFaulted = true;
        Diagnostics.Failure = FString::Printf(TEXT("Jolt Update failed: error bits 0x%x, remaining temporary bytes %llu."),
            Diagnostics.LastUpdateErrorBits, Diagnostics.TempCurrentBytes);
        return { EProphecyJoltWorldResult::PhysicsFailure, Diagnostics.Failure };
    }
    const double ValidationStarted = FPlatformTime::Seconds();
    for (const auto& Slot : Native->Slots)
    {
        if (Slot.Body.IsInvalid()) continue;
        const JPH::BodyLockRead Lock(Native->IdleBodyReadLocks(), Slot.Body);
        bool bValid = Lock.SucceededAndIsInBroadPhase();
        if (Slot.WeldParent.IsSet())
        {
            const auto* Parent = Native->Find(Slot.WeldParent);
            bValid = Lock.Succeeded() && !Lock.GetBody().IsInBroadPhase()
                && Parent && Parent->Weld && Parent->Weld->Source == &Lock.GetBody();
        }
        if (bValid)
        {
            const JPH::Body& Body = Lock.GetBody();
            bValid = Finite(ProphecyJolt::Conversions::FromJoltPosition(Body.GetPosition()))
                && Finite(ProphecyJolt::Conversions::FromJoltPosition(Body.GetCenterOfMassPosition()))
                && !ProphecyJolt::Conversions::FromJoltRotation(Body.GetRotation()).ContainsNaN()
                && Finite(ProphecyJolt::Conversions::FromJoltLinearVelocity(Body.GetLinearVelocity()))
                && Finite(ProphecyJolt::Conversions::FromJoltAngularVelocity(Body.GetAngularVelocity()));
        }
        if (!bValid)
        {
            Diagnostics.bFaulted = true;
            Diagnostics.Failure = TEXT("Jolt body registry/state is invalid after Update; explicit shutdown is required.");
            Diagnostics.LastValidationWallSeconds = FPlatformTime::Seconds() - ValidationStarted;
            return { EProphecyJoltWorldResult::PhysicsFailure, Diagnostics.Failure };
        }
    }
    Diagnostics.LastValidationWallSeconds = FPlatformTime::Seconds() - ValidationStarted;
    ++Diagnostics.CompletedSteps;
    Diagnostics.SimulatedSeconds += static_cast<double>(DeltaSeconds);
    return {};
}

FProphecyJoltWorldStatus UProphecyJoltWorldSubsystem::GetDiagnostics(FProphecyJoltWorldDiagnostics& OutDiagnostics) const
{
    if (!IsInGameThread()) return ProphecyJolt::WorldPrivate::Fail(EProphecyJoltWorldResult::WrongThread, TEXT("Diagnostics require the game thread."));
    OutDiagnostics = Diagnostics;
    return {};
}

int32 UProphecyJoltWorldSubsystem::GetLiveSimulationCount()
{
    return ProphecyJolt::WorldPrivate::LiveSimulations.load(std::memory_order_relaxed);
}
