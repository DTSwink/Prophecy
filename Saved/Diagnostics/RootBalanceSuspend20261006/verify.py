import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
assert lib.call_method('IsRootSelfBalancingSuspended',(None,)) is False
assert lib.call_method('SuspendRootSelfBalancing',(None,1.0)) is False
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootBalanceSuspend20261006'
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
(p/'verification.json').write_text(json.dumps({'nodes_callable':True,'blueprint':r},indent=2));print(r)
