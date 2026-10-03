import os

import unreal

EXPORT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "BlenderExchange")
os.makedirs(EXPORT_DIR, exist_ok=True)

MESHES = [
    ("/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh", "Body_MH342.fbx"),
    ("/Game/MetaHumans/test_UEFNExactFull/Face/SKM_test_UEFNFit_FaceMesh", "Face_MH.fbx"),
    ("/Game/_mygame/SKM_UEFN_Mannequin", "UEFN_Mannequin.fbx"),
]

ANIMS = [
    ("/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot", "Anim_Climb.fbx"),
    ("/Game/Characters/UEFN_Mannequin/Animations/Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand", "Anim_CliffCatch.fbx"),
    ("/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20", "Anim_Sprint.fbx"),
    ("/Game/Characters/UEFN_Mannequin/Animations/Slide/M_Neutral_Slide_KneesOut_Loop", "Anim_Slide.fbx"),
    ("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop", "Anim_Idle.fbx"),
]


def export_fbx(asset_path, filename, is_anim):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError("Missing asset: " + asset_path)
    options = unreal.FbxExportOption()
    options.set_editor_property("ascii", False)
    options.set_editor_property("collision", False)
    options.set_editor_property("level_of_detail", False)
    options.set_editor_property("export_morph_targets", False)
    options.set_editor_property("vertex_color", False)
    options.set_editor_property("force_front_x_axis", False)
    if is_anim:
        options.set_editor_property("export_preview_mesh", False)
        options.set_editor_property("map_skeletal_motion_to_root", False)
        options.set_editor_property("export_local_time", True)

    task = unreal.AssetExportTask()
    task.set_editor_property("object", asset)
    task.set_editor_property("filename", os.path.join(EXPORT_DIR, filename))
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("options", options)

    ok = unreal.Exporter.run_asset_export_task(task)
    errors = list(task.get_editor_property("errors"))
    size = -1
    out_path = os.path.join(EXPORT_DIR, filename)
    if os.path.isfile(out_path):
        size = os.path.getsize(out_path)
    print("EXPORT|{}|{}|ok={}|bytes={}|errors={}".format(asset_path, filename, ok, size, errors))
    if not ok or size <= 0:
        raise RuntimeError("Export failed for " + asset_path)


for path, name in MESHES:
    export_fbx(path, name, is_anim=False)
for path, name in ANIMS:
    export_fbx(path, name, is_anim=True)

print("EXPORT_ALL_DONE|" + EXPORT_DIR)
