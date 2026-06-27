using UnrealBuildTool;

public class ProphecyEditor : ModuleRules
{
	public ProphecyEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PrivateDependencyModuleNames.AddRange(new[]
		{
			"Core",
			"CoreUObject",
			"Blutility",
			"BlueprintGraph",
			"Engine",
			"GameAnimationSample3",
			"ImageCore",
			"KismetCompiler",
			"MetaHumanCharacter",
			"MetaHumanCharacterEditor",
			"MetaHumanCharacterPalette",
			"MetaHumanDefaultEditorPipeline",
			"MetaHumanSDKRuntime",
			"Projects",
			"UnrealEd"
		});
	}
}
