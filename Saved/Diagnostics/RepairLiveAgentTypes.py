import unreal, sys
mode = sys.argv[1] if len(sys.argv)>1 else 'Inspect'
assert mode in ('Inspect','Repair')
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert mode != 'Repair' or not ed.get_game_world(), 'Preserve active Play session'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes '+mode)
print('Live agent type check: '+mode)
