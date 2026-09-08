"""Run through the editor bridge. Adds ONLY the user's requested reference.

Uses UE's native animation asset/player, not an extra NN or Python tick.
Existing user actors and dirty Blueprint packages are never saved or modified.
"""
import json
import math
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
HANDOFF = Path(r"C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260907_good_pt_continuous_random_30_hits_unreal_handoff")
ASSET = "/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference"
LABEL = "SlashChain30_Reference_Looping"

def install():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor.get_game_world() is None, "End PIE before installing the saved reference"
    assert editor.get_editor_world().get_path_name() == "/Game/testNN.testNN"
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), "Do not save unrelated level edits"
    assert not (ROOT / 'Content/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference.uasset').exists(), "Reference already saved; do not overwrite"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert not any(a.get_actor_label() == LABEL for a in actors.get_all_level_actors())
    data = json.loads((ROOT / "Saved/SlashChain/animation_tracks.json").read_text())
    mesh = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin")
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property("target_skeleton", mesh.get_editor_property("skeleton"))
    factory.set_editor_property("preview_skeletal_mesh", mesh)
    package, name = ASSET.rsplit("/", 1)
    sequence = unreal.load_asset(ASSET) if unreal.EditorAssetLibrary.does_asset_exist(ASSET) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, package, unreal.AnimSequence, factory)
    assert sequence
    ctl = sequence.get_editor_property("controller")
    ctl.open_bracket("Import immutable 30-hit reference", False)
    try:
        ctl.set_frame_rate(unreal.FrameRate(30, 1), False)
        # Duplicate the last pose for the final 1/30 s, then reset at loop seam.
        # No invented transition between the final attack and the conditioning pose.
        ctl.set_number_of_frames(unreal.FrameNumber(455), False)
        for track in data["tracks"]:
            ctl.add_bone_curve(track["name"], False)
            positions = [unreal.Vector(*v) for v in track["positions"]]
            rotations = [unreal.Quat(*v) for v in track["rotations"]]
            assert ctl.set_bone_track_keys(track["name"],positions,rotations,[unreal.Vector(1,1,1)]*456,False)
    finally:
        ctl.close_bracket(False)
    sequence.set_editor_property("enable_root_motion", False)
    sequence.set_editor_property("force_root_lock", False)
    unreal.EditorAssetLibrary.set_metadata_tag(sequence,"SourceSHA256",data["source_sha256"])
    unreal.EditorAssetLibrary.set_metadata_tag(sequence,"Source",str(HANDOFF / "continuous_random_30_hits.npz"))
    actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(450,-385,0))
    actor.set_actor_label(LABEL)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_editor_property("disable_post_process_blueprint", True)
    component.override_animation_data(sequence,True,True,0.,1.)
    unreal.EditorAssetLibrary.save_loaded_asset(sequence,only_if_is_dirty=True)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print(json.dumps({"actor":actor.get_path_name(),"animation":ASSET,"duration_seconds":455/30,
        "looping":True,"dirty_assets_preserved":[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))

install()
