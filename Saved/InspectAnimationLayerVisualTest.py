import unreal


level_path = "/Game/testNN"
unreal.EditorLevelLibrary.load_level(level_path)

registry = unreal.AssetRegistryHelpers.get_asset_registry()
anim_class = unreal.TopLevelAssetPath("/Script/Engine", "AnimSequence")
animations = []
for asset in registry.get_assets_by_class(anim_class, True):
    name = str(asset.asset_name)
    if "M_Neutral" in name and ("Walk" in name or "Run" in name):
        animations.append((name, str(asset.package_name)))

actors = []
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    class_name = actor.get_class().get_name()
    if "Prophecy" in class_name or "PoseAgent" in class_name:
        actors.append((actor.get_name(), class_name, actor.get_path_name()))

print("VISUAL_TEST_LEVEL", unreal.EditorLevelLibrary.get_editor_world().get_path_name())
print("VISUAL_TEST_ACTORS", actors)
print("VISUAL_TEST_ANIMATIONS", animations[:40])
