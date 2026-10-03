import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
base = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent:EventGraph."
for prefix, count in (("K2Node_PromotableOperator_", 8), ("K2Node_CallFunction_", 33), ("K2Node_MacroInstance_", 4)):
    for index in range(count):
        unreal.SystemLibrary.execute_console_command(
            world, "obj dump " + base + prefix + str(index))
print("POSE_OPERATOR_DUMPS_REQUESTED")
