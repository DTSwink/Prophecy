"""Small editor remote helper; accepts Python code from a file."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,r'C:/Program Files/Epic Games/UE_5.7/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python')
import remote_execution
r=remote_execution.RemoteExecution();r.start()
try:
    time.sleep(2)
    n=[n for n in r.remote_nodes if n.get('project_name')=='GameAnimationSample3']
    assert len(n)==1,n
    r.open_command_connection(n[0]['node_id'])
    code=Path(sys.argv[1]).read_text() if len(sys.argv)>1 else "import unreal,json\nprint(json.dumps({'map':unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name(),'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}))"
    print(json.dumps(r.run_command(code),indent=2))
finally:r.stop()
