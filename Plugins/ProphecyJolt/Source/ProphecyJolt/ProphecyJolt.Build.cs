using System;
using UnrealBuildTool;

public class ProphecyJolt : ModuleRules
{
    public ProphecyJolt(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        bUseUnity = false;
        CppStandard = CppStandardVersion.Cpp20;
        FPSemantics = FPSemanticsMode.Precise;
        // Module-local ISA: every Jolt inline consumer needs the same signature
        // contract. Leave the game/editor/engine modules on their existing ISA.
        string Simd = (Environment.GetEnvironmentVariable("PROPHECY_JOLT_SIMD") ?? "SSE2").Trim().ToUpperInvariant();
        if (Simd != "SSE2" && Simd != "AVX2")
            throw new BuildException("PROPHECY_JOLT_SIMD must be SSE2 or AVX2.");
        MinCpuArchX64 = Simd == "AVX2" ? MinimumCpuArchitectureX64.AVX2 : MinimumCpuArchitectureX64.None;
        // UE 5.7 enables exceptions for Editor. Match the dependency in game
        // builds too, without changing any other project module's settings.
        bEnableExceptions = true;
        bUseRTTI = false;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        // The live-rig importer reads the existing Chaos primitive geometry.
        PrivateDependencyModuleNames.AddRange(new[] { "Projects", "PhysicsCore", "Chaos", "ChaosCore", "ProphecyJoltLibrary" });
    }
}
