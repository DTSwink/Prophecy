using UnrealBuildTool;
public class WeaponWheelLabEditorTarget : TargetRules
{
    public WeaponWheelLabEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        WindowsPlatform.bWriteSarif = false;
        bUseAdaptiveUnityBuild = false;
        ExtraModuleNames.Add("WeaponWheelLab");
    }
}
