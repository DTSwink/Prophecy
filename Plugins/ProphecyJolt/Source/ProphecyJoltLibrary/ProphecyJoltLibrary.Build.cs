using System;
using System.IO;
using System.Security.Cryptography;
using EpicGames.Core;
using UnrealBuildTool;

public class ProphecyJoltLibrary : ModuleRules
{
    public ProphecyJoltLibrary(ReadOnlyTargetRules Target) : base(Target)
    {
        Type = ModuleType.External;
        if (Target.Platform != UnrealTargetPlatform.Win64)
            throw new BuildException("ProphecyJolt currently has a verified build recipe for Win64 only.");
        if (Target.bDebugBuildsActuallyUseDebugCRT && Target.Configuration == UnrealTargetConfiguration.Debug)
            throw new BuildException("ProphecyJolt debug CRT is not prepared. The current dependency recipe uses /MD.");

        // This opt-in is evaluated while generating the UBT makefile. A scoped
        // profile switch MUST build with -NoUBTMakefiles (see the diagnostic notes).
        string Simd = (Environment.GetEnvironmentVariable("PROPHECY_JOLT_SIMD") ?? "SSE2").Trim().ToUpperInvariant();
        if (Simd != "SSE2" && Simd != "AVX2")
            throw new BuildException("PROPHECY_JOLT_SIMD must be SSE2 or AVX2.");
        bool IsAvx2 = Simd == "AVX2";
        string Configuration = Target.Configuration == UnrealTargetConfiguration.Shipping ? "Shipping" : "Development";
        string LibraryBaseName = "ProphecyJolt_5_6_" + Configuration + (IsAvx2 ? "_AVX2" : "");
        string DllFilename = LibraryBaseName + ".dll";
        string ImportLibraryFilename = LibraryBaseName + ".lib";
        string ProjectRoot = Path.GetFullPath(Path.Combine(PluginDirectory, "..", ".."));
        string InstallBase = Path.Combine(ProjectRoot, "Intermediate", "JoltMigration", "Install");
        string InstallRoot = IsAvx2 ? Path.Combine(InstallBase, "AVX2", Configuration) : Path.Combine(InstallBase, Configuration);
        string ManifestPath = Path.Combine(InstallRoot, "manifest.json");
        string LibraryPath = Path.Combine(InstallRoot, "lib", ImportLibraryFilename);
        string DllPath = Path.Combine(InstallRoot, "bin", DllFilename);
        if (!File.Exists(ManifestPath) || !File.Exists(LibraryPath) || !File.Exists(DllPath))
            throw new BuildException("Prepare Jolt explicitly before UBT: powershell -File Tools/Jolt/BuildJolt.ps1 -Configuration " + Configuration + " -Simd " + Simd);

        JsonObject Manifest = JsonObject.Read(new FileReference(ManifestPath));
        string SafetyPatch = Path.Combine(ProjectRoot, "Tools", "Jolt", "Patches", "NumericalSafety.patch");
        if (!Manifest.TryGetIntegerField("numericalSafetyPatchVersion", out int SafetyVersion) || SafetyVersion != 1
            || !File.Exists(SafetyPatch))
            throw new BuildException("Rebuild the Jolt dependency with Tools/Jolt/BuildJolt.ps1: numerical-safety patch is required.");
        VerifyHash(SafetyPatch, Manifest.GetStringField("numericalSafetyPatchSha256"));
        VerifyHash(DllPath, Manifest.GetStringField("dllSha256"));
        VerifyHash(LibraryPath, Manifest.GetStringField("importLibrarySha256"));
        ExternalDependencies.Add(SafetyPatch);
        if (Manifest.GetIntegerField("schema") != (IsAvx2 ? 3 : 2)
            || Manifest.GetStringField("sourceSha") != "e77f175595e64cb44218cc9d9d56fc365ad0e36a"
            || Manifest.GetStringField("configuration") != Configuration
            || Manifest.GetStringField("dllFilename") != DllFilename
            || Manifest.GetStringField("importLibraryFilename") != ImportLibraryFilename
            || Manifest.GetStringField("simd") != Simd
            || Manifest.GetStringField("floatingPoint") != "precise"
            || Manifest.GetBoolField("crossPlatformDeterministic")
            || Manifest.GetBoolField("debugRenderer") || Manifest.GetBoolField("profiler")
            || !Manifest.GetBoolField("objectStream")
            || Manifest.GetStringField("runtime") != "MD"
            || Manifest.GetStringField("worldPrecision") != "double"
            || Manifest.GetBoolField("assertions") != (Configuration == "Development")
            || !Manifest.GetBoolField("cppExceptions"))
            throw new BuildException("Jolt dependency manifest does not match the selected build contract.");
        if (IsAvx2)
        {
            string ContractHeader = Path.Combine(InstallRoot, "include", "ProphecyJoltBuildContract.h");
            string CpuProbe = Path.Combine(InstallRoot, "tools", "ProphecyJoltCpuPreflight.exe");
            if (Manifest.GetIntegerField("buildContractVersion") != 1
                || Manifest.GetIntegerField("instructionMask") != 2015
                || Manifest.GetStringField("compilerArchitecture") != "AVX2" || !Manifest.GetBoolField("fma")
                || !File.Exists(ContractHeader) || !File.Exists(CpuProbe))
                throw new BuildException("The AVX2 native dependency contract/preflight is incomplete.");
            VerifyHash(DllPath, Manifest.GetStringField("dllSha256"));
            VerifyHash(LibraryPath, Manifest.GetStringField("importLibrarySha256"));
            VerifyHash(ContractHeader, Manifest.GetStringField("contractHeaderSha256"));
            VerifyHash(CpuProbe, Manifest.GetStringField("cpuPreflightSha256"));
            ExternalDependencies.Add(ContractHeader);
            ExternalDependencies.Add(CpuProbe);
            PublicDefinitions.AddRange(new[] { "JPH_USE_SSE4_1", "JPH_USE_SSE4_2", "JPH_USE_AVX", "JPH_USE_AVX2",
                "JPH_USE_LZCNT", "JPH_USE_TZCNT", "JPH_USE_F16C", "JPH_USE_FMADD", "PROPHECY_JOLT_PRECISE_BUILD=1" });
        }
        PublicDefinitions.Add("PROPHECY_JOLT_PROFILE_AVX2=" + (IsAvx2 ? "1" : "0"));
        ExternalDependencies.Add(ManifestPath);
        PublicSystemIncludePaths.Add(Path.Combine(InstallRoot, "include"));
        PublicAdditionalLibraries.Add(LibraryPath);
        // Jolt exports global data (allocators/factory), so MSVC delay loading is
        // inappropriate. UE adds plugin Binaries/Win64 to its import search path.
        // A monolithic game needs the DLL beside its executable before startup.
        // Distinct configuration names prevent an editor import from selecting a
        // Shipping DLL left in a shared host directory by an earlier game build.
        string RuntimeDirectory = Target.LinkType == TargetLinkType.Monolithic
            ? "$(TargetOutputDir)" : "$(PluginDir)/Binaries/Win64";
        RuntimeDependencies.Add(RuntimeDirectory + "/" + DllFilename, DllPath, StagedFileType.NonUFS);
        // Editor DLL search also visits the project's executable directory. Keep
        // a prior monolithic-build copy from shadowing the selected plugin DLL.
        if (Target.LinkType != TargetLinkType.Monolithic)
            RuntimeDependencies.Add(Path.Combine(ProjectRoot, "Binaries", "Win64", DllFilename), DllPath, StagedFileType.NonUFS);
        RuntimeDependencies.Add(RuntimeDirectory + "/Jolt-LICENSE.txt", Path.Combine(InstallRoot, "Jolt-LICENSE.txt"), StagedFileType.NonUFS);
        PublicDefinitions.AddRange(new[] { "JPH_SHARED_LIBRARY", "JPH_DOUBLE_PRECISION", "JPH_OBJECT_STREAM" });
        if (Configuration == "Development")
            PublicDefinitions.Add("JPH_ENABLE_ASSERTS");
    }

    private static void VerifyHash(string PathName, string Expected)
    {
        using (SHA256 Hasher = SHA256.Create())
        using (FileStream Input = File.OpenRead(PathName))
        {
            string Actual = BitConverter.ToString(Hasher.ComputeHash(Input)).Replace("-", "");
            if (!string.Equals(Actual, Expected, StringComparison.OrdinalIgnoreCase))
                throw new BuildException("Jolt dependency hash mismatch: " + PathName);
        }
    }
}
