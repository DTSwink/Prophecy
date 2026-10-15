"""Dedicated recorded-physics comparison map; preserves the user's current map."""
import unreal,json,shutil,hashlib,time
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve();out=root/'Saved/MimicKitTransfer/no-armature-3913'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None,'User Play is active'
MAP='/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure'
assert not unreal.EditorAssetLibrary.does_asset_exist(MAP),'Do not overwrite an existing map'
old_world=editor.get_editor_world();old_name=old_world.get_path_name()
old_camera=unreal.EditorLevelLibrary.get_level_viewport_camera_info()
dirty_content=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
preservation=dict(previous_map=old_name,dirty_content=dirty_content)
if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
    assert old_name=='/Game/testNN.testNN','Unexpected dirty map: stop before changing it'
    backup=out/'before-failure-map';backup.mkdir(exist_ok=True)
    for ext in ('.umap','.uexp','.ubulk'):
        src=root/f'Content/testNN{ext}'
        if src.exists():
            dst=backup/src.name
            assert not dst.exists(),'Preservation backup already exists'
            shutil.copy2(src,dst)
    preservation['prior_disk_sha256']=hashlib.sha256((root/'Content/testNN.umap').read_bytes()).hexdigest()
    assert levels.save_current_level(),'Failed to preserve current map'
    preservation['saved_current_edits_sha256']=hashlib.sha256((root/'Content/testNN.umap').read_bytes()).hexdigest()
(out/'failure-map-preservation.json').write_text(json.dumps(preservation,indent=2))
assert levels.new_level(MAP)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,0,-5))
floor.set_actor_label('Replay floor (visual only)')
c=floor.static_mesh_component;c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
floor.set_actor_scale3d(unreal.Vector(16,12,.1))
c.set_material(0,unreal.load_asset('/Engine/EngineMaterials/WorldGridMaterial'))
light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,500),unreal.Rotator(pitch=-45,yaw=-65,roll=0))
light.light_component.set_editor_property('intensity',4.)
light.light_component.set_editor_property('mobility',unreal.ComponentMobility.MOVABLE)
sky=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,300))
sky.light_component.set_editor_property('mobility',unreal.ComponentMobility.MOVABLE)
sky.light_component.set_editor_property('intensity',1.)
for x,tag,label in [(-155,'JoltFailure','JOLT | failure after 0.63 s'),(155,'NewtonCompare','TRAINING SIMULATOR | same policy')]:
    actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(x,0,0))
    actor.set_actor_label(label)
    c=actor.skeletal_mesh_component;c.set_skeletal_mesh_asset(mesh)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    c.set_editor_property('disable_post_process_blueprint',True)
    c.set_forced_lod(1)
    c.override_animation_data(unreal.load_asset(f'/Game/_mygame/Tests/MimicKitTransfer/AS_{tag}_3913'),True,True,0.,.25)
    c.set_update_animation_in_editor(True)
    text=actors.spawn_actor_from_class(unreal.TextRenderActor,unreal.Vector(x,20,200),unreal.Rotator(pitch=0,yaw=-90,roll=0))
    text.set_actor_label(label+' - label');t=text.text_render
    t.set_text(label);t.set_world_size(12);t.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    t.set_text_render_color(unreal.Color(255,110,80,255) if x<0 else unreal.Color(100,230,255,255))
caption=actors.spawn_actor_from_class(unreal.TextRenderActor,unreal.Vector(0,20,230),unreal.Rotator(pitch=0,yaw=-90,roll=0))
caption.text_render.set_text('RECORDED PHYSICS - 0.25x - XY centered\n4 seconds, looping | not live Unreal physics')
caption.text_render.set_world_size(12);caption.text_render.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
position=unreal.Vector(90,-720,300);rotation=unreal.MathLibrary.find_look_at_rotation(position,unreal.Vector(0,0,110))
camera=actors.spawn_actor_from_class(unreal.CameraActor,position,rotation)
camera.set_actor_label('Comparison camera');camera.camera_component.set_field_of_view(52)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(position,rotation)
levels.pilot_level_actor(camera)
actors.set_selected_level_actors([])
assert levels.save_current_level()
assert sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())==sorted(dirty_content)
receipt=dict(map=MAP,previous_map=old_name,actors=len(actors.get_all_level_actors()),playback_rate=.25,
             previous_camera=str(old_camera),recorded_physics=True,live_policy=False,
             dirty_content_preserved=dirty_content)
(out/'failure-map-created.json').write_text(json.dumps(receipt,indent=2))
# Close only the preview tabs created by this task, exposing the dedicated map.
assetedit=unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
for name in ('AS_Rig15_Newton_3913','AS_Rig15_Jolt_3913'):
    assetedit.close_all_editors_for_asset(unreal.load_asset('/Game/_mygame/Tests/MimicKitTransfer/'+name))
print(json.dumps(receipt,indent=2))
