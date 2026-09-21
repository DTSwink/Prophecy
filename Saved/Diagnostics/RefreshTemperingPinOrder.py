import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshTemperingPinOrder')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.LowerTempering.SeparateReturns+Prophecy.NN.AgentReset.PhysicalBaseline+Prophecy.Blends.SixtyTickClock')
print('Refreshed tempering pin order and started focused compatibility checks; Blueprint remains unsaved.')
