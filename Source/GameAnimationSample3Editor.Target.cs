using UnrealBuildTool;
using System.Collections.Generic;

public class GameAnimationSample3EditorTarget : TargetRules
{
	public GameAnimationSample3EditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		// Normal and Live Coding actions share SARIF output paths in UE5.7,
		// invalidating their command history even when source is unchanged.
		WindowsPlatform.bWriteSarif = false;
		ExtraModuleNames.Add("GameAnimationSample3");
		ExtraModuleNames.Add("ProphecyEditor");
	}
}
