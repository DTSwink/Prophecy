#include "ProphecyJoltShapeAsset.h"

#include "Misc/SecureHash.h"
#include "ProphecyJoltConversions.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/StreamIn.h>
#include <Jolt/Core/StreamOut.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/PhysicsMaterialSimple.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::ShapeArchive
{
static_assert(JPH_VERSION_MAJOR == 5 && JPH_VERSION_MINOR == 6 && JPH_VERSION_PATCH == 0, "Review and recook the fixture when changing Jolt.");
constexpr int32 CurrentSchema = 1;
constexpr int32 MaxFixtureBytes = 64 * 1024;
constexpr TCHAR SourceRevision[] = TEXT("e77f175595e64cb44218cc9d9d56fc365ad0e36a");
constexpr TCHAR FixtureSource[] = TEXT("ProphecyJolt/CompoundFixture/v1;cm;identity-basis;density=1000kg/m3;convex-radius=0;child=1001,material=Fixture.Left,center=(-100,0,0),half=(25,50,25),quat=(0,0,0,1);child=1002,material=Fixture.Right,center=(100,0,50),half=(50,25,25),yaw=90deg");
const FVector FixtureCOM(0.0, 0.0, 25.0);
const FVector FixtureMin(-125.0, -50.0, -25.0);
const FVector FixtureMax(125.0, 50.0, 75.0);

bool Fail(FString& OutError, const FString& Message)
{
	OutError = Message;
	return false;
}

FString HashBytes(const TArray<uint8>& Bytes)
{
	return FSHA1::HashBuffer(Bytes.GetData(), static_cast<uint64>(Bytes.Num())).ToString();
}

FString HashSource(const FString& Source)
{
	const FTCHARToUTF8 Utf8(*Source);
	return FSHA1::HashBuffer(Utf8.Get(), static_cast<uint64>(Utf8.Length())).ToString();
}

JPH::Vec3 LocalMeters(const FVector& Centimeters)
{
	return static_cast<JPH::Vec3>(Conversions::ToJoltPosition(Centimeters));
}

FVector LocalCentimeters(JPH::Vec3Arg Meters)
{
	return Conversions::FromJoltPosition(JPH::RVec3(Meters));
}

TArray<FProphecyJoltShapeChild> FixtureChildren()
{
	TArray<FProphecyJoltShapeChild> Result;
	FProphecyJoltShapeChild& Left = Result.AddDefaulted_GetRef();
	Left.ChildId = 1001;
	Left.MaterialId = TEXT("Fixture.Left");
	Left.LocalPositionCm = FVector(-100.0, 0.0, 0.0);
	Left.BoxHalfExtentCm = FVector(25.0, 50.0, 25.0);
	FProphecyJoltShapeChild& Right = Result.AddDefaulted_GetRef();
	Right.ChildId = 1002;
	Right.MaterialId = TEXT("Fixture.Right");
	Right.LocalPositionCm = FVector(100.0, 0.0, 50.0);
	Right.LocalRotation = FRotator(0.0, 90.0, 0.0).Quaternion();
	Right.BoxHalfExtentCm = FVector(50.0, 25.0, 25.0);
	return Result;
}

bool RuntimeReady(FString& OutError)
{
#if !PLATFORM_WINDOWS || !PLATFORM_64BITS || !PLATFORM_CPU_X86_FAMILY || !PLATFORM_LITTLE_ENDIAN
	return Fail(OutError, TEXT("This shape fixture archive supports Win64 little-endian only; recook for the target platform."));
#else
	if (!JPH::VerifyJoltVersionID() || JPH::Factory::sInstance == nullptr)
	{
		return Fail(OutError, TEXT("Jolt runtime/ABI initialization is missing or incompatible."));
	}
	if (JPH::Factory::sInstance->Find("PhysicsMaterialSimple") == nullptr)
	{
		return Fail(OutError, TEXT("Jolt material types are not registered by the runtime module."));
	}
	return true;
#endif
}

class FShapeMemoryReader final : public JPH::StreamIn
{
public:
	explicit FShapeMemoryReader(const TArray<uint8>& InBytes) : Bytes(InBytes) {}

	virtual void ReadBytes(void* OutData, size_t Count) override
	{
		if (bFailed || Count > static_cast<size_t>(Bytes.Num() - Offset))
		{
			bFailed = true;
			bEOF = true;
			FMemory::Memzero(OutData, Count);
			return;
		}
		if (Count > 0)
		{
			FMemory::Memcpy(OutData, Bytes.GetData() + Offset, Count);
			Offset += static_cast<int32>(Count);
		}
	}

	virtual bool IsEOF() const override { return bEOF; }
	virtual bool IsFailed() const override { return bFailed; }
	int32 GetOffset() const { return Offset; }

private:
	const TArray<uint8>& Bytes;
	int32 Offset = 0;
	bool bFailed = false;
	bool bEOF = false;
};

#if WITH_EDITOR
class FShapeMemoryWriter final : public JPH::StreamOut
{
public:
	virtual void WriteBytes(const void* Data, size_t Count) override
	{
		if (bFailed || Count > static_cast<size_t>(MaxFixtureBytes - Bytes.Num()))
		{
			bFailed = true;
			return;
		}
		if (Count > 0)
		{
			Bytes.Append(static_cast<const uint8*>(Data), static_cast<int32>(Count));
		}
	}

	virtual bool IsFailed() const override { return bFailed; }
	TArray<uint8> Bytes;

private:
	bool bFailed = false;
};
#endif
}

