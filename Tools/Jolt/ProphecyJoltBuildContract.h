#pragma once

#include <stdint.h>

// Plain integer/C ABI: this header has no Jolt, Unreal, or SIMD-type dependency.
namespace ProphecyJoltBuildContract
{
constexpr uint32_t ProtocolVersion = 1;
enum EInstruction : uint32_t
{
    SSE2 = 1u << 0, SSE41 = 1u << 1, SSE42 = 1u << 2,
    AVX = 1u << 3, AVX2 = 1u << 4, AVX512 = 1u << 5,
    F16C = 1u << 6, LZCNT = 1u << 7, TZCNT = 1u << 8,
    FMA = 1u << 9, CompilerBMI2 = 1u << 10
};
constexpr uint32_t ExpectedAVX2FMA = SSE2 | SSE41 | SSE42 | AVX | AVX2
    | F16C | LZCNT | TZCNT | FMA | CompilerBMI2;
enum EPolicy : uint32_t
{
    Precise = 1u << 0, Exceptions = 1u << 1,
    RTTI = 1u << 2, CrossPlatformDeterministic = 1u << 3
};
constexpr uint32_t ExpectedPolicy = Precise | Exceptions;

// Include after Jolt/Jolt.h to fingerprint its effective automatic definitions.
#if defined(JPH_VERSION_ID)
constexpr uint32_t CompilationInstructions()
{
    uint32_t Result = 0;
#ifdef JPH_USE_SSE
    Result |= SSE2;
#endif
#ifdef JPH_USE_SSE4_1
    Result |= SSE41;
#endif
#ifdef JPH_USE_SSE4_2
    Result |= SSE42;
#endif
#ifdef JPH_USE_AVX
    Result |= AVX;
#endif
#ifdef JPH_USE_AVX2
    Result |= AVX2;
#endif
#ifdef JPH_USE_AVX512
    Result |= AVX512;
#endif
#ifdef JPH_USE_F16C
    Result |= F16C;
#endif
#ifdef JPH_USE_LZCNT
    Result |= LZCNT;
#endif
#ifdef JPH_USE_TZCNT
    Result |= TZCNT;
#endif
#ifdef JPH_USE_FMADD
    Result |= FMA;
#endif
#if defined(_MSC_VER) && defined(__AVX2__)
    Result |= CompilerBMI2;
#endif
    return Result;
}
constexpr uint32_t CompilationPolicy()
{
    uint32_t Result = 0;
#if defined(PROPHECY_JOLT_PRECISE_BUILD) && PROPHECY_JOLT_PRECISE_BUILD
    Result |= Precise;
#endif
#ifdef _CPPUNWIND
    Result |= Exceptions;
#endif
#ifdef _CPPRTTI
    Result |= RTTI;
#endif
#ifdef JPH_CROSS_PLATFORM_DETERMINISTIC
    Result |= CrossPlatformDeterministic;
#endif
    return Result;
}
#endif
}

#if defined(PROPHECY_JOLT_BUILD_CONTRACT_EXPORTS)
#define PROPHECY_JOLT_CONTRACT_API __declspec(dllexport)
#else
#define PROPHECY_JOLT_CONTRACT_API __declspec(dllimport)
#endif
extern "C"
{
PROPHECY_JOLT_CONTRACT_API uint32_t ProphecyJolt_GetContractVersion();
PROPHECY_JOLT_CONTRACT_API uint64_t ProphecyJolt_GetNativeVersionId();
PROPHECY_JOLT_CONTRACT_API uint32_t ProphecyJolt_GetNativeInstructions();
PROPHECY_JOLT_CONTRACT_API uint32_t ProphecyJolt_GetNativePolicy();
PROPHECY_JOLT_CONTRACT_API const char* ProphecyJolt_GetNativeConfiguration();
}
#undef PROPHECY_JOLT_CONTRACT_API
