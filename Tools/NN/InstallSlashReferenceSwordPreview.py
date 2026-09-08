"""Editor-only preview changes: fixed forearms + existing hand-attached sword."""
import json
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
data=json.loads((root/'Saved/SlashChain/sword_preview.json').read_text())
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
assert editor.get_editor_world().get_path_name()=='/Game/testNN.testNN'
had_dirty_map=bool(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
save_user_edits=bool(globals().get('save_user_edits',False))
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
reference=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='SlashChain30_Reference_Looping')
mesh=reference.get_component_by_class(unreal.SkeletalMeshComponent)
destination='/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_ForearmClamped'
animation=unreal.load_asset(destination) if unreal.EditorAssetLibrary.does_asset_exist(destination) else unreal.EditorAssetLibrary.duplicate_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference',destination)
assert animation
assert unreal.EditorAssetLibrary.get_metadata_tag(animation,'SourceSHA256') in ('',data['source_sha256'])
unreal.EditorAssetLibrary.set_metadata_tag(animation,'SourceSHA256',data['source_sha256'])
ctl=animation.controller
ctl.open_bracket('Fix preview forearm lengths',False)
try:
    for track in data['tracks']:
        if track['name'] not in ('hand_l','hand_r'): continue
        assert ctl.set_bone_track_keys(track['name'],[unreal.Vector(*v) for v in track['positions']],
            [unreal.Quat(*q) for q in track['rotations']],[unreal.Vector(1,1,1)]*456,False)
finally: ctl.close_bracket(False)
unreal.EditorAssetLibrary.set_metadata_tag(animation,'PresentationOnly','Both forearm lengths fixed to skeleton rest length; NN/source untouched')
mesh.override_animation_data(animation,True,True,0.,1.)
sword=next((a for a in actors.get_all_level_actors() if a.get_actor_label()=='SlashChain30_Sword'),None)
if sword is None: sword=actors.spawn_actor_from_class(unreal.StaticMeshActor,reference.get_actor_location())
sword.set_actor_label('SlashChain30_Sword')
component=sword.get_component_by_class(unreal.StaticMeshComponent)
component.set_mobility(unreal.ComponentMobility.MOVABLE)
component.set_static_mesh(unreal.load_asset(data['sword']['mesh']))
component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
component.set_editor_property('generate_overlap_events',False)
assert component.attach_to_component(mesh,data['sword']['bone'],unreal.AttachmentRule.KEEP_RELATIVE,
    unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
grip=data['sword']
component.set_relative_transform(unreal.Transform(location=unreal.Vector(*grip['location_cm']),
    rotation=unreal.Quat(*grip['quaternion_xyzw']).rotator(),scale=unreal.Vector(*grip['scale'])),False,True)
assert unreal.EditorAssetLibrary.save_loaded_asset(animation,only_if_is_dirty=True)
if not had_dirty_map or save_user_edits:
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
print(json.dumps({'reference':reference.get_actor_label(),'animation':destination,'sword':sword.get_actor_label(),
                  'attached_bone':str(component.get_attach_socket_name()),'grip':str(component.get_relative_transform()),'map_saved':not had_dirty_map or save_user_edits,
                  'dirty_assets_preserved':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))
