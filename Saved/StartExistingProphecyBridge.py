import os
import runpy

import unreal


bridge_path = os.path.join(
    unreal.Paths.project_dir(),
    "Tools",
    "ProphecyEditorBridge.py",
)
runpy.run_path(bridge_path, run_name="__main__")
