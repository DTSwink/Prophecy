#include "ProphecyNativePhysicalAgent.h"

#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNPoseTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

AProphecyNativePhysicalAgent::AProphecyNativePhysicalAgent()
{
	bManualNNPoseApplication = false;
	bAutoEnsureStandaloneNNManager = false;
	bAutoPublishManualFollowerSubstepTargets = false;
	bAutoApplyWorldMagnetization = false;
	bShowKinematicDebugMesh = false;
	PhysicalDriveMode = EProphecyAgentPhysicalDriveMode::PerBodyWorld;
	GetAgentMesh()->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
	GetAgentMesh()->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
}

void AProphecyNativePhysicalAgent::BeginPlay()
{
	// Test baseline, before Blueprint BeginPlay so explicit user setters win.
	SetAllPhysicalFeedbackTolerances(1000000.0f, 360.0f);
	Super::BeginPlay();
	// A standalone placed test pawn gets its own normal NN lane. An existing
	// manager may instead spawn this class through AgentClass; never create two.
	if (!Cast<AProphecyNNLocomotionManager>(GetOwner()))
	{
		bool bHasManager = false;
		for (TActorIterator<AProphecyNNLocomotionManager> It(GetWorld()); It; ++It)
		{
			bHasManager = true;
			break;
		}
		if (!bHasManager)
		{
			AProphecyNNLocomotionManager* Manager = GetWorld()->SpawnActorDeferred<AProphecyNNLocomotionManager>(
				AProphecyNNLocomotionManager::StaticClass(), FTransform::Identity, nullptr, nullptr,
				ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
			if (Manager)
			{
				Manager->PlayerAgent = this;
				Manager->ConfigureSimpleLocomotionTest();
				// Production selects July5 through a BP-only variable; this native
				// class explicitly uses the same accepted latest checkpoint.
				Manager->WalkOnnxModelPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_b100.onnx");
				Manager->WalkRuntimeContractPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json");
				Manager->InitialPhysicalDriveMode = EProphecyAgentPhysicalDriveMode::PerBodyWorld;
				Manager->FinishSpawning(FTransform::Identity);
			}
		}
	}
	SetActorTickEnabled(true);
}

void AProphecyNativePhysicalAgent::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bNativeStarted && HasValidAgentHandle())
	{
		int32 Id;
		float Interval;
		bool bInterpolate;
		FProphecyNNPoseSnapshot Pose;
		if (GetNNPoseDataSource(Id, Interval, bInterpolate) &&
			FProphecyNNPoseStore::GetAgentLocalPose(Id, Pose) && Pose.IsValid())
		{
			bNativeStarted = !bStartNativeSimulation || SetNativePhysicalSimulation(true);
		}
	}
}

UPhysicalAnimationComponent* AProphecyNativePhysicalAgent::GetNativePhysicalAnimation() const
{
	return FindComponentByClass<UPhysicalAnimationComponent>();
}

bool AProphecyNativePhysicalAgent::SetNativePhysicalSimulation(bool bEnabled)
{
	USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	if (!NativeMesh || !NativeMesh->GetAnimInstance() || !NativeMesh->GetPhysicsAsset()) return false;
	if (bEnabled)
	{
		if (PhysicalDriveMode != EProphecyAgentPhysicalDriveMode::PerBodyWorld &&
			!SetPhysicalDriveMode(EProphecyAgentPhysicalDriveMode::PerBodyWorld)) return false;
		PhysicalDriveSettings.bIsLocalSimulation = false;
		if (GetSimulationMode() != EProphecyAgentSimulationMode::Physical)
		{
			NativeMesh->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
			if (!SetSimulationMode(EProphecyAgentSimulationMode::Physical)) return false;
		}
		NativeMesh->bEnableUpdateRateOptimizations = false;
		NativeMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		if (!ApplyPhysicalDriveSettingsNow()) return false;
		// Native target actors are created by the component's next PrePhysics tick.
		NativeTargetsPendingFrame = GFrameCounter;
		const auto SavedScales = NativeStrengthScales;
		for (const auto& Pair : SavedScales)
		{
			SetNativeBodyStrength(Pair.Key, Pair.Value.X, Pair.Value.Y);
		}
		SetNativeContactsAndGravity(bNativeContacts, bNativeGravity);
		SetNativeUseAuthoredAngularLimits(bNativeUseAuthoredAngularLimits);
	}
	else if (!SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)) return false;
	SetActorTickEnabled(true);
	return true;
}

