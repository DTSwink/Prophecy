import unreal, pathlib, shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
audit=root/'SwordThigh/BlueprintGraph.txt'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copyfile(audit, root/'KickTemperingReturn-before.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.RepairKickTemperingReturns')
shutil.copyfile(audit, root/'KickTemperingReturn-after.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.NN.LowerTempering.KickProfiles+Prophecy.NN.LowerTempering.FootRoles+Prophecy.NN.LowerTempering.SeparateReturns')
print('KICK_TEMPERING_RETURN_REPAIR_REQUESTED_NO_SAVE')
