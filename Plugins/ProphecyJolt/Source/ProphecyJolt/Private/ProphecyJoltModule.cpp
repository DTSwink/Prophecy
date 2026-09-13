#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltBody.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Core/Memory.h>
#include <Jolt/RegisterTypes.h>
#if PROPHECY_JOLT_PROFILE_AVX2
#include <ProphecyJoltBuildContract.h>
#endif
THIRD_PARTY_INCLUDES_END

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJolt, Log, All);

// Narrow UE 5.7 Win64 storage guards, evaluated for both profiles. These do
// not certify every inline function or cross-module calling convention.
static_assert(sizeof(FVector) == 24 && alignof(FVector) == 8, "Review the UE FVector boundary.");
static_assert(sizeof(FQuat) == 32 && alignof(FQuat) == 16, "Review the UE FQuat boundary.");
static_assert(sizeof(TPersistentVectorRegisterType<double>) == 32
    && alignof(TPersistentVectorRegisterType<double>) == 16, "UE persistent SIMD storage must stay 16-aligned.");
static_assert(sizeof(FTransform) == 96 && alignof(FTransform) == 16, "Review the UE FTransform boundary.");

#if PROPHECY_JOLT_PROFILE_AVX2
static_assert(ProphecyJoltBuildContract::CompilationInstructions() == ProphecyJoltBuildContract::ExpectedAVX2FMA,
    "Rebuild every native Jolt consumer with the declared AVX2/FMA profile.");
static_assert(ProphecyJoltBuildContract::CompilationPolicy() == ProphecyJoltBuildContract::ExpectedPolicy,
    "The AVX2 Jolt consumer must retain precise FP, exceptions, no RTTI and no determinism override.");
#endif

namespace ProphecyJoltRuntime
{
void* Allocate(size_t Size) { return FMemory::Malloc(Size, 16); }
void* Reallocate(void* Block, size_t OldSize, size_t NewSize) { return FMemory::Realloc(Block, NewSize, 16); }
void Free(void* Block) { FMemory::Free(Block); }
void* AlignedAllocate(size_t Size, size_t Alignment) { return FMemory::Malloc(Size, static_cast<uint32>(Alignment)); }

void Trace(const char* Format, ...)
{
    ANSICHAR Buffer[2048];
    va_list Arguments;
    va_start(Arguments, Format);
    FCStringAnsi::GetVarArgs(Buffer, UE_ARRAY_COUNT(Buffer), Format, Arguments);
    va_end(Arguments);
    UE_LOG(LogProphecyJolt, Log, TEXT("%s"), UTF8_TO_TCHAR(Buffer));
}

#ifdef JPH_ENABLE_ASSERTS
bool AssertFailed(const char* Expression, const char* Message, const char* File, JPH::uint Line)
{
    UE_LOG(LogProphecyJolt, Fatal, TEXT("Jolt assertion: %s (%s) at %s:%u"),
        UTF8_TO_TCHAR(Expression), Message ? UTF8_TO_TCHAR(Message) : TEXT(""), UTF8_TO_TCHAR(File), Line);
    return true;
}
#endif
}

class FProphecyJoltModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
#if PROPHECY_JOLT_PROFILE_AVX2
        // This is a post-load ABI/fingerprint check. It is NOT a pre-DLL CPU
        // guard: the baseline preflight must run before launching this process.
        if (ProphecyJolt_GetContractVersion() != ProphecyJoltBuildContract::ProtocolVersion
            || ProphecyJolt_GetNativeVersionId() != JPH_VERSION_ID
            || ProphecyJolt_GetNativeInstructions() != ProphecyJoltBuildContract::CompilationInstructions()
            || ProphecyJolt_GetNativePolicy() != ProphecyJoltBuildContract::CompilationPolicy())
        {
            UE_LOG(LogProphecyJolt, Fatal, TEXT("Jolt native DLL/consumer AVX2 build-contract mismatch."));
            return;
        }
        UE_LOG(LogProphecyJolt, Display, TEXT("Local AVX2 diagnostic native DLL: %s; ISA mask=%u, policy=%u. External CPU preflight required."),
            UTF8_TO_TCHAR(ProphecyJolt_GetNativeConfiguration()), ProphecyJolt_GetNativeInstructions(), ProphecyJolt_GetNativePolicy());
#endif
        if (!JPH::VerifyJoltVersionID())
        {
            UE_LOG(LogProphecyJolt, Fatal, TEXT("Jolt library/header feature ABI mismatch."));
            return;
        }
        checkf(JPH::Factory::sInstance == nullptr, TEXT("Jolt globals already owned by another module."));
        JPH::Allocate = ProphecyJoltRuntime::Allocate;
        JPH::Reallocate = ProphecyJoltRuntime::Reallocate;
        JPH::Free = ProphecyJoltRuntime::Free;
        JPH::AlignedAllocate = ProphecyJoltRuntime::AlignedAllocate;
        JPH::AlignedFree = ProphecyJoltRuntime::Free;
        JPH::Trace = ProphecyJoltRuntime::Trace;
#ifdef JPH_ENABLE_ASSERTS
        JPH::AssertFailed = ProphecyJoltRuntime::AssertFailed;
#endif
        JPH::Factory::sInstance = new JPH::Factory();
        JPH::RegisterTypes();
        bRegistered = true;
        UE_LOG(LogProphecyJolt, Display, TEXT("Jolt 5.6.0 ready: %s. Gameplay backend remains unchanged."),
            UTF8_TO_TCHAR(JPH::GetConfigurationString()));
    }

    virtual void ShutdownModule() override
    {
        if (bRegistered)
        {
            if (UProphecyJoltWorldSubsystem::GetLiveSimulationCount() != 0 || FProphecyJoltPreparedRig::GetLivePreparedRigCount() != 0
                || FProphecyJoltPreparedBody::GetLivePreparedBodyCount() != 0)
            {
                UE_LOG(LogProphecyJolt, Fatal, TEXT("Jolt runtime shutdown while world simulations or prepared rigs are still alive."));
                return;
            }
            JPH::UnregisterTypes();
            delete JPH::Factory::sInstance;
            JPH::Factory::sInstance = nullptr;
            bRegistered = false;
        }
    }

    // An ordinary hot-unload must not invalidate allocator/callback function pointers.
    virtual bool SupportsDynamicReloading() override { return false; }

private:
    bool bRegistered = false;
};

IMPLEMENT_MODULE(FProphecyJoltModule, ProphecyJolt)
