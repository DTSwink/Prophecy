import sys, time, json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
remote=remote_execution.RemoteExecution(); remote.start(); time.sleep(1.0)
print('nodes', json.dumps(remote.remote_nodes))
if not remote.remote_nodes: remote.stop(); raise SystemExit(2)
remote.open_command_connection(remote.remote_nodes[0]['node_id'])
code=r'''
import unreal, json
names=[n for n in dir(unreal) if 'object' in n.lower() or 'actor' in n.lower() or 'world' in n.lower()]
print('PROPHECY_UNREAL_ATTRS='+json.dumps(names[:300]))
'''
res=remote.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print(json.dumps(res))
remote.stop()
