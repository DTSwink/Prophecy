import unreal,builtins,gc,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Do not interrupt user Play'
w=ed.get_editor_world()
for cmd in ('Prophecy.Tempering.SupportSource 1','Prophecy.Tempering.KneePlane 1',
            'Prophecy.Tempering.ConnectedSources 0','Prophecy.Tempering.GeometryTrace 0',
            'Prophecy.Editor.LiveAgentTypes Inspect'):
    unreal.SystemLibrary.execute_console_command(w,cmd)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RecoveryKnee-final-verification.json'
assert p.exists()
s=getattr(builtins,'_calf_connection',None)
if isinstance(s,dict):
    print('RELEASED_KNEE_CAPTURE',len(s.get('rows',[])))
    s.get('rows',[]).clear()
gc.collect()
print('RECOVERY_KNEE_FINISHED',ed.get_editor_world().get_path_name())
