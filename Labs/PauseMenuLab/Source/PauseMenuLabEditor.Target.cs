using UnrealBuildTool;
public class PauseMenuLabEditorTarget : TargetRules {
 public PauseMenuLabEditorTarget(TargetInfo Target):base(Target) {
 Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.Latest;
 IncludeOrderVersion=EngineIncludeOrderVersion.Latest;
 WindowsPlatform.bWriteSarif=false; bUseAdaptiveUnityBuild=false;
 ExtraModuleNames.Add("PauseMenuLab");
 }
}
