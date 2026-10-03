import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes:
    print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal, json
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
print('LEVEL_VIEWPORT_METHODS=' + json.dumps([x for x in dir(les) if 'viewport' in x.lower() or 'camera' in x.lower() or 'play' in x.lower() or 'pie' in x.lower()]))
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
for o in res.get('output',[]): print(o.get('output',''))
r.stop()
