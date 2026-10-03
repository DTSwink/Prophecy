import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
d=dict(play_active=w is not None,native_geometry=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Attack.NativeGeometry'))
if w is None:d['map']=ed.get_editor_world().get_path_name()
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackPerformance20261002/final-editor.json').write_text(json.dumps(d,indent=2),encoding='utf8')
print('ATTACK_FAST_FINAL',d)
