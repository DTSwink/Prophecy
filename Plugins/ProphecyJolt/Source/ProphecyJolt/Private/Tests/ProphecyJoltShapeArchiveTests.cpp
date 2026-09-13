#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "Misc/AutomationTest.h"
#include "Misc/SecureHash.h"
#include "ProphecyJoltShapeAsset.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltShapeArchiveRoundTripTest, "Prophecy.Jolt.ShapeArchive.CompoundRoundTrip", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltShapeArchiveRoundTripTest::RunTest(const FString& Parameters)
{
	UProphecyJoltShapeAsset* Asset = NewObject<UProphecyJoltShapeAsset>();
	FString Error;
	if (!TestTrue(TEXT("Build complete compound archive in memory"), Asset->BuildCompoundFixture(Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Two explicit child identities"), Asset->Children.Num(), 2);
	TestTrue(TEXT("Archive contains bytes"), Asset->ArchiveByteCount > 0);
	TestEqual(TEXT("Archive length metadata"), Asset->ArchiveBytes.Num(), Asset->ArchiveByteCount);
	TestTrue(TEXT("Distinct materials retained"), Asset->Children[0].MaterialId != Asset->Children[1].MaterialId);
	TestTrue(TEXT("Distinct archive subshape IDs retained"), Asset->Children[0].ArchiveSubShapeId != Asset->Children[1].ArchiveSubShapeId);
	TestNearlyEqual(TEXT("Analytic compound COM includes child offset"), Asset->ExpectedCenterOfMassCm, FVector(0.0, 0.0, 25.0));
	UProphecyJoltShapeAsset* Copy = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	if (!TestTrue(TEXT("Copied archive restores children/materials and passes runtime queries"), Copy->ValidateCompoundFixture(Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Copy preserves complete archive hash"), Copy->ArchiveSha1, Asset->ArchiveSha1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltShapeArchiveRejectionTest, "Prophecy.Jolt.ShapeArchive.RejectInvalidData", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltShapeArchiveRejectionTest::RunTest(const FString& Parameters)
{
	UProphecyJoltShapeAsset* Asset = NewObject<UProphecyJoltShapeAsset>();
	FString Error;
	if (!TestTrue(TEXT("Build source archive"), Asset->BuildCompoundFixture(Error)))
	{
		AddError(Error);
		return false;
	}
	UProphecyJoltShapeAsset* Corrupt = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	Corrupt->ArchiveBytes[Corrupt->ArchiveBytes.Num() / 2] ^= 0x80;
	TestFalse(TEXT("Corrupt payload rejected before restore"), Corrupt->ValidateCompoundFixture(Error));
	TestTrue(TEXT("Corruption explains hash mismatch"), Error.Contains(TEXT("hash mismatch")));
	UProphecyJoltShapeAsset* Truncated = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	Truncated->ArchiveBytes.SetNum(Truncated->ArchiveBytes.Num() - 1);
	TestFalse(TEXT("Truncated payload rejected"), Truncated->ValidateCompoundFixture(Error));
	TestTrue(TEXT("Truncation explains length mismatch"), Error.Contains(TEXT("length mismatch")));
	UProphecyJoltShapeAsset* Schema = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	++Schema->SchemaVersion;
	TestFalse(TEXT("Different schema rejected"), Schema->ValidateCompoundFixture(Error));
	TestTrue(TEXT("Schema rejection explains regeneration"), Error.Contains(TEXT("schema mismatch")));
	UProphecyJoltShapeAsset* Precision = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	Precision->WorldPositionBits = 32;
	TestFalse(TEXT("Different precision rejected"), Precision->ValidateCompoundFixture(Error));
	UProphecyJoltShapeAsset* Material = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	Material->Children[0].MaterialId = TEXT("WrongMaterial");
	TestFalse(TEXT("Different material provenance rejected"), Material->ValidateCompoundFixture(Error));
	UProphecyJoltShapeAsset* Trailing = DuplicateObject<UProphecyJoltShapeAsset>(Asset, GetTransientPackage());
	Trailing->ArchiveBytes.Add(0);
	Trailing->ArchiveByteCount = Trailing->ArchiveBytes.Num();
	Trailing->ArchiveSha1 = FSHA1::HashBuffer(Trailing->ArchiveBytes.GetData(), static_cast<uint64>(Trailing->ArchiveBytes.Num())).ToString();
	TestFalse(TEXT("Even hash-consistent trailing bytes are rejected"), Trailing->ValidateCompoundFixture(Error));
	TestTrue(TEXT("Trailing stream data diagnosed"), Error.Contains(TEXT("trailing bytes")));
	TestTrue(TEXT("Original archive remains valid after rejection cases"), Asset->ValidateCompoundFixture(Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
