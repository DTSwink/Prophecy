import builtins,unreal
key='_prophecy_short_step_original'
assert hasattr(builtins,key)
settings=unreal.get_default_object(unreal.PhysicsSettings)
assert abs(settings.get_editor_property('max_substep_delta_time')-.01)<1.e-8
delattr(builtins,key)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
print('Keeping verified 10 ms maximum substep; persisted in Config/DefaultEngine.ini')
