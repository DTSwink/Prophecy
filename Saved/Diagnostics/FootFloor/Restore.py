import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for suffix in ('BounceThresholdCm','SpeculativeDistanceCm','PenetrationSlopCm'):
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Jolt.Diagnostic.'+suffix+' -1')
print('FOOT_DIAGNOSTICS_RESET; ACTIVE_PLAY_WORLD='+str(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()))
print('DIRTY_CONTENT='+str([x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]))
print('DIRTY_MAPS='+str([x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]))
