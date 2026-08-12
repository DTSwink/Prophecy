#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Algo/Sort.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "HAL/PlatformTime.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "PreviewScene.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"

namespace ProphecyActorPawnBenchmark
{
	constexpr int32 InstanceCount = 100;
	constexpr int32 SpawnSampleCount = 11;
	constexpr int32 TickWarmupCount = 256;
	constexpr int32 TickSampleCount = 15;
	constexpr int32 TicksPerSample = 2048;
	constexpr float TickDeltaSeconds = 1.0f / 60.0f;

	struct FSummary
	{
		double Minimum = 0.0;
		double Median = 0.0;
		double Mean = 0.0;
		double Maximum = 0.0;
	};

	struct FBenchmarkScene
	{
		TUniquePtr<FPreviewScene> Scene;
		UWorld* World = nullptr;
		TArray<TObjectPtr<AActor>> Instances;
	};

	FSummary Summarize(const TArray<double>& Samples)
	{
		FSummary Result;
		if (Samples.IsEmpty())
		{
			return Result;
		}

		TArray<double> SortedSamples = Samples;
		Algo::Sort(SortedSamples);
		Result.Minimum = SortedSamples[0];
		Result.Median = SortedSamples[SortedSamples.Num() / 2];
		Result.Maximum = SortedSamples.Last();
		for (const double Sample : SortedSamples)
		{
			Result.Mean += Sample;
		}
		Result.Mean /= double(SortedSamples.Num());
		return Result;
	}

	FBenchmarkScene CreateScene(UClass* InstanceClass, const int32 Count)
	{
		FPreviewScene::ConstructionValues Values;
		Values.SetCreateDefaultLighting(false)
			.SetCreatePhysicsScene(false)
			.ShouldSimulatePhysics(false)
			.SetTransactional(false)
			.SetEditor(false);

		FBenchmarkScene Result;
		Result.Scene = MakeUnique<FPreviewScene>(Values);
		Result.World = Result.Scene->GetWorld();
		Result.Instances.Reserve(Count);
		Result.World->BeginPlay();

		FActorSpawnParameters SpawnParameters;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		SpawnParameters.ObjectFlags |= RF_Transient;
		SpawnParameters.bDeferConstruction = true;
		for (int32 Index = 0; Index < Count; ++Index)
		{
			const FTransform Transform(FVector(double(Index) * 10.0, 0.0, 0.0));
			AActor* Instance = Result.World->SpawnActor<AActor>(InstanceClass, Transform, SpawnParameters);
			if (!Instance)
			{
				continue;
			}

			Instance->PrimaryActorTick.bCanEverTick = false;
			Instance->PrimaryActorTick.bStartWithTickEnabled = false;
			if (APawn* Pawn = Cast<APawn>(Instance))
			{
				Pawn->AutoPossessAI = EAutoPossessAI::Disabled;
				Pawn->AutoPossessPlayer = EAutoReceiveInput::Disabled;
			}
			Instance->FinishSpawning(Transform, false);
			Instance->SetActorTickEnabled(false);
			Result.Instances.Add(Instance);
		}
		return Result;
	}

	double MeasureSpawnMilliseconds(UClass* InstanceClass, int32& OutSpawnedCount)
	{
		FPreviewScene::ConstructionValues Values;
		Values.SetCreateDefaultLighting(false)
			.SetCreatePhysicsScene(false)
			.ShouldSimulatePhysics(false)
			.SetTransactional(false)
			.SetEditor(false);
		TUniquePtr<FPreviewScene> Scene = MakeUnique<FPreviewScene>(Values);
		UWorld* World = Scene->GetWorld();
		World->BeginPlay();

		TArray<TObjectPtr<AActor>> Instances;
		Instances.Reserve(InstanceCount);
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		SpawnParameters.ObjectFlags |= RF_Transient;
		SpawnParameters.bDeferConstruction = true;

		const double StartSeconds = FPlatformTime::Seconds();
		for (int32 Index = 0; Index < InstanceCount; ++Index)
		{
			const FTransform Transform(FVector(double(Index) * 10.0, 0.0, 0.0));
			AActor* Instance = World->SpawnActor<AActor>(InstanceClass, Transform, SpawnParameters);
			if (!Instance)
			{
				continue;
			}

			Instance->PrimaryActorTick.bCanEverTick = false;
			Instance->PrimaryActorTick.bStartWithTickEnabled = false;
			if (APawn* Pawn = Cast<APawn>(Instance))
			{
				Pawn->AutoPossessAI = EAutoPossessAI::Disabled;
				Pawn->AutoPossessPlayer = EAutoReceiveInput::Disabled;
			}
			Instance->FinishSpawning(Transform, false);
			Instance->SetActorTickEnabled(false);
			Instances.Add(Instance);
		}
		const double ElapsedMilliseconds = (FPlatformTime::Seconds() - StartSeconds) * 1000.0;
		OutSpawnedCount = Instances.Num();
		return ElapsedMilliseconds;
	}

