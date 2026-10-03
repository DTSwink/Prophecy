import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_path(
    "/Game/Characters/UEFN_Mannequin/Animations", recursive=True
)
rows = []
for asset in assets:
    if str(asset.asset_class_path.asset_name) != "AnimSequence":
        continue
    rows.append(str(asset.package_name))
rows.sort()
print("ANIM_COUNT|{}".format(len(rows)))
for row in rows:
    print("ANIM|" + row)
