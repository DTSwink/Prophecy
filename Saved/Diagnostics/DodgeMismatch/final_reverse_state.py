import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');cdo=unreal.get_default_object(bp.generated_class())
print(json.dumps(dict(pie=bool(ed.get_game_world()),reverse_default=cdo.get_editor_property('CombatDemoReverseRoles'),dodge_default=cdo.get_editor_property('CombatDemoUseDodge'),dirty_content=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],dirty_maps=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])))
