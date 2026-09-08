#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "AssetCompilingManager.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraph/EdGraphNode.h"
#include "Engine/Blueprint.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PreviewScene.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "UObject/UObjectGlobals.h"

namespace ProphecyBoatBuoyancyAutomation
{
constexpr float FixedDeltaSeconds = 1.0f / 60.0f;
constexpr float DurationSeconds = 12.0f;
constexpr float FinalWindowSeconds = 3.0f;
constexpr float BoatStartZ = -75.531329f;
constexpr float SafetyFloorTopZ = -1000.0f;
constexpr int32 SampleCount = static_cast<int32>(DurationSeconds / FixedDeltaSeconds);

// Start the real project character above the boat and let CharacterMovement
// establish a genuine floor hit. Spawning at the old in-level transform put
// the capsule through the hull, so that case never loaded the boat at all.
const FVector CharacterRelativeLocation(-29.2983799, -12.6322797, 220.0);
const FVector CubeRelativeLocation(-29.2983799, -12.6322797, 70.0);

enum class ELoadCase : uint8
{
	Empty,
	Cube90Kg,
	Character
};

struct FSample
{
	float Time = 0.0f;
	float Z = 0.0f;
	float VerticalVelocity = 0.0f;
	float Tilt = 0.0f;
};

struct FCaseResult
{
	FString Name;
	float BoatMassKg = 0.0f;
	float SimulatedLoadMassKg = 0.0f;
	float CharacterMovementMassKg = 0.0f;
	float InitialLoadZ = 0.0f;
	float MinimumLoadZ = 0.0f;
	float FinalLoadZ = 0.0f;
	int32 CharacterBasedOnBoatFrames = 0;
	TArray<FString> LoadComponents;
	TArray<FSample> Samples;
	float InitialZ = 0.0f;
	float MinimumZ = 0.0f;
	float FinalZ = 0.0f;
	float SettledMeanZ = 0.0f;
	float SettledStdDevZ = 0.0f;
	float SettledTrendCmPerSecond = 0.0f;
	float SettledMeanAbsVerticalVelocity = 0.0f;
	float MaximumTiltDegrees = 0.0f;
	float DepthBelowEmptyMeanCm = 0.0f;
	float SinkThresholdZ = 0.0f;
	bool bSinking = false;
	bool bSettled = false;
};

struct FCaseWorld
{
	TUniquePtr<FPreviewScene> Scene;
	TObjectPtr<AActor> Boat = nullptr;
	TObjectPtr<UPrimitiveComponent> BoatMesh = nullptr;
	TObjectPtr<AActor> Load = nullptr;
	TObjectPtr<APlayerController> Controller = nullptr;
	FCaseResult Result;
};

struct FRunnerState
{
	TArray<FCaseWorld> Cases;
	int32 SampleIndex = 0;
	bool bTickInFlight = false;
};

FString CaseName(const ELoadCase LoadCase)
{
	switch (LoadCase)
	{
	case ELoadCase::Cube90Kg:
		return TEXT("cube_90kg");
	case ELoadCase::Character:
		return TEXT("character");
	default:
		return TEXT("empty");
	}
}

UPrimitiveComponent* FindPrimitiveComponent(AActor* Actor, const FName ComponentName)
{
	if (!Actor)
	{
		return nullptr;
	}

	TInlineComponentArray<UPrimitiveComponent*> Components(Actor);
	for (UPrimitiveComponent* Component : Components)
	{
		if (Component && Component->GetFName() == ComponentName)
		{
			return Component;
		}
	}
	return nullptr;
}

float MeasureSimulatedMass(AActor* Actor, TArray<FString>& OutComponents)
{
	float TotalMass = 0.0f;
	if (!Actor)
	{
		return TotalMass;
	}

	TInlineComponentArray<UPrimitiveComponent*> Components(Actor);
	for (UPrimitiveComponent* Component : Components)
	{
		if (Component && Component->IsSimulatingPhysics())
		{
			const float Mass = Component->GetMass();
			TotalMass += Mass;
			OutComponents.Add(FString::Printf(TEXT("%s:%.4f"), *Component->GetName(), Mass));
		}
	}
	return TotalMass;
}

bool BuildCaseWorld(
	const ELoadCase LoadCase,
	UClass* BoatClass,
	UClass* CharacterClass,
	UStaticMesh* CubeMesh,
	FCaseWorld& OutCase,
	FAutomationTestBase& Test)
{
	FPreviewScene::ConstructionValues Values;
	Values.SetCreateDefaultLighting(false)
		.SetCreatePhysicsScene(true)
		.ShouldSimulatePhysics(true)
		.SetTransactional(false)
		.SetEditor(false)
		.ForceUseMovementComponentInNonGameWorld(true);
	OutCase.Scene = MakeUnique<FPreviewScene>(Values);
	UWorld* World = OutCase.Scene->GetWorld();
	if (!Test.TestNotNull(*FString::Printf(TEXT("%s preview world"), *CaseName(LoadCase)), World))
	{
		return false;
	}

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	SpawnParameters.ObjectFlags |= RF_Transient;

	AStaticMeshActor* Floor = World->SpawnActor<AStaticMeshActor>(
		AStaticMeshActor::StaticClass(),
		FVector(0.0, 0.0, SafetyFloorTopZ - 50.0),
		FRotator::ZeroRotator,
		SpawnParameters);
	if (!Test.TestNotNull(TEXT("safety floor"), Floor))
	{
		return false;
	}
	UStaticMeshComponent* FloorMesh = Floor->GetStaticMeshComponent();
	FloorMesh->SetMobility(EComponentMobility::Static);
	FloorMesh->SetStaticMesh(CubeMesh);
	FloorMesh->SetCollisionProfileName(TEXT("BlockAll"));
	Floor->SetActorScale3D(FVector(50.0, 50.0, 1.0));

	OutCase.Boat = World->SpawnActor<AActor>(
		BoatClass,
		FVector(0.0, 0.0, BoatStartZ),
		FRotator::ZeroRotator,
		SpawnParameters);
	if (!Test.TestNotNull(*FString::Printf(TEXT("%s boat"), *CaseName(LoadCase)), OutCase.Boat.Get()))
	{
		return false;
	}
	OutCase.BoatMesh = FindPrimitiveComponent(OutCase.Boat, TEXT("SM_Boat"));
	if (!Test.TestNotNull(TEXT("BP_Boat.SM_Boat"), OutCase.BoatMesh.Get()))
	{
		return false;
	}
	// The live BP_Boat actor in mybasic has these component-instance overrides.
	// Reproduce them explicitly because a raw class spawn defaults physics off.
	OutCase.BoatMesh->SetCollisionProfileName(TEXT("PhysicsActor"));
	OutCase.BoatMesh->SetSimulatePhysics(true);
	if (!Test.TestTrue(TEXT("BP_Boat.SM_Boat simulates physics"), OutCase.BoatMesh->IsSimulatingPhysics()))
	{
		return false;
	}

	OutCase.Result.Name = CaseName(LoadCase);
	OutCase.Result.BoatMassKg = OutCase.BoatMesh->GetMass();

	if (LoadCase == ELoadCase::Cube90Kg)
	{
		AStaticMeshActor* Cube = World->SpawnActor<AStaticMeshActor>(
			AStaticMeshActor::StaticClass(),
			FVector(CubeRelativeLocation.X, CubeRelativeLocation.Y, BoatStartZ + CubeRelativeLocation.Z),
			FRotator::ZeroRotator,
			SpawnParameters);
		if (!Test.TestNotNull(TEXT("90 kg cube"), Cube))
		{
			return false;
		}
		OutCase.Load = Cube;
		UStaticMeshComponent* CubeComponent = Cube->GetStaticMeshComponent();
		CubeComponent->SetMobility(EComponentMobility::Movable);
		CubeComponent->SetStaticMesh(CubeMesh);
		Cube->SetActorScale3D(FVector(0.5));
		CubeComponent->SetCollisionProfileName(TEXT("PhysicsActor"));
		CubeComponent->SetSimulatePhysics(true);
		CubeComponent->SetMassOverrideInKg(NAME_None, 90.0f, true);
		OutCase.Result.SimulatedLoadMassKg = CubeComponent->GetMass();
		OutCase.Result.LoadComponents.Add(
			FString::Printf(TEXT("%s:%.4f"), *CubeComponent->GetName(), CubeComponent->GetMass()));
	}
	else if (LoadCase == ELoadCase::Character)
	{
		OutCase.Load = World->SpawnActor<AActor>(
			CharacterClass,
			FVector(
				CharacterRelativeLocation.X,
				CharacterRelativeLocation.Y,
				BoatStartZ + CharacterRelativeLocation.Z),
			FRotator(0.0, 4.2599558, 0.0),
			SpawnParameters);
		if (!Test.TestNotNull(TEXT("real character"), OutCase.Load.Get()))
		{
			return false;
		}
		if (UCharacterMovementComponent* Movement =
			OutCase.Load->FindComponentByClass<UCharacterMovementComponent>())
		{
			OutCase.Result.CharacterMovementMassKg = Movement->Mass;
			Movement->bRunPhysicsWithNoController = true;
			Movement->SetComponentTickEnabled(true);
		}
		OutCase.Controller = World->SpawnActor<APlayerController>(
			APlayerController::StaticClass(),
			FVector::ZeroVector,
			FRotator::ZeroRotator,
			SpawnParameters);
	}

	World->BeginPlay();
	if (!World->HasBegunPlay())
	{
		World->GetWorldSettings()->NotifyBeginPlay();
		World->GetWorldSettings()->NotifyMatchStarted();
	}
	if (OutCase.Controller)
	{
		if (APawn* Pawn = Cast<APawn>(OutCase.Load))
		{
			OutCase.Controller->Possess(Pawn);
			Pawn->DispatchRestart(false);
		}
		if (UCharacterMovementComponent* Movement =
			OutCase.Load->FindComponentByClass<UCharacterMovementComponent>())
		{
			// A raw pawn in a transient preview world is not restarted by a
			// GameMode. Explicitly enter Falling so gravity and floor finding run
			// exactly as they do for a player spawned by gameplay.
			Movement->Activate(true);
			Movement->SetComponentTickEnabled(true);
			Movement->SetMovementMode(MOVE_Falling);
			Movement->Velocity = FVector::ZeroVector;
		}
		OutCase.Load->SetActorTickEnabled(true);
	}
	// Placed BP_Boat instances have ticking enabled in the user's level. A
	// transient spawn does not inherit per-instance tick state, so make the test
	// match the live actor before measuring its Event Tick buoyancy graph.
	OutCase.Boat->SetActorTickEnabled(true);
	if (!Test.TestTrue(TEXT("transient BP_Boat actor tick is enabled"), OutCase.Boat->IsActorTickEnabled()))
	{
		return false;
	}
	OutCase.BoatMesh->WakeAllRigidBodies();
	if (OutCase.Load)
	{
		OutCase.Result.InitialLoadZ = OutCase.Load->GetActorLocation().Z;
		OutCase.Result.MinimumLoadZ = OutCase.Result.InitialLoadZ;
		OutCase.Result.FinalLoadZ = OutCase.Result.InitialLoadZ;
		TInlineComponentArray<UPrimitiveComponent*> LoadComponents(OutCase.Load);
		for (UPrimitiveComponent* Component : LoadComponents)
		{
			if (Component && Component->IsSimulatingPhysics())
			{
				Component->WakeAllRigidBodies();
			}
		}
	}
	return true;
}

void Summarize(FCaseResult& Result)
{
	if (Result.Samples.IsEmpty())
	{
		return;
	}

	Result.InitialZ = Result.Samples[0].Z;
	Result.MinimumZ = Result.Samples[0].Z;
	Result.FinalZ = Result.Samples.Last().Z;
	Result.MaximumTiltDegrees = 0.0f;
	for (const FSample& Sample : Result.Samples)
	{
		Result.MinimumZ = FMath::Min(Result.MinimumZ, Sample.Z);
		Result.MaximumTiltDegrees = FMath::Max(Result.MaximumTiltDegrees, Sample.Tilt);
	}

	const float WindowStart = FMath::Max(DurationSeconds - FinalWindowSeconds, 0.0f);
	int32 WindowCount = 0;
	double SumTime = 0.0;
	double SumZ = 0.0;
	for (const FSample& Sample : Result.Samples)
	{
		if (Sample.Time >= WindowStart)
		{
			++WindowCount;
			SumTime += Sample.Time;
			SumZ += Sample.Z;
		}
	}
	if (WindowCount == 0)
	{
		return;
	}

	const double MeanTime = SumTime / WindowCount;
	const double MeanZ = SumZ / WindowCount;
	double SumSquaredZ = 0.0;
	double TrendNumerator = 0.0;
	double TrendDenominator = 0.0;
	double SumAbsVelocity = 0.0;
	for (const FSample& Sample : Result.Samples)
	{
		if (Sample.Time < WindowStart)
		{
			continue;
		}
		const double TimeDelta = Sample.Time - MeanTime;
		const double ZDelta = Sample.Z - MeanZ;
		SumSquaredZ += ZDelta * ZDelta;
		TrendNumerator += TimeDelta * ZDelta;
		TrendDenominator += TimeDelta * TimeDelta;
		SumAbsVelocity += FMath::Abs(Sample.VerticalVelocity);
	}

	Result.SettledMeanZ = static_cast<float>(MeanZ);
	Result.SettledStdDevZ = static_cast<float>(FMath::Sqrt(SumSquaredZ / WindowCount));
	Result.SettledTrendCmPerSecond = TrendDenominator > UE_SMALL_NUMBER
		? static_cast<float>(TrendNumerator / TrendDenominator)
		: 0.0f;
	Result.SettledMeanAbsVerticalVelocity = static_cast<float>(SumAbsVelocity / WindowCount);
}

FString JsonEscape(FString Value)
{
	Value.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	Value.ReplaceInline(TEXT("\""), TEXT("\\\""));
	Value.ReplaceInline(TEXT("\r"), TEXT("\\r"));
	Value.ReplaceInline(TEXT("\n"), TEXT("\\n"));
	return Value;
}

FString ResultToJson(const FCaseResult& Result)
{
	TArray<FString> Components;
	for (const FString& Component : Result.LoadComponents)
	{
		Components.Add(FString::Printf(TEXT("\"%s\""), *JsonEscape(Component)));
	}
	return FString::Printf(
		TEXT("    {\n")
		TEXT("      \"case\": \"%s\",\n")
		TEXT("      \"samples\": %d,\n")
		TEXT("      \"boat_mass_kg\": %.6f,\n")
		TEXT("      \"simulated_load_mass_kg\": %.6f,\n")
		TEXT("      \"movement_mass_kg\": %.6f,\n")
		TEXT("      \"initial_load_z\": %.6f,\n")
		TEXT("      \"minimum_load_z\": %.6f,\n")
		TEXT("      \"final_load_z\": %.6f,\n")
		TEXT("      \"character_based_on_boat_frames\": %d,\n")
		TEXT("      \"load_components\": [%s],\n")
		TEXT("      \"initial_z\": %.6f,\n")
		TEXT("      \"minimum_z\": %.6f,\n")
		TEXT("      \"final_z\": %.6f,\n")
		TEXT("      \"settled_mean_z\": %.6f,\n")
		TEXT("      \"settled_stddev_z\": %.6f,\n")
		TEXT("      \"settled_trend_cm_s\": %.6f,\n")
		TEXT("      \"settled_mean_abs_vz\": %.6f,\n")
		TEXT("      \"maximum_tilt_deg\": %.6f,\n")
		TEXT("      \"empty_baseline_z\": %.6f,\n")
		TEXT("      \"sink_threshold_z\": %.6f,\n")
		TEXT("      \"depth_below_empty_mean_cm\": %.6f,\n")
		TEXT("      \"verdict\": \"%s\",\n")
		TEXT("      \"settled\": %s\n")
		TEXT("    }"),
		*Result.Name,
		Result.Samples.Num(),
		Result.BoatMassKg,
		Result.SimulatedLoadMassKg,
		Result.CharacterMovementMassKg,
		Result.InitialLoadZ,
		Result.MinimumLoadZ,
		Result.FinalLoadZ,
		Result.CharacterBasedOnBoatFrames,
		*FString::Join(Components, TEXT(", ")),
		Result.InitialZ,
		Result.MinimumZ,
		Result.FinalZ,
		Result.SettledMeanZ,
		Result.SettledStdDevZ,
		Result.SettledTrendCmPerSecond,
		Result.SettledMeanAbsVerticalVelocity,
		Result.MaximumTiltDegrees,
		Result.SettledMeanZ + Result.DepthBelowEmptyMeanCm,
		Result.SinkThresholdZ,
		Result.DepthBelowEmptyMeanCm,
		Result.bSinking ? TEXT("SINKING") : TEXT("FLOATING"),
		Result.bSettled ? TEXT("true") : TEXT("false"));
}

bool WriteReport(const TArray<FCaseWorld>& Cases)
{
	TArray<FString> JsonResults;
	for (const FCaseWorld& Case : Cases)
	{
		JsonResults.Add(ResultToJson(Case.Result));
	}
	const FString Report = FString::Printf(
		TEXT("{\n")
		TEXT("  \"ok\": true,\n")
		TEXT("  \"pipeline\": \"headless Unreal Automation Test using three transient GamePreview physics worlds\",\n")
		TEXT("  \"loaded_project_map\": false,\n")
		TEXT("  \"created_map_asset\": false,\n")
		TEXT("  \"duration_per_case_seconds\": %.3f,\n")
		TEXT("  \"final_window_seconds\": %.3f,\n")
		TEXT("  \"criteria\": {\n")
		TEXT("    \"sinking\": \"mean >75 cm below empty (or 4x empty std), 250 cm deep excursion, or >10 cm/s continued descent while >50 cm low\",\n")
		TEXT("    \"settled\": \"abs trend <5 cm/s, std <25 cm, mean abs Vz <25 cm/s\"\n")
		TEXT("  },\n")
		TEXT("  \"results\": [\n%s\n  ]\n")
		TEXT("}\n"),
		DurationSeconds,
		FinalWindowSeconds,
		*FString::Join(JsonResults, TEXT(",\n")));

	const FString OutputDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling/BoatBuoyancy"));
	IFileManager::Get().MakeDirectory(*OutputDirectory, true);
	return FFileHelper::SaveStringToFile(
		Report,
		*FPaths::Combine(OutputDirectory, TEXT("latest_metrics.json")),
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

bool DumpBoatEventGraph()
{
	UBlueprint* Blueprint = LoadObject<UBlueprint>(
		nullptr,
		TEXT("/Game/_mygame/assets/boat/StaticMeshes/BP_Boat.BP_Boat"));
	UEdGraph* Graph = Blueprint ? FBlueprintEditorUtils::FindEventGraph(Blueprint) : nullptr;
	if (!Graph)
	{
		return false;
	}

	TArray<FString> Lines;
	Lines.Add(FString::Printf(TEXT("Graph: %s nodes=%d"), *Graph->GetPathName(), Graph->Nodes.Num()));
	for (const UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node)
		{
			continue;
		}
		Lines.Add(FString::Printf(
			TEXT("\nNODE [%d,%d] %s | %s"),
			Node->NodePosX,
			Node->NodePosY,
			*Node->GetClass()->GetName(),
			*Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString().Replace(TEXT("\n"), TEXT(" / "))));
		for (const UEdGraphPin* Pin : Node->Pins)
		{
			if (!Pin)
			{
				continue;
			}
			TArray<FString> Links;
			for (const UEdGraphPin* LinkedPin : Pin->LinkedTo)
			{
				if (LinkedPin && LinkedPin->GetOwningNode())
				{
					Links.Add(FString::Printf(
						TEXT("%s.%s"),
						*LinkedPin->GetOwningNode()->GetNodeTitle(ENodeTitleType::ListView).ToString().Replace(TEXT("\n"), TEXT(" / ")),
						*LinkedPin->PinName.ToString()));
				}
			}
			Lines.Add(FString::Printf(
				TEXT("  %s %s type=%s default='%s' links=[%s]"),
				Pin->Direction == EGPD_Input ? TEXT("IN ") : TEXT("OUT"),
				*Pin->PinName.ToString(),
				*Pin->PinType.PinCategory.ToString(),
				*Pin->DefaultValue,
				*FString::Join(Links, TEXT(", "))));
		}
	}

	const FString OutputDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling/BoatBuoyancy"));
	IFileManager::Get().MakeDirectory(*OutputDirectory, true);
	return FFileHelper::SaveStringArrayToFile(
		Lines,
		*FPaths::Combine(OutputDirectory, TEXT("BP_Boat_EventGraph.txt")),
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
} // namespace ProphecyBoatBuoyancyAutomation

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(
	FProphecyBoatPhysicsFramesCommand,
	TSharedPtr<ProphecyBoatBuoyancyAutomation::FRunnerState>,
	State,
	FAutomationTestBase*,
	Test);

bool FProphecyBoatPhysicsFramesCommand::Update()
{
	using namespace ProphecyBoatBuoyancyAutomation;
	if (!State.IsValid() || !Test)
	{
		return true;
	}

	// Sampling on the next automation frame is intentional. Chaos can publish
	// its proxy readback after UWorld::Tick returns, so reading immediately in
	// the same call produced a frozen transform with a nonzero body velocity.
	if (State->bTickInFlight)
	{
		const float Time = State->SampleIndex * FixedDeltaSeconds;
		for (FCaseWorld& Case : State->Cases)
		{
			const FVector Location = Case.BoatMesh->GetComponentLocation();
			const FRotator Rotation = Case.BoatMesh->GetComponentRotation();
			FSample& Sample = Case.Result.Samples.AddDefaulted_GetRef();
			Sample.Time = Time;
			Sample.Z = Location.Z;
			Sample.VerticalVelocity = Case.BoatMesh->GetPhysicsLinearVelocity().Z;
			Sample.Tilt = FMath::Max(FMath::Abs(Rotation.Roll), FMath::Abs(Rotation.Pitch));
			if (Case.Load)
			{
				const float LoadZ = Case.Load->GetActorLocation().Z;
				Case.Result.MinimumLoadZ = FMath::Min(Case.Result.MinimumLoadZ, LoadZ);
				Case.Result.FinalLoadZ = LoadZ;
				if (UCharacterMovementComponent* Movement =
					Case.Load->FindComponentByClass<UCharacterMovementComponent>())
				{
					if (Movement->CurrentFloor.HitResult.GetComponent() == Case.BoatMesh.Get())
					{
						++Case.Result.CharacterBasedOnBoatFrames;
					}
				}
			}
		}
		State->bTickInFlight = false;
		if (State->SampleIndex >= SampleCount)
		{
			return true;
		}
	}

	for (FCaseWorld& Case : State->Cases)
	{
		Case.Scene->GetWorld()->Tick(LEVELTICK_All, FixedDeltaSeconds);
	}
	++State->SampleIndex;
	State->bTickInFlight = true;
	return false;
}

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(
	FProphecyBoatFinalizeMetricsCommand,
	TSharedPtr<ProphecyBoatBuoyancyAutomation::FRunnerState>,
	State,
	FAutomationTestBase*,
	Test);

bool FProphecyBoatFinalizeMetricsCommand::Update()
{
	using namespace ProphecyBoatBuoyancyAutomation;
	if (!State.IsValid() || !Test || State->Cases.IsEmpty())
	{
		return true;
	}

	for (FCaseWorld& Case : State->Cases)
	{
		if (Case.Result.Name == TEXT("character"))
		{
			Case.Result.LoadComponents.Reset();
			Case.Result.SimulatedLoadMassKg =
				MeasureSimulatedMass(Case.Load, Case.Result.LoadComponents);
		}
		Summarize(Case.Result);
	}
	const FCaseResult& Empty = State->Cases[0].Result;
	const float SinkThreshold = Empty.SettledMeanZ - FMath::Max(75.0f, 4.0f * Empty.SettledStdDevZ);
	for (FCaseWorld& Case : State->Cases)
	{
		FCaseResult& Result = Case.Result;
		Result.SinkThresholdZ = SinkThreshold;
		Result.DepthBelowEmptyMeanCm = Empty.SettledMeanZ - Result.SettledMeanZ;
		const bool bContinuingDescent = Result.SettledTrendCmPerSecond < -10.0f
			&& Result.FinalZ < Empty.SettledMeanZ - 50.0f;
		Result.bSinking = Result.SettledMeanZ < SinkThreshold
			|| Result.MinimumZ < Empty.SettledMeanZ - 250.0f
			|| bContinuingDescent;
		Result.bSettled = FMath::Abs(Result.SettledTrendCmPerSecond) < 5.0f
			&& Result.SettledStdDevZ < 25.0f
			&& Result.SettledMeanAbsVerticalVelocity < 25.0f;
		Test->AddInfo(FString::Printf(
			TEXT("%s: boat=%.3fkg load=%.3fkg move=%.3fkg meanZ=%.3f depth=%.3f trend=%.3f std=%.3f based=%d verdict=%s"),
			*Result.Name,
			Result.BoatMassKg,
			Result.SimulatedLoadMassKg,
			Result.CharacterMovementMassKg,
			Result.SettledMeanZ,
			Result.DepthBelowEmptyMeanCm,
			Result.SettledTrendCmPerSecond,
			Result.SettledStdDevZ,
			Result.CharacterBasedOnBoatFrames,
			Result.bSinking ? TEXT("SINKING") : TEXT("FLOATING")));
	}
	const FCaseResult& CharacterResult = State->Cases[2].Result;
	Test->TestTrue(
		TEXT("real character established sustained floor contact on BP_Boat"),
		CharacterResult.CharacterBasedOnBoatFrames >= 60);

	Test->TestTrue(TEXT("write Saved/Profiling/BoatBuoyancy/latest_metrics.json"), WriteReport(State->Cases));
	State->Cases.Empty();
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FProphecyBoatBuoyancyMetricsTest,
	"Prophecy.Boat.BuoyancyMetrics",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyBoatBuoyancyMetricsTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyBoatBuoyancyAutomation;

	AddExpectedError(
		TEXT("Ensure condition failed: !FindPin(FFunctionEntryHelper::GetWorldContextPinName())"),
		EAutomationExpectedErrorFlags::Contains,
		1);
	UClass* BoatClass = StaticLoadClass(
		AActor::StaticClass(),
		nullptr,
		TEXT("/Game/_mygame/assets/boat/StaticMeshes/BP_Boat.BP_Boat_C"));
	UClass* CharacterClass = StaticLoadClass(
		AActor::StaticClass(),
		nullptr,
		TEXT("/Game/_mygame/SandboxCharacter_CMC.SandboxCharacter_CMC_C"));
	UStaticMesh* CubeMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (!TestNotNull(TEXT("BP_Boat class"), BoatClass)
		|| !TestNotNull(TEXT("SandboxCharacter_CMC class"), CharacterClass)
		|| !TestNotNull(TEXT("Engine cube mesh"), CubeMesh))
	{
		return false;
	}
	FlushAsyncLoading();
	FAssetCompilingManager::Get().FinishAllCompilation();
	TestTrue(TEXT("dump BP_Boat Event Graph"), DumpBoatEventGraph());

	TSharedPtr<FRunnerState> State = MakeShared<FRunnerState>();
	State->Cases.SetNum(3);
	if (!BuildCaseWorld(ELoadCase::Empty, BoatClass, CharacterClass, CubeMesh, State->Cases[0], *this)
		|| !BuildCaseWorld(ELoadCase::Cube90Kg, BoatClass, CharacterClass, CubeMesh, State->Cases[1], *this)
		|| !BuildCaseWorld(ELoadCase::Character, BoatClass, CharacterClass, CubeMesh, State->Cases[2], *this))
	{
		return false;
	}

	ADD_LATENT_AUTOMATION_COMMAND(FProphecyBoatPhysicsFramesCommand(State, this));
	ADD_LATENT_AUTOMATION_COMMAND(FProphecyBoatFinalizeMetricsCommand(State, this));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
