#include "ProphecyGameModuleSimd.h"

#include "Dom/JsonObject.h"
#include "HAL/PlatformMisc.h"
#include "Math/Matrix.h"
#include "Math/Transform.h"
#include "Math/VectorRegister.h"

#ifndef PROPHECY_GAME_SIMD_PROFILE
#define PROPHECY_GAME_SIMD_PROFILE 0
#endif

static_assert(sizeof(FVector) == 24 && alignof(FVector) == 8, "Audited UE 5.7 FVector storage changed.");
static_assert(sizeof(FQuat) == 32 && alignof(FQuat) == 16, "Audited UE 5.7 FQuat storage changed.");
static_assert(sizeof(FTransform) == 96 && alignof(FTransform) == 16, "Audited UE 5.7 FTransform storage changed.");
static_assert(sizeof(FMatrix) == 128 && alignof(FMatrix) == 16, "Audited UE 5.7 FMatrix storage changed.");

#if PROPHECY_GAME_SIMD_PROFILE == 2
#if !defined(__AVX2__) || !PLATFORM_ALWAYS_HAS_AVX || !PLATFORM_ALWAYS_HAS_AVX_2 || !UE_PLATFORM_MATH_USE_AVX
#error AVX2_PRIVATE requires matching compiler, Unreal platform and math definitions.
#endif
#elif PROPHECY_GAME_SIMD_PROFILE == 1
#if defined(__AVX__) || defined(__AVX2__) || PLATFORM_ALWAYS_HAS_AVX || PLATFORM_ALWAYS_HAS_AVX_2 || UE_PLATFORM_MATH_USE_AVX
#error SSE2_PRIVATE must not inherit an AVX compiler/platform/PCH environment.
#endif
#elif PROPHECY_GAME_SIMD_PROFILE != 0
#error Unknown game-module SIMD diagnostic profile.
#endif

namespace ProphecyGameModuleSimd
{
namespace
{
constexpr const TCHAR* ExpectedVariable = TEXT("PROPHECY_GAME_DIAGNOSTIC_EXPECTED_PROFILE");
constexpr const TCHAR* PreflightVariable = TEXT("PROPHECY_GAME_DIAGNOSTIC_PREFLIGHT");

const TCHAR* ProfileName()
{
#if PROPHECY_GAME_SIMD_PROFILE == 2
    return TEXT("AVX2_PRIVATE");
#elif PROPHECY_GAME_SIMD_PROFILE == 1
    return TEXT("SSE2_PRIVATE");
#else
    return TEXT("DEFAULT");
#endif
}

template <typename T>
TSharedPtr<FJsonObject> Layout()
{
    auto Value = MakeShared<FJsonObject>();
    Value->SetNumberField(TEXT("size_bytes"), sizeof(T));
    Value->SetNumberField(TEXT("alignment_bytes"), alignof(T));
    return Value;
}
}

bool ValidateRequestedProfile(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread())
    { OutError = TEXT("Game-module profile validation requires the game thread."); return false; }
    const FString Expected = FPlatformMisc::GetEnvironmentVariable(ExpectedVariable);
    const FString Preflight = FPlatformMisc::GetEnvironmentVariable(PreflightVariable);
    if (Expected.IsEmpty())
    {
#if PROPHECY_GAME_SIMD_PROFILE != 0
        OutError = TEXT("An explicit game-module ISA benchmark requires the guarded game-specific launcher and expected-profile provenance.");
        return false;
#else
        return true;
#endif
    }
    if (Expected != ProfileName() || Preflight.IsEmpty())
    {
        OutError = FString::Printf(TEXT("Game-module ISA mismatch or missing launch provenance: expected=%s, loaded=%s, preflight=%s."),
            *Expected, ProfileName(), *Preflight);
        return false;
    }
    return true;
}

TSharedPtr<FJsonObject> Report()
{
    auto Value = MakeShared<FJsonObject>();
    Value->SetNumberField(TEXT("schema"), 1);
    Value->SetStringField(TEXT("profile"), ProfileName());
    Value->SetNumberField(TEXT("profile_id"), PROPHECY_GAME_SIMD_PROFILE);
    Value->SetBoolField(TEXT("private_pch_requested"), PROPHECY_GAME_SIMD_PROFILE != 0);
    Value->SetStringField(TEXT("expected_profile"), FPlatformMisc::GetEnvironmentVariable(ExpectedVariable));
    Value->SetStringField(TEXT("preflight_sidecar"), FPlatformMisc::GetEnvironmentVariable(PreflightVariable));
#if defined(__AVX2__)
    Value->SetBoolField(TEXT("compiler_avx2"), true);
#else
    Value->SetBoolField(TEXT("compiler_avx2"), false);
#endif
    Value->SetBoolField(TEXT("platform_always_has_avx"), PLATFORM_ALWAYS_HAS_AVX != 0);
    Value->SetBoolField(TEXT("platform_always_has_avx2"), PLATFORM_ALWAYS_HAS_AVX_2 != 0);
#if UE_PLATFORM_MATH_USE_AVX
    Value->SetBoolField(TEXT("ue_math_uses_avx"), true);
#else
    Value->SetBoolField(TEXT("ue_math_uses_avx"), false);
#endif
#if UE_PLATFORM_MATH_USE_FMA3
    Value->SetBoolField(TEXT("ue_math_uses_fma3_intrinsics"), true);
#else
    Value->SetBoolField(TEXT("ue_math_uses_fma3_intrinsics"), false);
#endif
#if defined(_MSC_VER)
    Value->SetNumberField(TEXT("compiler_msc_ver"), _MSC_VER);
    Value->SetNumberField(TEXT("compiler_msc_full_ver"), _MSC_FULL_VER);
#endif
    Value->SetBoolField(TEXT("editor_build"), WITH_EDITOR != 0);
    Value->SetBoolField(TEXT("shipping_build"), UE_BUILD_SHIPPING != 0);
    Value->SetStringField(TEXT("fp_setting"), TEXT("Unchanged module default; inspect response files. Existing MSVC baseline uses /fp:fast. No new FP relaxation or no-FMA guarantee."));
    auto Layouts = MakeShared<FJsonObject>();
    Layouts->SetObjectField(TEXT("FVector"), Layout<FVector>());
    Layouts->SetObjectField(TEXT("FQuat"), Layout<FQuat>());
    Layouts->SetObjectField(TEXT("FTransform"), Layout<FTransform>());
    Layouts->SetObjectField(TEXT("FMatrix"), Layout<FMatrix>());
    Layouts->SetObjectField(TEXT("PersistentVectorRegister4Double"), Layout<PersistentVectorRegister4Double>());
    Layouts->SetObjectField(TEXT("VectorRegister4Double"), Layout<VectorRegister4Double>());
    Value->SetObjectField(TEXT("layouts"), Layouts);
    Value->SetStringField(TEXT("scope"), TEXT("This game's compiled fingerprint only. Four storage assertions are not full ABI proof. Native Jolt, Core/Engine and ORT binary identities are recorded separately by the external launcher. CPU admission must occur before this DLL loads; this runtime check cannot provide a baseline fallback."));
    return Value;
}
}