	double MeasureTickMillisecondsPerFrame(UWorld* World)
	{
		const double StartSeconds = FPlatformTime::Seconds();
		for (int32 TickIndex = 0; TickIndex < TicksPerSample; ++TickIndex)
		{
			World->Tick(ELevelTick::LEVELTICK_All, TickDeltaSeconds);
		}
		return ((FPlatformTime::Seconds() - StartSeconds) * 1000.0) / double(TicksPerSample);
	}

}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FProphecyAgentRuntimeContractTest,
	"Prophecy.Agent.RuntimeContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyAgentRuntimeContractTest::RunTest(const FString& Parameters)
{
	const AProphecyAgent* AgentDefaults = GetDefault<AProphecyAgent>();
	const AProphecyNNLocomotionManager* ManagerDefaults = GetDefault<AProphecyNNLocomotionManager>();
	TestEqual(
		TEXT("agent production drive is pelvis + joint torque"),
		int32(AgentDefaults->GetPhysicalDriveMode()),
		int32(EProphecyAgentPhysicalDriveMode::RootAndJointTorque));
	TestEqual(
		TEXT("manager production drive is pelvis + joint torque"),
		int32(ManagerDefaults->InitialPhysicalDriveMode),
		int32(EProphecyAgentPhysicalDriveMode::RootAndJointTorque));
	TestEqual(TEXT("foot-roll integration defaults to four steps"), ManagerDefaults->FootRollIntegrationSteps, 4);
	TestTrue(TEXT("manager defaults to the lightweight agent class"), ManagerDefaults->AgentClass == AProphecyAgent::StaticClass());
	TestTrue(TEXT("lightweight agent can be subclassed as a Blueprint"), FKismetEditorUtilities::CanCreateBlueprintOfClass(AProphecyAgent::StaticClass()));
	TestTrue(TEXT("physical agents default to MACD"), AgentDefaults->IsMACDEnabled());

	FPreviewScene::ConstructionValues Values;
	Values.SetCreateDefaultLighting(false)
		.SetCreatePhysicsScene(true)
		.ShouldSimulatePhysics(true)
		.SetTransactional(false)
		.SetEditor(false);
	TUniquePtr<FPreviewScene> Scene = MakeUnique<FPreviewScene>(Values);
	UWorld* World = Scene->GetWorld();
	if (!TestNotNull(TEXT("preview world"), World))
	{
		return false;
	}

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	SpawnParameters.ObjectFlags |= RF_Transient;
	AProphecyAgent* PhysicalAgent = World->SpawnActor<AProphecyAgent>(
		AProphecyAgent::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParameters);
	AProphecyAgent* KinematicAgent = World->SpawnActor<AProphecyAgent>(
		AProphecyAgent::StaticClass(), FVector(300.0, 0.0, 0.0), FRotator::ZeroRotator, SpawnParameters);
	if (!TestNotNull(TEXT("physical test agent"), PhysicalAgent)
		|| !TestNotNull(TEXT("kinematic test agent"), KinematicAgent))
	{
		return false;
	}
	World->BeginPlay();

	UCapsuleComponent* KinematicCapsule = KinematicAgent->GetAgentCapsule();
	USkeletalMeshComponent* KinematicMesh = KinematicAgent->GetAgentMesh();
	TestEqual(TEXT("kinematic capsule object channel"), int32(KinematicCapsule->GetCollisionObjectType()), int32(ECC_GameTraceChannel8));
	TestEqual(TEXT("kinematic capsule collision enabled"), int32(KinematicCapsule->GetCollisionEnabled()), int32(ECollisionEnabled::QueryAndPhysics));
	TestEqual(TEXT("kinematic capsule blocks kinematic capsules"), int32(KinematicCapsule->GetCollisionResponseToChannel(ECC_GameTraceChannel8)), int32(ECR_Block));
	TestEqual(TEXT("kinematic capsule blocks physical limbs"), int32(KinematicCapsule->GetCollisionResponseToChannel(ECC_GameTraceChannel9)), int32(ECR_Block));
	TestEqual(TEXT("kinematic skeletal collision disabled"), int32(KinematicMesh->GetCollisionEnabled()), int32(ECollisionEnabled::NoCollision));

	if (!TestTrue(TEXT("agent enters Physical mode through the explicit switch"), PhysicalAgent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)))
	{
		return false;
	}
	UCapsuleComponent* PhysicalCapsule = PhysicalAgent->GetAgentCapsule();
	USkeletalMeshComponent* PhysicalMesh = PhysicalAgent->GetAgentMesh();
	TestEqual(TEXT("physical capsule blocks static floor"), int32(PhysicalCapsule->GetCollisionResponseToChannel(ECC_WorldStatic)), int32(ECR_Block));
	TestEqual(TEXT("physical capsule ignores all agent capsules"), int32(PhysicalCapsule->GetCollisionResponseToChannel(ECC_GameTraceChannel8)), int32(ECR_Ignore));
	TestEqual(TEXT("physical capsule ignores physical limbs"), int32(PhysicalCapsule->GetCollisionResponseToChannel(ECC_GameTraceChannel9)), int32(ECR_Ignore));
	TestEqual(TEXT("physical limbs use the limb object channel"), int32(PhysicalMesh->GetCollisionObjectType()), int32(ECC_GameTraceChannel9));
	TestEqual(TEXT("physical limbs have physics collision"), int32(PhysicalMesh->GetCollisionEnabled()), int32(ECollisionEnabled::QueryAndPhysics));
	TestEqual(TEXT("physical limbs block kinematic capsules"), int32(PhysicalMesh->GetCollisionResponseToChannel(ECC_GameTraceChannel8)), int32(ECR_Block));
	TestEqual(TEXT("physical limbs block other physical limbs"), int32(PhysicalMesh->GetCollisionResponseToChannel(ECC_GameTraceChannel9)), int32(ECR_Block));
	TestEqual(TEXT("kinematic capsule versus physical capsule resolves to ignore"), int32(KinematicCapsule->GetCollisionResponseToComponent(PhysicalCapsule)), int32(ECR_Ignore));
	TestEqual(TEXT("kinematic capsule versus physical limb resolves to block"), int32(KinematicCapsule->GetCollisionResponseToComponent(PhysicalMesh)), int32(ECR_Block));

	TestTrue(TEXT("agent returns to Kinematic mode"), PhysicalAgent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic));
	TestEqual(TEXT("returned capsule blocks kinematic capsules"), int32(PhysicalCapsule->GetCollisionResponseToChannel(ECC_GameTraceChannel8)), int32(ECR_Block));
	TestEqual(TEXT("returned skeletal collision disabled"), int32(PhysicalMesh->GetCollisionEnabled()), int32(ECollisionEnabled::NoCollision));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FProphecyActorVsPawnBenchmark,
	"Prophecy.Agent.ActorVsPawnBenchmark",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyActorVsPawnBenchmark::RunTest(const FString& Parameters)
{
	using namespace ProphecyActorPawnBenchmark;

	TArray<double> ActorSpawnSamples;
	TArray<double> PawnSpawnSamples;
	ActorSpawnSamples.Reserve(SpawnSampleCount);
	PawnSpawnSamples.Reserve(SpawnSampleCount);
	for (int32 SampleIndex = 0; SampleIndex < SpawnSampleCount; ++SampleIndex)
	{
		int32 ActorCount = 0;
		int32 PawnCount = 0;
		if ((SampleIndex & 1) == 0)
		{
			ActorSpawnSamples.Add(MeasureSpawnMilliseconds(AActor::StaticClass(), ActorCount));
			PawnSpawnSamples.Add(MeasureSpawnMilliseconds(APawn::StaticClass(), PawnCount));
		}
		else
		{
			PawnSpawnSamples.Add(MeasureSpawnMilliseconds(APawn::StaticClass(), PawnCount));
			ActorSpawnSamples.Add(MeasureSpawnMilliseconds(AActor::StaticClass(), ActorCount));
		}
		if (!TestEqual(TEXT("bare Actor instances spawned"), ActorCount, InstanceCount)
			|| !TestEqual(TEXT("bare Pawn instances spawned"), PawnCount, InstanceCount))
		{
			return false;
		}
	}

	FBenchmarkScene EmptyScene = CreateScene(AActor::StaticClass(), 0);
	FBenchmarkScene ActorScene = CreateScene(AActor::StaticClass(), InstanceCount);
	FBenchmarkScene PawnScene = CreateScene(APawn::StaticClass(), InstanceCount);
	if (!TestNotNull(TEXT("empty benchmark world"), EmptyScene.World)
		|| !TestNotNull(TEXT("Actor benchmark world"), ActorScene.World)
		|| !TestNotNull(TEXT("Pawn benchmark world"), PawnScene.World)
		|| !TestEqual(TEXT("steady-state Actor count"), ActorScene.Instances.Num(), InstanceCount)
		|| !TestEqual(TEXT("steady-state Pawn count"), PawnScene.Instances.Num(), InstanceCount))
	{
		return false;
	}

	for (const TObjectPtr<AActor>& Instance : PawnScene.Instances)
	{
		const APawn* Pawn = CastChecked<APawn>(Instance.Get());
		if (!TestNull(TEXT("benchmark Pawn remains unpossessed"), Pawn->GetController()))
		{
			return false;
		}
	}

	for (int32 WarmupIndex = 0; WarmupIndex < TickWarmupCount; ++WarmupIndex)
	{
		EmptyScene.World->Tick(ELevelTick::LEVELTICK_All, TickDeltaSeconds);
		ActorScene.World->Tick(ELevelTick::LEVELTICK_All, TickDeltaSeconds);
		PawnScene.World->Tick(ELevelTick::LEVELTICK_All, TickDeltaSeconds);
	}

	TArray<double> EmptyTickSamples;
	TArray<double> ActorTickSamples;
	TArray<double> PawnTickSamples;
	EmptyTickSamples.Reserve(TickSampleCount);
	ActorTickSamples.Reserve(TickSampleCount);
	PawnTickSamples.Reserve(TickSampleCount);
	for (int32 SampleIndex = 0; SampleIndex < TickSampleCount; ++SampleIndex)
	{
		switch (SampleIndex % 3)
		{
		case 0:
			EmptyTickSamples.Add(MeasureTickMillisecondsPerFrame(EmptyScene.World));
			ActorTickSamples.Add(MeasureTickMillisecondsPerFrame(ActorScene.World));
			PawnTickSamples.Add(MeasureTickMillisecondsPerFrame(PawnScene.World));
			break;
		case 1:
			PawnTickSamples.Add(MeasureTickMillisecondsPerFrame(PawnScene.World));
			EmptyTickSamples.Add(MeasureTickMillisecondsPerFrame(EmptyScene.World));
			ActorTickSamples.Add(MeasureTickMillisecondsPerFrame(ActorScene.World));
			break;
		default:
			ActorTickSamples.Add(MeasureTickMillisecondsPerFrame(ActorScene.World));
			PawnTickSamples.Add(MeasureTickMillisecondsPerFrame(PawnScene.World));
			EmptyTickSamples.Add(MeasureTickMillisecondsPerFrame(EmptyScene.World));
			break;
		}
	}

	const FSummary ActorSpawn = Summarize(ActorSpawnSamples);
	const FSummary PawnSpawn = Summarize(PawnSpawnSamples);
	const FSummary EmptyTick = Summarize(EmptyTickSamples);
	const FSummary ActorTick = Summarize(ActorTickSamples);
	const FSummary PawnTick = Summarize(PawnTickSamples);
	const int32 ActorBytes = AActor::StaticClass()->GetStructureSize();
	const int32 PawnBytes = APawn::StaticClass()->GetStructureSize();
	const double ActorIncrementMicroseconds = (ActorTick.Median - EmptyTick.Median) * 1000.0;
	const double PawnIncrementMicroseconds = (PawnTick.Median - EmptyTick.Median) * 1000.0;
	const double PawnMinusActorMicroseconds = (PawnTick.Median - ActorTick.Median) * 1000.0;

	const FString Result = FString::Printf(
		TEXT("PROPHECY_ACTOR_PAWN_BENCH instances=%d actor_bytes=%d pawn_bytes=%d byte_delta_each=%d ")
		TEXT("actor_spawn_ms_median=%.6f pawn_spawn_ms_median=%.6f spawn_delta_ms=%.6f ")
		TEXT("empty_tick_ms_median=%.9f actor_tick_ms_median=%.9f pawn_tick_ms_median=%.9f ")
		TEXT("actor_increment_us=%.6f pawn_increment_us=%.6f pawn_minus_actor_us=%.6f ")
		TEXT("actor_spawn_range_ms=[%.6f,%.6f] pawn_spawn_range_ms=[%.6f,%.6f] ")
		TEXT("actor_tick_range_ms=[%.9f,%.9f] pawn_tick_range_ms=[%.9f,%.9f]"),
		InstanceCount,
		ActorBytes,
		PawnBytes,
		PawnBytes - ActorBytes,
		ActorSpawn.Median,
		PawnSpawn.Median,
		PawnSpawn.Median - ActorSpawn.Median,
		EmptyTick.Median,
		ActorTick.Median,
		PawnTick.Median,
		ActorIncrementMicroseconds,
		PawnIncrementMicroseconds,
		PawnMinusActorMicroseconds,
		ActorSpawn.Minimum,
		ActorSpawn.Maximum,
		PawnSpawn.Minimum,
		PawnSpawn.Maximum,
		ActorTick.Minimum,
		ActorTick.Maximum,
		PawnTick.Minimum,
		PawnTick.Maximum);
	AddInfo(Result);
	UE_LOG(LogTemp, Display, TEXT("%s"), *Result);
	return true;
}

#endif
