import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairAttackCheckpointEnum')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'))
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
print('ATTACK_CHECKPOINT_CHOICES',list(unreal.ProphecyAttackCheckpoint))
