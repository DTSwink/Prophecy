using UnrealBuildTool;
public class MainMenuSceneLabEditorTarget : TargetRules {
 public MainMenuSceneLabEditorTarget(TargetInfo Target):base(Target) {
  Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.Latest;
  IncludeOrderVersion=EngineIncludeOrderVersion.Latest;
  bUseAdaptiveUnityBuild=false; WindowsPlatform.bWriteSarif=false;
  ExtraModuleNames.Add("MainMenuSceneLab");
 }
}
