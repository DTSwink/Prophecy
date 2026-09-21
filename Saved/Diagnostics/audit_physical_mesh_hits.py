import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
rows=[]
def read(obj,name):
    try:return str(obj.get_editor_property(name))
    except:return None
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    meshes=[]
    for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
        meshes.append(dict(name=m.get_name(),collision=str(m.get_collision_enabled()),profile=str(m.get_collision_profile_name()),object_type=str(m.get_collision_object_type()),notify=read(m.get_editor_property('body_instance'),'notify_rigid_body_collision'),physics_body=str(m.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY)),pawn=str(m.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)),sim=m.is_any_simulating_physics()))
    rows.append(dict(name=a.get_name(),mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),notify=read(a,'generate_physical_hit_events'),demo=read(a,'CombatDemoEnabled'),dodge=read(a,'CombatDemoUseDodge'),meshes=meshes))
out=dict(pie=bool(ed.get_game_world()),agents=rows)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PhysicalMeshHits';p.mkdir(parents=True,exist_ok=True)
(p/'audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
t=unreal.AssetExportTask();t.object=bp;t.filename=str(p/'CurrentBP.copy');t.automated=True;t.prompt=False;t.replace_identical=True
print('BP export',unreal.Exporter.run_asset_export_task(t))

