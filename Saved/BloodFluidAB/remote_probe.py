import sys, time, json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
remote = remote_execution.RemoteExecution()
remote.start()
time.sleep(2.0)
print('nodes', json.dumps(remote.remote_nodes))
if not remote.remote_nodes:
    remote.stop(); raise SystemExit(2)
node = remote.remote_nodes[0]
remote.open_command_connection(node['node_id'])
code = r'''
import unreal, json
rows=[]
for world in [unreal.EditorLevelLibrary.get_editor_world()]:
    rows.append({'editor_world': world.get_name() if world else None})
for obj in unreal.get_objects_of_class(unreal.World):
    n=obj.get_name()
    if 'PIE' in obj.get_path_name() or 'UEDPIE' in obj.get_path_name() or obj.world_type.name in ('PIE','GAME'):
        rows.append({'world_path': obj.get_path_name(), 'world_name': n, 'world_type': obj.world_type.name})
print('PROPHECY_REMOTE_WORLD_DUMP='+json.dumps(rows))
'''
res = remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE, raise_on_failure=False)
print('result', json.dumps(res))
remote.close_command_connection(); remote.stop()