#if WITH_EDITOR
bool UProphecyJoltShapeAsset::BuildCompoundFixture(FString& OutError)
{
	using namespace ProphecyJolt::ShapeArchive;
	OutError.Reset();
	if (!RuntimeReady(OutError))
	{
		return false;
	}
	TArray<FProphecyJoltShapeChild> NewChildren = FixtureChildren();
	JPH::StaticCompoundShapeSettings Settings;
	for (const FProphecyJoltShapeChild& Child : NewChildren)
	{
		const FTCHARToUTF8 MaterialName(*Child.MaterialId);
		const JPH::RefConst<JPH::PhysicsMaterial> Material = new JPH::PhysicsMaterialSimple(
			JPH::string_view(MaterialName.Get(), MaterialName.Length()), Child.ChildId == 1001 ? JPH::Color::sRed : JPH::Color::sBlue);
		JPH::BoxShapeSettings BoxSettings(LocalMeters(Child.BoxHalfExtentCm), 0.0f, Material);
		BoxSettings.mDensity = 1000.0f;
		BoxSettings.mUserData = Child.ChildId;
		const JPH::Shape::ShapeResult BoxResult = BoxSettings.Create();
		if (BoxResult.HasError())
		{
			return Fail(OutError, FString::Printf(TEXT("Fixture child creation failed: %s"), UTF8_TO_TCHAR(BoxResult.GetError().c_str())));
		}
		Settings.AddShape(LocalMeters(Child.LocalPositionCm), ProphecyJolt::Conversions::ToJoltRotation(Child.LocalRotation), BoxResult.Get(), Child.ChildId);
	}
	const JPH::Shape::ShapeResult Result = Settings.Create();
	if (Result.HasError())
	{
		return Fail(OutError, FString::Printf(TEXT("Fixture compound creation failed: %s"), UTF8_TO_TCHAR(Result.GetError().c_str())));
	}
	const JPH::RefConst<JPH::Shape> Shape = Result.Get();
	if (Shape->GetSubType() != JPH::EShapeSubType::StaticCompound)
	{
		return Fail(OutError, TEXT("Fixture did not create a two-child static compound."));
	}
	const JPH::StaticCompoundShape& Compound = static_cast<const JPH::StaticCompoundShape&>(*Shape);
	for (JPH::uint Index = 0; Index < Compound.GetNumSubShapes(); ++Index)
	{
		const uint32 Id = Compound.GetCompoundUserData(Index);
		FProphecyJoltShapeChild* Child = NewChildren.FindByPredicate([Id](const FProphecyJoltShapeChild& Item) { return Item.ChildId == Id; });
		if (Child == nullptr)
		{
			return Fail(OutError, TEXT("Fixture child identity was lost during compound construction."));
		}
		Child->ArchiveSubShapeId = Compound.GetSubShapeIDFromIndex(static_cast<int>(Index), JPH::SubShapeIDCreator()).GetID().GetValue();
	}
	FShapeMemoryWriter Writer;
	JPH::Shape::ShapeToIDMap ShapeIds;
	JPH::Shape::MaterialToIDMap MaterialIds;
	Shape->SaveWithChildren(Writer, ShapeIds, MaterialIds);
	if (Writer.IsFailed() || Writer.Bytes.IsEmpty() || ShapeIds.size() != 3 || MaterialIds.size() != 2)
	{
		return Fail(OutError, TEXT("Complete fixture archive must contain a compound, two children and two materials within its size limit."));
	}

	SchemaVersion = CurrentSchema;
	JoltSourceRevision = SourceRevision;
	ArchivePlatform = TEXT("Win64");
	WorldPositionBits = 64;
	ByteOrder = TEXT("LittleEndian");
	SourceDescriptor = FixtureSource;
	SourceSha1 = HashSource(SourceDescriptor);
	ArchiveBytes = MoveTemp(Writer.Bytes);
	ArchiveByteCount = ArchiveBytes.Num();
	ArchiveSha1 = HashBytes(ArchiveBytes);
	Children = MoveTemp(NewChildren);
	ExpectedCenterOfMassCm = FixtureCOM;
	ExpectedBoundsMinCm = FixtureMin;
	ExpectedBoundsMaxCm = FixtureMax;
	return ValidateCompoundFixture(OutError);
}
#endif

