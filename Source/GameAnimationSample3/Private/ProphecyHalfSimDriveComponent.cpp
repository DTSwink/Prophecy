#include "ProphecyHalfSimDriveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Chaos/ChaosConstraintSettings.h"

UProphecyHalfSimDriveComponent::UProphecyHalfSimDriveComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UProphecyHalfSimDriveComponent::Stop()
{
    SetComponentTickEnabled(false);
    if (Native)
    {
        Native->SetStrengthMultiplyer(0);
        Native->SetComponentTickEnabled(false);
        if (Mesh) Native->RemoveTickPrerequisiteComponent(Mesh);
        Native->SetSkeletalMeshComponent(nullptr); // Release old targets, not just zero their strength.
    }
    if (Mesh)
    {
        RemoveTickPrerequisiteComponent(Mesh);
        Mesh->bUpdateJointsFromAnimation = false;
        for (FConstraintInstance* J : Mesh->Constraints) if (J)
        {
            J->SetOrientationDriveSLERP(false);
            J->SetAngularVelocityDriveSLERP(false);
            J->SetOrientationDriveTwistAndSwing(false, false);
            J->SetAngularVelocityDriveTwistAndSwing(false, false);
        }
    }
    BodySettings.Reset();
    BodyCancelGravity.Reset();
    NativeTargetCount = JointMotorCount = 0;
    Mesh = nullptr; Native = nullptr;
}

bool UProphecyHalfSimDriveComponent::Configure(USkeletalMeshComponent* InMesh,
    UPhysicalAnimationComponent* InNative, EProphecyHalfSimDriveMethod InMethod,
    FName InRoot, const FPhysicalAnimationData& InSettings, float InStrength)
{
    if (!InMesh || !InMesh->GetSkeletalMeshAsset() || !InMesh->GetPhysicsAsset() || !InNative) return false;
    Stop();
    Mesh = InMesh; Native = InNative; Method = InMethod; Root = InRoot;
    BaseSettings = InSettings;
    Strength = FMath::Max(0.f, InStrength);
    const bool Joint = Method == EProphecyHalfSimDriveMethod::JointMotors || Method == EProphecyHalfSimDriveMethod::JointMotorsPelvis;
    const bool UseNative = Method == EProphecyHalfSimDriveMethod::NativeWorld ||
        Method == EProphecyHalfSimDriveMethod::NativeLocal || Method == EProphecyHalfSimDriveMethod::NativeLocalPelvis ||
        Method == EProphecyHalfSimDriveMethod::JointMotorsPelvis;
    for (FConstraintInstance* J : Mesh->Constraints) if (J)
    {
        J->SetAngularSwing1Limit(ACM_Free, 0);
        J->SetAngularSwing2Limit(ACM_Free, 0);
        J->SetAngularTwistLimit(ACM_Free, 0);
        J->SetOrientationDriveTwistAndSwing(false, false);
        J->SetAngularVelocityDriveTwistAndSwing(false, false);
        J->SetAngularDriveMode(EAngularDriveMode::SLERP);
        J->SetOrientationDriveSLERP(Joint);
        J->SetAngularVelocityDriveSLERP(Joint);
        J->SetAngularVelocityTarget(FVector::ZeroVector);
        if (Joint) ++JointMotorCount;
    }
    Mesh->bUpdateJointsFromAnimation = Joint;
    if (UseNative)
    {
        Native->SetSkeletalMeshComponent(Mesh);
        Native->AddTickPrerequisiteComponent(Mesh);
    }
    const auto& Ref = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    const int32 RootIndex = Ref.FindBoneIndex(Root);
    for (const USkeletalBodySetup* Body : Mesh->GetPhysicsAsset()->SkeletalBodySetups) if (Body)
    {
        const int32 I = Ref.FindBoneIndex(Body->BoneName);
        if (I == RootIndex || (I != INDEX_NONE && Ref.BoneIsChildOf(I, RootIndex)))
            SetBodySettings(Body->BoneName, InSettings);
    }
    Native->SetStrengthMultiplyer(Strength);
    Native->SetComponentTickEnabled(UseNative);
    if (Joint) Mesh->UpdateRBJointMotors();
    if (Method == EProphecyHalfSimDriveMethod::WorldForcePD || Method == EProphecyHalfSimDriveMethod::WorldOneStep)
    {
        AddTickPrerequisiteComponent(Mesh);
        AnimationCS.SetNum(Ref.GetNum());
        SetComponentTickEnabled(true);
    }
    return true;
}

