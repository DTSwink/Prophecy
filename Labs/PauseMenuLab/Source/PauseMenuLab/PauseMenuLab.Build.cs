using UnrealBuildTool;
public class PauseMenuLab:ModuleRules {
 public PauseMenuLab(ReadOnlyTargetRules Target):base(Target) {
 PCHUsage=PCHUsageMode.NoPCHs;
 PrivateDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","InputCore","Slate","SlateCore","ApplicationCore","AppFramework","Json","ImageCore","RenderCore","RHI"});
 }
}
