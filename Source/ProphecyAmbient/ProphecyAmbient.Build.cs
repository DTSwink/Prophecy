using UnrealBuildTool;

// Ambient wildlife (bumblebees, gulls, kingfishers). Small, isolated runtime module so changes here
// never regroup or rebuild the GameAnimationSample3 unity files.
public class ProphecyAmbient : ModuleRules
{
	public ProphecyAmbient(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "Niagara" });
		PrivateDependencyModuleNames.AddRange(new string[] { "RenderCore", "RHI", "ImageWrapper", "Json", "PhysicsCore" });
	}
}
