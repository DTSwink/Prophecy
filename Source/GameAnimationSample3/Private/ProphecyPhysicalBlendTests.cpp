#include "ProphecyPhysicalBlendSubsystem.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPhysicalBlendsTest,
	"Prophecy.Agent.PhysicalBlends.RuntimeAndBatch",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyPhysicalBlendsTest::RunTest(const FString& Parameters)
{
	const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
		.CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
		.CreateFXSystem(false).SetTransactional(false);
	auto* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
	if (!TestNotNull(TEXT("Fixture world"), World)) return false;
	if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT
	{
		World->DestroyWorld(false);
		if (GEngine) GEngine->DestroyWorldContext(World);
		World->MarkAsGarbage();
	};
	auto* Blends = World->GetSubsystem<UProphecyPhysicalBlendSubsystem>();
	auto* Asset = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (!TestNotNull(TEXT("Shared updater"), Blends) || !TestNotNull(TEXT("Actual PHAT fixture"), Asset)) return false;
	auto Spawn = [&]()
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		auto* Agent = World->SpawnActor<AProphecyAgent>(Params);
		Agent->bAutoEnsureStandaloneNNManager = false;
		Agent->GetAgentMesh()->SetSkeletalMeshAsset(Asset);
		return Agent;
	};
	auto* Agent = Spawn();
	auto ReadStrength = [&]() { FProphecyBodyMagnetizationSettings S; Agent->GetBodyMagnetizationSettings(TEXT("head"), S); return S; };
	auto ReadFeedback = [&]() { FProphecyPhysicalFeedbackToleranceSettings S; Agent->GetPhysicalFeedbackTolerance(TEXT("head"), S); return S; };
	// Test convenience: authored seconds expand to 60 explicit engine ticks.
	float FrameDelta=1.f/60.f;
	auto Step = [&](float NominalSeconds)
	{
		if (NominalSeconds<=0) { Blends->Advance(World,LEVELTICK_All,NominalSeconds);return; }
		for (int32 I=0;I<FMath::RoundToInt(NominalSeconds*60.f);++I)
			Blends->Advance(World,LEVELTICK_All,FrameDelta);
	};
	TestFalse(TEXT("Idle has no delegate"), Blends->TickHandle.IsValid());
	Agent->SetBodyMagnetization(TEXT("head"), true, 0, 0);
	Agent->BodyMagnetizationSettings[TEXT("head")].bCancelGravity = false;
	Agent->BodyMagnetizationSettings[TEXT("head")].bSimulateBody = false;
	TestTrue(TEXT("Start head release/recovery"), Agent->BlendBodyMagnetization(TEXT("head"), 1, 2, 1));
	TestTrue(TEXT("Start simultaneous feedback transition"), Agent->BlendPhysicalFeedbackTolerance(TEXT("head"), 4, 20, 1));
	TestEqual(TEXT("One registration for both channels"), Blends->ActiveAgents.Num(), 1);
	TestEqual(TEXT("Two active bone channels"), Blends->ActiveAgents[0].Blends.Num(), 2);
	for (int32 I=0;I<15;++I) FWorldDelegates::OnWorldPreActorTick.Broadcast(World, LEVELTICK_All, 1.f/30.f);
	TestEqual(TEXT("Smooth strength quarter point"), ReadStrength().LinearStrengthScale, 0.15625f);
	TestEqual(TEXT("Angular strength independently interpolated"), ReadStrength().AngularStrengthScale, 0.3125f);
	TestEqual(TEXT("Feedback reaches smooth quarter point"), ReadFeedback().AngularToleranceDegrees, 3.125f);
	TestFalse(TEXT("Gravity preserved"), ReadStrength().bCancelGravity);
	TestFalse(TEXT("Membership preserved"), ReadStrength().bSimulateBody);
	World->GetWorldSettings()->SetPauserPlayerState(World->SpawnActor<APlayerState>());
	Step(1);
	TestEqual(TEXT("Pause freezes active blends"), ReadStrength().LinearStrengthScale, 0.15625f);
	World->GetWorldSettings()->SetPauserPlayerState(nullptr);
	Step(0);
	Step(-1);
	TestEqual(TEXT("Nonpositive deltas do not advance"), ReadStrength().LinearStrengthScale, 0.15625f);
	Agent->CustomTimeDilation = 0.5f;
	FrameDelta=1.f/120.f;
	Step(0.25f);
	TestEqual(TEXT("30 ticks give midpoint regardless of FPS or dilation"), ReadStrength().LinearStrengthScale, 0.5f);
	Agent->CustomTimeDilation = 1;
	TestTrue(TEXT("Retrigger from current state"), Agent->BlendBodyMagnetization(TEXT("head"), 0, 0, 1));
	TestEqual(TEXT("Retrigger has no immediate jump"), ReadStrength().LinearStrengthScale, 0.5f);
	TestEqual(TEXT("Retrigger replaces rather than stacking"), Blends->ActiveAgents[0].Blends.Num(), 2);
	Step(0.5f);
	TestEqual(TEXT("Retrigger starts from halfway value"), ReadStrength().LinearStrengthScale, 0.25f);
	TestEqual(TEXT("Other channel finishes exactly"), ReadFeedback().AngularToleranceDegrees, 20.0f);
	Agent->SetBodyMagnetization(TEXT("head"), true, 0.7f, 0.8f);
	Step(2);
	TestEqual(TEXT("Immediate setter cancels blend"), ReadStrength().LinearStrengthScale, 0.7f);
	TestFalse(TEXT("Last completion/cancellation removes callback"), Blends->TickHandle.IsValid());
	TestTrue(TEXT("Zero duration immediate endpoint"), Agent->BlendBodyMagnetization(TEXT("head"), 1, 1, 0));
	TestEqual(TEXT("Immediate target exact"), ReadStrength().LinearStrengthScale, 1.0f);
	Agent->SetBodyMagnetization(TEXT("head"), false, 5, 5);
	Agent->BlendBodyMagnetization(TEXT("head"), 1, 1, 1);
	TestEqual(TEXT("Disabled starts from effective zero"), ReadStrength().LinearStrengthScale, 0.0f);
	TestTrue(TEXT("Blend explicitly enables per-body drive"), ReadStrength().bMagnetizationEnabled);
	Step(2);
	TestEqual(TEXT("Sufficient ticks reach exact endpoint"), ReadStrength().LinearStrengthScale, 1.0f);
	TestFalse(TEXT("Invalid body rejected"), Agent->BlendBodyMagnetization(TEXT("missing"), 1, 1, 1));
	TestFalse(TEXT("Lowerarm not a feedback channel"), Agent->BlendPhysicalFeedbackTolerance(TEXT("lowerarm_r"), 1, 1, 1));
	TestFalse(TEXT("NaN rejected"), Agent->BlendBodyMagnetization(TEXT("head"), std::numeric_limits<float>::quiet_NaN(), 1, 1));
	TestFalse(TEXT("Infinite duration rejected"), Agent->BlendBodyMagnetization(TEXT("head"), 1, 1, std::numeric_limits<float>::infinity()));
	TestEqual(TEXT("Invalid calls create no work"), Blends->ActiveAgents.Num(), 0);
	Agent->SetAllBodyMagnetization(true, 0, 0);
	Agent->SetAllPhysicalFeedbackTolerances(0, 0);
	TestTrue(TEXT("Arm body descendants selected"), Agent->BlendBodyMagnetizationBelow(TEXT("upperarm_r"), true, 1, 1, 1) >= 3);
	TestEqual(TEXT("Only controlled arm feedback bones selected"), Agent->BlendPhysicalFeedbackToleranceBelow(TEXT("upperarm_r"), true, 3, 5, 1), 2);
	Step(0.5f);
	FProphecyBodyMagnetizationSettings Body;
	Agent->GetBodyMagnetizationSettings(TEXT("lowerarm_r"), Body);
	TestEqual(TEXT("Body descendants include lowerarm"), Body.LinearStrengthScale, 0.5f);
	Agent->GetBodyMagnetizationSettings(TEXT("upperarm_l"), Body);
	TestEqual(TEXT("Opposite arm untouched"), Body.LinearStrengthScale, 0.0f);
	Agent->SetBodyMagnetizationBelow(TEXT("upperarm_r"), true, true, 0.3f, 0.3f);
	Agent->SetPhysicalFeedbackToleranceBelow(TEXT("upperarm_r"), true, 2, 4);
	TestFalse(TEXT("Below setters cancel selected transitions"), Blends->TickHandle.IsValid());
	Agent->BlendPhysicalFeedbackTolerance(TEXT("head"), 5, 5, 1);
	Step(0.25f);
	const float Held = ReadFeedback().LinearToleranceCm;
	Agent->CancelPhysicalFeedbackToleranceBlend();
	Step(1);
	TestEqual(TEXT("Explicit cancellation holds current feedback"), ReadFeedback().LinearToleranceCm, Held);
	Agent->BlendBodyMagnetization(TEXT("head"), 1, 1, 1);
	Agent->BlendPhysicalFeedbackTolerance(TEXT("head"), 5, 5, 1);
	Agent->SetAllBodyMagnetization(true, 0, 0);
	Agent->SetAllPhysicalFeedbackTolerances(0, 0);
	TestFalse(TEXT("All setters cancel both collections"), Blends->TickHandle.IsValid());

	// Shared updater throughput only: excludes physics/NN, actor ticks and request-time allocations.
	TArray<AProphecyAgent*> Crowd;
	for (int32 Index = 0; Index < 100; ++Index)
	{
		auto* Other = Spawn();
		Other->SetBodyMagnetization(TEXT("head"), true, 0, 0);
		Other->BlendBodyMagnetization(TEXT("head"), 1, 1, 100);
		Other->BlendPhysicalFeedbackTolerance(TEXT("head"), 3, 5, 100);
		Crowd.Add(Other);
	}
	TestEqual(TEXT("100 active agents share updater"), Blends->ActiveAgents.Num(), 100);
	Step(0.01f);
	const double Begin = FPlatformTime::Seconds();
	for (int32 Frame = 0; Frame < 600; ++Frame) Step(1.0f / 60.0f);
	AddInfo(FString::Printf(TEXT("100 agents / 200 active head channels: shared updater mean %.6f ms (no NN/physics)"),
		(FPlatformTime::Seconds() - Begin) * 1000.0 / 600.0));
	Crowd.Last()->Destroy();
	Step(0.01f);
	TestEqual(TEXT("Destroyed agent pruned safely"), Blends->ActiveAgents.Num(), 99);
	Step(200);
	TestTrue(TEXT("All transitions finish"), Blends->ActiveAgents.IsEmpty());
	TestFalse(TEXT("No delegate after batch completion"), Blends->TickHandle.IsValid());
	Agent->BlendBodyMagnetization(TEXT("head"), 1, 1, 1);
	Blends->OnWorldEndPlay(*World);
	TestTrue(TEXT("World end clears active transitions"), Blends->ActiveAgents.IsEmpty());
	TestFalse(TEXT("World end removes delegate"), Blends->TickHandle.IsValid());
	TestFalse(TEXT("No late work accepted during teardown"), Agent->BlendBodyMagnetization(TEXT("head"), 0, 0, 1));
	return true;
}
#endif
