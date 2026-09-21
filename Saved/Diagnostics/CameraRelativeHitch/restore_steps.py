import builtins,unreal
key='_prophecy_short_step_original'
original=getattr(builtins,key)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.get_default_object(unreal.PhysicsSettings).set_editor_property('max_substep_delta_time',original)
delattr(builtins,key)
print('Restored maximum substep',original)
