"""Temporary VSM normal-bias A/B. Restores the existing console value on exit.

Uses the transient Boss capture and never persists renderer/project settings.
"""
import time
import traceback
import unreal

mesh = context['mesh']
capture = context['capture']
target = context['target']
original_bias = unreal.SystemLibrary.get_console_variable_float_value('r.Shadow.Virtual.NormalBias')
original_flags = list(capture.show_flag_settings)
original_cast = mesh.cast_shadow
jobs = list(globals().get('bias_jobs', [('bias_original', original_bias), ('bias_1', 1.), ('bias_2', 2.), ('bias_4', 4.), ('bias_8', 8.), ('bias_restored', original_bias)]))
state = {'callback': None, 'deadline': 0., 'phase': 0, 'name': None}
capture.set_editor_property('show_flag_settings', [])
capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
capture.texture_target = target
mesh.set_cast_shadow(True)

def set_bias(value):
    unreal.SystemLibrary.execute_console_command(context['preview'], 'r.Shadow.Virtual.NormalBias ' + str(value))

def stop():
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback'] = None
    set_bias(original_bias)
    capture.set_editor_property('show_flag_settings', original_flags)
    mesh.set_cast_shadow(original_cast)

def tick(_):
    try:
        if time.monotonic() < state['deadline']:
            return
        if state['phase'] == 0:
            if not jobs:
                stop()
                print('SHADOW_BIAS_COMPLETE_RESTORED', original_bias)
                return
            state['name'], value = jobs.pop(0)
            set_bias(value)
            state['phase'] = 1
            state['deadline'] = time.monotonic() + .5
        elif state['phase'] == 1:
            capture.capture_scene()
            state['phase'] = 2
            state['deadline'] = time.monotonic() + .2
        else:
            unreal.RenderingLibrary.export_render_target(context['preview'], target, str(context['OUT']), state['name'] + '.png')
            state['phase'] = 0
    except Exception:
        stop()
        unreal.log_error(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
