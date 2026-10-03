import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes:
    print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal,json
for objname in ['EditorLevelLibrary','UnrealEditorSubsystem','LevelEditorSubsystem']:
    obj=getattr(unreal,objname)
    try:
        if objname.endswith('Subsystem'): obj=unreal.get_editor_subsystem(obj)
    except Exception: pass
    print(objname+' camera attrs='+json.dumps([n for n in dir(obj) if 'camera' in n.lower() or 'viewport' in n.lower()]))
    for n in [n for n in dir(obj) if 'camera' in n.lower() or 'viewport' in n.lower()]:
        try:
            f=getattr(obj,n)
            d=getattr(f,'__doc__',None)
            if d: print('DOC '+objname+'.'+n+'='+d[:500].replace('\n',' | '))
        except Exception: pass
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
for o in res.get('output',[]): print(o.get('output',''))
r.stop()
