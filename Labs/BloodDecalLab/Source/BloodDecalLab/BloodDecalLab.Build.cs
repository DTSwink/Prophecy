using UnrealBuildTool;
public class BloodDecalLab : ModuleRules
{
    public BloodDecalLab(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        PublicDependencyModuleNames.AddRange(new[] {"Core", "CoreUObject", "Engine"});
        PrivateDependencyModuleNames.AddRange(new[] {"Json", "RenderCore"});
    }
}
