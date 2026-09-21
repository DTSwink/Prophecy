import unreal, pathlib
unreal.unregister_slate_post_tick_callback(kick_knee_capture.cb)
source=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureKickKnee.py').read_text()
namespace={}
exec(source.rsplit('kick_knee_capture=KickKneeCapture()',1)[0],namespace)
kick_knee_capture.__class__.tick=namespace['KickKneeCapture'].tick
kick_knee_capture.__class__.finish=namespace['KickKneeCapture'].finish
kick_knee_capture.cb=unreal.register_slate_post_tick_callback(kick_knee_capture.tick)
print('Recorder excludes empty data-only mesh components; Play continues unchanged.',kick_knee_capture.n)
