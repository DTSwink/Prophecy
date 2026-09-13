#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include "ProphecyJoltBuildContract.h"

static_assert(JPH_VERSION_MAJOR == 5 && JPH_VERSION_MINOR == 6 && JPH_VERSION_PATCH == 0,
    "Review the contract when changing the pinned Jolt version.");
static_assert(ProphecyJoltBuildContract::CompilationInstructions() == ProphecyJoltBuildContract::ExpectedAVX2FMA,
    "The AVX2 diagnostic DLL must use precisely the declared AVX2/FMA instruction profile.");
static_assert(ProphecyJoltBuildContract::CompilationPolicy() == ProphecyJoltBuildContract::ExpectedPolicy,
    "The AVX2 diagnostic DLL must retain precise FP, exceptions, no RTTI and no cross-platform determinism.");

extern "C" uint32_t ProphecyJolt_GetContractVersion() { return ProphecyJoltBuildContract::ProtocolVersion; }
extern "C" uint64_t ProphecyJolt_GetNativeVersionId() { using JPH::uint64; return JPH_VERSION_ID; }
extern "C" uint32_t ProphecyJolt_GetNativeInstructions() { return ProphecyJoltBuildContract::CompilationInstructions(); }
extern "C" uint32_t ProphecyJolt_GetNativePolicy() { return ProphecyJoltBuildContract::CompilationPolicy(); }
extern "C" const char* ProphecyJolt_GetNativeConfiguration() { return JPH::GetConfigurationString(); }
