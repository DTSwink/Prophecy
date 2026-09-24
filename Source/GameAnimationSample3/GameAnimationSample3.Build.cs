using UnrealBuildTool;

public class GameAnimationSample3 : ModuleRules
{
	public GameAnimationSample3(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/prophecy_slash_half_gt.json", StagedFileType.UFS);
		RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/defense/prophecy_parry_upper.onnx", StagedFileType.UFS);
		RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/defense/parry_skeleton.json", StagedFileType.UFS);
		RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/defense/parry_colliders.json", StagedFileType.UFS);
		RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/defense/attacker_colliders.json", StagedFileType.UFS);
		foreach (string Asset in new[] { "prophecy_dodge_walk.onnx", "prophecy_dodge_run.onnx", "prophecy_dodge_upper.onnx", "dodge_skeleton.json", "dodge_colliders.json", "dodge_lower_settings.json", "dodge_banks.json" })
			RuntimeDependencies.Add("$(ProjectDir)/Content/locomotion/NN/defense/" + Asset, StagedFileType.UFS);
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

		PrivateDependencyModuleNames.AddRange(new[] { "ProphecyJolt", "RHI", "PCG" });
		PrivateIncludePaths.Add(System.IO.Path.GetFullPath(System.IO.Path.Combine(
			ModuleDirectory, "..", "..", "StandaloneSim", "sim_core", "include")));

		PublicDependencyModuleNames.AddRange(new[]
		{
			"Core",
			"CoreUObject",
			"Chaos",
			"Engine",
			"AnimationCore",
			"InputCore",
			"EnhancedInput",
			"ImageWrapper",
			"Json",
			"NNE",
			"MeshDescription",
			"MeshConversion",
			"Niagara",
			"PhysicsCore",
			"ProceduralMeshComponent",
			"Projects",
			"StaticMeshDescription"
		});

		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(new[]
			{
				"AssetTools",
				"MaterialEditor",
				"UnrealEd"
			});
		}
	}
}
