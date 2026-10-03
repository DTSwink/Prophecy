import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world,
    "obj dump /Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.Default__BP_ProphecyManualPoseAgent_C")
print("MANUAL_FOLLOW_CDO_DUMP_REQUESTED")
