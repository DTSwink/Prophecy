#include "ProphecyJoltSkeletalPropComponent.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltPose.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltQueryPose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/BodyInstance.h"

struct FProphecyJoltSkeletalPropState
{
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<USkeletalMesh> Asset;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Owner;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> Coordinator;
    FProphecyJoltRigSnapshot Snapshot;
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FName> Names;
    TArray<double> Masses;
    TArray<bool> Dynamic;
    TArray<FTransform> BaseLocal, Bodies, BodyToComponent;
    ProphecyJolt::Pose::FPreparedLayout Layout;
    FProphecyJoltComposedPose Pose;
    FProphecyJoltQueryPose Queries;
    FGuid Pending, Registration;
    uint64 Revision = 0;
    FString Error;
};
void FProphecyJoltSkeletalPropStateDeleter::operator()(FProphecyJoltSkeletalPropState* S) const { delete S; }
UProphecyJoltSkeletalPropComponent::UProphecyJoltSkeletalPropComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}
UProphecyJoltSkeletalPropComponent::~UProphecyJoltSkeletalPropComponent() = default;

UProphecyJoltSkeletalPropComponent* UProphecyJoltSkeletalPropComponent::Find(const UPrimitiveComponent* Mesh)
{
    if (!IsValid(Mesh) || !IsValid(Mesh->GetOwner())) return nullptr;
    TInlineComponentArray<UProphecyJoltSkeletalPropComponent*> Bindings(Mesh->GetOwner());
    for (auto* Binding : Bindings)
        if (Binding->State && Binding->State->Mesh == Mesh) return Binding;
    return nullptr;
}
bool UProphecyJoltSkeletalPropComponent::Admit(USkeletalMeshComponent& Mesh, FString& Error)
{
    if (auto* Existing = Find(&Mesh)) { Error = Existing->State->Error; return Error.IsEmpty(); }
    auto* Binding = NewObject<UProphecyJoltSkeletalPropComponent>(Mesh.GetOwner(), NAME_None, RF_Transient);
    Mesh.GetOwner()->AddInstanceComponent(Binding);
    Binding->RegisterComponent();
    const bool Result = Binding->Enable(Mesh, Error);
    if (!Result)
    {
        // Never silently return a failed mannequin to Chaos.
        Mesh.SetAllBodiesSimulatePhysics(false);
        Mesh.SetSimulatePhysics(false);
        Mesh.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        if (Binding->State) Binding->State->Error = Error;
    }
    return Result;
}
bool UProphecyJoltSkeletalPropComponent::Enable(USkeletalMeshComponent& Mesh, FString& Error)
{
    State.Reset(new FProphecyJoltSkeletalPropState);
    State->Mesh = &Mesh; State->Asset = Mesh.GetSkeletalMeshAsset();
    State->Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    State->Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!State->Owner.IsValid() || !State->Coordinator.IsValid() || !State->Asset.IsValid())
    { Error = TEXT("Skeletal prop has no mesh or Jolt world."); return false; }
    Mesh.HandleExistingParallelEvaluationTask(true, true);
    if (!ProphecyJolt::Rig::CaptureLiveRig(Mesh, State->Snapshot, Error)) return false;
    const auto& Ref = State->Asset->GetRefSkeleton();
    const auto& CS = Mesh.GetComponentSpaceTransforms();
    if (CS.Num() != Ref.GetNum()) { Error = TEXT("Skeletal prop needs its complete initial pose."); return false; }
    TArray<int32> Parents;
    for (int32 I=0; I<Ref.GetNum(); ++I)
    {
        const int32 Parent = Ref.GetParentIndex(I);
        Parents.Add(Parent);
        State->BaseLocal.Add(Parent == INDEX_NONE ? CS[I] : CS[I].GetRelativeTransform(CS[Parent]));
    }
    State->BaseLocal[0] = State->BaseLocal[0] * FTransform(FQuat::Identity, FVector::ZeroVector, Mesh.GetComponentScale());
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    for (auto& Body : State->Snapshot.Bodies)
    {
        Body.bMACD = false; // Chaos-only setting; ordinary PHAT CCD is retained.
        FProphecyJoltPoseBodyMapping Mapping;
        Mapping.BoneIndex = Body.BoneIndex;
        Mapping.VisualScale = Mesh.GetSocketTransform(Body.BodyName).GetScale3D();
        Mappings.Add(Mapping);
        State->Names.Add(Body.BodyName); State->Masses.Add(Body.MassKg);
        State->Dynamic.Add(Body.bSimulating);
        State->BodyToComponent.Add(Body.BodyOriginToWorld.GetRelativeTransform(Mesh.GetComponentTransform()));
    }
    if (!State->Layout.Build(Ref.GetNum(), Parents, Mappings, Error)) return false;
    bool Deferred = false;
    if (!State->Coordinator->RequestClientAdmission(*this,
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::Complete),
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::Cancel),
        Deferred, State->Pending, Error)) return false;
    // Capture precedes the handoff. Pending admission must not run another Chaos step.
    Mesh.SetAllBodiesSimulatePhysics(false);
    Mesh.SetSimulatePhysics(false);
    Mesh.SetAllBodiesPhysicsBlendWeight(0);
    Mesh.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Mesh.PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
    Mesh.KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    Mesh.bDeferKinematicBoneUpdate = false;
    Mesh.bEnableUpdateRateOptimizations = false;
    Mesh.bPauseAnims = false; Mesh.bNoSkeletonUpdate = false; Mesh.bForceRefpose = false;
    Mesh.SetEnableAnimation(true);
    Mesh.SetDisablePostProcessBlueprint(true);
    Mesh.SetComponentTickEnabled(false);
    Mesh.SetAnimInstanceClass(UProphecyJoltPoseAnimInstance::StaticClass());
    return Deferred || EnableNow(Error);
}
bool UProphecyJoltSkeletalPropComponent::EnableNow(FString& Error)
{
    auto* Mesh = State ? State->Mesh.Get() : nullptr;
    if (!Mesh || !IsRegistered() || Mesh->IsBeingDestroyed() || GetOwner()->IsActorBeingDestroyed())
    { Error = TEXT("Skeletal prop was removed before admission."); return false; }
    FProphecyJoltPreparedRig Prepared;
    if (!Prepared.Build(State->Snapshot, Error)) return false;
    TArray<FString> Coverage;
    const auto Created = State->Owner->CreateRig(State->Snapshot, Prepared, State->Rig, State->Handles, Coverage);
    if (!Created.IsSuccess()) { Error = Created.Message; return false; }
    bool Hits = Mesh->BodyInstance.bNotifyRigidBodyCollision;
    for (const FBodyInstance* Body : Mesh->Bodies) if (Body) Hits |= Body->bNotifyRigidBodyCollision;
    auto Result = State->Owner->SetRigHitEvents(State->Rig, Mesh, Hits);
    if (!Result.IsSuccess())
    { Error = Result.Message; State->Owner->DestroyRig(State->Rig); State->Handles.Reset(); return false; }
    if (!State->Queries.Initialize(*Mesh, Error) || !ConsumeCompletedJoltWorldStep(Error)
        || !State->Coordinator->RegisterStepClient(*this, nullptr, State->Registration, Error))
    {
        State->Owner->DestroyRig(State->Rig); State->Handles.Reset(); return false;
    }
    State->Snapshot = {}; // Geometry is owned by the rig; no duplicate capture retained.
    return true;
}
void UProphecyJoltSkeletalPropComponent::Complete(const FGuid& Token)
{
    if (!State || State->Pending != Token) return;
    State->Pending.Invalidate();
    FString Error;
    if (!EnableNow(Error) || !RefreshCollisionPolicy(Error)) LatchJoltStepError(Error);
}
void UProphecyJoltSkeletalPropComponent::Cancel(const FGuid& Token)
{
    if (State && State->Pending == Token) State->Pending.Invalidate();
}
bool UProphecyJoltSkeletalPropComponent::IsJoltStepClientActive() const
{
    return State && State->Owner.IsValid() && State->Owner->OwnsRig(State->Rig);
}
bool UProphecyJoltSkeletalPropComponent::GetBodyHandle(FName Bone, FProphecyJoltBodyHandle& Handle) const
{
    if (!IsJoltStepClientActive()) return false;
    int32 Index = State->Names.IndexOfByKey(Bone);
    if (Bone.IsNone() && State->Mesh.IsValid()) Index = State->Mesh->RootBodyData.BodyIndex;
    if (!State->Handles.IsValidIndex(Index)) return false;
    Handle = State->Handles[Index]; return true;
}
bool UProphecyJoltSkeletalPropComponent::StepAndPublish(float Dt, FString& Error)
{
    return State && State->Coordinator.IsValid()
        && State->Coordinator->StepExplicit(*this, State->Registration, Dt, Error);
}
bool UProphecyJoltSkeletalPropComponent::RefreshCollisionPolicy(FString& Error)
{
    auto* Mesh = State ? State->Mesh.Get() : nullptr;
    if (!Mesh || !IsJoltStepClientActive())
    { Error = TEXT("Skeletal prop collision refresh requires completed admission."); return false; }
    TArray<FProphecyJoltCollisionUpdate, TInlineAllocator<32>> Updates;
    for (int32 I = 0; I < State->Handles.Num(); ++I)
    {
        const FBodyInstance* Body = Mesh->GetBodyInstance(State->Names[I]);
        if (!Body) { Error = TEXT("Skeletal prop collision body was removed."); return false; }
        auto& Update = Updates.AddDefaulted_GetRef();
        Update.Handle = State->Handles[I];
        Update.ObjectChannel = Mesh->GetCollisionObjectType();
        // Match UE's skeletal component override without treating its retained
        // QueryOnly receiver as a request to disable the native physical body.
        Update.Responses = FCollisionResponseContainer::CreateMinContainer(
            Body->GetResponseToChannels(), Mesh->GetCollisionResponseToChannels());
    }
    const auto Result = State->Owner->UpdateBodyCollision(Updates);
    if (!Result.IsSuccess()) { Error = Result.Message; return false; }
    return true;
}
double UProphecyJoltSkeletalPropComponent::GetCapturedBodyMassKg(FName Bone) const
{
    const int32 Index = State ? State->Names.IndexOfByKey(Bone) : INDEX_NONE;
    return State && State->Masses.IsValidIndex(Index) ? State->Masses[Index] : 0;
}
bool UProphecyJoltSkeletalPropComponent::SetSimulationEnabled(bool Enabled, FString& Error)
{
    if (!IsJoltStepClientActive()) { Error = TEXT("Skeletal prop admission is not complete."); return false; }
    const auto Result = State->Owner->SetRigKinematicLimb(State->Handles, !Enabled);
    if (!Result.IsSuccess()) { Error = Result.Message; return false; }
    for (int32 I=0; I<State->Handles.Num(); ++I)
    {
        State->Dynamic[I] = Enabled;
        if (!Enabled)
        {
            FProphecyJoltBodyState Body;
            if (State->Owner->ReadBody(State->Handles[I], Body).IsSuccess())
                State->BodyToComponent[I] = FTransform(Body.Rotation, Body.PositionCm).GetRelativeTransform(State->Mesh->GetComponentTransform());
        }
    }
    return true;
}
bool UProphecyJoltSkeletalPropComponent::PrepareJoltWorldStep(float Dt, bool, FString& Error)
{
    if (!State || !State->Error.IsEmpty()) { Error = State ? State->Error : TEXT("Missing skeletal prop."); return false; }
    auto* Mesh = State->Mesh.Get();
    if (!Mesh || Mesh->GetSkeletalMeshAsset() != State->Asset.Get())
    { Error = TEXT("Skeletal prop mesh changed while bound."); return false; }
    for (int32 I=0; I<State->Handles.Num(); ++I)
        if (!State->Dynamic[I])
        {
            const auto Result = State->Owner->MoveKinematicBody(State->Handles[I],
                State->BodyToComponent[I] * Mesh->GetComponentTransform(), Dt);
            if (!Result.IsSuccess()) { Error = Result.Message; return false; }
        }
    return true;
}
bool UProphecyJoltSkeletalPropComponent::ConsumeCompletedJoltWorldStep(FString& Error)
{
    auto* Mesh = State ? State->Mesh.Get() : nullptr;
    auto* Anim = Mesh ? Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance()) : nullptr;
    if (!Anim || !IsJoltStepClientActive()) { Error = TEXT("Skeletal prop lost its pose receiver."); return false; }
    State->Bodies.Reset();
    for (const auto& Handle : State->Handles)
    {
        FProphecyJoltBodyState Body;
        const auto Result = State->Owner->ReadBody(Handle, Body);
        if (!Result.IsSuccess()) { Error = Result.Message; return false; }
        State->Bodies.Emplace(Body.Rotation, Body.PositionCm);
    }
    const FTransform Carrier(Mesh->GetComponentQuat(), Mesh->GetComponentLocation());
    if (!State->Layout.Compose(State->BaseLocal, State->Bodies, Carrier, State->Pose, Error)) return false;
    State->Pose.LocalTransforms[0] = State->Pose.WorldTransforms[0].GetRelativeTransform(Mesh->GetComponentTransform());
    if (!Anim->PublishCompletedLocalPose(State->Pose.LocalTransforms, ++State->Revision, Error)) return false;
    Mesh->HandleExistingParallelEvaluationTask(true, true);
    Mesh->TickAnimation(0, false);
    if (!State || !IsValid(Mesh) || Mesh->IsBeingDestroyed()) { Error = TEXT("Skeletal prop removed during pose evaluation."); return false; }
    const uint64 Revision = State->Revision;
    if (!Anim->ArmPostEvaluateQueryCommit(FProphecyJoltPostEvaluateQueryCommit::CreateWeakLambda(this,
        [this, Mesh](FString& QueryError)
        { return State && State->Mesh == Mesh && State->Queries.Publish(*Mesh, State->Pose.WorldTransforms, QueryError); }),
        Revision, Error)) return false;
    const TWeakObjectPtr<UProphecyJoltPoseAnimInstance> WeakAnim(Anim);
    Mesh->RefreshBoneTransforms(nullptr);
    if (WeakAnim.IsValid()) WeakAnim->ClearPostEvaluateQueryCommit();
    return State && WeakAnim.IsValid() && WeakAnim->GetPostEvaluateQueryCommitResult(Revision, Error);
}
void UProphecyJoltSkeletalPropComponent::LatchJoltStepError(const FString& Error)
{
    if (State) State->Error = Error;
    UE_LOG(LogTemp, Error, TEXT("Jolt skeletal prop %s: %s"), *GetNameSafe(GetOwner()), *Error);
}
void UProphecyJoltSkeletalPropComponent::Release()
{
    if (!State) return;
    if (State->Coordinator.IsValid())
    {
        State->Coordinator->CancelClientAdmission(*this, State->Pending);
        State->Coordinator->UnregisterStepClient(*this, State->Registration);
    }
    if (State->Owner.IsValid() && State->Owner->OwnsRig(State->Rig)) State->Owner->DestroyRig(State->Rig);
    State.Reset();
}
void UProphecyJoltSkeletalPropComponent::EndPlay(const EEndPlayReason::Type Reason) { Release(); Super::EndPlay(Reason); }
void UProphecyJoltSkeletalPropComponent::OnUnregister() { Release(); Super::OnUnregister(); }
