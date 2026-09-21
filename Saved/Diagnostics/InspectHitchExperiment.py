import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('HITCH_EXPERIMENT_STATE',json.dumps({'pie':bool(w),'world':ed.get_editor_world().get_path_name(),'support_source':unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportSource'),'trace':unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNInputTraceFrames'),'dirty':[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))
