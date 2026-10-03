import unreal, pathlib, shutil, json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
world=ed.get_editor_world()
assert world.get_path_name()=='/Game/testNN.testNN'
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor_class=unreal.load_class(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C')
assert actor_class
assert not unreal.GameplayStatics.get_all_actors_of_class(world,actor_class), 'Characters already present; do not duplicate'
saved=pathlib.Path(unreal.Paths.project_saved_dir())
backup=saved/'Diagnostics/MissingCharacters-20261002'
backup.mkdir(exist_ok=True)
source=saved/'Autosaves/Game/testNN_Auto6.umap'
shutil.copy2(source,backup/source.name)
package=unreal.load_package(source.as_posix())
assert package, source.as_posix()
source_world=unreal.find_object(package,'testNN_Auto6')
assert source_world, str(package)
actors=list(unreal.GameplayStatics.get_all_actors_of_class(source_world,actor_class))
assert len(actors)==3, str(actors)
existing={a.get_path_name():str(a.get_actor_transform()) for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)}
selected=list(sub.get_selected_level_actors())
with unreal.ScopedEditorTransaction('Restore three missing testNN characters from autosave'):
    restored=list(sub.duplicate_actors(actors,world,unreal.Vector()))
    assert len(restored)==3, str(restored)
    for src,dst in zip(actors,restored):
        assert dst.get_world()==world
        assert str(src.get_actor_transform())==str(dst.get_actor_transform())
        dst.set_actor_label(src.get_actor_label())
        print('RESTORED',dst.get_path_name(),dst.get_actor_label(),str(dst.get_actor_transform()))
sub.set_selected_level_actors(selected)
after={a.get_path_name():str(a.get_actor_transform()) for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)}
assert all(after.get(k)==v for k,v in existing.items()), 'Existing scene actors changed'
report={'source':str(source),'restored':[a.get_path_name() for a in restored],'existing_scene_preserved':True,'explicit_asset_save':False}
(backup/'restored.json').write_text(json.dumps(report,indent=2))
print('THREE_CHARACTERS_RESTORED_EXISTING_SCENE_PRESERVED_NO_SAVE')
