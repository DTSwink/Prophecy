"""Same-frame original/corrected Lit and true Material AO buffer captures."""
import time
import traceback
import unreal

mesh = context['mesh']
capture = context['capture']
camera = context['camera']
target = context['target']
original_pp = capture.post_process_settings.copy()
original_persist = capture.always_persist_rendering_state
original_materials = list(mesh.get_editor_property('override_materials'))
context['preview'].set_actor_rotation(unreal.Rotator(pitch=0, yaw=globals().get('view_yaw', 180), roll=0), True)
origin = mesh.get_socket_location(globals().get('view_bone', 'spine_05')) + globals().get('view_target_offset', unreal.Vector(0, 0, -8))
position = origin + globals().get('view_camera_offset', unreal.Vector(0, 105, 8))
camera.set_actor_location_and_rotation(position, unreal.MathLibrary.find_look_at_rotation(position, origin), False, True)
capture.fov_angle = globals().get('view_fov', 36.)
capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
capture.texture_target = target
capture.set_editor_property('show_flag_settings', [])
capture.post_process_blend_weight = 1.
capture.always_persist_rendering_state = True
assert mesh.cast_shadow

ao_display = unreal.Material()
ao_display.set_editor_property('material_domain', unreal.MaterialDomain.MD_POST_PROCESS)
scene = unreal.MaterialEditingLibrary.create_material_expression(ao_display, unreal.MaterialExpressionSceneTexture)
scene.set_editor_property('scene_texture_id', unreal.SceneTextureId.PPI_MATERIAL_AO)
assert unreal.MaterialEditingLibrary.connect_material_property(scene, 'Color', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
unreal.MaterialEditingLibrary.recompile_material(ao_display)
ao_pp = unreal.PostProcessSettings(override_auto_exposure_bias=True, auto_exposure_bias=2.)
ao_pp.set_editor_property('weighted_blendables', unreal.WeightedBlendables(array=[unreal.WeightedBlendable(weight=1., object=ao_display)]))
jobs = list(globals().get('capture_jobs', [('ao_original_lit', False, False), ('ao_corrected_lit', True, False),
        ('ao_original_buffer', False, True), ('ao_corrected_buffer', True, True)]))
state = {'callback': None, 'deadline': time.monotonic() + 12., 'phase': 0, 'name': None}

def stop():
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback'] = None
    capture.post_process_settings = original_pp
    capture.always_persist_rendering_state = original_persist
    mesh.set_editor_property('override_materials', original_materials)

def tick(_):
    try:
        if time.monotonic() < state['deadline']:
            return
        if state['phase'] == 0:
            if not jobs:
                stop()
                print('BOSS_AO_FIX_COMPARISON_COMPLETE')
                return
            state['name'], fixed, buffer = jobs.pop(0)
            mesh.set_editor_property('override_materials', repair['test_materials'] if fixed else [])
            capture.post_process_settings = ao_pp if buffer else original_pp
            state['phase'] = 1
            state['deadline'] = time.monotonic() + .75
        elif state['phase'] == 1:
            capture.capture_scene()
            state['phase'] = 3
            state['deadline'] = time.monotonic() + .3
        elif state['phase'] == 3:
            # Warm the view-state/MID and material resource before the measured capture.
            capture.capture_scene()
            state['phase'] = 2
            state['deadline'] = time.monotonic() + .3
        else:
            unreal.RenderingLibrary.export_render_target(context['preview'], target, str(context['OUT']), state['name'] + '.png')
            state['phase'] = 0
    except Exception:
        stop()
        unreal.log_error(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
