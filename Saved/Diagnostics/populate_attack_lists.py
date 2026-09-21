import unreal, pathlib, shutil, datetime, json
asset='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
bp=unreal.load_asset(asset)
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE active; no edit performed'
root=pathlib.Path(unreal.Paths.project_dir())
backup=root/'Saved/Diagnostics/AttackLists'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True,exist_ok=True)
shutil.copy2(root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset', backup/'Before.uasset')
melee=['jabL','jabR','hookL','hookR','overL','overR','headbutt','kickL','kickR']
slashes=['slashL','slashR','slashLD','slashRD','slashLU','slashRU','pike']
expected={'attack list':melee+slashes,'melee list':melee,'slash list':slashes}
runtime=json.loads((root/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text())
assert {n.lower() for n in expected['attack list']} == set(runtime['post_hit_tail_steps'])
cdo=unreal.get_default_object(bp.generated_class())
for name,values in expected.items():
    cdo.set_editor_property(name,[unreal.Name(x) for x in values])
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
cdo=unreal.get_default_object(bp.generated_class())
actual={name:[str(x) for x in cdo.get_editor_property(name)] for name in expected}
for name,values in expected.items():
    assert [s.lower() for s in actual[name]] == [s.lower() for s in values], (name,actual[name])
assert unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), 'Blueprint save failed'
(backup/'result.json').write_text(json.dumps(actual,indent=2))
print('SAVED_ATTACK_LISTS',json.dumps(actual))
print('BACKUP',str(backup))
