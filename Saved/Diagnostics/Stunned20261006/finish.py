import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Stunned20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Leave active user Play untouched'
w=ed.get_editor_world()
assert w.get_path_name().startswith('/Game/testNN'),w.get_path_name()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
d={'world':w.get_path_name(),'play':False,'blueprint':r,'dirty_content':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'dirty_maps':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'editor_modes':{a.get_actor_label():unreal.ProphecyPhysicalProfileLibrary.get_magnetization_mode(a) for a in actors}}
(p/'final-state.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
