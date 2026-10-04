import unreal,pathlib,time,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashLDProfile20261004'
w=ed.get_game_world()
assert w is not None,'No current Play; do not create a session during user testing'
old=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.FKReturn.Audit')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 1')
ob={'start':time.monotonic(),'world':w,'old':old}
def done(_):
 if time.monotonic()-ob['start']<30 and ed.get_game_world()==ob['world']:return
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.FKReturn.Audit '+str(ob['old']))
 unreal.unregister_slate_post_tick_callback(ob['cb'])
 (p/'observation-restored.json').write_text(json.dumps({'audit':ob['old'],'playUntouched':True}))
ob['cb']=unreal.register_slate_post_tick_callback(done)
print('Read-only return audit enabled for 30 seconds; no Play or profile changes')
