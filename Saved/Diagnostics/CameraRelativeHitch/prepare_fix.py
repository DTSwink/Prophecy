import json,pathlib,unreal
settings=unreal.get_default_object(unreal.PhysicsSettings)
values={}
for name in ('substepping','max_substep_delta_time','max_substeps'):
    values[name]=settings.get_editor_property(name)
root=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/CameraRelativeHitch'
(root/'physics-settings.json').write_text(json.dumps(values,indent=2))
print(json.dumps(values))
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
