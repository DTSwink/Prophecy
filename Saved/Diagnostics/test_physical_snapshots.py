import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('SNAPSHOT_TEST_PIE_PRESERVED', bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.Agent.PhysicalContext.SelectionAndAttacks+Prophecy.Agent.PhysicalBlends.RuntimeAndBatch')
