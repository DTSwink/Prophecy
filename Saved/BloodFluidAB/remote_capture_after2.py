import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes: print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal, os, traceback
try:
    outdir=os.path.join(unreal.Paths.project_saved_dir(),'BloodFluidAB','Diag')
    os.makedirs(outdir, exist_ok=True)
    path=os.path.join(outdir,'pie_after_constant_layer_color.png')
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    try:
        unreal.AutomationLibrary.take_high_res_screenshot(1024,768,path)
    except TypeError:
        unreal.AutomationLibrary.take_high_res_screenshot(1024,768,path,None,False,False,unreal.ComparisonTolerance.LOW,'pie_after_constant_layer_color',0.1,True)
    print('PROPHECY_SCREENSHOT='+path)
except Exception:
    print('PROPHECY_SCREENSHOT_ERROR='+traceback.format_exc())
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print('success',res.get('success'))
for o in res.get('output',[]): print(o.get('type'), o.get('output',''))
r.stop()
