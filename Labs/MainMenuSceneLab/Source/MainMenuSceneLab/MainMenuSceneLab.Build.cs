using UnrealBuildTool;
public class MainMenuSceneLab:ModuleRules {
 public MainMenuSceneLab(ReadOnlyTargetRules Target):base(Target) {
  PCHUsage=PCHUsageMode.NoPCHs;
  PrivateDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","InputCore","Slate","SlateCore","ApplicationCore","Json","RenderCore","RHI","ProceduralMeshComponent","Niagara","NiagaraCore","WaterAdvanced"});
  if(Target.bBuildEditor)PrivateDependencyModuleNames.AddRange(new[]{"NiagaraEditor","AssetTools","UnrealEd"});
 }
}
