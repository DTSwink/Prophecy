using UnrealBuildTool;
using System.Collections.Generic;

public class GameAnimationSample3EditorTarget : TargetRules
{
	public GameAnimationSample3EditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("GameAnimationSample3");
		ExtraModuleNames.Add("ProphecyEditor");
	}
}
