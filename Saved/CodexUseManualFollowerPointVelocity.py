import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world, "prophecy.Editor.UseManualFollowerBonePointVelocity")
print("MANUAL_FOLLOW_POINT_VELOCITY_REQUESTED")
