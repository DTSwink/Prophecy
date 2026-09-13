using UnrealBuildTool;

public class ProphecyJoltSmokeHostTarget : TargetRules
{
    public ProphecyJoltSmokeHostTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("ProphecyJoltSmokeHost");
    }
}
