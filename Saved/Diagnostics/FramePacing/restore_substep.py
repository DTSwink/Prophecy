import builtins,json,pathlib,unreal
state=getattr(builtins,'_prophecy_camera_relative_hitch',None)
if state and state.get('handle'): state['finish']('Stopped for requested substep restoration')
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
settings=unreal.get_default_object(unreal.PhysicsSettings)
settings.set_editor_property('max_substep_delta_time',0.016667)
result={'max_substep_delta_time':settings.get_editor_property('max_substep_delta_time'),
    'substepping':settings.get_editor_property('substepping'),'max_substeps':settings.get_editor_property('max_substeps')}
(pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/FramePacing/restored-settings.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
