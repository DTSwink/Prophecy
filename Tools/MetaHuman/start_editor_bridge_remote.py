"""Start the existing project bridge in an already-open project editor."""
import sys
import time

sys.path.insert(0, r'C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python')
import remote_execution

remote = remote_execution.RemoteExecution()
remote.start()
try:
    time.sleep(3)
    nodes = remote.remote_nodes
    print(nodes, flush=True)
    matches = [n for n in nodes if 'GameAnimationSample3' in str(n.get('project_name', ''))]
    assert len(matches) == 1, 'Expected exactly one matching project editor'
    remote.open_command_connection(matches[0]['node_id'])
    print(remote.run_command(
        "import runpy, os\nos.environ['PROPHECY_EDITOR_BRIDGE_PORT']='8766'\n"
        "runpy.run_path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/ProphecyEditorBridge.py',run_name='__main__')"
    ), flush=True)
finally:
    remote.stop()
