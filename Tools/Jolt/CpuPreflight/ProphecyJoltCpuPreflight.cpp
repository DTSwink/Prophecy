#include <cstdio>
#include <intrin.h>
#include "../ProphecyJoltBuildContract.h"

#if !defined(_MSC_VER) || !defined(_M_X64) || defined(__AVX__) || defined(__AVX2__) || defined(__AVX512F__)
#error Compile this preflight for baseline MSVC x64, without any AVX /arch option.
#endif

// No Jolt imports or advanced SIMD intrinsics. The only XGETBV is conditional on
// the CPU/OS XSAVE capability bits. Exit 0 means this complete AVX2/FMA profile is
// supported; exit 1 refuses launch. Do not infer support from the CPU name.
int main()
{
    using namespace ProphecyJoltBuildContract;
    int Cpu[4] = {};
    __cpuid(Cpu, 0);
    const uint32_t MaximumBasicLeaf = static_cast<uint32_t>(Cpu[0]);
    uint32_t Leaf1C = 0, Leaf1D = 0, Leaf7B = 0, Extended1C = 0;
    if (MaximumBasicLeaf >= 1)
    {
        __cpuidex(Cpu, 1, 0);
        Leaf1C = static_cast<uint32_t>(Cpu[2]);
        Leaf1D = static_cast<uint32_t>(Cpu[3]);
    }
    if (MaximumBasicLeaf >= 7)
    {
        __cpuidex(Cpu, 7, 0);
        Leaf7B = static_cast<uint32_t>(Cpu[1]);
    }
    __cpuid(Cpu, static_cast<int>(0x80000000u));
    if (static_cast<uint32_t>(Cpu[0]) >= 0x80000001u)
    {
        __cpuid(Cpu, static_cast<int>(0x80000001u));
        Extended1C = static_cast<uint32_t>(Cpu[2]);
    }
    const bool HasXSAVE = (Leaf1C & (1u << 26)) != 0;
    const bool HasOSXSAVE = (Leaf1C & (1u << 27)) != 0;
    const uint64_t Xcr0 = HasXSAVE && HasOSXSAVE ? _xgetbv(0) : 0;
    const bool HasAVXContext = (Xcr0 & 6u) == 6u;
    const bool HasAVX = HasAVXContext && (Leaf1C & (1u << 28)) != 0;
    const bool HasPOPCNT = (Leaf1C & (1u << 23)) != 0;
    uint32_t Supported = 0;
    if ((Leaf1D & (1u << 26)) != 0) Supported |= SSE2;
    if ((Leaf1C & (1u << 19)) != 0) Supported |= SSE41;
    if ((Leaf1C & (1u << 20)) != 0) Supported |= SSE42;
    if (HasAVX) Supported |= AVX;
    if (HasAVX && (Leaf7B & (1u << 5)) != 0) Supported |= AVX2;
    if (HasAVX && (Leaf1C & (1u << 29)) != 0) Supported |= F16C;
    if ((Extended1C & (1u << 5)) != 0) Supported |= LZCNT;
    if ((Leaf7B & (1u << 3)) != 0) Supported |= TZCNT;
    if (HasAVX && (Leaf1C & (1u << 12)) != 0) Supported |= FMA;
    if ((Leaf7B & (1u << 8)) != 0) Supported |= CompilerBMI2;
    const uint32_t Missing = ExpectedAVX2FMA & ~Supported;
    const bool IsSupported = Missing == 0 && HasPOPCNT;
    std::printf("{\"schema\":1,\"profile\":\"AVX2_FMA_PRECISE\",\"baseline_probe\":true,"
        "\"supported\":%s,\"required_instruction_mask\":%u,\"supported_instruction_mask\":%u,"
        "\"missing_instruction_mask\":%u,\"popcnt\":%s,\"xsave\":%s,\"osxsave\":%s,"
        "\"xcr0\":%llu,\"avx_os_context\":%s,\"cpuid_leaf1_ecx\":%u,"
        "\"cpuid_leaf1_edx\":%u,\"cpuid_leaf7_ebx\":%u,\"cpuid_extended1_ecx\":%u}\n",
        IsSupported ? "true" : "false", ExpectedAVX2FMA, Supported, Missing,
        HasPOPCNT ? "true" : "false", HasXSAVE ? "true" : "false", HasOSXSAVE ? "true" : "false",
        static_cast<unsigned long long>(Xcr0), HasAVXContext ? "true" : "false",
        Leaf1C, Leaf1D, Leaf7B, Extended1C);
    return IsSupported ? 0 : 1;
}
