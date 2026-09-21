import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
c=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'))
print('CDO debug1',c.get_editor_property('bool debug 1'))
print('dirty', [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
