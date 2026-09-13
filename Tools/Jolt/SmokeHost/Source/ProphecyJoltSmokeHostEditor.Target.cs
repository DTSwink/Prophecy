using UnrealBuildTool;

public class ProphecyJoltSmokeHostEditorTarget : TargetRules
{
    public ProphecyJoltSmokeHostEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("ProphecyJoltSmokeHost");
    }
}
