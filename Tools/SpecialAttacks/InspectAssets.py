"""Read-only inventory for the isolated special-attack test host."""
import json
import pathlib
import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
seeds = [str(a.package_name) for a in registry.get_assets_by_path(
    "/Game/_mygame/animations/special_attacks", recursive=True)]
seeds += ["/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"]
pending = list(seeds)
seen = set()
options = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True, include_hard_package_references=True,
    include_searchable_names=False, include_soft_management_references=False,
    include_hard_management_references=False)
while pending:
    package = pending.pop()
    if package in seen or not package.startswith("/Game/"):
        continue
    seen.add(package)
    pending.extend(str(p) for p in registry.get_dependencies(package, options))
clips = []
for package in seeds[:-1]:
    asset = unreal.load_asset(package)
    clips.append({"package": package, "class": asset.get_class().get_name(),
                  "duration": asset.get_editor_property("sequence_length"),
                  "skeleton": asset.get_editor_property("skeleton").get_path_name()})
result = {"project": unreal.Paths.project_dir(), "clips": clips,
          "packages": sorted(seen)}
out = pathlib.Path(unreal.Paths.project_dir()) / "Saved/Diagnostics/SpecialAttacks/assets.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"clips": clips, "dependency_count": len(seen)}))
