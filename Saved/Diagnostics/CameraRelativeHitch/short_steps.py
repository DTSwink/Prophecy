import builtins,unreal
key='_prophecy_short_step_original'
assert not hasattr(builtins,key)
settings=unreal.get_default_object(unreal.PhysicsSettings)
setattr(builtins,key,settings.get_editor_property('max_substep_delta_time'))
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
settings.set_editor_property('max_substep_delta_time',0.01)
print('Temporary unsaved 10 ms maximum substep; original retained for restoration')
