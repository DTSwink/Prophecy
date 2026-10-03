import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes:
    print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import traceback
try:
    path = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\ProphecyRunBloodFluidDiagnosticCompare.py"
    with open(path, "r", encoding="utf-8") as f:
        exec(compile(f.read(), path, "exec"), {"__file__": path})
except Exception:
    print("PROPHECY_DIAG_COMPARE_START_ERROR=" + traceback.format_exc())
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print('success',res.get('success'))
print('result',res.get('result'))
for o in res.get('output',[]): print(o.get('type'), o.get('output',''))
r.stop()
