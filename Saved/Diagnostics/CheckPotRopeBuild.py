import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
world=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
for path in ['/Game/_mygame/sword/A_Pot','/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent']:
 bp=unreal.load_asset(path)
 unreal.BlueprintEditorLibrary.compile_blueprint(bp)
 print('COMPILED',path)
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Jolt.Pose.+Prophecy.Jolt.RigWorld.KinematicAnchor+Prophecy.Jolt.Constraints.StandardComponents')
