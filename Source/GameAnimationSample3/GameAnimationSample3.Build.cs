using UnrealBuildTool;

public class GameAnimationSample3 : ModuleRules
{
	public GameAnimationSample3(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PrivateIncludePaths.Add(System.IO.Path.GetFullPath(System.IO.Path.Combine(
			ModuleDirectory, "..", "..", "StandaloneSim", "sim_core", "include")));

		PublicDependencyModuleNames.AddRange(new[]
		{
			"Core",
			"CoreUObject",
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
