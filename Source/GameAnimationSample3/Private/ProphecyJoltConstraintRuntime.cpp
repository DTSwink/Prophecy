#include "ProphecyJoltConstraintRuntime.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSkeletalPropComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "Engine/World.h"
#include "UObject/UObjectArray.h"
#include "UObject/UObjectIterator.h"
#include "Containers/Queue.h"
#include "Engine/SkeletalMesh.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltPose.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"
#include "ProphecyJoltConstrainedSkeleton.inl"

namespace ProphecyJolt::Constraints
{
namespace
{
#include "ProphecyOptimisedSwordCut.inl"
struct FBinding
{
    FProphecyJoltJointHandle Joint;
    FProphecyJoltJointSettings Settings;
    FConstraintProfileProperties Profile;
    FTransform SourceFrames[2];
    float Scale = 1.f;
    bool bCaptured = false;
    FString Error;
    TOptional<SwordCuts::FState> SwordCut;
};
struct FWorldBindings
{
    TMap<TWeakObjectPtr<UPhysicsConstraintComponent>, FBinding> Bindings;
    FProphecyJoltBodyHandle WorldAnchor;
};
TMap<TWeakObjectPtr<UWorld>, FWorldBindings> Worlds;
TSet<TWeakObjectPtr<UPhysicsConstraintComponent>> Pending;
TSet<TWeakObjectPtr<UPhysicsConstraintComponent>> Suspended;

// Listen only while a Jolt scene exists. Construction notifications do not inspect
// unfinished components or mutate physics; the shared-step boundary drains them.
class FCreationListener final : public FUObjectArray::FUObjectCreateListener
{
public:
    const UClass* ConstraintClass = nullptr;
    TQueue<FWeakObjectPtr, EQueueMode::Mpsc> Created;
    virtual void NotifyUObjectCreated(const UObjectBase* Object, int32) override
    {
        if (Object->GetClass() && Object->GetClass()->IsChildOf(ConstraintClass))
            Created.Enqueue(FWeakObjectPtr(static_cast<const UObject*>(Object)));
    }
    virtual void OnUObjectArrayShutdown() override { GUObjectArray.RemoveUObjectCreateListener(this); }
} Listener;

bool SameBody(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{ return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation; }

FName PikeWoundTag()
{
    static const FName Tag(TEXT("Prophecy.PikeWoundCorrection"));
    return Tag;
}

bool IsPikeSlider(const FConstraintProfileProperties& Profile)
{
    return Profile.LinearLimit.XMotion == LCM_Locked && Profile.LinearLimit.YMotion == LCM_Locked
        && Profile.LinearLimit.ZMotion != LCM_Locked && !Profile.LinearLimit.bSoftConstraint
        && Profile.TwistLimit.TwistMotion == ACM_Locked
        && Profile.ConeLimit.Swing1Motion == ACM_Locked && Profile.ConeLimit.Swing2Motion == ACM_Locked;
}

void Retire(UProphecyJoltWorldSubsystem& Native, FBinding& Binding)
{
    if (Native.OwnsJoint(Binding.Joint)) Native.DestroyJoint(Binding.Joint);
    Binding.Joint = {}; Binding.bCaptured = false;
    Binding.Error.Reset();
}

bool BodyFor(UPrimitiveComponent* Mesh, FName Bone, UWorld& World, FProphecyJoltBodyHandle& Body, FString& Error)
{
    if (!IsValid(Mesh) || !Mesh->IsRegistered() || Mesh->GetWorld() != &World) return false;
    if (auto* Agent = Cast<AProphecyAgent>(Mesh->GetOwner()); Agent && Agent->GetPoseReferenceMesh() == Mesh)
        if (auto* Character = Agent->GetJoltCharacterComponent(); Character && Character->IsJoltPhysical())
            return Character->GetBodyHandle(Bone, Body);
    if (auto* Skeleton=Cast<USkeletalMeshComponent>(Mesh))
    {
        if (Cast<AProphecyAgent>(Mesh->GetOwner())) return false;
        // A placed mannequin already owns its articulation. Its Unreal bodies
        // are deliberately query-only and must never be captured as a new rig.
        if (auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Skeleton))
        {
            if (Prop->GetBodyHandle(Bone, Body)) return true;
            if (Prop->IsJoltStepClientActive())
                Error = FString::Printf(TEXT("Bone %s has no Jolt body on %s."), *Bone.ToString(), *Skeleton->GetPathName());
            return false; // Pending/failed admission is not permission to create a second owner.
        }
        return ConstrainedSkeleton::BodyFor(*Skeleton,Bone,Body,Error);
    }
    auto* Scene = UProphecyJoltSceneCollisionComponent::FindForWorld(&World);
    return Scene && Scene->GetBodyHandle(*Mesh, INDEX_NONE, Body);
}

FProphecyJoltAxisLimit Linear(TEnumAsByte<ELinearConstraintMotion> Motion, float Size)
{
    if (Motion == LCM_Free) return { EProphecyJoltAxisMotion::Free, 0, 0 };
    if (Motion == LCM_Locked || Size <= 0) return {};
    return { EProphecyJoltAxisMotion::Limited, -double(Size), double(Size) };
}
FProphecyJoltAxisLimit Angular(TEnumAsByte<EAngularConstraintMotion> Motion, float Degrees)
{
    if (Motion == ACM_Free || (Motion == ACM_Limited && Degrees >= 179.5f))
        return { EProphecyJoltAxisMotion::Free, 0, 0 };
    if (Motion == ACM_Locked || Degrees <= .5f) return {};
    const double Radians = FMath::DegreesToRadians(double(Degrees));
    return { EProphecyJoltAxisMotion::Limited, -Radians, Radians };
}

void Reconcile(UPhysicsConstraintComponent& Component, FBinding& Binding,
    UWorld& World, FWorldBindings& Registry, UProphecyJoltWorldSubsystem& Native)
{
    if (Component.IsBroken() || Suspended.Contains(&Component)) { Retire(Native, Binding); return; }
    UPrimitiveComponent* A = nullptr; UPrimitiveComponent* B = nullptr; FName BoneA, BoneB;
    Component.GetConstrainedComponents(A, BoneA, B, BoneB);
    // A named endpoint that disappeared is not an intentional world anchor.
    if ((!A && (!Component.ComponentName1.ComponentName.IsNone() || Component.OverrideComponent1.IsStale()))
        || (!B && (!Component.ComponentName2.ComponentName.IsNone() || Component.OverrideComponent2.IsStale())))
    { Retire(Native,Binding); return; }
    if (!A && !B) { Retire(Native, Binding); return; }
    FProphecyJoltBodyHandle Bodies[2];
    FString EndpointError;
    if ((A && !BodyFor(A, BoneA, World, Bodies[0],EndpointError)) || (B && !BodyFor(B, BoneB, World, Bodies[1],EndpointError)))
    {
        const FString Previous=Binding.Error; Retire(Native, Binding); Binding.Error=EndpointError;
        if (!EndpointError.IsEmpty() && EndpointError!=Previous)
            UE_LOG(LogTemp,Warning,TEXT("Jolt constraint %s: %s"),*Component.GetPathName(),*EndpointError);
        return;
    } // Admission may be queued. Never bind to the retained Chaos query actor.
    if (!A || !B)
    {
        if (!Native.OwnsBody(Registry.WorldAnchor))
        {
            FProphecyJoltFixtureBodySettings Anchor;
            Anchor.bDynamic = false; Anchor.CollisionResponses.SetAllChannels(ECR_Ignore);
            const auto Made = Native.CreateSphere(.01, Anchor, Registry.WorldAnchor);
            if (!Made.IsSuccess()) { Binding.Error = Made.Message; return; }
        }
        if (!A) Bodies[0] = Registry.WorldAnchor;
        if (!B) Bodies[1] = Registry.WorldAnchor;
    }
    FProphecyJoltBodyState BodyStates[2];
    if (!Native.ReadBody(Bodies[0], BodyStates[0]).IsSuccess() || !Native.ReadBody(Bodies[1], BodyStates[1]).IsSuccess()) return;
    if (!BodyStates[0].bDynamic && !BodyStates[1].bDynamic) { Retire(Native, Binding); return; }
    auto& Instance = Component.ConstraintInstance;
    const auto& Profile = Instance.ProfileInstance;
    const FTransform Frames[] = { Instance.GetRefFrame(EConstraintFrame::Frame1), Instance.GetRefFrame(EConstraintFrame::Frame2) };
    const float Scale = FMath::Max(Component.GetComponentScale().GetAbsMin(), .01);
    // Unreal drives body 1 relative to body 2; Jolt drives body 2 relative to body 1.
    const bool SameEndpoints = Binding.bCaptured && SameBody(Bodies[1], Binding.Settings.BodyA) && SameBody(Bodies[0], Binding.Settings.BodyB);
    const bool SameFrames = SameEndpoints && Frames[0].Equals(Binding.SourceFrames[0], 0) && Frames[1].Equals(Binding.SourceFrames[1], 0) && Scale == Binding.Scale;
    if (SameFrames && Native.OwnsJoint(Binding.Joint)
        && FConstraintProfileProperties::StaticStruct()->CompareScriptStruct(&Profile, &Binding.Profile, 0))
    {
        if (Binding.SwordCut)
        {
            auto Settings = Binding.Settings;
            if (SwordCuts::DirectionalFriction(*Binding.SwordCut, BodyStates[1], BodyStates[0], Settings)
                && Native.UpdateJoint(Binding.Joint, Settings).IsSuccess()) Binding.Settings = Settings;
        }
        return;
    }

    FProphecyJoltJointSettings Settings;
    Settings.Type = EProphecyJoltJointType::HardSixDOF;
    Settings.BodyA = Bodies[1]; Settings.BodyB = Bodies[0];
    FTransform* Destination[] = { &Settings.FrameB, &Settings.FrameA };
    for (int32 I=0; I<2; ++I)
    {
        if (SameFrames) { *Destination[I] = I == 0 ? Binding.Settings.FrameB : Binding.Settings.FrameA; continue; }
        auto Source = Component.GetBodyTransform(I == 0 ? EConstraintFrame::Frame1 : EConstraintFrame::Frame2);
        Source.RemoveScaling();
        auto Frame = Frames[I];
        if (I == 0 ? A != nullptr : B != nullptr) Frame.ScaleTranslation(Scale);
        *Destination[I] = (Frame * Source).GetRelativeTransform(FTransform(BodyStates[I].Rotation, BodyStates[I].PositionCm));
        Destination[I]->RemoveScaling(); Destination[I]->NormalizeRotation();
    }
    const float LimitScale = Instance.bScaleLinearLimits ? Scale : 1.f;
    Settings.Translation[0] = Linear(Profile.LinearLimit.XMotion, Profile.LinearLimit.Limit * LimitScale);
    Settings.Translation[1] = Linear(Profile.LinearLimit.YMotion, Profile.LinearLimit.Limit * LimitScale);
    Settings.Translation[2] = Linear(Profile.LinearLimit.ZMotion, Profile.LinearLimit.Limit * LimitScale);
    int32 LimitedAxes = 0;
    for (const auto& Axis : Settings.Translation) LimitedAxes += Axis.Motion == EProphecyJoltAxisMotion::Limited;
    Settings.bRadialTranslation = LimitedAxes >= 2;
    Settings.Rotation[0] = Angular(Profile.TwistLimit.TwistMotion, Profile.TwistLimit.TwistLimitDegrees);
    Settings.Rotation[1] = Angular(Profile.ConeLimit.Swing2Motion, Profile.ConeLimit.Swing2LimitDegrees);
    Settings.Rotation[2] = Angular(Profile.ConeLimit.Swing1Motion, Profile.ConeLimit.Swing1LimitDegrees);
    auto CopyDrive = [](const FConstraintDrive& From, bool bAcceleration, FProphecyJoltJointDrive& To)
    {
        To.bPosition = From.bEnablePositionDrive; To.bVelocity = From.bEnableVelocityDrive;
        To.bAcceleration = bAcceleration; To.Stiffness = From.Stiffness;
        To.Damping = From.Damping; To.MaximumForce = From.MaxForce;
    };
    CopyDrive(Profile.LinearDrive.XDrive, Profile.LinearDrive.bAccelerationMode, Settings.Drives[0]);
    CopyDrive(Profile.LinearDrive.YDrive, Profile.LinearDrive.bAccelerationMode, Settings.Drives[1]);
    CopyDrive(Profile.LinearDrive.ZDrive, Profile.LinearDrive.bAccelerationMode, Settings.Drives[2]);
    const auto& AngularDrive = Profile.AngularDrive;
    const bool Slerp = AngularDrive.AngularDriveMode == EAngularDriveMode::SLERP;
    const bool SlerpAvailable = !Slerp || (Settings.Rotation[0].Motion != EProphecyJoltAxisMotion::Locked
        && Settings.Rotation[1].Motion != EProphecyJoltAxisMotion::Locked && Settings.Rotation[2].Motion != EProphecyJoltAxisMotion::Locked);
    if (SlerpAvailable) for (int32 I=0; I<3; ++I)
        CopyDrive(Slerp ? AngularDrive.SlerpDrive : (I == 0 ? AngularDrive.TwistDrive : AngularDrive.SwingDrive),
            AngularDrive.bAccelerationMode, Settings.Drives[3+I]);
    Settings.PositionTargetCm = Profile.LinearDrive.PositionTarget;
    Settings.VelocityTargetCmPerSecond = Profile.LinearDrive.VelocityTarget;
    Settings.OrientationTarget = AngularDrive.OrientationTarget.Quaternion();
    Settings.AngularVelocityTargetRadians = AngularDrive.AngularVelocityTarget * (2. * UE_PI);
    if (Binding.SwordCut)
    {
        SwordCuts::Limits(*Binding.SwordCut, Settings);
        SwordCuts::DirectionalFriction(*Binding.SwordCut, BodyStates[1], BodyStates[0], Settings);
    }
    Settings.bSoftTranslation = Profile.LinearLimit.bSoftConstraint;
    Settings.TranslationStiffness = Profile.LinearLimit.Stiffness;
    Settings.TranslationDamping = Profile.LinearLimit.Damping;
    FProphecyJoltBodyPair Pair{ Bodies[0], Bodies[1] };
    TConstArrayView<FProphecyJoltBodyPair> Pairs = Profile.bDisableCollision ? MakeArrayView(&Pair, 1) : TConstArrayView<FProphecyJoltBodyPair>();
    if (!SameEndpoints) Retire(Native, Binding);
    const auto Result = Native.OwnsJoint(Binding.Joint) ? Native.UpdateJoint(Binding.Joint, Settings) : Native.CreateJoint(Settings, Pairs, Binding.Joint);
    if (!Result.IsSuccess())
    {
        if (Binding.Error != Result.Message) UE_LOG(LogTemp, Warning, TEXT("Jolt constraint %s: %s"), *Component.GetPathName(), *Result.Message);
        Binding.Error = Result.Message; return;
    }
    const auto Filter = Native.UpdateJointSuppressedPairs(Binding.Joint, Pairs);
    if (!Filter.IsSuccess())
    {
        if (Binding.Error != Filter.Message) UE_LOG(LogTemp, Warning, TEXT("Jolt constraint %s: %s"), *Component.GetPathName(), *Filter.Message);
        Binding.Error = Filter.Message; return;
    }
    Component.TermComponentConstraint(); // Native joint now owns the connection; keep editable UE settings.
    Binding.Settings = Settings; Binding.Profile = Profile; Binding.Scale = Scale;
    Binding.SourceFrames[0] = Frames[0]; Binding.SourceFrames[1] = Frames[1];
    Binding.bCaptured = true; Binding.Error.Reset();
}
}

void Enable(UWorld* World)
{
    if (!World || Worlds.Contains(World)) return;
    if (Worlds.IsEmpty())
    {
        Listener.ConstraintClass = UPhysicsConstraintComponent::StaticClass();
        GUObjectArray.AddUObjectCreateListener(&Listener);
    }
    auto& Registry = Worlds.Add(World);
    for (TObjectIterator<UPhysicsConstraintComponent> It; It; ++It)
        if (It->GetWorld() == World && !It->IsTemplate()) Registry.Bindings.FindOrAdd(*It);
}

void Disable(UWorld* World)
{
    for(auto It=Suspended.CreateIterator();It;++It)if(!It->IsValid()||It->Get()->GetWorld()==World)It.RemoveCurrent();
    auto* Registry = Worlds.Find(World);
    if (!Registry) return;
    if (auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>())
    {
        for (auto& Pair : Registry->Bindings) Retire(*Native, Pair.Value);
        if (Native->OwnsBody(Registry->WorldAnchor)) Native->DestroyBody(Registry->WorldAnchor);
    }
    Worlds.Remove(World);
    ConstrainedSkeleton::Disable(World);
    if (Worlds.IsEmpty())
    {
        GUObjectArray.RemoveUObjectCreateListener(&Listener);
        Pending.Reset(); FWeakObjectPtr Item; while (Listener.Created.Dequeue(Item)) {}
    }
}

void Prepare(UWorld* World)
{
    auto* Registry = Worlds.Find(World);
    if (!Registry) return;
    auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Native) return;
    ConstrainedSkeleton::Prepare(World);
    FWeakObjectPtr Item;
    while (Listener.Created.Dequeue(Item)) if (auto* Object = Cast<UPhysicsConstraintComponent>(Item.Get())) Pending.Add(Object);
    for (auto It = Pending.CreateIterator(); It; ++It)
    {
        auto* Component = It->Get();
        if (!Component || Component->IsTemplate()) { It.RemoveCurrent(); continue; }
        if (Component->GetWorld() && !Component->GetWorld()->IsGameWorld()) { It.RemoveCurrent(); continue; }
        if (Component->GetWorld() == World)
        { Registry->Bindings.FindOrAdd(Component); It.RemoveCurrent(); }
    }
    for (auto It = Registry->Bindings.CreateIterator(); It; ++It)
    {
        auto* Component = It.Key().Get();
        if (!Component || Component->IsBeingDestroyed() || !IsValid(Component->GetOwner()) || Component->GetOwner()->IsActorBeingDestroyed()
            || Component->ComponentHasTag(TEXT("Prophecy.ManagedConstraint")))
        {
            Retire(*Native, It.Value());
            if (!It.Value().SwordCut) It.RemoveCurrent(); // Active cuts publish cleanup at Finish, outside this iterator.
            continue;
        }
        if (!Component->IsRegistered()) { Retire(*Native, It.Value()); continue; }
        Reconcile(*Component, It.Value(), *World, *Registry, *Native);
        if (It.Value().bCaptured && Native->OwnsJoint(It.Value().Joint))
            Native->SetJointPikeWoundCorrection(It.Value().Joint,
                (Component->ComponentHasTag(PikeWoundTag()) && IsPikeSlider(It.Value().Profile))
                || (It.Value().SwordCut && It.Value().SwordCut->Type != 0));
    }
}

