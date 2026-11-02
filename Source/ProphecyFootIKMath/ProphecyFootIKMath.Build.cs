using UnrealBuildTool;
using System.IO;

// The compatibility functions need IEEE operation order. Keep this isolated
// from gameplay/Jolt compiler settings and from unity/PCH compilation.
public class ProphecyFootIKMath : ModuleRules
{
    public ProphecyFootIKMath(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.NoPCHs;
        bUseUnity = false;
        FPSemantics = FPSemanticsMode.Precise;
        PublicDependencyModuleNames.Add("Core");
        PrivateIncludePaths.Add(Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "Tools", "FootIK", "v8-math")));
    }
}
