using UnrealBuildTool;
public class BloodDecalLabEditorTarget : TargetRules
{
    public BloodDecalLabEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        bUseAdaptiveUnityBuild = false;
        WindowsPlatform.bWriteSarif = false;
        ExtraModuleNames.Add("BloodDecalLab");
    }
}
