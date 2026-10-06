import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Stunned20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
for name in ['start_stunned','disable_stunned','is_stunned','on_stunned_ended']:
 assert hasattr(unreal.ProphecyAgent,name),name
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
(p/'reflection.json').write_text(json.dumps({'world':ed.get_editor_world().get_path_name(),'blueprint':r},indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Agent.Stunned+Prophecy.Blends.SixtyTickClock+Prophecy.NN.AgentReset.PhysicalBaseline')
print('STUN_REFLECTION_VERIFIED_TESTS_REQUESTED')
