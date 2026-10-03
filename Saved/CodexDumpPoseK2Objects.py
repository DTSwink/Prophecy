import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
base = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent:EventGraph.K2Node_VariableGet_"
for index in range(24):
    unreal.SystemLibrary.execute_console_command(world, "obj dump " + base + str(index))
print("POSE_K2_OBJECT_LIST_REQUESTED")
