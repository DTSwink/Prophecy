import unreal,time
# Permit the queued pure-math test to pass its editor FPS gate while PIE is paused.
# Restore the in-memory preference; do not save editor settings or advance PIE.
settings=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
key='bThrottleCPUWhenNotForeground'
old=settings.get_editor_property(key)
settings.set_editor_property(key,False)
state={'start':time.monotonic()}
def restore(_):
 if time.monotonic()-state['start']<15:return
 settings.set_editor_property(key,old)
 unreal.unregister_slate_post_tick_callback(state['cb'])
 print('WRIST_MATH_THROTTLE_RESTORED',old)
state['cb']=unreal.register_slate_post_tick_callback(restore)
print('Wrist math editor FPS gate temporarily unthrottled; PIE stays paused')
