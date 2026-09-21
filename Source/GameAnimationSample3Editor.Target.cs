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
		// Git commits must not move files between individual and unity translation
		// units during Live Coding: retained console variables/native globals can
		// otherwise belong to a different patch than their callers. Keep unity,
		// but keep its grouping independent of the working tree's dirty state.
		bUseAdaptiveUnityBuild = false;
		ExtraModuleNames.Add("GameAnimationSample3");
		ExtraModuleNames.Add("ProphecyEditor");
	}
}
