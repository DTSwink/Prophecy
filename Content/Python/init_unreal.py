import os
import runpy

import unreal

import prophecy_node_labels

prophecy_node_labels.apply()


if os.environ.get("PROPHECY_EDITOR_BRIDGE", "0") == "1":
    bridge_path = os.path.join(unreal.Paths.project_dir(), "Tools", "ProphecyEditorBridge.py")
    runpy.run_path(bridge_path, run_name="__main__")

