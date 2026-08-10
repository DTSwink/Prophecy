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
			"AssetTools",
			"Core",
			"CoreUObject",
			"Blutility",
			"BlueprintGraph",
			"Engine",
			"GameAnimationSample3",
			"ImageCore",
			"Json",
			"KismetCompiler",
			"Landscape",
			"MetaHumanCharacter",
			"MetaHumanCharacterEditor",
			"MetaHumanCharacterPalette",
			"MetaHumanDefaultEditorPipeline",
			"MetaHumanSDKRuntime",
			"Projects",
			"PhysicsCore",
			"SkeletalMeshEditor",
			"SkeletalMeshModifiers",
			"UnrealEd"
		});
	}
}