void SetSuspended(UPhysicsConstraintComponent* Component,bool Value)
{
    if(!IsValid(Component))return;
    if(Value){Suspended.Add(Component);Component->TermComponentConstraint();}
    else Suspended.Remove(Component);
}

bool SetPikeWoundCorrection(UPhysicsConstraintComponent* Component, bool Enabled)
{
    if (!IsValid(Component)) return false;
    if (!Enabled) { Component->ComponentTags.Remove(PikeWoundTag()); return true; }
    UPrimitiveComponent* Wound = nullptr; UPrimitiveComponent* Sword = nullptr; FName WoundBone, SwordBone;
    Component->GetConstrainedComponents(Wound, WoundBone, Sword, SwordBone);
    if (!IsValid(Wound) || !IsValid(Sword) || !Cast<UStaticMeshComponent>(Sword)
        || !SwordBone.IsNone() || Component->IsBroken() || !IsPikeSlider(Component->ConstraintInstance.ProfileInstance))
        return false;
    Component->ComponentTags.AddUnique(PikeWoundTag());
    return true;
}

bool GetJoint(UPhysicsConstraintComponent* Component, FProphecyJoltJointHandle& Joint, FString& Error)
{
    Joint = {}; Error.Reset();
    const auto* Registry = IsValid(Component) ? Worlds.Find(Component->GetWorld()) : nullptr;
    const auto* Binding = Registry ? Registry->Bindings.Find(Component) : nullptr;
    if (!Binding) return false;
    Joint = Binding->Joint; Error = Binding->Error;
    const auto* Native = Component->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    return Native && Native->OwnsJoint(Joint);
}

