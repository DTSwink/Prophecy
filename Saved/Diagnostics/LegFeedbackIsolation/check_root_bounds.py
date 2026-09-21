import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPelvisBoundsLibrary')
assert cls,'Root pelvis bounds class missing from loaded patch'
api=unreal.get_default_object(cls)
r=api.call_method('SetRootPelvisBounds',(None,True,20.0,None))
assert not r,'Null agent must be rejected'
config=api.call_method('GetRootPelvisBounds',(None,))
print('ROOT_PELVIS_BOUNDS_REFLECTED',str(cls),str(config))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Root.PelvisBounds.PlanarCircle')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/root_bounds_reflected.json'
p.write_text(json.dumps({'class':str(cls),'null_set_rejected':not r,'default_config':str(config),'pie_active':bool(ed.get_game_world())}))
