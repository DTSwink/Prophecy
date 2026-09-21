import pathlib
import sys
import time


REMOTE_EXECUTION_PATH = (
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
sys.path.insert(0, REMOTE_EXECUTION_PATH)

import remote_execution


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: RunUnrealRemote.py <unreal-python-file> [arguments ...]")

    remote_argv = [sys.argv[1], *sys.argv[2:]]
    code = "import sys\nsys.argv = " + repr(remote_argv) + "\n" + pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + 15.0
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.25)
        if not remote.remote_nodes:
            raise RuntimeError("No Unreal remote-execution node was discovered")
        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        result = remote.run_command(
            code,
            unattended=True,
            exec_mode=remote_execution.MODE_EXEC_FILE,
        )
        for entry in result.get("output", []):
            print(entry.get("output", ""))
        if not result.get("success"):
            raise RuntimeError(result.get("result", "Remote execution failed"))
    finally:
        remote.stop()


if __name__ == "__main__":
    main()
