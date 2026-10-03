import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes:
    print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal, json, traceback
try:
    les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    view=les.get_exact_camera_view()
    print('CAMERA_VIEW_TYPE='+str(type(view)))
    print('CAMERA_VIEW_REPR='+repr(view))
except Exception:
    print('CAMERA_VIEW_ERROR='+traceback.format_exc())
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
for o in res.get('output',[]): print(o.get('output',''))
r.stop()