bool AProphecyNativePhysicalAgent::SetNativeBodyStrength(FName BoneName, float LinearScale, float AngularScale)
{
	USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	UPhysicalAnimationComponent* Drives = GetNativePhysicalAnimation();
	if (!FMath::IsFinite(LinearScale) || !FMath::IsFinite(AngularScale) ||
		LinearScale < 0.0f || AngularScale < 0.0f || !NativeMesh || !Drives ||
		!NativeMesh->GetPhysicsAsset() || NativeMesh->GetPhysicsAsset()->FindBodyIndex(BoneName) == INDEX_NONE) return false;
	NativeStrengthScales.Add(BoneName, FVector2D(LinearScale, AngularScale));
	if (GetSimulationMode() == EProphecyAgentSimulationMode::Physical)
	{
		FPhysicalAnimationData Data = PhysicalDriveSettings;
		Data.bIsLocalSimulation = false;
		Data.PositionStrength *= LinearScale;
		Data.VelocityStrength *= LinearScale;
		Data.MaxLinearForce *= LinearScale;
		Data.OrientationStrength *= AngularScale;
		Data.AngularVelocityStrength *= AngularScale;
		Data.MaxAngularForce *= AngularScale;
		Drives->ApplyPhysicalAnimationSettings(BoneName, Data);
		NativeMesh->WakeAllRigidBodies();
	}
	return true;
}

int32 AProphecyNativePhysicalAgent::SetNativeBodyStrengthBelow(FName ParentBone,
	float LinearScale, float AngularScale, bool bIncludeParent)
{
	const USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	if (!NativeMesh || !NativeMesh->GetSkeletalMeshAsset() || !NativeMesh->GetPhysicsAsset()) return 0;
	const FReferenceSkeleton& Ref = NativeMesh->GetSkeletalMeshAsset()->GetRefSkeleton();
	const int32 Parent = Ref.FindBoneIndex(ParentBone);
	if (Parent == INDEX_NONE) return 0;
	int32 Changed = 0;
	for (const USkeletalBodySetup* Body : NativeMesh->GetPhysicsAsset()->SkeletalBodySetups)
	{
		if (!Body) continue;
		const int32 Index = Ref.FindBoneIndex(Body->BoneName);
		if ((Index == Parent && bIncludeParent) || (Index != INDEX_NONE && Index != Parent && Ref.BoneIsChildOf(Index, Parent)))
		{
			Changed += SetNativeBodyStrength(Body->BoneName, LinearScale, AngularScale) ? 1 : 0;
		}
	}
	return Changed;
}

void AProphecyNativePhysicalAgent::SetNativeContactsAndGravity(bool bContacts, bool bGravity)
{
	bNativeContacts = bContacts;
	bNativeGravity = bGravity;
	USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	if (GetSimulationMode() != EProphecyAgentSimulationMode::Physical) return;
	// Keep a valid physics state even during no-contact calibration.
	NativeMesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	NativeMesh->SetCollisionObjectType(ECC_PhysicsBody);
	NativeMesh->SetCollisionResponseToAllChannels(ECR_Ignore);
	if (bContacts)
	{
		NativeMesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
		NativeMesh->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
		NativeMesh->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
	}
	GetAgentCapsule()->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Ignore);
	NativeMesh->SetEnableGravity(bGravity);
	NativeMesh->WakeAllRigidBodies();
}

