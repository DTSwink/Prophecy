"""Regenerate isolated source copies/patch against active baseline; never edit it."""
from pathlib import Path
import difflib
import hashlib
import json

root = Path(__file__).resolve().parents[3]
draft = Path(__file__).resolve().parent
paths = [
    "Source/GameAnimationSample3/GameAnimationSample3.Build.cs",
    "Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp",
]
hashes = {}
patch = []
for relative in paths:
    source = root / relative
    original = source.read_text(encoding="utf-8-sig")
    hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    if relative.endswith(".Build.cs"):
        anchor = "\t\tPCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;"
        addition = '''
		// Local, opt-in game-module ISA experiment; never change the native Jolt
		// profile here. An empty/default selection preserves ordinary settings.
		string GameSimd = (System.Environment.GetEnvironmentVariable("PROPHECY_GAME_SIMD") ?? "DEFAULT").Trim().ToUpperInvariant();
		if (GameSimd.Length == 0) GameSimd = "DEFAULT";
		if (GameSimd != "DEFAULT" && GameSimd != "SSE2_PRIVATE" && GameSimd != "AVX2_PRIVATE")
			throw new BuildException("PROPHECY_GAME_SIMD must be DEFAULT, SSE2_PRIVATE or AVX2_PRIVATE.");
		int GameSimdProfile = GameSimd == "AVX2_PRIVATE" ? 2 : GameSimd == "SSE2_PRIVATE" ? 1 : 0;
		PrivateDefinitions.Add("PROPHECY_GAME_SIMD_PROFILE=" + GameSimdProfile);
		if (GameSimdProfile != 0)
		{
			if (Target.Platform != UnrealTargetPlatform.Win64 || Target.Architecture != UnrealArch.X64)
				throw new BuildException("The explicit game-module ISA diagnostic is local Win64 x64 only.");
			string NativeSimd = (System.Environment.GetEnvironmentVariable("PROPHECY_JOLT_SIMD") ?? "SSE2").Trim().ToUpperInvariant();
			if (NativeSimd != "SSE2")
				throw new BuildException("Game-module ISA diagnostics require PROPHECY_JOLT_SIMD=SSE2; native Jolt is a separate factor.");
			PCHUsage = PCHUsageMode.NoSharedPCHs;
			PrivatePCHHeaderFile = "Private/ProphecyGameModuleSimdPCH.h";
			MinCpuArchX64 = GameSimdProfile == 2 ? MinimumCpuArchitectureX64.AVX2 : MinimumCpuArchitectureX64.None;
			// Preserve existing FP/optimization/unity/exception/C++ semantics in
			// both explicit profiles. Shared PCHs do not key on MinCpuArchX64.
		}
'''
        assert original.count(anchor) == 1
        changed = original.replace(anchor, anchor + addition)
    else:
        changed = original
        for anchor, replacement in [
            ('#include "ProphecyPhysicsBenchmark.h"', '#include "ProphecyPhysicsBenchmark.h"\n#include "ProphecyGameModuleSimd.h"'),
            ('    FString Override; if (FParse::Value(FCommandLine::Get(),TEXT("PhysicsBenchJson="),Override)) Output = FPaths::ConvertRelativePathToFull(Override);',
             '    FString Override; if (FParse::Value(FCommandLine::Get(),TEXT("PhysicsBenchJson="),Override)) Output = FPaths::ConvertRelativePathToFull(Override);\n    FString GameProfileError;\n    if (!ProphecyGameModuleSimd::ValidateRequestedProfile(GameProfileError)) { Finish(GameProfileError); return; }'),
            ('    O->SetNumberField(TEXT("benchmark_version"),3);',
             '    O->SetNumberField(TEXT("benchmark_version"),3);\n    O->SetObjectField(TEXT("game_module_build_profile"), ProphecyGameModuleSimd::Report());'),
        ]:
            assert changed.count(anchor) == 1, anchor
            changed = changed.replace(anchor, replacement)
    destination = draft / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(changed, encoding="utf-8", newline="\n")
    patch.extend(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                    fromfile="a/" + relative, tofile="b/" + relative))
(draft / "ExistingFiles.patch").write_text("".join(patch), encoding="utf-8", newline="\n")
(draft / "BaselineHashes.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
print(json.dumps(hashes, indent=2))
print("Wrote draft copies and isolated existing-file patch only.")
