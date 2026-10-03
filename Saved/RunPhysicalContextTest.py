import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),
    'Automation RunTests Prophecy.Agent.PhysicalContext.SelectionAndAttacks')
print('Requested the short physical-context regression')
