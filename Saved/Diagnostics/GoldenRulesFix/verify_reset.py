import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'User Play active; defer final checks'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Agent.Fists.TickTiming+Prophecy.Agent.ModeTransitions.TickRetirement')
print('GOLDEN_RULES_FINAL_RESET_CHECKS')