void UProphecyHalfSimDriveComponent::SetBodySettings(FName Bone, const FPhysicalAnimationData& Data, bool CancelGravity)
{
    if (!Mesh || !Native) return;
    const bool IsNew = !BodySettings.Contains(Bone);
    BodySettings.Add(Bone, Data);
    BodyCancelGravity.Add(Bone, CancelGravity);
    const bool IsRoot = Bone == Root;
    const bool NativeBody = Method == EProphecyHalfSimDriveMethod::NativeWorld ||
        (Method == EProphecyHalfSimDriveMethod::NativeLocal && !IsRoot) ||
        Method == EProphecyHalfSimDriveMethod::NativeLocalPelvis ||
        (Method == EProphecyHalfSimDriveMethod::JointMotorsPelvis && IsRoot);
    if (NativeBody)
    {
        FPhysicalAnimationData D = Data;
        D.bIsLocalSimulation = !IsRoot && (Method == EProphecyHalfSimDriveMethod::NativeLocal || Method == EProphecyHalfSimDriveMethod::NativeLocalPelvis);
        Native->ApplyPhysicalAnimationSettings(Bone, D);
        if (IsNew) ++NativeTargetCount;
    }
    if (Method == EProphecyHalfSimDriveMethod::JointMotors || Method == EProphecyHalfSimDriveMethod::JointMotorsPelvis)
        for (FConstraintInstance* J : Mesh->Constraints) if (J && J->GetChildBoneName() == Bone)
            J->SetAngularDriveParams(Data.OrientationStrength * Strength * Chaos::ConstraintSettings::AngularDriveStiffnessScale(),
                Data.AngularVelocityStrength * Strength * Chaos::ConstraintSettings::AngularDriveDampingScale(), Data.MaxAngularForce * Strength);
}

void UProphecyHalfSimDriveComponent::SetStrength(float Value)
{
    Strength = FMath::Max(0.f, Value);
    if (Native) Native->SetStrengthMultiplyer(Strength);
    if (Mesh && (Method == EProphecyHalfSimDriveMethod::JointMotors || Method == EProphecyHalfSimDriveMethod::JointMotorsPelvis))
        for (FConstraintInstance* J : Mesh->Constraints) if (J)
            if (const auto* D = BodySettings.Find(J->GetChildBoneName()))
                J->SetAngularDriveParams(D->OrientationStrength * Strength * Chaos::ConstraintSettings::AngularDriveStiffnessScale(),
                    D->AngularVelocityStrength * Strength * Chaos::ConstraintSettings::AngularDriveDampingScale(), D->MaxAngularForce * Strength);
}

