import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('ATTACK_PERFORMANCE_FINAL',dict(play_active=bool(ed.get_game_world()),optimization=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Attack.SkipOverwrittenLocomotion'),maxfps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')))
