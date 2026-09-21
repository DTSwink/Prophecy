import builtins, unreal
if hasattr(builtins,'_pelvis_build_fps'):
    unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),
        't.MaxFPS '+str(builtins._pelvis_build_fps))
    print('Restored t.MaxFPS',builtins._pelvis_build_fps)
    del builtins._pelvis_build_fps
