import unreal
if 's' in globals() and isinstance(s,dict) and 'cb' in s:
 unreal.unregister_slate_post_tick_callback(s['cb'])
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=e.get_game_world() or e.get_editor_world()
for key,value in [('t.MaxFPS',10),('Slate.bAllowThrottling',1),('t.IdleWhenNotForeground',0),('Slate.MaxTicksPerSecondWithoutActiveTimer',0)]:
 unreal.SystemLibrary.execute_console_command(w,key+' '+str(value))
print('WRIST_TEST_EDITOR_RATES_RESTORED; USER_PIE',bool(e.get_game_world()))
