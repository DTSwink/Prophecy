import unreal, pathlib, shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
audit=root/'SwordThigh/BlueprintGraph.txt'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copyfile(audit,root/'SeparateKickTempering-before.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SeparateKickTemperingReturns')
shutil.copyfile(audit,root/'SeparateKickTempering-after.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.NN.LowerTempering.SeparatedKickReturns+Prophecy.NN.LowerTempering.KickProfiles+Prophecy.NN.LowerTempering.FootRoles+Prophecy.NN.LowerTempering.SeparateReturns+Prophecy.NN.LowerTempering.ReturnTimeline')
print('SEPARATE_KICK_TEMPERING_REQUESTED_NO_SAVE')
