using UnrealBuildTool;

public class ProphecyJoltEditor : ModuleRules
{
    public ProphecyJoltEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        CppStandard = CppStandardVersion.Cpp20;
        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Core", "CoreUObject", "Engine", "UnrealEd", "AssetRegistry",
            "BlueprintGraph", "Json", "JsonUtilities", "PhysicsCore", "Niagara", "ProphecyJolt"
        });
    }
}
