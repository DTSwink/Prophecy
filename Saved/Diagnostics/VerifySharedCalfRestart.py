import unreal,gc,types
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
assert unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Debug.SharedCalfRecovery')==1
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
callbacks=[o for o in gc.get_objects() if isinstance(o,types.FunctionType) and o.__name__=='tick' and 'Prophecy.Debug.SharedCalfRecovery 1' in o.__code__.co_consts]
assert not callbacks,'Old capture callback survived restart'
print('SHARED_CALF_NORMAL_BUILD_READY',ed.get_editor_world().get_path_name())
