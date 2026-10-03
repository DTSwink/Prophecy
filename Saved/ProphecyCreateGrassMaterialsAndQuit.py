import os

import unreal


script_path = os.path.join(unreal.Paths.project_saved_dir(), "ProphecyCreateGrassMaterials.py")
with open(script_path, "r", encoding="utf-8") as handle:
    code = compile(handle.read(), script_path, "exec")
exec(code, {"__name__": "__main__"})

unreal.SystemLibrary.quit_editor()

