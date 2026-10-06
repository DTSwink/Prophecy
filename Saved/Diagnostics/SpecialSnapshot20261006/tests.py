import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Leave user Play untouched'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Agent.PhysicalContext+Prophecy.PhysicalProfiles.ClampSnapshots+Prophecy.NN.SpecialRecovery+Prophecy.NN.AgentReset.PhysicalBaseline')
print('SPECIAL_SNAPSHOT_TESTS_REQUESTED')
