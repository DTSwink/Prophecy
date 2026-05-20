using UnrealBuildTool;

public class GameAnimationSample3 : ModuleRules
{
	public GameAnimationSample3(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

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
			"Projects",
			"StaticMeshDescription"
		});
	}
}