bool AProphecyNativePhysicalAgent::SetNativeUseAuthoredAngularLimits(bool bEnabled)
{
	bNativeUseAuthoredAngularLimits = bEnabled;
	USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	const UPhysicsAsset* Asset = NativeMesh ? NativeMesh->GetPhysicsAsset() : nullptr;
	if (!Asset || NativeMesh->Constraints.Num() != Asset->ConstraintSetup.Num()) return false;
	for (int32 Index=0; Index<NativeMesh->Constraints.Num(); ++Index)
	{
		FConstraintInstance* Joint = NativeMesh->Constraints[Index];
		const UPhysicsConstraintTemplate* Template = Asset->ConstraintSetup[Index];
		if (!Joint || !Template) continue;
		const FConstraintProfileProperties& Profile = Template->DefaultInstance.ProfileInstance;
		Joint->SetAngularSwing1Limit(bEnabled ? Profile.ConeLimit.Swing1Motion.GetValue() : ACM_Free,
			Profile.ConeLimit.Swing1LimitDegrees);
		Joint->SetAngularSwing2Limit(bEnabled ? Profile.ConeLimit.Swing2Motion.GetValue() : ACM_Free,
			Profile.ConeLimit.Swing2LimitDegrees);
		Joint->SetAngularTwistLimit(bEnabled ? Profile.TwistLimit.TwistMotion.GetValue() : ACM_Free,
			Profile.TwistLimit.TwistLimitDegrees);
	}
	NativeMesh->WakeAllRigidBodies();
	return true;
}

bool AProphecyNativePhysicalAgent::GetNativeBodySample(FName BoneName, FTransform& TargetWorld,
	FTransform& ActualWorld, FVector& LinearVelocity, FVector& AngularVelocityRadians,
	float& MassKg, float& PhysicsBlendWeight) const
{
	TargetWorld = ActualWorld = FTransform::Identity;
	LinearVelocity = AngularVelocityRadians = FVector::ZeroVector;
	MassKg = PhysicsBlendWeight = 0.0f;
	const USkeletalMeshComponent* NativeMesh = GetAgentMesh();
	const UPhysicalAnimationComponent* Drives = GetNativePhysicalAnimation();
	const FBodyInstance* Body = NativeMesh ? NativeMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Drives || !Drives->IsComponentTickEnabled() || !Body || !Body->IsInstanceSimulatingPhysics() ||
		NativeTargetsPendingFrame == MAX_uint64 || GFrameCounter <= NativeTargetsPendingFrame + 1 ||
		(BoneName != PhysicalRootBodyName && !NativeMesh->BoneIsChildOf(BoneName, PhysicalRootBodyName))) return false;
	TargetWorld = Drives->GetBodyTargetTransform(BoneName);
	ActualWorld = Body->GetUnrealWorldTransform();
	LinearVelocity = Body->GetUnrealWorldVelocity();
	AngularVelocityRadians = Body->GetUnrealWorldAngularVelocityInRadians();
	MassKg = Body->GetBodyMass();
	PhysicsBlendWeight = Body->PhysicsBlendWeight;
	return true;
}

// Explicit PIE-only fixture. No production actors/assets/settings are edited.
static FAutoConsoleCommandWithWorld SpawnNativePhysicalTestCommand(
	TEXT("Prophecy.NativePhysical.Spawn"),
	TEXT("Spawn isolated native physical agent/floor in PIE with no existing NN manager."),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
	{
		if (!World || World->WorldType != EWorldType::PIE) return;
		for (TActorIterator<AProphecyNNLocomotionManager> It(World); It; ++It)
		{
			UE_LOG(LogTemp, Warning, TEXT("Native test requires PIE with no existing NN manager; refusing duplicate pose IDs."));
			return;
		}
		FActorSpawnParameters Params;
		Params.ObjectFlags |= RF_Transient;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.Name = TEXT("NativePhysicalTestFloor");
		AActor* Floor = World->SpawnActor<AActor>(AActor::StaticClass(), FVector(10000, 0, 1950), FRotator::ZeroRotator, Params);
		UBoxComponent* FloorBox = NewObject<UBoxComponent>(Floor, TEXT("FloorBox"));
		Floor->SetRootComponent(FloorBox);
		Floor->AddInstanceComponent(FloorBox);
		FloorBox->SetBoxExtent(FVector(4000,4000,50));
		FloorBox->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		FloorBox->SetCollisionObjectType(ECC_WorldStatic);
		FloorBox->SetCollisionResponseToAllChannels(ECR_Block);
		FloorBox->RegisterComponent();
		Floor->SetActorLocation(FVector(10000,0,1950));
		Params.Name = TEXT("NativePhysicalTest");
		World->SpawnActor<AProphecyNativePhysicalAgent>(AProphecyNativePhysicalAgent::StaticClass(),
			FVector(10000,0,2091), FRotator::ZeroRotator, Params);
	}));
