import unreal,pathlib
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(),'Preserve user Play'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'Prophecy.RootTranslation.CachedPoseRebase')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'Prophecy.SlashTraceFrames')
print((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig'))
print('No asset saved. No Play session remains.')
