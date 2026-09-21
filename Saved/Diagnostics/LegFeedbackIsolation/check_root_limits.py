import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Run the focused checks outside PIE'
checks={}
for name,method,args,getter in [
 ('ProphecyRootPelvisBoundsLibrary','SetRootPelvisBounds',(None,True,20.0,None),'GetRootPelvisBounds'),
 ('ProphecyRootSpeedLimitsLibrary','SetRootVelocityLimits',(None,1000000.0,1000000.0,True),'GetRootVelocityLimits')]:
 cls=unreal.load_class(None,'/Script/GameAnimationSample3.'+name)
 assert cls,name+' missing'
 api=unreal.get_default_object(cls)
 assert not api.call_method(method,args), 'Null agent accepted'
 checks[name]=str(api.call_method(getter,(None,)))
print('ROOT_LIMITS_REFLECTED',json.dumps(checks))
assert '1000000' in checks['ProphecyRootSpeedLimitsLibrary']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
 'Automation RunTests Prophecy.Root.PelvisBounds.PlanarCircle+Prophecy.Root.VelocityLimits.CombinedWindow')
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/root_limits_reflected.json').write_text(json.dumps(checks))
