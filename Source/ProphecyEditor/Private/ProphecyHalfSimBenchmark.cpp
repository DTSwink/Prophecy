#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

namespace
{
// Benchmark-only migration on freshly spawned PIE copies. No Blueprint/level edits.
void PrepareHalfSimCrowd(const TArray<FString>& Args, UWorld* World)
{
	if (!World || World->WorldType != EWorldType::PIE || Args.Num() != 1) return;
	const bool bHalf = Args[0].Equals(TEXT("HalfSim"));
	if (!bHalf && !Args[0].Equals(TEXT("Physical"))) return;
	TArray<AProphecyAgent*> Originals;
	for (TActorIterator<AProphecyAgent> It(World); It; ++It) Originals.Add(*It);
	if (Originals.IsEmpty()) return;
	AProphecyAgent* Prototype = Originals[0];
	const auto DriveMode = Prototype->PhysicalDriveMode;
	for (AProphecyAgent* A : Originals)
	{
		A->bAutoEnsureStandaloneNNManager = false;
		A->SetActorTickEnabled(false);
		A->SetActorEnableCollision(false);
		A->SetActorHiddenInGame(true);
	}
	TArray<AProphecyNNLocomotionManager*> OldManagers;
	for (TActorIterator<AProphecyNNLocomotionManager> It(World); It; ++It) OldManagers.Add(*It);
	for (auto* Manager : OldManagers) Manager->Destroy();
	if (!IsValid(Prototype)) return;

	TArray<AProphecyAgent*> Crowd;
	for (int32 I = 0; I < 100; ++I)
	{
		FActorSpawnParameters P;
		P.Template = Prototype;
		P.bDeferConstruction = true;
		P.ObjectFlags |= RF_Transient;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const FTransform Transform(FRotator::ZeroRotator, FVector((I % 10 - 4.5) * 300., (I / 10 - 4.5) * 300., 100.));
		auto* A = World->SpawnActor<AProphecyAgent>(Prototype->GetClass(), Transform, P);
		if (!A) continue;
		A->bAutoEnsureStandaloneNNManager = false;
		A->AutoPossessPlayer = EAutoReceiveInput::Disabled;
		A->bShowKinematicDebugMesh = false;
		A->SetAgentHandle(FProphecyAgentHandle{});
		A->FinishSpawning(Transform);
		A->bAutoEnsureStandaloneNNManager = true;
		A->SetActorEnableCollision(true);
		A->SetActorHiddenInGame(false);
		A->StopLocomotionInput();
		Crowd.Add(A);
	}
	// Originals are only the transient PIE copies, not the user's editor actors.
	for (auto* A : Originals) if (IsValid(A)) A->Destroy();
	if (Crowd.Num() != 100) return;
	FActorSpawnParameters P;
	P.bDeferConstruction = true;
	P.ObjectFlags |= RF_Transient;
	auto* Manager = World->SpawnActor<AProphecyNNLocomotionManager>(AProphecyNNLocomotionManager::StaticClass(), FTransform::Identity, P);
	Manager->ConfigureSimpleLocomotionTest();
	Manager->CrowdSize = 100;
	Manager->InitialPhysicalDriveMode = DriveMode;
	Manager->WalkOnnxModelPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_b100.onnx");
	Manager->WalkRuntimeContractPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json");
	Manager->FinishSpawning(FTransform::Identity);

	int32 Configured = 0;
	for (AProphecyAgent* A : Crowd)
	{
		if (!A->HasValidAgentHandle()) continue;
		A->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
		A->StopNNAttack();
		USkeletalMeshComponent* Physical = A->GetPoseReferenceMesh();
		USkeletalMeshComponent* Mesh = A->GetAgentMesh();
		if (bHalf)
		{
			if (!Physical || Physical == Mesh || !Physical->GetSkeletalMeshAsset()) continue;
			Mesh->SetSkeletalMesh(Physical->GetSkeletalMeshAsset());
			Mesh->SetRelativeTransform(Physical->GetRelativeTransform());
			for (int32 I = 0; I < Physical->GetNumMaterials(); ++I) Mesh->SetMaterial(I, Physical->GetMaterial(I));
			Physical->SetAllBodiesSimulatePhysics(false);
			Physical->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Physical->SetGenerateOverlapEvents(false);
			Physical->SetComponentTickEnabled(false);
			Physical->SetAnimInstanceClass(nullptr);
			Physical->SetVisibility(false);
			Physical->SetHiddenInGame(true);
			Physical->SetSkeletalMesh(nullptr);
			// GetPoseReferenceMesh's normal fallback becomes the inherited Mesh.
			Physical->Rename(TEXT("BenchmarkDisabledPhysicalMesh"), nullptr, REN_DontCreateRedirectors | REN_NonTransactional);
			Mesh->SetVisibility(true);
			Mesh->SetHiddenInGame(false);
			Mesh->AddTickPrerequisiteActor(Manager);
		}
		USkeletalMeshComponent* Active = A->GetPoseReferenceMesh();
		// Equal render policy in both arms, all 100 agents included regardless of visibility.
		Active->SetVisibility(true);
		Active->SetHiddenInGame(false);
		Active->SetForcedLOD(1);
		Active->SetCastShadow(false);
		Active->SetDisablePostProcessBlueprint(true);
		Active->bEnableUpdateRateOptimizations = false;
		Active->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		if (A->SetSimulationMode(bHalf ? EProphecyAgentSimulationMode::HalfSim : EProphecyAgentSimulationMode::Physical)) ++Configured;
		// Native physical animation owns Half Sim. The legacy Blueprint per-body
		// velocity follower is neither needed nor allowed to move the disabled mesh.
		A->SetActorTickEnabled(!bHalf);
	}

	// Identical floor/camera for each pass; no actor-to-actor pile-up at startup.
	FActorSpawnParameters SceneP;
	SceneP.ObjectFlags |= RF_Transient;
	auto* Floor = World->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FVector(0, 0, -60), FRotator::ZeroRotator, SceneP);
	Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
	Floor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
	Floor->SetActorScale3D(FVector(50, 50, 1));
	Floor->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
	auto* Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FVector(-3500, 0, 2600), FRotator(-35, 0, 0), SceneP);
	Camera->GetCameraComponent()->SetFieldOfView(65);
	if (auto* PC = World->GetFirstPlayerController()) PC->SetViewTarget(Camera);
	UE_LOG(LogTemp, Display, TEXT("HALFSIM_BENCH configured=%d requested=100 mode=%s"), Configured, *Args[0]);
}
FAutoConsoleCommandWithWorldAndArgs PrepareCommand(TEXT("Prophecy.HalfSimBench.Prepare"),
	TEXT("PIE-only 100-agent benchmark setup. Argument: HalfSim or Physical. No asset saves."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&PrepareHalfSimCrowd));
}
