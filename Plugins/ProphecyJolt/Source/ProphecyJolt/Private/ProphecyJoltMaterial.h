#pragma once

#include "CoreMinimal.h"
#include "Chaos/Defines.h"
#include "PhysicsSettingsEnums.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Body/Body.h>
#include <Jolt/Physics/Collision/Shape/CompoundShape.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::Material
{
// Welded colliders retain the source body's material. The record is stable and
// immutable throughout Update; it contains native data only, never a UObject.
struct alignas(16) FAttachedMaterialData
{
    const JPH::CompoundShape* Compound = nullptr;
    const JPH::Shape* CarrierRoot = nullptr;
    const JPH::Body* Source = nullptr;
    bool IsSource(const JPH::SubShapeID& ID) const
    {
        JPH::SubShapeID Rest;
        return Compound->GetCompoundUserData(Compound->GetSubShapeIndexFromID(ID,Rest))==1;
    }
};
constexpr uint64 AttachedMarker = uint64(1) << 63;
inline const FAttachedMaterialData* AttachedData(const JPH::Body& Body)
{
    const uint64 Data = Body.GetUserData();
    return (Data & AttachedMarker) ? reinterpret_cast<const FAttachedMaterialData*>(UPTRINT(Data & ~(AttachedMarker | uint64(15)))) : nullptr;
}
inline const JPH::Body& MaterialBody(const JPH::Body& Body, const JPH::SubShapeID& ID)
{
    if (const auto* Data = AttachedData(Body))
    {
        if (Data->IsSource(ID)) return *Data->Source;
    }
    return Body;
}
using FChaosMaterial = Chaos::FChaosPhysicsMaterial;
static_assert(uint8(FChaosMaterial::ECombineMode::Avg) == EFrictionCombineMode::Average
    && uint8(FChaosMaterial::ECombineMode::Min) == EFrictionCombineMode::Min
    && uint8(FChaosMaterial::ECombineMode::Multiply) == EFrictionCombineMode::Multiply
    && uint8(FChaosMaterial::ECombineMode::Max) == EFrictionCombineMode::Max);

inline bool ValidModes(uint8 Friction, uint8 Restitution)
{
    return Friction <= EFrictionCombineMode::Max && Restitution <= EFrictionCombineMode::Max;
}

// The adapter owns native BODY user data. Shape/triangle user data remains query provenance.
// Four inline bits, not a UObject pointer or registry index; immutable for the body's lifetime.
inline uint64 PackModes(uint8 Friction, uint8 Restitution)
{
    return uint64(Friction) | (uint64(Restitution) << 2);
}

inline float Combine(float A, float B, uint8 ModeA, uint8 ModeB)
{
    const auto Mode = FChaosMaterial::ChooseCombineMode(
        static_cast<FChaosMaterial::ECombineMode>(ModeA), static_cast<FChaosMaterial::ECombineMode>(ModeB));
    // Use UE's arithmetic and priority. Saturate only an otherwise unrepresentable native
    // coefficient (e.g. multiplication of two enormous but individually finite frictions).
    return static_cast<float>(FMath::Min(FChaosMaterial::CombineHelper(A, B, Mode), Chaos::FReal(MAX_flt)));
}

inline float CombineFriction(const JPH::Body& BodyA, const JPH::SubShapeID& IDA, const JPH::Body& BodyB, const JPH::SubShapeID& IDB)
{
    const auto& A=MaterialBody(BodyA,IDA); const auto& B=MaterialBody(BodyB,IDB);
    return Combine(A.GetFriction(), B.GetFriction(), uint8(A.GetUserData() & 3), uint8(B.GetUserData() & 3));
}

inline float CombineRestitution(const JPH::Body& BodyA, const JPH::SubShapeID& IDA, const JPH::Body& BodyB, const JPH::SubShapeID& IDB)
{
    const auto& A=MaterialBody(BodyA,IDA); const auto& B=MaterialBody(BodyB,IDB);
    return Combine(A.GetRestitution(), B.GetRestitution(), uint8((A.GetUserData() >> 2) & 3), uint8((B.GetUserData() >> 2) & 3));
}
}