bool StartOptimisedSwordCut(AActor* Owner, UPhysicsConstraintComponent* Component)
{
    if (!IsValid(Owner) || !IsValid(Component) || Owner->GetWorld() != Component->GetWorld()) return false;
    auto* Registry = Worlds.Find(Owner->GetWorld());
    SwordCuts::FRecords Records(Owner);
    if (!Registry || !Records.Valid()) return false;
    FScriptArrayHelper Values(Records.Array, Records.Array->ContainerPtrToValuePtr<void>(Owner));
    const int32 Index = Records.Find(Values, Component);
    if (Index == INDEX_NONE) return false;
    UPrimitiveComponent* Victim = nullptr; UPrimitiveComponent* Sword = nullptr; FName Bone, SwordBone;
    Component->GetConstrainedComponents(Victim, Bone, Sword, SwordBone);
    if (!IsValid(Victim) || !IsValid(Sword) || !SwordBone.IsNone()) return false;
    SwordCuts::FState Cut;
    Cut.Owner = Owner;
    Cut.Length = SwordCuts::Number(SwordCuts::Field(Owner->GetClass(), TEXT("blade length")), Owner);
    Cut.HalfWidth = SwordCuts::Number(SwordCuts::Field(Owner->GetClass(), TEXT("blade half width")), Owner);
    const double Hilt = SwordCuts::Number(SwordCuts::Field(Owner->GetClass(), TEXT("hilt half length")), Owner);
    const auto* Value = Values.GetRawPtr(Index);
    Cut.Type = int32(SwordCuts::Number(SwordCuts::Field(Records.Struct, TEXT("typecut")), Value));
    Cut.Matter = int32(SwordCuts::Number(SwordCuts::Field(Records.Struct, TEXT("typematter")), Value));
    Cut.Id = int32(SwordCuts::Number(SwordCuts::Field(Records.Struct, TEXT("id")), Value, -1));
    auto* DampingProperty = FindFProperty<FStructProperty>(Owner->GetClass(), TEXT("velocity cut dampings"));
    if (!(Cut.Length > 0 && Cut.HalfWidth > 0) || !DampingProperty || DampingProperty->Struct != TBaseStructure<FVector>::Get()) return false;
    const FVector Dampings = *DampingProperty->ContainerPtrToValuePtr<FVector>(Owner);
    const FVector Wound = Component->GetComponentLocation();
    const FQuat Rotation = Sword->GetComponentQuat();
    FVector HiltPosition = Sword->GetComponentLocation() + Sword->GetUpVector() * Hilt;
    // A_Sword classifies slash directions as -1/+1. The post-solve wound point
    // can already lie beyond the far edge at high speed, so it cannot identify
    // which edge entered. Preserve the accepted hit's signed classification.
    Cut.Side = Cut.Type < 0 ? -1 : 1;
    Cut.SideStop = -Cut.HalfWidth;
    Cut.StepsToCap = Cut.Matter == 0 ? 5 : 0;
    Cut.LastFrame = GFrameCounter;
    auto& Binding = Registry->Bindings.FindOrAdd(Component);
    if (Binding.SwordCut) return true; // Already adopted, never restart its deadline.
    // The accepted hit is dispatched after integration. At high speed a slash
    // can already cross the whole blade width before its joint exists. Correct
    // only that initial far-edge overshoot, once, retaining incoming velocity.
    // All subsequent motion/limits are solved physically; no per-step pose write.
    if (Cut.Type != 0)
    {
        const FVector WidthAxis = Sword->GetRightVector();
        const double SignedTravel = Cut.Side * FVector::DotProduct(Wound - HiltPosition, WidthAxis);
        if (SignedTravel < -Cut.HalfWidth)
        {
            const FVector Correction = WidthAxis * (Cut.Side * (SignedTravel + Cut.HalfWidth));
            Sword->SetWorldLocation(Sword->GetComponentLocation() + Correction, false, nullptr, ETeleportType::TeleportPhysics);
            HiltPosition += Correction;
        }
    }
    // Keep a pike's accepted contact line. Hit callbacks run after integration
    // and contact cancellation, so the reported wound need not lie on the
    // current blade centreline. Recentring it introduces a transverse position
    // error at admission and the solver kicks the sword sideways to remove it.
    // Shift only across the blade: the axial origin stays at the hilt, retaining
    // the same penetration limit and tip-relative release distance.
    if (Cut.Type == 0)
    {
        const FVector BladeAxis = Sword->GetUpVector();
        const FVector ContactOffset = Wound - HiltPosition;
        HiltPosition += ContactOffset - BladeAxis * FVector::DotProduct(ContactOffset, BladeAxis);
    }
    // Author the wound in the victim and the blade frame at the hilt plane.
    const double Scale = FMath::Max(Component->GetComponentScale().GetAbsMin(), .01);
    for (int32 I = 0; I < 2; ++I)
    {
        const auto Frame = I == 0 ? EConstraintFrame::Frame1 : EConstraintFrame::Frame2;
        FTransform Body = Component->GetBodyTransform(Frame); Body.RemoveScaling();
        FTransform Local = FTransform(Rotation, I == 0 ? Wound : HiltPosition).GetRelativeTransform(Body);
        Local.ScaleTranslation(1. / Scale); Local.RemoveScaling();
        Component->SetConstraintReferenceFrame(Frame, Local);
    }
    Component->SetLinearXLimit(LCM_Locked, 0);
    Component->SetLinearYLimit(Cut.Type == 0 ? LCM_Locked : LCM_Free, 0);
    Component->SetLinearZLimit(LCM_Free, 0);
    Component->SetAngularSwing1Limit(ACM_Locked, 0);
    Component->SetAngularSwing2Limit(ACM_Locked, 0);
    Component->SetAngularTwistLimit(Cut.Type == 0 ? ACM_Locked : ACM_Free, 0);
    Component->SetLinearPositionDrive(false, false, false);
    Component->SetLinearVelocityDrive(false, Cut.Type != 0, true);
    Component->SetLinearVelocityTarget(FVector::ZeroVector);
    Component->SetLinearDriveParams(0, FMath::Max(0., Dampings[FMath::Clamp(Cut.Matter, 0, 2)]), 0);
    Binding.SwordCut = Cut;
    Binding.bCaptured = false;
    UE_LOG(LogTemp, Log, TEXT("Optimised sword cut admitted: %s type=%d matter=%d length=%.3f width=%.3f capFrames=%d"),
        *Component->GetName(), Cut.Type, Cut.Matter, Cut.Length, Cut.HalfWidth * 2, Cut.StepsToCap);
    return true;
}

