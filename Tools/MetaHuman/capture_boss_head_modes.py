"""Three head-only diagnostic views, retaining the asset's original materials.

Run in the existing Boss shading capture namespace with context=boss_shading.
The normal-buffer display material only remaps a signed render target to RGB;
it is never assigned to the character or saved.
"""
import time
import traceback
import unreal

context['stop']()
mesh=context['mesh']
camera=context['camera']
capture=context['capture']
target=context['target']
mesh.set_editor_property('override_materials',[])
capture.post_process_settings=unreal.PostProcessSettings(override_auto_exposure_bias=True,auto_exposure_bias=2.)
origin=mesh.get_socket_location('neck_01')+unreal.Vector(0,0,5.5)
position=origin+unreal.Vector(0,100,0)
camera.set_actor_location_and_rotation(position,unreal.MathLibrary.find_look_at_rotation(position,origin),False,True)
capture.fov_angle=31.
normal_target=unreal.RenderingLibrary.create_render_target2d(context['preview'],900,900,unreal.TextureRenderTargetFormat.RTF_RGBA16F)
normal_target.set_editor_property('srgb',False)
normal_rgb=unreal.RenderingLibrary.create_render_target2d(context['preview'],900,900,unreal.TextureRenderTargetFormat.RTF_RGBA8)
display=unreal.Material()
display.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
sample=unreal.MaterialEditingLibrary.create_material_expression(display,unreal.MaterialExpressionTextureSample)
sample.set_editor_property('texture',normal_target)
sample.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
multiply=unreal.MaterialEditingLibrary.create_material_expression(display,unreal.MaterialExpressionMultiply)
multiply.set_editor_property('const_b',.5)
add=unreal.MaterialEditingLibrary.create_material_expression(display,unreal.MaterialExpressionAdd)
add.set_editor_property('const_b',.5)
assert unreal.MaterialEditingLibrary.connect_material_expressions(sample,'RGB',multiply,'A')
assert unreal.MaterialEditingLibrary.connect_material_expressions(multiply,'',add,'A')
assert unreal.MaterialEditingLibrary.connect_material_property(add,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
unreal.MaterialEditingLibrary.recompile_material(display)

jobs=[('head_lit',unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR),
      ('head_unlit',unreal.SceneCaptureSource.SCS_BASE_COLOR),
      ('head_world_normals',unreal.SceneCaptureSource.SCS_NORMAL)]
state={'phase':0,'job':None,'callback':None,'deadline':time.monotonic()+10.}

def stop():
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback']=None
    capture.texture_target=target
    capture.capture_source=unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    mesh.set_editor_property('override_materials',[])

def tick(_):
    try:
        if time.monotonic()<state['deadline']: return
        if state['phase']==0:
            if not jobs:
                stop()
                print('HEAD_THREE_VIEWS_COMPLETE_ORIGINAL_MATERIALS')
                return
            state['job']=jobs.pop(0)
            capture.capture_source=state['job'][1]
            capture.texture_target=normal_target if state['job'][1]==unreal.SceneCaptureSource.SCS_NORMAL else target
            capture.capture_scene()
            state['phase']=1
        elif state['phase']==1:
            if state['job'][1]==unreal.SceneCaptureSource.SCS_NORMAL:
                unreal.RenderingLibrary.draw_material_to_render_target(context['preview'],normal_rgb,display)
                state['phase']=2
            else:
                unreal.RenderingLibrary.export_render_target(context['preview'],target,str(context['OUT']),state['job'][0]+'.png')
                state['phase']=0
        else:
            unreal.RenderingLibrary.export_render_target(context['preview'],normal_rgb,str(context['OUT']),state['job'][0]+'.png')
            state['phase']=0
    except Exception:
        stop()
        unreal.log_error(traceback.format_exc())

state['callback']=unreal.register_slate_post_tick_callback(tick)
