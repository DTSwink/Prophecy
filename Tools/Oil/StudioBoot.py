import unreal as u,runpy
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
u.EditorPythonScripting.set_keep_python_script_alive(True)
w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
for cmd in ['t.MaxFPS 24','r.MotionBlurQuality 0','r.RefractionQuality 2']:u.SystemLibrary.execute_console_command(w,cmd)
runpy.run_path(str(Path(u.Paths.project_dir()).resolve()/'Tools/Oil/StudioPhoto.py'))
