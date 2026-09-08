"""Execute the Boss import script in a running Prophecy Unreal Editor."""

import sys
import time
from pathlib import Path


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)
import remote_execution


SCRIPT = Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Tools\MetaHuman\import_boss_uefn_to_unreal.py"
)


def main():
    code = SCRIPT.read_text(encoding="utf-8")
    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + 180.0
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.25)
        if not remote.remote_nodes:
            raise RuntimeError("No running Unreal Editor remote node discovered")
        node = remote.remote_nodes[0]
        remote.open_command_connection(node["node_id"])
        result = remote.run_command(
            code,
            unattended=True,
            exec_mode=remote_execution.MODE_EXEC_FILE,
        )
        output = "".join(
            entry.get("output", "") for entry in result.get("output", [])
        )
        print(output.strip())
        if not result.get("success"):
            raise RuntimeError(result.get("result", "Remote execution failed"))
    finally:
        remote.stop()


if __name__ == "__main__":
    main()
