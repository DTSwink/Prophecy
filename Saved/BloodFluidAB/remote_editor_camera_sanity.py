import sys,time,json
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
r=remote_execution.RemoteExecution(); r.start(); time.sleep(1)
if not r.remote_nodes:
    print('NO_NODES'); r.stop(); raise SystemExit(2)
r.open_command_connection(r.remote_nodes[0]['node_id'])
code=r'''
import unreal, os, traceback, math
try:
    # End PIE so this is definitely editor-world capture.
    les=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    world=unreal.EditorLevelLibrary.get_editor_world()
    loc=unreal.Vector(-650.0,-240.0,230.0)
    target=unreal.Vector(-625.0,900.0,105.0)
    rot=unreal.MathLibrary.find_look_at_rotation(loc,target)
    cam=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor,loc,rot,transient=True)
    cam.set_actor_label('TMP_BloodDiagSanity_Camera')
    cam.camera_component.set_editor_property('field_of_view',62.0)
    outdir=os.path.join(unreal.Paths.project_saved_dir(),'BloodFluidAB','DiagCompare')
    os.makedirs(outdir,exist_ok=True)
    path=os.path.join(outdir,'editor_camera_sanity.png')
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    unreal.AutomationLibrary.take_high_res_screenshot(1024,768,path,cam,False,False,unreal.ComparisonTolerance.LOW,'editor_camera_sanity',0.1,True)
    print('SANITY_SHOT='+path)
except Exception:
    print('SANITY_ERR='+traceback.format_exc())
'''
res=r.run_command(code, unattended=True, exec_mode=remote_execution.MODE_EXEC_FILE)
print('success',res.get('success'))
for o in res.get('output',[]): print(o.get('type'),o.get('output',''))
r.stop()
