import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal, traceback
try:
    count=0
    worlds=[]
    try: worlds += list(unreal.EditorLevelLibrary.get_pie_worlds(True))
    except Exception: pass
    try:
        ew=unreal.EditorLevelLibrary.get_editor_world()
        if ew: worlds.append(ew)
    except Exception: pass
    seen=set()
    for w in worlds:
        if not w or w.get_path_name() in seen: continue
        seen.add(w.get_path_name())
        for a in unreal.ActorIterator(w):
            if a.get_class().get_name() == "ProphecyBloodFluidPostProcessController":
                a.apply_blood_fluid_post_process_settings()
                count += 1
    print('PROPHECY_APPLIED_CONTROLLERS='+str(count))
except Exception:
    print('PROPHECY_APPLY_ERROR='+traceback.format_exc())
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print('success',res.get('success'))
for o in res.get('output',[]): print(o.get('type'), o.get('output',''))
r.stop()