void Finish(UWorld* World)
{
    ConstrainedSkeleton::Finish(World);
    auto* Registry = Worlds.Find(World);
    if (!Registry) return;
    auto* Native = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Native) return;
    TArray<TWeakObjectPtr<UPhysicsConstraintComponent>, TInlineAllocator<4>> Broken;
    struct FNotification { TWeakObjectPtr<UPhysicsConstraintComponent> Joint; TWeakObjectPtr<AActor> Owner; double Depth; bool Release; int32 Id = -1; };
    TArray<FNotification, TInlineAllocator<4>> Notifications;
    for (auto& Pair : Registry->Bindings)
    {
        auto& Binding = Pair.Value;
        if (Binding.SwordCut)
        {
            auto& Cut = *Binding.SwordCut;
            FProphecyJoltBodyState A, B;
            if (Binding.bCaptured && Native->ReadBody(Binding.Settings.BodyA, A).IsSuccess()
                && Native->ReadBody(Binding.Settings.BodyB, B).IsSuccess())
            {
                Cut.WasCaptured = true;
                const FTransform FA = Binding.Settings.FrameA * FTransform(A.Rotation, A.PositionCm);
                const FTransform FB = Binding.Settings.FrameB * FTransform(B.Rotation, B.PositionCm);
                const FVector Travel = FA.InverseTransformPosition(FB.GetLocation());
                // Only two projections and comparisons per active cut, after the
                // normal shared solve. No traces, Blueprint calls or pose writes.
                const bool Out = Travel.Z > Cut.Length + .05
                    || (Cut.Type != 0 && Cut.Side * Travel.Y > Cut.HalfWidth + .05);
                const double Depth = FMath::Clamp(1. - Travel.Z / Cut.Length, 0., 1.);
                if (Cut.Type == 0 && Cut.Matter == 2 && (Depth >= 1. && Cut.LastStain < 1. || Depth > Cut.LastStain + 1. / 1024.))
                {
                    Cut.LastStain = Depth;
                    Notifications.Add({Pair.Key, Cut.Owner, Depth, false});
                }
                if (!Out && Cut.StepsToCap > 0 && Cut.LastFrame != GFrameCounter)
                {
                    Cut.LastFrame = GFrameCounter;
                    if (--Cut.StepsToCap == 0)
                    {
                        if (Cut.Type == 0) Cut.MinimumZ = FMath::Clamp(Travel.Z, 0., Cut.Length);
                        else Cut.SideStop = FMath::Clamp(Cut.Side * Travel.Y, -Cut.HalfWidth, Cut.HalfWidth);
                        SwordCuts::Limits(Cut, Binding.Settings);
                        const auto Status = Native->UpdateJoint(Binding.Joint, Binding.Settings);
                        if (!Status.IsSuccess()) UE_LOG(LogTemp, Error, TEXT("Optimised cut cap failed: %s"), *Status.Message);
                    }
                }
                if (Out)
                {
                    Notifications.Add({Pair.Key, Cut.Owner, 0, true, Cut.Id});
                    Binding.SwordCut.Reset();
                    Retire(*Native, Binding); Broken.Add(Pair.Key);
                    continue;
                }
            }
            else if (auto* C = Pair.Key.Get(); !C || C->IsBeingDestroyed() || C->IsBroken() || Cut.WasCaptured)
            {
                Notifications.Add({Pair.Key, Cut.Owner, 0, true, Cut.Id});
                Binding.SwordCut.Reset();
            }
        }
        if (!Binding.bCaptured || (!Binding.Profile.bLinearBreakable && !Binding.Profile.bAngularBreakable)) continue;
        FVector Force, Torque;
        if (!Native->ReadJointReaction(Binding.Joint, Force, Torque).IsSuccess()) continue;
        if ((Binding.Profile.bLinearBreakable && Force.Size() > Binding.Profile.LinearBreakThreshold)
            || (Binding.Profile.bAngularBreakable && Torque.Size() > Binding.Profile.AngularBreakThreshold))
        {
            if (Binding.SwordCut)
            {
                Notifications.Add({Pair.Key, Binding.SwordCut->Owner, 0, true, Binding.SwordCut->Id});
                Binding.SwordCut.Reset();
            }
            Retire(*Native, Binding); Broken.Add(Pair.Key);
        }
    }
    // Blueprint callbacks may remove other components or end the world. Never
    // retain registry references across them, and publish only after native step.
    for (const auto& Weak : Broken) if (auto* Component = Weak.Get(); Component && IsValid(World) && !World->bIsTearingDown)
    {
        Component->BreakConstraint();
        Component->OnConstraintBroken.Broadcast(Component->ConstraintInstance.ConstraintIndex);
    }
    for (const auto& N : Notifications) if (IsValid(World) && !World->bIsTearingDown)
    {
        if (N.Release) SwordCuts::Release(N.Owner.Get(), N.Joint.Get(), N.Id);
        else SwordCuts::Stain(N.Owner.Get(), N.Depth);
    }
}

