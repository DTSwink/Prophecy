using UnrealBuildTool;
using System.Collections.Generic;

public class GameAnimationSample3Target : TargetRules
{
	public GameAnimationSample3Target(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("GameAnimationSample3");
	}
}
