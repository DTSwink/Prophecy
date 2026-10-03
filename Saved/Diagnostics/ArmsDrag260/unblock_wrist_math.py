import unreal,time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_game_world() or ed.get_editor_world()
names=['t.MaxFPS','Slate.bAllowThrottling','t.IdleWhenNotForeground','Slate.MaxTicksPerSecondWithoutActiveTimer']
old={n:unreal.SystemLibrary.get_console_variable_float_value(n) for n in names}
print('WRIST_TEST_EDITOR_RATES',old)
for n,v in [('t.MaxFPS',60),('Slate.bAllowThrottling',0),('t.IdleWhenNotForeground',0),('Slate.MaxTicksPerSecondWithoutActiveTimer',60)]:
 unreal.SystemLibrary.execute_console_command(world,n+' '+str(v))
s={'start':time.monotonic()}
def restore(_):
 if time.monotonic()-s['start']<18:return
 for n,v in old.items():unreal.SystemLibrary.execute_console_command(world,n+' '+str(v))
 unreal.unregister_slate_post_tick_callback(s['cb'])
 print('WRIST_TEST_EDITOR_RATES_RESTORED')
s['cb']=unreal.register_slate_post_tick_callback(restore)
