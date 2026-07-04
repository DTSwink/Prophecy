using UnrealBuildTool;

public class ProphecyEditor : ModuleRules
{
	public ProphecyEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		// Live Coding patch links for this small editor module have hit LNK2011
		// when commandlet objects are relinked without their PCH object.
		PCHUsage = PCHUsageMode.NoPCHs;

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
