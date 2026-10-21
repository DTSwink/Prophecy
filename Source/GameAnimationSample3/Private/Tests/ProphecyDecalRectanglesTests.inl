#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Materials/Material.h"
#include "Components/BoxComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDecalRectanglesTest, "Prophecy.Blood.RectangleIntegration",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyDecalRectanglesTest::RunTest(const FString&)
{
	const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
		.CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
		.CreateFXSystem(false).SetTransactional(false);
	UWorld* W = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
	if (!TestNotNull(TEXT("test world"), W)) return false;
	if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
	AActor* A = W->SpawnActor<AActor>();
	auto* C = NewObject<UProphecyFoliageDecalGridComponent>(A);
	A->AddInstanceComponent(C); C->RegisterComponent();
	C->DecalMaterial = UMaterial::GetDefaultMaterial(MD_DeferredDecal);
	C->CellSizeCm = 10; C->DecalPadding = 1; C->MergeBudgetMs = 100;
	C->bAutoProcessMerges = false;
	auto Drain = [&]()
	{
		for (int32 I = 0; I < 256 && C->PendingMergeCount; ++I) C->ProcessPendingMerges();
		return TestEqual(TEXT("queue drained"), C->PendingMergeCount, 0);
	};
	auto Add = [&](int32 X, int32 Y, float Z = 0.f)
	{
		return C->AddFloorStainToGrid(FVector((X + .5) * 10, (Y + .5) * 10, Z), FVector::UpVector, 0);
	};
	// The previously stranded long edge must become one actual non-square projector.
	for (int32 X = 0; X < 16; ++X) for (int32 Y = 0; Y < 2; ++Y) Add(X, Y);
	Drain();
	TestEqual(TEXT("strip is one rectangle"), C->ActiveDecalCount, 1);
	auto Decals = C->GetActiveFoliageGridDecals();
	if (Decals.Num() == 1)
	{
		TestTrue(TEXT("half extents 80 by 10"), Decals[0]->DecalSize.Equals(FVector(60, 10, 80)));
		TestTrue(TEXT("projector intersects plane"), Decals[0]->GetComponentLocation().Z - Decals[0]->DecalSize.X < 0);
		UDecalComponent* Original = Decals[0];
		TestEqual(TEXT("repeated hit does no work"), Add(0, 0), 0);
		TestEqual(TEXT("repeat stays idle"), C->PendingMergeCount, 0);
		Add(16, 0); Add(16, 1); Drain();
		TestTrue(TEXT("growing rectangle reuses component"), C->GetActiveFoliageGridDecals()[0] == Original);
	}
	C->ClearFoliageDecalGrid();
	// UE DeferredDecal.usf fades at the projection-volume edges. Merely
	// intersecting the floor is insufficient: the receiver must be fully opaque.
	for (float Offset : {0.f, 2.f, 120.f})
	{
		C->ProjectionSurfaceOffsetCm = Offset;
		Add(0, 0); Drain();
		auto Visible = C->GetActiveFoliageGridDecals();
		if (TestEqual(TEXT("fade fixture has one decal"), Visible.Num(), 1))
		{
			const float NormalizedDepth = FMath::Abs(Visible[0]->GetComponentLocation().Z) / Visible[0]->DecalSize.X;
			const float Fade = FMath::Clamp(4.f - 4.f * NormalizedDepth, 0.f, 1.f);
			TestEqual(TEXT("receiver remains in full-opacity depth range"), Fade, 1.f);
		}
		C->ClearFoliageDecalGrid();
	}
	C->ProjectionSurfaceOffsetCm = 2.f;
	// Compare actual projected rectangles against every occupied base cell, including a hole.
	TSet<FIntPoint> Expected;
	for (int32 Y = 0; Y < 16; ++Y) for (int32 X = 0; X < 16; ++X)
		if (!(X >= 5 && X < 11 && Y >= 5 && Y < 11)) { Add(X, Y); Expected.Add({X, Y}); }
	Drain();
	TestEqual(TEXT("ring uses four rectangles"), C->ActiveDecalCount, 4);
	TSet<FIntPoint> Seen;
	for (UDecalComponent* D : C->GetActiveFoliageGridDecals())
	{
		const FVector P = D->GetComponentLocation();
		const int32 X0 = FMath::RoundToInt((P.X - D->DecalSize.Z) / 10);
		const int32 Y0 = FMath::RoundToInt((P.Y - D->DecalSize.Y) / 10);
		const int32 Width = FMath::RoundToInt(D->DecalSize.Z * 2 / 10);
		const int32 Height = FMath::RoundToInt(D->DecalSize.Y * 2 / 10);
		for (int32 Y = Y0; Y < Y0 + Height; ++Y) for (int32 X = X0; X < X0 + Width; ++X)
		{
			TestFalse(TEXT("no overlap"), Seen.Contains({X, Y}));
			TestTrue(TEXT("no empty cell covered"), Expected.Contains({X, Y}));
			Seen.Add({X, Y});
		}
	}
	TestEqual(TEXT("all occupied cells projected"), Seen.Num(), Expected.Num());
	C->ClearFoliageDecalGrid();
	Add(-2, -1); Add(-1, -1); Drain();
	TestEqual(TEXT("negative cells merge"), C->ActiveDecalCount, 1);
	Add(-2, -1, 100); Add(-1, -1, 100); Drain();
	TestEqual(TEXT("different heights remain separate"), C->ActiveDecalCount, 2);
	C->ClearFoliageDecalGrid();
	auto* ReceiverA = NewObject<UBoxComponent>(A);
	auto* ReceiverB = NewObject<UBoxComponent>(A);
	for (auto* Receiver : {ReceiverA, ReceiverB})
	{
		FHitResult Hit;
		Hit.bBlockingHit = true; Hit.Component = Receiver;
		Hit.ImpactPoint = FVector(5, 5, 0); Hit.ImpactNormal = FVector::UpVector;
		TestEqual(TEXT("separate receiver accepted"), C->AddFloorHitToGrid(Hit, 0), 1);
	}
	Drain(); TestEqual(TEXT("receiver identity preserved"), C->ActiveDecalCount, 2);
	C->ClearFoliageDecalGrid();
	const FVector SlopeNormal = FVector(-.2, 0, 1).GetSafeNormal();
	const FVector SlopeU = (FVector::ForwardVector - SlopeNormal * SlopeNormal.X).GetSafeNormal();
	const FVector SlopeV = FVector::CrossProduct(SlopeNormal, SlopeU);
	for (int32 X = 0; X < 8; ++X)
		C->AddFloorStainToGrid(SlopeU * ((X + .5) * 10) + SlopeV * 5, SlopeNormal, 0);
	Drain(); TestEqual(TEXT("sloped strip merges"), C->ActiveDecalCount, 1);
	if (C->ActiveDecalCount)
		TestTrue(TEXT("sloped projection follows receiver"), (-C->GetActiveFoliageGridDecals()[0]->GetForwardVector()).Equals(SlopeNormal, .0001));
	C->ClearFoliageDecalGrid();
	C->MaxActiveDecals = 1;
	Add(0, 0); Drain();
	Add(2, 0); C->ProcessPendingMerges();
	TestEqual(TEXT("capacity keeps old footprint"), C->ActiveDecalCount, 1);
	TestEqual(TEXT("capacity retains pending occupancy"), C->PendingMergeCount, 1);
	C->MaxActiveDecals = 4; Drain();
	TestEqual(TEXT("capacity increase recovers"), C->ActiveDecalCount, 2);
	C->ClearFoliageDecalGrid(); C->MaxActiveDecals = 4096;
	for (int32 Y = 0; Y < 32; ++Y) for (int32 X = 0; X < 32; ++X) if ((X + Y) % 2 == 0) Add(X, Y);
	C->ProcessPendingMerges();
	TestTrue(TEXT("cold allocation capped at sixteen"), A->GetInstanceComponents().Num() <= 17);
	TestEqual(TEXT("partial preparation invisible"), C->ActiveDecalCount, 0);
	Drain(); TestEqual(TEXT("checkerboard completed"), C->ActiveDecalCount, 512);
	C->ClearFoliageDecalGrid();
	TestEqual(TEXT("components cleaned"), A->GetInstanceComponents().Num(), 1);
	C->SetMergeProcessingEnabled(true); Add(0, 0); Drain();
	// The component has no tick and no recurring timer once the queue is empty.
	TestFalse(TEXT("no component tick"), C->PrimaryComponentTick.bCanEverTick);
	TestTrue(TEXT("automatic mode retained when idle"), C->IsMergeProcessingEnabled());
	C->ClearFoliageDecalGrid();
	W->DestroyWorld(false);
	if (GEngine) GEngine->DestroyWorldContext(W);
	W->MarkAsGarbage();
	return true;
}
#endif
