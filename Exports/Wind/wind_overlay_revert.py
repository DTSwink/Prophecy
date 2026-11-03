"""Undo wind_overlay.py: put the forest's material instances back on their original masters (the _Wind duplicates stay)."""
import os, json
import unreal
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
path = os.path.join(unreal.Paths.project_saved_dir(), "WindTest", "overlay_revert.json")
revert = json.load(open(path))
for mi_path, parent_path in revert.items():
    mi = unreal.load_asset(mi_path)
    parent = unreal.load_asset(parent_path.split(".")[0])
    if mi and parent:
        MEL.set_material_instance_parent(mi, parent)
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi, only_if_is_dirty=False)
        unreal.log("WINDREVERT %s -> %s" % (mi_path, parent_path))
