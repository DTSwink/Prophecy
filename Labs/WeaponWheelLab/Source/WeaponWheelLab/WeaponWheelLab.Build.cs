using UnrealBuildTool;
public class WeaponWheelLab : ModuleRules
{
    public WeaponWheelLab(ReadOnlyTargetRules Target) : base(Target)
    {
        // This one-file lab does not need a 2.4 GB UnrealEd shared PCH.
        PCHUsage = PCHUsageMode.NoPCHs;
        PrivateDependencyModuleNames.AddRange(new[] {
            "Core", "CoreUObject", "Engine", "InputCore", "Slate", "SlateCore", "ApplicationCore", "AppFramework", "Json", "ImageCore", "RenderCore", "RHI"
        });
    }
}
