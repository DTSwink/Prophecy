import pathlib,time,unreal
diagnostic_root=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/FramePacing'
diagnostic_root.mkdir(parents=True,exist_ok=True)
trace_directory=pathlib.Path('C:/Users/singerie/.codex/tmp-jolt-trace')
trace_directory.mkdir(parents=True,exist_ok=True)
trace_path=trace_directory/('runtime-'+time.strftime('%H%M%S')+'.utrace')
editor_world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(editor_world,'Trace.File '+trace_path.as_posix()+' cpu,frame,gpu,bookmark,log,task,threadidlescope')
exec((pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/CameraRelativeHitch/capture.py').read_text(),globals())
state['trace_path']=str(trace_path)
state['path']=str(diagnostic_root/('capture-'+time.strftime('%H%M%S')+'.json'))
original_finish=finish
def finish(reason):
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() or editor_world
    unreal.SystemLibrary.execute_console_command(world,'Trace.Stop')
    original_finish(reason)
state['finish']=finish
print('TRACE_AND_MOVEMENT_CAPTURE',state['path'],str(trace_path))