void UProphecyHalfSimDriveComponent::TickComponent(float Dt, ELevelTick Type, FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Dt, Type, Tick);
    if (!Mesh || (Method != EProphecyHalfSimDriveMethod::WorldForcePD && Method != EProphecyHalfSimDriveMethod::WorldOneStep) || Dt <= 0) return;
    // Rebuild from animation locals, NEVER the physics-blended component pose.
    const auto& Local = Mesh->GetBoneSpaceTransforms();
    const auto& Ref = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    if (Local.Num() != AnimationCS.Num()) return;
    for (int32 I = 0; I < Local.Num(); ++I)
    {
        const int32 P = Ref.GetParentIndex(I);
        AnimationCS[I] = P == INDEX_NONE ? Local[I] : Local[I] * AnimationCS[P];
    }
    for (FBodyInstance* B : Mesh->Bodies)
    {
        if (!B || !B->BodySetup.IsValid() || !B->IsInstanceSimulatingPhysics()) continue;
        const auto* D = BodySettings.Find(B->BodySetup->BoneName);
        if (!D || !AnimationCS.IsValidIndex(B->InstanceBoneIndex)) continue;
        const FTransform Target = AnimationCS[B->InstanceBoneIndex] * Mesh->GetComponentTransform();
        if (Method == EProphecyHalfSimDriveMethod::WorldOneStep)
        {
            const float L = BaseSettings.PositionStrength > 0 ? D->PositionStrength/BaseSettings.PositionStrength : 0;
            const float R = BaseSettings.OrientationStrength > 0 ? D->OrientationStrength/BaseSettings.OrientationStrength : 0;
            ApplyOneStepBody(B,Target,Dt,L*Strength,R*Strength,BodyCancelGravity.FindRef(B->BodySetup->BoneName),
                B->bEnableGravity && GetWorld() ? GetWorld()->GetGravityZ() : 0.f);
            continue;
        }
        const FTransform Actual = B->GetUnrealWorldTransform();
        // Implicit PD acceleration: stable at the benchmark's 60 Hz timestep.
        // Different gain semantics from Chaos constraint motors; not claimed equivalent.
        auto PD = [Dt](FVector Error, FVector Velocity, float Kp, float Kd)
        { return (Kp * Error - (Kd + Kp * Dt) * Velocity) / (1.f + Kd * Dt + Kp * Dt * Dt); };
        FVector Acc = PD(Target.GetLocation() - Actual.GetLocation(), B->GetUnrealWorldVelocity(), D->PositionStrength*Strength, D->VelocityStrength*Strength);
        if (D->MaxLinearForce > 0) Acc = Acc.GetClampedToMaxSize(D->MaxLinearForce*Strength/FMath::Max(B->GetBodyMass(), .001f));
        B->AddForce(Acc, true, true);
        FQuat Q = (Target.GetRotation() * Actual.GetRotation().Inverse()).GetNormalized();
        if (Q.W < 0) Q = Q * -1.f;
        FVector Axis; double Angle; Q.ToAxisAndAngle(Axis, Angle);
        FVector AngularAcc = PD(Axis * Angle, B->GetUnrealWorldAngularVelocityInRadians(), D->OrientationStrength*Strength, D->AngularVelocityStrength*Strength);
        if (D->MaxAngularForce > 0)
        {
            const FQuat R = Actual.GetRotation();
            const FVector Torque = R.RotateVector(B->GetBodyInertiaTensor() * R.UnrotateVector(AngularAcc));
            B->AddTorqueInRadians(Torque.GetClampedToMaxSize(D->MaxAngularForce*Strength), true, false);
        }
        else B->AddTorqueInRadians(AngularAcc, true, true);
    }
}

bool UProphecyHalfSimDriveComponent::ApplyOneStepBody(FBodyInstance* Body, const FTransform& Target,
    float Dt, float LinearScale, float AngularScale, bool CancelGravity, float GravityZ)
{
    if (!Body || !Body->IsInstanceSimulatingPhysics() || Dt <= UE_SMALL_NUMBER) return false;
    const FTransform Actual=Body->GetUnrealWorldTransform();
    if (LinearScale > 0)
    {
        FVector Acc=(Target.GetLocation()-Actual.GetLocation()-Body->GetUnrealWorldVelocity()*Dt)/FMath::Square(Dt);
        if (CancelGravity) Acc.Z-=GravityZ;
        Body->AddForce(Acc*LinearScale,true,true);
    }
    if (AngularScale > 0)
    {
        FQuat Q=(Target.GetRotation()*Actual.GetRotation().Inverse()).GetNormalized();
        if (Q.W<0) Q=Q*-1.f;
        FVector Axis=FVector::ForwardVector; float Angle=0;
        Q.ToAxisAndAngle(Axis,Angle);
        Body->AddTorqueInRadians((Axis*(Angle/Dt)-Body->GetUnrealWorldAngularVelocityInRadians())/Dt*AngularScale,true,true);
    }
    return true;
}

void UProphecyHalfSimDriveComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Stop();
    Super::EndPlay(Reason);
}
