#include "ProphecyJoltMeshPhysics.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

namespace ProphecyJolt::MeshPhysics
{
bool Execute(UPrimitiveComponent& Component, const FProphecyJoltPhysicsCommand& Command, const FSelection& Selection)
{
    if (!IsInGameThread())
    {
        UE_LOG(LogTemp, Warning, TEXT("Physics nodes require the game thread: %s"), *Component.GetPathName());
        return true;
    }
    AActor* Owner = Component.GetOwner();
    if (!IsValid(Owner)) return false;
    AProphecyAgent* Agent = Cast<AProphecyAgent>(Owner);
    UProphecyJoltCharacterComponent* Character = Agent && Agent->GetPoseReferenceMesh() == &Component
        ? Agent->GetJoltCharacterComponent() : nullptr;
    if (Character && !Character->IsJoltPhysical()) Character = nullptr;
    UProphecyJoltBodyComponent* Standalone = nullptr;
    if (!Character)
    {
        Standalone = Owner->FindComponentByClass<UProphecyJoltBodyComponent>();
        if (!Standalone || !Standalone->IsJoltBody() || Standalone->GetSourceComponent() != &Component) return false;
    }
    // Never send a failed Jolt request to Chaos's retained query bodies.
    UProphecyJoltWorldSubsystem* World = Component.GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!World || (Character && Character->IsSteppingStopped()) || (Standalone && Standalone->IsSteppingStopped())) return true;
    if (Command.Value.ContainsNaN() || (Selection.Type == ESelection::Radial
        && (Selection.Origin.ContainsNaN() || !FMath::IsFinite(Selection.Radius) || !FMath::IsFinite(Selection.Strength))))
    {
        UE_LOG(LogTemp, Warning, TEXT("Rejected non-finite Jolt physics node input on %s"), *Component.GetPathName());
        return true;
    }
    struct FSelected { FProphecyJoltBodyHandle Handle; double Mass = 0; };
    TArray<FSelected, TInlineAllocator<32>> Bodies;
    double TotalMass = 0;
    if (Character)
    {
        const auto& Mesh = *CastChecked<USkeletalMeshComponent>(&Component);
        const UPhysicsAsset* Asset = Mesh.GetPhysicsAsset();
        const USkeletalMesh* SkeletalMesh = Mesh.GetSkeletalMeshAsset();
        if (!Asset || !SkeletalMesh) return true;
        FName Bone = Selection.Bone;
        if (Selection.Type == ESelection::Bone && Bone.IsNone())
        {
            if (!Asset->SkeletalBodySetups.IsValidIndex(Mesh.RootBodyData.BodyIndex)) return true;
            Bone = Asset->SkeletalBodySetups[Mesh.RootBodyData.BodyIndex]->BoneName;
        }
        const FReferenceSkeleton& Ref = SkeletalMesh->GetRefSkeleton();
        const int32 Root = Ref.FindBoneIndex(Bone);
        if (Selection.Type == ESelection::Below && Bone.IsNone() && !Selection.bIncludeSelf) return true;
        if (Selection.Type == ESelection::Below && !Bone.IsNone() && Root == INDEX_NONE) return true;
        for (const auto& Setup : Asset->SkeletalBodySetups)
        {
            if (!Setup) continue;
            const FName Name = Setup->BoneName;
            const double Mass = Selection.Type == ESelection::Radial ? Character->GetCapturedBodyMassKg(Name) : 0;
            TotalMass += Mass;
            if (Selection.Type == ESelection::Bone && Name != Bone) continue;
            if (Selection.Type == ESelection::Below && !Bone.IsNone())
            {
                const int32 Index = Ref.FindBoneIndex(Name);
                if (Index == Root ? !Selection.bIncludeSelf : !Ref.BoneIsChildOf(Index, Root)) continue;
            }
            FProphecyJoltBodyHandle Handle;
            if (Character->GetBodyHandle(Name, Handle)) Bodies.Add({Handle, Mass});
        }
    }
    else
    {
        FProphecyJoltBodyHandle Handle;
        if (Standalone->GetBodyHandle(Handle)) Bodies.Add({Handle, 0});
    }
    for (const FSelected& Selected : Bodies)
    {
        FProphecyJoltPhysicsCommand Applied = Command;
        if (Selection.Type == ESelection::Radial)
        {
            if (Selection.Radius <= 0) continue;
            FProphecyJoltBodyState State;
            if (!World->ReadBody(Selected.Handle, State).IsSuccess()) continue;
            const FVector Delta = State.CenterOfMassPositionCm - Selection.Origin;
            const double Distance = Delta.Size();
            if (Distance > Selection.Radius) continue;
            double Strength = Selection.Strength;
            if (Character && !Command.bMassIndependent) Strength *= Selected.Mass / FMath::Max(TotalMass, double(UE_KINDA_SMALL_NUMBER));
            if (Selection.Falloff == RIF_Linear) Strength *= 1.0 - Distance / Selection.Radius;
            Applied.Value = Delta.GetSafeNormal() * Strength;
        }
        const auto Result = World->ExecutePhysicsCommand(Selected.Handle, Applied);
        if (!Result.IsSuccess())
            UE_LOG(LogTemp, Warning, TEXT("Jolt physics node rejected on %s: %s"), *Component.GetPathName(), *Result.Message);
    }
    return true;
}
}
