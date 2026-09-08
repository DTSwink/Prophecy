"""Reversible, fixed-camera lighting isolation on the existing transient preview.

Run with context=boss_shading; does not modify or save any mesh/material asset.
"""
import time
import traceback
import unreal

context['stop']()
mesh = context['mesh']
camera = context['camera']
capture = context['capture']
target = context['target']
saved = {
    'flags': list(capture.show_flag_settings),
    'shadow': mesh.cast_shadow,
    'materials': list(mesh.get_editor_property('override_materials')),
    'source': capture.capture_source,
    'target': capture.texture_target,
}
origin = mesh.get_socket_location('spine_05') + unreal.Vector(0, 0, -8)
position = origin + globals().get('camera_offset', unreal.Vector(0, -105, 8))
camera.set_actor_location_and_rotation(position, unreal.MathLibrary.find_look_at_rotation(position, origin), False, True)
capture.fov_angle = 36.
capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
capture.texture_target = target
mesh.set_editor_property('override_materials', [])
jobs = [
    ('back_baseline', [], True),
    ('back_no_cast_shadow', [], False),
    ('back_no_dynamic_shadows', ['DynamicShadows'], True),
    ('back_no_contact_shadows', ['ContactShadows'], True),
    ('back_no_specular', ['Specular'], True),
    ('back_no_subsurface', ['SubsurfaceScattering'], True),
    ('back_no_ao', ['AmbientOcclusion', 'MaterialAmbientOcclusion', 'LumenShortRangeAmbientOcclusion'], True),
    ('back_restored', [], True),
]
state = {'callback': None, 'phase': 0, 'deadline': 0., 'name': None}

def stop():
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback'] = None
    capture.show_flag_settings = saved['flags']
    capture.capture_source = saved['source']
    capture.texture_target = saved['target']
    mesh.set_cast_shadow(saved['shadow'])
    mesh.set_editor_property('override_materials', saved['materials'])

def tick(_):
    try:
        if time.monotonic() < state['deadline']:
            return
        if state['phase'] == 0:
            if not jobs:
                stop()
                print('BACK_LIGHTING_AB_COMPLETE_RESTORED')
                return
            name, disabled, cast = jobs.pop(0)
            state['name'] = globals().get('prefix', '') + name
            capture.set_editor_property('show_flag_settings', [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in disabled])
            mesh.set_cast_shadow(cast)
            state['phase'] = 1
            state['deadline'] = time.monotonic() + 1.
        elif state['phase'] == 1:
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