bool UProphecyJoltShapeAsset::ValidateCompoundFixture(FString& OutError) const
{
	using namespace ProphecyJolt::ShapeArchive;
	OutError.Reset();
	if (SchemaVersion != CurrentSchema)
	{
		return Fail(OutError, TEXT("Shape archive schema mismatch; regenerate the fixture."));
	}
	if (JoltSourceRevision != SourceRevision || ArchivePlatform != TEXT("Win64") || WorldPositionBits != 64 || ByteOrder != TEXT("LittleEndian"))
	{
		return Fail(OutError, TEXT("Shape archive source/platform/precision mismatch; recook for this runtime."));
	}
	// Diagnostic assertion/profiling bits deliberately are not archive identity.
	if (SourceDescriptor != FixtureSource || SourceSha1 != HashSource(SourceDescriptor))
	{
		return Fail(OutError, TEXT("Shape archive source provenance mismatch."));
	}
	if (ArchiveByteCount <= 0 || ArchiveByteCount > MaxFixtureBytes || ArchiveByteCount != ArchiveBytes.Num())
	{
		return Fail(OutError, TEXT("Shape archive length mismatch or fixture size limit exceeded."));
	}
	if (ArchiveSha1 != HashBytes(ArchiveBytes))
	{
		return Fail(OutError, TEXT("Shape archive hash mismatch; regenerate the damaged data."));
	}
	const TArray<FProphecyJoltShapeChild> ExpectedChildren = FixtureChildren();
	if (Children.Num() != 2 || !ExpectedCenterOfMassCm.Equals(FixtureCOM, 1.0e-6)
		|| !ExpectedBoundsMinCm.Equals(FixtureMin, 1.0e-6) || !ExpectedBoundsMaxCm.Equals(FixtureMax, 1.0e-6))
	{
		return Fail(OutError, TEXT("Shape archive fixture metadata mismatch."));
	}
	for (int32 Index = 0; Index < Children.Num(); ++Index)
	{
		const FProphecyJoltShapeChild& Child = Children[Index];
		const FProphecyJoltShapeChild& Expected = ExpectedChildren[Index];
		if (Child.ChildId != Expected.ChildId || Child.MaterialId != Expected.MaterialId
			|| !Child.LocalPositionCm.Equals(Expected.LocalPositionCm, 1.0e-6)
			|| !Child.LocalRotation.Equals(Expected.LocalRotation, 1.0e-6)
			|| !Child.BoxHalfExtentCm.Equals(Expected.BoxHalfExtentCm, 1.0e-6))
		{
			return Fail(OutError, TEXT("Shape archive child/material provenance mismatch."));
		}
	}
	if (!RuntimeReady(OutError))
	{
		return false;
	}
	FShapeMemoryReader Reader(ArchiveBytes);
	JPH::Shape::IDToShapeMap ShapeIds;
	JPH::Shape::IDToMaterialMap MaterialIds;
	const JPH::Shape::ShapeResult Result = JPH::Shape::sRestoreWithChildren(Reader, ShapeIds, MaterialIds);
	if (Result.HasError())
	{
		return Fail(OutError, FString::Printf(TEXT("Shape archive restore failed: %s"), UTF8_TO_TCHAR(Result.GetError().c_str())));
	}
	if (Reader.IsFailed() || Reader.GetOffset() != ArchiveByteCount || !Result.IsValid() || Result.Get() == nullptr)
	{
		return Fail(OutError, TEXT("Shape archive stream is incomplete, contains trailing bytes or has no root shape."));
	}
	const JPH::RefConst<JPH::Shape> Shape = Result.Get();
	if (ShapeIds.size() != 3 || MaterialIds.size() != 2 || Shape->GetSubType() != JPH::EShapeSubType::StaticCompound)
	{
		return Fail(OutError, TEXT("Shape archive did not restore the complete compound/children/material graph."));
	}
	const JPH::StaticCompoundShape& Compound = static_cast<const JPH::StaticCompoundShape&>(*Shape);
	const JPH::Vec3 CenterOfMass = Shape->GetCenterOfMass();
	const JPH::AABox Bounds = Shape->GetLocalBounds();
	if (Compound.GetNumSubShapes() != 2 || !LocalCentimeters(CenterOfMass).Equals(ExpectedCenterOfMassCm, 0.001)
		|| !LocalCentimeters(Bounds.mMin + CenterOfMass).Equals(ExpectedBoundsMinCm, 0.001)
		|| !LocalCentimeters(Bounds.mMax + CenterOfMass).Equals(ExpectedBoundsMaxCm, 0.001))
	{
		return Fail(OutError, TEXT("Restored shape bounds or center of mass differ from the analytic fixture."));
	}
	for (const FProphecyJoltShapeChild& Child : Children)
	{
		// Shape queries use the compound COM frame, not the authored origin.
		const FVector StartCm(Child.LocalPositionCm.X, Child.LocalPositionCm.Y, 200.0);
		const JPH::RayCast Ray(LocalMeters(StartCm) - CenterOfMass, LocalMeters(FVector(0.0, 0.0, -300.0)));
		JPH::RayCastResult Hit;
		if (!Shape->CastRay(Ray, JPH::SubShapeIDCreator(), Hit))
		{
			return Fail(OutError, TEXT("Restored fixture ray missed a child."));
		}
		JPH::SubShapeID Remainder;
		const JPH::uint Index = Compound.GetSubShapeIndexFromID(Hit.mSubShapeID2, Remainder);
		const JPH::CompoundShape::SubShape& SubShape = Compound.GetSubShape(Index);
		const JPH::PhysicsMaterial* Material = Shape->GetMaterial(Hit.mSubShapeID2);
		const FVector ExpectedHitCm(Child.LocalPositionCm.X, Child.LocalPositionCm.Y, Child.LocalPositionCm.Z + Child.BoxHalfExtentCm.Z);
		if (Compound.GetCompoundUserData(Index) != Child.ChildId || Shape->GetSubShapeUserData(Hit.mSubShapeID2) != Child.ChildId
			|| Hit.mSubShapeID2.GetValue() != Child.ArchiveSubShapeId || Material == nullptr
			|| FString(UTF8_TO_TCHAR(Material->GetDebugName())) != Child.MaterialId
			|| SubShape.mShape->GetSubType() != JPH::EShapeSubType::Box
			|| !LocalCentimeters(SubShape.GetPositionCOM() + CenterOfMass).Equals(Child.LocalPositionCm, 0.001)
			|| !ProphecyJolt::Conversions::FromJoltRotation(SubShape.GetRotation()).Equals(Child.LocalRotation, 1.0e-5)
			|| !LocalCentimeters(static_cast<const JPH::BoxShape&>(*SubShape.mShape).GetHalfExtent()).Equals(Child.BoxHalfExtentCm, 0.001)
			|| !LocalCentimeters(Ray.GetPointOnRay(Hit.mFraction) + CenterOfMass).Equals(ExpectedHitCm, 0.001))
		{
			return Fail(OutError, TEXT("Restored child transform, material identity, subshape identity or ray surface mismatch."));
		}
	}
	return true;
}