bool ReadReaction(UPhysicsConstraintComponent* Component, FVector& Force, FVector& Torque)
{
    Force = Torque = FVector::ZeroVector;
    if (!IsValid(Component) || !Worlds.Contains(Component->GetWorld())) return false;
    FProphecyJoltJointHandle Joint; FString Error;
    if (GetJoint(Component, Joint, Error))
        Component->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->ReadJointReaction(Joint, Force, Torque);
    return true; // A pending/broken Jolt connection must not report stale Chaos forces.
}

bool ReadRotation(UPhysicsConstraintComponent* Component, FQuat& Relative)
{
    Relative = FQuat::Identity;
    if (!IsValid(Component) || !Worlds.Contains(Component->GetWorld())) return false;
    FProphecyJoltJointHandle Joint; FString Error;
    if (!GetJoint(Component, Joint, Error)) return true;
    auto* Native = Component->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltJointSettings Settings; FProphecyJoltBodyState A, B;
    if (Native->ReadJoint(Joint, Settings).IsSuccess() && Native->ReadBody(Settings.BodyA,A).IsSuccess()
        && Native->ReadBody(Settings.BodyB,B).IsSuccess())
        Relative = (A.Rotation * Settings.FrameA.GetRotation()).Inverse() * (B.Rotation * Settings.FrameB.GetRotation());
    return true;
}
}


