import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal,json
names=[n for n in dir(unreal) if n.lower().startswith('get') and ('world' in n.lower() or 'object' in n.lower() or 'editor' in n.lower())]
print('GET_NAMES='+json.dumps(names))
for clsname in ['UnrealEditorSubsystem','LevelEditorSubsystem','EditorActorSubsystem','GameplayStatics','EditorLevelLibrary','SystemLibrary']:
    try:
        cls=getattr(unreal, clsname)
        inst=None
        if clsname.endswith('Subsystem'):
            try: inst=unreal.get_editor_subsystem(cls)
            except Exception: pass
        obj=inst or cls
        print(clsname+'='+json.dumps([n for n in dir(obj) if 'world' in n.lower() or 'pie' in n.lower() or 'play' in n.lower() or 'actor' in n.lower() or 'all' in n.lower()][:200]))
    except Exception as e:
        print(clsname+'_ERR='+repr(e))
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
for out in res.get('output',[]): print(out.get('output',''))
r.stop()
