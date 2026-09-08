"""Temporary, unsaved editor-scene close-ups for the Boss shading investigation."""
import json
import time
import traceback
from pathlib import Path
import unreal

OUT=Path(unreal.Paths.project_saved_dir()).resolve()/'BossShading/20260908'
OUT.mkdir(parents=True,exist_ok=True)
editor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
selected=list(editor.get_selected_level_actors())
preview=editor.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(2000,0,0),unreal.Rotator(),True)
preview.set_actor_label('BossShading_TEMP')
mesh=preview.get_component_by_class(unreal.SkeletalMeshComponent)
asset=unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted')
mesh.set_skeletal_mesh_asset(asset)
mesh.set_forced_lod(1)
mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
camera=editor.spawn_actor_from_class(unreal.SceneCapture2D,unreal.Vector(2000,200,140),unreal.Rotator(),True)
camera.set_actor_label('BossShadingCapture_TEMP')
capture=camera.get_component_by_class(unreal.SceneCaptureComponent2D)
capture.capture_every_frame=False
capture.capture_on_movement=False
capture.capture_source=unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
capture.primitive_render_mode=unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
capture.show_only_component(mesh)
capture.post_process_settings=unreal.PostProcessSettings(override_auto_exposure_bias=True,auto_exposure_bias=2.)
target=unreal.RenderingLibrary.create_render_target2d(preview,900,900,unreal.TextureRenderTargetFormat.RTF_RGBA8)
capture.texture_target=target
neutral=unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial')
editor.set_selected_level_actors(selected)
views=[('chest','spine_04',unreal.Vector(0,155,7),32.),
       ('waist','pelvis',unreal.Vector(0,140,0),27.),
       ('wrist','hand_l',unreal.Vector(0,100,15),22.)]
state={'callback':None,'jobs':[],'phase':0,'deadline':0.,'name':None}

def stop():
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback']=None

def tick(_):
    try:
        if time.monotonic()<state['deadline']: return
        if state['phase']==0:
            if not state['jobs']:
                stop()
                print('BOSS_SHADING_CAPTURES_COMPLETE')
                return
            label,bone,offset,fov,mat=state['jobs'].pop(0)
            overrides = neutral if isinstance(neutral, list) else [neutral]*len(asset.materials)
            mesh.set_editor_property('override_materials',overrides if mat=='neutral' else [])
            origin=mesh.get_socket_location(bone)
            position=origin+offset
            camera.set_actor_location_and_rotation(position,unreal.MathLibrary.find_look_at_rotation(position,origin),False,True)
            capture.fov_angle=fov
            state['name']=label
            state['phase']=1
            state['deadline']=time.monotonic()+.25
        elif state['phase']==1:
            capture.capture_scene()
            state['phase']=2
        else:
            unreal.RenderingLibrary.export_render_target(preview,target,str(OUT),state['name']+'.png')
            state['phase']=0
    except Exception:
        stop()
        unreal.log_error(traceback.format_exc())

def capture_set(prefix,neutral_too=True):
    assert state['callback'] is None
    state['jobs']=[(prefix+'_'+label+'_'+mat,bone,offset,fov,mat)
        for mat in (['skin','neutral'] if neutral_too else ['skin']) for label,bone,offset,fov in views]
    state['phase']=0
    state['deadline']=0.
    state['callback']=unreal.register_slate_post_tick_callback(tick)

def cleanup():
    stop()
    editor.destroy_actor(camera)
    editor.destroy_actor(preview)
    editor.set_selected_level_actors(selected)

capture_set('before')
