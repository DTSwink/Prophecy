import unreal,pathlib,json,shutil,time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'PIE running; leave user session alone'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp,'Random Stream debug',True)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
cls=bp.generated_class();cdo=unreal.get_default_object(cls)
key='Random Stream debug';seed=cdo.get_editor_property(key).initial_seed
actors=list(unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),cls))
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RandomStreamSeed';folder.mkdir(parents=True,exist_ok=True)
backup=folder/time.strftime('%Y%m%d-%H%M%S');backup.mkdir(exist_ok=True)
root=pathlib.Path(unreal.Paths.project_dir())
shutil.copy2(root/'Content/testNN.umap',backup/'BeforeInstanceSeedFix.umap')
rows=[]
with unreal.ScopedEditorTransaction('Reset debug random streams to Blueprint default'):
 for a in actors:
  rows.append(dict(actor=a.get_path_name(),before=a.get_editor_property(key).initial_seed,after=seed))
  a.modify();a.set_editor_property(key,unreal.RandomStream(initial_seed=seed))
# Test the normal class-default propagation, then restore the user's value.
try:
 cdo.set_editor_property(key,unreal.RandomStream(initial_seed=seed+1))
 propagated=[a.get_editor_property(key).initial_seed for a in actors]
 assert propagated==[seed+1]*len(actors),propagated
finally:
 cdo.set_editor_property(key,unreal.RandomStream(initial_seed=seed))
assert all(a.get_editor_property(key).initial_seed==seed for a in actors)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
report=dict(seed=seed,actors=rows,temporary_class_seed=seed+1,propagated=propagated,restored=seed,backup=str(backup))
(folder/'fix.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))

