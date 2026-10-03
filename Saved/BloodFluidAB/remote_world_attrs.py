import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal,json
subs=[]
for n in dir(unreal):
    if 'world' in n.lower() or 'play' in n.lower() or 'pie' in n.lower() or 'editor' in n.lower() or 'subsystem' in n.lower():
        subs.append(n)
print('PROPHECY_WORLD_ATTRS='+json.dumps(subs))
try:
    ues=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    print('PROPHECY_UNREALEDITORSUBSYSTEM_DIR='+json.dumps([n for n in dir(ues) if 'world' in n.lower() or 'play' in n.lower() or 'pie' in n.lower()]))
except Exception as e: print('UES_ERR='+repr(e))
try:
    les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    print('PROPHECY_LEVELEDITORSUBSYSTEM_DIR='+json.dumps([n for n in dir(les) if 'world' in n.lower() or 'play' in n.lower() or 'pie' in n.lower() or 'map' in n.lower()]))
except Exception as e: print('LES_ERR='+repr(e))
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print(json.dumps(res)[:6000])
r.stop()
