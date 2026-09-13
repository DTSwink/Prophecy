using UnrealBuildTool;

public class ProphecyJoltSmokeHost : ModuleRules
{
    public ProphecyJoltSmokeHost(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        CppStandard = CppStandardVersion.Cpp20;
        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Core", "CoreUObject", "Engine", "Json", "ProphecyJolt"
        });
    }
}
