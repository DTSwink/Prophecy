import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_editor_world()
for cmd in ['Prophecy.PhysicalFoot.RecoveryLength 1','Prophecy.PhysicalFoot.TraceFrames 0','Prophecy.NNInputTraceFrames 0','Prophecy.Editor.LiveAgentTypes Inspect']:
 unreal.SystemLibrary.execute_console_command(w,cmd)
print('SIM_FOOT_FINISHED PIE',bool(ed.get_game_world()))
