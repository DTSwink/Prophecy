import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_editor_world()
if not ed.get_game_world():
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'))
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets')
print('SPECIAL_FOREARM_CHECKS_QUEUED')
