import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('GOLDEN_RULES_EDITOR_STATE',bool(ed.get_game_world()))
print('DOUBLE_REACH_INSTANCES',[o.get_path_name() for o in unreal.ObjectIterator(unreal.ProphecyDoubleReachAnimInstance) if not o.get_name().startswith('Default__')])
