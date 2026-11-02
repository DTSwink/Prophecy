import os,pathlib,json,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Spear.Install')
audit=(out/'SpearSetup.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in audit and 'hulls=17' in audit and 'triangles=43494' in audit,audit[:400]
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear');cdo=unreal.get_default_object(bp.generated_class())
result={k:str(cdo.get_editor_property(k)) for k in ('blade length','hilt half length','blade half width','Pike Target Thickness Cm','tags','Optimised','debug mode','freeze tick','active','impulse cut threshold')}
assert cdo.get_editor_property('Pike Target Thickness Cm')==15
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
(out/'defaults.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Spear')
